from __future__ import annotations

import json
from pathlib import Path

from System.whatsapp_autonomy_gate import (
    AutonomyInputs,
    attraction_score,
    evaluate_autonomy,
    gaussian,
    infer_repetition_and_timing,
)
from System import whatsapp_autonomy_settings as settings
from System import whatsapp_bridge_autopilot as wa
from System import whatsapp_social_graph as graph


def test_gaussian_timing_peaks_at_preferred_interval() -> None:
    assert gaussian(180.0, 180.0, 120.0) == 1.0
    assert gaussian(0.0, 180.0, 120.0) < 1.0

    score = attraction_score(
        consent=True,
        user_replied_recently=0.8,
        emotional_warmth=0.7,
        urgency=0.2,
        topic_match=0.9,
        repetition=0.0,
        time_since_last_msg_min=180.0,
    )

    assert 0.0 < score <= 1.0


def test_autonomy_blocks_without_consent() -> None:
    decision = evaluate_autonomy(
        AutonomyInputs(
            consent=False,
            user_replied_recently=1.0,
            emotional_warmth=1.0,
            urgency=1.0,
            topic_match=1.0,
            repetition=0.0,
            time_since_last_msg_min=180.0,
            user_initiated=True,
        )
    )

    assert decision.should_send is False
    assert decision.status == "SILENCE_NO_CONSENT"
    assert decision.score == 0.0


def test_repetition_and_timing_are_inferred_from_bridge_ledger(tmp_path: Path) -> None:
    ledger = tmp_path / "bridge.jsonl"
    ledger.write_text(
        json.dumps(
            {
                "event_kind": "WHATSAPP_SEND_ATTEMPT",
                "ts": 1000.0,
                "resolved_jid": "15551234567@s.whatsapp.net",
                "text": "hello from Alice",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    inferred = infer_repetition_and_timing(
        target="15551234567@s.whatsapp.net",
        text="hello from Alice",
        now=1120.0,
        bridge_ledger=ledger,
    )

    assert inferred["time_since_last_msg_min"] == 2.0
    assert inferred["repetition"] > 0.95


def test_bridge_autonomous_send_silences_no_consent(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(wa, "_LEDGER", tmp_path / "bridge.jsonl")
    monkeypatch.setattr(wa, "_resolve_target", lambda _target: "15551234567@s.whatsapp.net")

    result = wa.autonomous_send_whatsapp(
        "Carlton",
        "hello",
        consent=False,
        user_initiated=True,
        topic_match=1.0,
    )

    assert result["ok"] is False
    assert result["status"] == "SILENCE_NO_CONSENT"
    assert "no external WhatsApp action" in result["truth_note"]
    assert result["intent_provenance"]["intent_source"] == "reflex"
    assert result["intent_provenance"]["consent"] == "none"


def test_bridge_blocks_group_send_by_default(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(wa, "_ALLOW_GROUP_SEND", False)
    monkeypatch.setattr(wa, "_LEDGER", tmp_path / "bridge.jsonl")
    monkeypatch.setattr(wa, "_resolve_target", lambda _target: "120363408204674197@g.us")

    result = wa.send_whatsapp("SIFTA Group", "hello group")

    assert result["ok"] is False
    assert result["status"] == "BLOCKED_GROUP_SEND_DISABLED"
    assert result["intent_provenance"]["intent_source"] == "owner"
    assert result["intent_provenance"]["consent"] == "explicit"


def test_target_auto_reply_setting_defaults_off_and_can_toggle(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "_SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(settings, "_SETTINGS_LEDGER", tmp_path / "settings.jsonl")

    assert settings.is_auto_enabled("15551234567@s.whatsapp.net", chat_type="direct") is False

    row = settings.set_auto_enabled(
        "15551234567@s.whatsapp.net",
        display_name="Carlton",
        chat_type="direct",
        enabled=True,
    )

    assert row["consent"] == "owner_delegated"
    assert settings.is_auto_enabled("15551234567@s.whatsapp.net", chat_type="direct") is True

    settings.set_auto_enabled(
        "15551234567@s.whatsapp.net",
        display_name="Carlton",
        chat_type="direct",
        enabled=False,
    )

    assert settings.is_auto_enabled("15551234567@s.whatsapp.net", chat_type="direct") is False
    assert "WHATSAPP_AUTO_REPLY_SETTING_CHANGED" in (tmp_path / "settings.jsonl").read_text()


def test_target_auto_reply_setting_refuses_owner_self(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "_SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(settings, "_SETTINGS_LEDGER", tmp_path / "settings.jsonl")

    try:
        settings.set_auto_enabled(
            "122093203140754@lid",
            display_name="George",
            chat_type="direct",
            enabled=True,
        )
    except ValueError as exc:
        assert "owner_self" in str(exc)
    else:
        raise AssertionError("owner_self auto-reply toggle must be rejected")


def test_target_auto_reply_setting_follows_phone_lid_alias(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "_SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(settings, "_SETTINGS_LEDGER", tmp_path / "settings.jsonl")
    contacts_path = tmp_path / "contacts.json"
    graph.save_contacts(
        {
            "phone": graph.enrich_contact_record(
                {},
                jid="18326231233@s.whatsapp.net",
                name="Carlton",
                now=1,
            ),
            "lid": graph.enrich_contact_record(
                {},
                jid="110411378614437@lid",
                name="Carlton",
                now=2,
            ),
        },
        contacts_path,
    )
    monkeypatch.setattr(graph, "CONTACTS_FILE", contacts_path)

    settings.set_auto_enabled(
        "18326231233@s.whatsapp.net",
        display_name="Carlton",
        chat_type="direct",
        enabled=True,
    )

    assert settings.is_auto_enabled("110411378614437@lid", chat_type="direct") is True
