from __future__ import annotations

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class _OllamaStreamResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def __iter__(self):
        yield json.dumps({"message": {"content": "Alice recovered."}, "done": False}).encode()
        yield json.dumps({"done": True}).encode()


def test_ollama_stream_timeout_retries_before_failure(monkeypatch):
    from Applications import sifta_talk_to_alice_widget as talk

    calls: list[float | None] = []
    sleeps: list[float] = []

    def fake_urlopen(_req, timeout=None):
        calls.append(timeout)
        if len(calls) < 4:
            raise TimeoutError("timed out")
        return _OllamaStreamResponse()

    worker = talk._BrainWorker(
        "alice-gemma4-e2b-cortex-5.1b-4.4gb:latest",
        [{"role": "user", "content": "Alice, can you hear me?"}],
    )
    done: list[str] = []
    failed: list[str] = []
    worker.done.connect(done.append)
    worker.failed.connect(failed.append)

    monkeypatch.setenv("SIFTA_OLLAMA_BRAIN_TIMEOUT_S", "not-a-number")
    monkeypatch.setenv("SIFTA_OLLAMA_MAX_ATTEMPTS", "4")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr(talk.time, "sleep", sleeps.append)

    worker.run()

    assert done == ["Alice recovered."]
    assert failed == []
    assert calls == [45.0, 45.0, 45.0, 45.0]
    assert sleeps == [0.4, 1.0, 2.0]


def test_ollama_stream_timeout_failure_is_not_reported_as_crash(monkeypatch):
    from Applications import sifta_talk_to_alice_widget as talk

    calls: list[float | None] = []

    def fake_urlopen(_req, timeout=None):
        calls.append(timeout)
        raise TimeoutError("timed out")

    worker = talk._BrainWorker(
        "alice-gemma4-e2b-cortex-5.1b-4.4gb:latest",
        [{"role": "user", "content": "Alice, wake up."}],
    )
    failed: list[str] = []
    worker.failed.connect(failed.append)

    monkeypatch.setenv("SIFTA_OLLAMA_BRAIN_TIMEOUT_S", "9")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr(talk.time, "sleep", lambda _seconds: None)

    worker.run()

    assert len(calls) == 2
    assert calls == [9.0, 9.0]
    assert len(failed) == 1
    assert failed[0].startswith("Brain timed out after 2 attempt(s)")
    assert "Brain crashed" not in failed[0]
