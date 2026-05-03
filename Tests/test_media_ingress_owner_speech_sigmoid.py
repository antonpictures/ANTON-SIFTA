#!/usr/bin/env python3
"""Regression tests for sigmoid owner-speech routing under declared YouTube."""

import json
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System import swarm_media_ingress_gate as gate
from System.swarm_media_ingress_gate import classify_spoken_ingress


def _declare_youtube(tmp_path: Path, monkeypatch) -> None:
    state = tmp_path / ".sifta_state"
    state.mkdir()
    monkeypatch.setattr(gate, "STATE_DIR", state)
    monkeypatch.setattr(gate, "LEDGER", state / "media_ingress_gate.jsonl")
    monkeypatch.setattr(gate, "AMBIENT_CONTEXT_FILE", state / "ambient_media_context.json")
    gate.AMBIENT_CONTEXT_FILE.write_text(
        json.dumps(
            {
                "ts": time.time(),
                "source": "ambient_media_youtube",
                "note": "Screen media is playing; voices are ambient unless owner evidence wins.",
                "ttl_s": 3600.0,
            }
        ),
        encoding="utf-8",
    )


def test_owner_sleep_statement_routes_direct_under_declared_youtube(monkeypatch, tmp_path):
    _declare_youtube(tmp_path, monkeypatch)

    decision = classify_spoken_ingress(
        "I am going to go to sleep. Here me all is.",
        stt_conf=0.45,
        focus_context="background_media_youtube",
    )

    assert decision["route"] == "direct"
    assert decision["reason"] == "owner_speech_sigmoid_under_declared_ambient_media"
    assert decision["confidence"] >= 0.55


def test_owner_body_noise_statement_routes_direct_under_declared_youtube(monkeypatch, tmp_path):
    _declare_youtube(tmp_path, monkeypatch)

    decision = classify_spoken_ingress(
        "body is always noisy, but it's noisy.",
        stt_conf=0.38,
        focus_context="background_media_youtube",
    )

    assert decision["route"] == "direct"
    assert decision["reason"] == "owner_grounding_signal_under_declared_ambient_media"
    assert decision["confidence"] >= 0.30


def test_owner_sleep_invitation_routes_direct_under_declared_youtube(monkeypatch, tmp_path):
    _declare_youtube(tmp_path, monkeypatch)

    decision = classify_spoken_ingress(
        "Okay, I'm gonna go to sleep. You can go to sleep too if you like.",
        stt_conf=0.69,
        focus_context="background_media_youtube",
    )

    assert decision["route"] == "direct"
    assert decision["reason"] == "owner_speech_sigmoid_under_declared_ambient_media"
    assert decision["confidence"] >= 0.55


def test_declared_youtube_narration_stays_ambient_without_owner_signal(monkeypatch, tmp_path):
    _declare_youtube(tmp_path, monkeypatch)

    decision = classify_spoken_ingress(
        "the theory of time is connected to entropy and biological complexity",
        stt_conf=0.92,
        focus_context="background_media_youtube",
    )

    assert decision["route"] == "ambient_media"
    assert decision["reason"] == "owner_declared_background_media_youtube"
