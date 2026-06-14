"""r1017 P0.1 — typed + interrogative owner turns must never land in no-reply lane."""

from __future__ import annotations

import json
from pathlib import Path

import System.swarm_media_ingress_gate as gate
from System.swarm_media_ingress_gate import classify_spoken_ingress

# Incident class 2026-06-11 19:09:38 — TYPED owner question during Donnie Brasco co-watch.
INCIDENT_P01_QUESTION = "Alice, who is on the screen in Alice Browser right now?"
INCIDENT_ID = "p01-190938-donnie-brasco-screen-question"


def _pin_own_browser_playback(monkeypatch, *, title: str = "Donnie Brasco (1997)") -> None:
    monkeypatch.setattr(
        gate,
        "is_my_own_browser_playback",
        lambda **kwargs: (
            True,
            {"domain": "www.youtube.com", "playing": True, "title": title},
        ),
    )


def test_typed_incident_question_routes_direct_during_own_browser_playback(monkeypatch) -> None:
    _pin_own_browser_playback(monkeypatch)
    decision = classify_spoken_ingress(INCIDENT_P01_QUESTION, stt_conf=1.0)
    assert decision["route"] == "direct"
    assert decision["reason"] in {"typed_input_always_direct", "owner_interrogative_reply_required"}


def test_spoken_interrogative_playback_question_routes_direct(monkeypatch) -> None:
    _pin_own_browser_playback(monkeypatch)
    decision = classify_spoken_ingress(INCIDENT_P01_QUESTION, stt_conf=0.92)
    assert decision["route"] == "direct"
    assert decision["reason"] == "owner_interrogative_reply_required"


def test_low_conf_phatic_still_observed_media_during_playback(monkeypatch) -> None:
    """Backchannel silencer jurisdiction stays spoken-low-conf only."""
    _pin_own_browser_playback(monkeypatch)
    decision = classify_spoken_ingress("Got him.", stt_conf=0.24)
    assert decision["route"] == "observed_media"
    assert decision["reason"] == "my_own_browser_playback_suppresses_owner_stt"


def test_mandatory_voice_gate_recovers_incident_question(tmp_path: Path, monkeypatch) -> None:
    from Applications import sifta_talk_to_alice_widget as tw
    from Applications import sifta_stigmergic_deterministic_tracker as tracker

    state = tmp_path / ".sifta_state"
    state.mkdir()
    monkeypatch.setattr(tw, "_STATE_DIR", state)
    monkeypatch.setattr(tracker, "_DETERMINISTIC_MISTAKES_LEDGER", state / "deterministic_mistakes.jsonl")
    monkeypatch.setattr(tracker, "_TRACKER_LEDGER", state / "stigmergic_deterministic_tracker.jsonl")
    monkeypatch.setattr(tw, "_media_focus_context_for_audio_gate", lambda: "youtube playing")
    monkeypatch.setattr(
        gate,
        "classify_spoken_ingress",
        lambda *args, **kwargs: {
            "route": "observed_media",
            "reason": "my_own_browser_playback_suppresses_owner_stt",
            "confidence": 0.92,
        },
    )
    monkeypatch.setattr(
        gate,
        "classify_external_consciousness_lane",
        lambda *args, **kwargs: {
            "source_class": "my_own_browser_playback",
            "attention_policy": "store_silent_context_as_self_body_output",
        },
    )
    monkeypatch.setattr(
        gate,
        "write_gate_receipt",
        lambda decision, **kwargs: {
            "ts": 123.0,
            "route": decision["route"],
            "reason": decision["reason"],
            "confidence": decision["confidence"],
            "stt_confidence": kwargs.get("stt_conf", 0.0),
            "external_consciousness": kwargs.get("external_consciousness", {}),
            "incident_closed": INCIDENT_ID,
        },
    )

    result = tw._mandatory_voice_ingress_receipt(INCIDENT_P01_QUESTION, 1.0, {})

    assert result is None
    row = json.loads((state / "deterministic_mistakes.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert row["recovered_to_cortex"] is True
    assert row["bypass_type"] == "owner_direct_turn_silenced_as_external_ingest"


def test_typed_turn_bypasses_backchannel_silencer() -> None:
    from Applications import sifta_talk_to_alice_widget as tw

    rule = tw._effective_backchannel_rule_for_owner_turn(
        "Mm-hmm.",
        0.38,
        typed_turn=True,
    )
    assert rule is None


def test_interrogative_spoken_high_conf_bypasses_backchannel() -> None:
    from Applications import sifta_talk_to_alice_widget as tw

    rule = tw._effective_backchannel_rule_for_owner_turn(
        INCIDENT_P01_QUESTION,
        0.92,
        typed_turn=False,
    )
    assert rule is None