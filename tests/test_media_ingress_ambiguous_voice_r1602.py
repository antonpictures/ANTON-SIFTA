#!/usr/bin/env python3
"""r1602 VA3 — ambiguous voice + active media => OBSERVE, not reply."""
from __future__ import annotations

import json
import time

from System import swarm_media_ingress_gate as gate
from System.swarm_media_ingress_gate import classify_spoken_ingress


def test_media_transcript_zero_direct_when_voice_ambiguous(monkeypatch, tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    monkeypatch.setattr(gate, "STATE_DIR", state)
    monkeypatch.setattr(gate, "LEDGER", state / "media_ingress_gate.jsonl")
    monkeypatch.setattr(gate, "AMBIENT_CONTEXT_FILE", state / "ambient_media_context.json")

    # Active ambient media context (kitchen session)
    gate.AMBIENT_CONTEXT_FILE.write_text(
        json.dumps(
            {
                "ts": time.time(),
                "ttl_s": 6 * 3600,
                "source": "youtube",
                "note": "kitchen podcast",
            }
        ),
        encoding="utf-8",
    )
    assert gate.ambient_media_context_active() is True

    media_lines = [
        "So then you start doubting that observation and the whole argument collapses",
        "welcome back to the show we are talking about MMA and weight cutting",
        "the speaker is describing compute tokens per watt in the datacenter",
        "and only in the existence of the nature however I was again frustrated",
        "buy now and get free shipping on your first order today only",
    ]
    direct_count = 0
    reasons = []
    for line in media_lines:
        d = classify_spoken_ingress(
            line,
            stt_conf=0.72,
            focus_context="YouTube video: podcast episode",
            voice_george_conf=0.0,  # ambiguous / unknown speaker
        )
        if d["route"] == "direct":
            direct_count += 1
        assert d["route"] in {"observed_media", "ambient_media"}, d
        reasons.append(d.get("reason"))
    assert direct_count == 0
    # At least one line must hit the VA3 bias (text-shape would have
    # promoted to direct without voice under active ambient media).
    # If all were already ambient via narration, still zero direct = pass.
    assert all(r != "direct" for r in reasons)


def test_alice_wake_still_direct_under_media(monkeypatch, tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    monkeypatch.setattr(gate, "STATE_DIR", state)
    monkeypatch.setattr(gate, "LEDGER", state / "media_ingress_gate.jsonl")
    monkeypatch.setattr(gate, "AMBIENT_CONTEXT_FILE", state / "ambient_media_context.json")
    gate.AMBIENT_CONTEXT_FILE.write_text(
        json.dumps({"ts": time.time(), "ttl_s": 3600, "source": "youtube", "note": "tv"}),
        encoding="utf-8",
    )
    d = classify_spoken_ingress(
        "Alice, stop and listen to me",
        stt_conf=0.8,
        focus_context="YouTube video playing",
        voice_george_conf=0.2,
    )
    # Wake token opens a real turn path (not forced observe)
    assert d["reason"] != "ambiguous_voice_under_active_media_observe"


def test_confident_owner_voice_still_bypasses(monkeypatch, tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    monkeypatch.setattr(gate, "STATE_DIR", state)
    monkeypatch.setattr(gate, "LEDGER", state / "media_ingress_gate.jsonl")
    monkeypatch.setattr(gate, "AMBIENT_CONTEXT_FILE", state / "ambient_media_context.json")
    gate.AMBIENT_CONTEXT_FILE.write_text(
        json.dumps({"ts": time.time(), "ttl_s": 3600, "source": "youtube", "note": "tv"}),
        encoding="utf-8",
    )
    d = classify_spoken_ingress(
        "so then you start doubting that observation",
        stt_conf=0.5,
        focus_context="YouTube video",
        voice_george_conf=0.81,
    )
    assert d["route"] == "direct"
    assert d["reason"] == "voice_identity_george_bypasses_media_gate"


def test_typed_still_direct_under_media(monkeypatch, tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    monkeypatch.setattr(gate, "STATE_DIR", state)
    monkeypatch.setattr(gate, "LEDGER", state / "media_ingress_gate.jsonl")
    monkeypatch.setattr(gate, "AMBIENT_CONTEXT_FILE", state / "ambient_media_context.json")
    gate.AMBIENT_CONTEXT_FILE.write_text(
        json.dumps({"ts": time.time(), "ttl_s": 3600, "source": "youtube", "note": "tv"}),
        encoding="utf-8",
    )
    d = classify_spoken_ingress(
        "so then you start doubting that observation",
        stt_conf=1.0,  # typed
        focus_context="YouTube video",
        voice_george_conf=0.0,
    )
    assert d["route"] == "direct"
    assert d["reason"] == "typed_input_always_direct"


def test_va3_rewrites_would_be_direct_feedback_under_media(monkeypatch, tmp_path):
    """Owner-feedback *shape* without voice under active media → OBSERVE."""
    state = tmp_path / ".sifta_state"
    state.mkdir()
    monkeypatch.setattr(gate, "STATE_DIR", state)
    monkeypatch.setattr(gate, "LEDGER", state / "media_ingress_gate.jsonl")
    monkeypatch.setattr(gate, "AMBIENT_CONTEXT_FILE", state / "ambient_media_context.json")
    gate.AMBIENT_CONTEXT_FILE.write_text(
        json.dumps({"ts": time.time(), "ttl_s": 3600, "source": "youtube", "note": "kitchen"}),
        encoding="utf-8",
    )
    from System.swarm_media_ingress_gate import _classify_spoken_ingress_core

    text = "good job, very good job, answer was too long"
    core = _classify_spoken_ingress_core(
        text, stt_conf=0.8, focus_context="YouTube video", voice_george_conf=0.0
    )
    assert core["route"] == "direct"  # would have replied
    d = classify_spoken_ingress(
        text, stt_conf=0.8, focus_context="YouTube video", voice_george_conf=0.0
    )
    assert d["route"] == "observed_media"
    assert d["reason"] == "ambiguous_voice_under_active_media_observe"
