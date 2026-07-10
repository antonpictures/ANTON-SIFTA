#!/usr/bin/env python3
"""r1608 Gift 3 — allosteric Hill gate for owner voice."""
from __future__ import annotations

import json
import time

from System.swarm_allosteric_gate import (
    hill,
    decide,
    voice_owner_allosteric_decision,
    should_commit_owner_voice,
)
from System import swarm_media_ingress_gate as gate
from System.swarm_media_ingress_gate import classify_spoken_ingress


def test_hill_is_sigmoid_around_k():
    # Deep reject below K, rising hard through K
    assert hill(0.40, K=0.58, n=8) < 0.15
    assert hill(0.51, K=0.58, n=8) < 0.40  # kitchen leak band
    assert hill(0.55, K=0.58, n=8) < hill(0.65, K=0.58, n=8)
    assert hill(0.70, K=0.58, n=8) > 0.70
    assert hill(0.0) == 0.0
    assert hill(1.0, K=0.58, n=8) > 0.95


def test_straddle_band_rejects_without_media():
    # Linear 0.55 used to sometimes pass hard 0.60 neighbors; allosteric rejects
    d = voice_owner_allosteric_decision(0.55, media_active=False)
    assert d["decision"] in {"reject", "ambiguous"}
    assert d["commit_owner"] is False
    assert should_commit_owner_voice(0.55) is False


def test_strong_owner_commits():
    d = voice_owner_allosteric_decision(0.72, media_active=False)
    assert d["decision"] == "commit"
    assert d["commit_owner"] is True
    assert should_commit_owner_voice(0.72) is True


def test_media_makes_cooperativity_stricter():
    mid = 0.58
    plain = voice_owner_allosteric_decision(mid, media_active=False)
    media = voice_owner_allosteric_decision(mid, media_active=True)
    # Under media, y should be <= plain (stricter or equal)
    assert media["y"] <= plain["y"] + 1e-9


def test_media_ingress_0_55_with_ambient_is_observe(monkeypatch, tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    monkeypatch.setattr(gate, "STATE_DIR", state)
    monkeypatch.setattr(gate, "LEDGER", state / "media_ingress_gate.jsonl")
    monkeypatch.setattr(gate, "AMBIENT_CONTEXT_FILE", state / "ambient_media_context.json")
    gate.AMBIENT_CONTEXT_FILE.write_text(
        json.dumps({"ts": time.time(), "ttl_s": 3600, "source": "youtube", "note": "kitchen"}),
        encoding="utf-8",
    )
    # Would-be owner feedback shape + weak voice in straddle band
    text = "good job, very good job, answer was too long"
    core = gate._classify_spoken_ingress_core(
        text, stt_conf=0.8, focus_context="YouTube", voice_george_conf=0.55
    )
    # Core may still promote direct via text heuristics
    full = classify_spoken_ingress(
        text, stt_conf=0.8, focus_context="YouTube", voice_george_conf=0.55
    )
    assert full["route"] != "direct" or full.get("reason") == "voice_identity_george_bypasses_media_gate"
    # With 0.55 and media, must not be owner bypass
    if full["route"] == "direct":
        assert full["reason"] != "voice_identity_george_bypasses_media_gate"
    else:
        assert full["route"] in {"observed_media", "ambient_media"}


def test_media_ingress_strong_voice_still_direct(monkeypatch, tmp_path):
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


def test_decide_generic_curve():
    r = decide(0.2, K=0.5, n=4)
    assert r["decision"] == "reject"
    c = decide(0.9, K=0.5, n=4)
    assert c["decision"] == "commit"
