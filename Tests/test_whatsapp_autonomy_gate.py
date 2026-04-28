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
from System import whatsapp_bridge_autopilot as wa


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


def test_bridge_blocks_group_send_by_default(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(wa, "_ALLOW_GROUP_SEND", False)
    monkeypatch.setattr(wa, "_LEDGER", tmp_path / "bridge.jsonl")
    monkeypatch.setattr(wa, "_resolve_target", lambda _target: "120363408204674197@g.us")

    result = wa.send_whatsapp("SIFTA Group", "hello group")

    assert result["ok"] is False
    assert result["status"] == "BLOCKED_GROUP_SEND_DISABLED"
