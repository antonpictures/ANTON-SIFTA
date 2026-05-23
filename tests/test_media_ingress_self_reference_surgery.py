import json
import time

from System import swarm_media_ingress_gate as gate
from System.swarm_media_ingress_gate import classify_spoken_ingress


def _declare_ambient_youtube(tmp_path, monkeypatch):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    monkeypatch.setattr(gate, "LEDGER", state / "media_ingress_gate.jsonl")
    monkeypatch.setattr(gate, "AMBIENT_CONTEXT_FILE", state / "ambient_media_context.json")
    monkeypatch.setattr(gate, "YOUTUBE_CONTEXT_LEDGER", state / "youtube_context.jsonl")
    monkeypatch.setattr(gate, "YOUTUBE_WATCH_LEDGER", state / "youtube_watch_memory.jsonl")
    gate.AMBIENT_CONTEXT_FILE.write_text(
        json.dumps(
            {
                "ts": time.time(),
                "source": "ambient_media_youtube",
                "note": "YouTube is playing; room audio is usually media.",
                "ttl_s": 3600.0,
            }
        ),
        encoding="utf-8",
    )


def test_owner_declared_youtube_does_not_swallow_system_is_you_correction(tmp_path, monkeypatch):
    _declare_ambient_youtube(tmp_path, monkeypatch)

    decision = classify_spoken_ingress(
        "the system is you always",
        stt_conf=0.40,
        focus_context="ARCHITECT APP FOCUS: YouTube video playing",
    )

    assert decision["route"] == "direct"
    assert decision["reason"] == "direct_self_reference_correction"


def test_owner_declared_youtube_does_not_swallow_pasted_system_correction(tmp_path, monkeypatch):
    _declare_ambient_youtube(tmp_path, monkeypatch)

    decision = classify_spoken_ingress(
        "is I said the system that I pasted you",
        stt_conf=0.60,
        focus_context="background_media_youtube",
    )

    assert decision["route"] == "direct"
    assert decision["reason"] == "direct_self_reference_correction"


def test_background_system_talk_without_you_still_routes_as_media(tmp_path, monkeypatch):
    _declare_ambient_youtube(tmp_path, monkeypatch)

    decision = classify_spoken_ingress(
        "the system is designed to scale compute through the tokens per watt",
        stt_conf=0.58,
        focus_context="background_media_youtube",
    )

    assert decision["route"] == "ambient_media"
    assert decision["reason"] == "owner_declared_background_media_youtube"
