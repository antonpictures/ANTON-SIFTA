from __future__ import annotations

import sys
import types

from System import swarm_web_global_chat_speech_worker as worker


def test_speech_worker_completes_a_successful_request(monkeypatch):
    completed: list[dict[str, object]] = []
    health: list[dict[str, object]] = []

    class FakeBackend:
        name = "fake"

        def speak(self, text, params):
            assert text == "Bună, mamă."
            assert params is not None
            return True

    vocal_cords = types.ModuleType("System.swarm_vocal_cords")
    class VoiceParams:
        def __init__(self, voice=None):
            self.voice = voice

    vocal_cords.VoiceParams = VoiceParams
    vocal_cords.get_default_backend = lambda: FakeBackend()
    monkeypatch.setitem(sys.modules, "System.swarm_vocal_cords", vocal_cords)
    monkeypatch.setattr(
        worker,
        "complete_web_speech_request",
        lambda request_id, *, ok, error="": completed.append(
            {"request_id": request_id, "ok": ok, "error": error}
        ),
    )
    monkeypatch.setattr(worker, "_append", lambda row: health.append(row))

    worker._speak({"request_id": "turn-1", "text": "Bună, mamă."})

    assert completed == [{"request_id": "turn-1", "ok": True, "error": ""}]
    assert len(health) == 1
    row = health[0]
    assert row["event"] == "WEB_TYPED_SPEECH_RUNTIME"
    assert row["request_id"] == "turn-1"
    assert row["backend"] == "fake"
    assert row["ok"] is True
    assert row["error"] == ""
    assert row["truth_label"] == "WEB_TYPED_SPEECH_RUNTIME_V1"
    # The web mouth must now carry the detected language and the resolved voice
    # so a Romanian reply cannot silently be read by the English default.
    assert row["language"] == "romanian"
    assert "ioana" in row["voice"].lower() or "romanian" in row["voice"].lower()
