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


class _FakeFailoverResponse:
    def __init__(self, chunks: list[bytes]):
        self._chunks = chunks

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def __iter__(self):
        return iter(self._chunks)


def test_brain_worker_normalizes_demoted_gemma_to_m5():
    from Applications import sifta_talk_to_alice_widget as talk

    worker = talk._BrainWorker(
        "alice-gemma4-e2b-cortex-5.1b-4.4gb:latest",
        [{"role": "user", "content": "Alice, can you hear me?"}],
    )

    assert worker._model == "alice-m5-cortex-8b-6.3gb:latest"


def test_ollama_stream_timeout_retries_before_failure(monkeypatch):
    from Applications import sifta_talk_to_alice_widget as talk

    calls: list[float | None] = []
    brain_calls: list[float | None] = []
    sleeps: list[float] = []

    def fake_urlopen(_req, timeout=None):
        calls.append(timeout)
        if timeout != 180.0:
            raise TimeoutError("preflight timed out")
        brain_calls.append(timeout)
        if len(brain_calls) < 4:
            raise TimeoutError("timed out")
        return _OllamaStreamResponse()

    worker = talk._BrainWorker(
        "alice-m5-cortex-8b-6.3gb:latest",
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
    assert brain_calls == [180.0, 180.0, 180.0, 180.0]
    assert sleeps == [0.4, 1.0, 2.0]


def test_ollama_stream_timeout_failure_is_not_reported_as_crash(monkeypatch):
    from Applications import sifta_talk_to_alice_widget as talk

    calls: list[float | None] = []

    class _FakeURLResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def read(self):
            return b"{}"

    def fake_urlopen(_req, timeout=None):
        if "/api/chat" in str(getattr(_req, "full_url", "")):
            calls.append(timeout)
            raise TimeoutError("timed out")
        return _FakeURLResponse()

    worker = talk._BrainWorker(
        "alice-m5-cortex-8b-6.3gb:latest",
        [{"role": "user", "content": "Alice, wake up."}],
    )
    failed: list[str] = []
    worker.failed.connect(failed.append)

    monkeypatch.setenv("SIFTA_OLLAMA_BRAIN_TIMEOUT_S", "9")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr(talk.time, "sleep", lambda _seconds: None)

    worker.run()

    assert calls == [30.0, 30.0]
    assert len(failed) == 1
    assert failed[0].startswith("Brain timed out after 2 attempt(s)")
    assert "Brain crashed" not in failed[0]


def test_no_token_watchdog_bounds_local_cortex_wait(monkeypatch, tmp_path):
    from Applications import sifta_talk_to_alice_widget as talk

    monkeypatch.delenv("SIFTA_BRAIN_NO_TOKEN_TIMEOUT_S", raising=False)
    monkeypatch.setattr(talk, "_STATE_DIR", tmp_path / ".sifta_state")

    assert talk._brain_no_token_watchdog_s(model="krishairnd/Gemma-4-Uncensored:latest") == 180.0
    assert talk._brain_no_token_watchdog_s(model="alice-m5-cortex-8b-6.3gb:latest") == 180.0


def test_no_token_watchdog_covers_cloud_and_agent_cortexes(monkeypatch, tmp_path):
    from Applications import sifta_talk_to_alice_widget as talk

    monkeypatch.delenv("SIFTA_BRAIN_NO_TOKEN_TIMEOUT_S", raising=False)
    monkeypatch.setattr(talk, "_STATE_DIR", tmp_path / ".sifta_state")

    for model in (
        "grok:grok-4.3",
        "claude:claude-code-cli-default",
        "codex:gpt-5.5",
        "qwen:accounts/fireworks/models/kimi-k2p6",
        "cline:cline-cli-default",
    ):
        assert talk._brain_no_token_watchdog_s(model=model) == 150.0


def test_no_token_watchdog_aligns_mimo_with_cloud_timeout(monkeypatch, tmp_path):
    from Applications import sifta_talk_to_alice_widget as talk
    from System.swarm_stigmergic_timeout_policy import record_timeout_outcome

    monkeypatch.delenv("SIFTA_BRAIN_NO_TOKEN_TIMEOUT_S", raising=False)
    monkeypatch.delenv("SIFTA_MIMO_CORTEX_TIMEOUT_S", raising=False)
    monkeypatch.delenv("SIFTA_TEACHER_CLI_TIMEOUT_S", raising=False)
    monkeypatch.setenv("SIFTA_STATE_DIR", str(tmp_path))
    record_timeout_outcome(
        "mimo:mimo-cli-default",
        outcome="timeout",
        timeout_s=120,
        elapsed_s=120,
        state_dir=tmp_path,
    )

    cloud_s = talk._cloud_brain_timeout_s(
        model="mimo:mimo-cli-default",
        state_dir=tmp_path,
    )
    assert talk._brain_no_token_watchdog_s(model="mimo:mimo-cli-default") == cloud_s


def test_no_token_watchdog_env_override_is_clamped(monkeypatch):
    from Applications import sifta_talk_to_alice_widget as talk

    monkeypatch.setenv("SIFTA_BRAIN_NO_TOKEN_TIMEOUT_S", "9")
    assert talk._brain_no_token_watchdog_s(model="krishairnd/Gemma-4-Uncensored:latest") == 30.0

    monkeypatch.setenv("SIFTA_BRAIN_NO_TOKEN_TIMEOUT_S", "9000")
    assert talk._brain_no_token_watchdog_s(model="krishairnd/Gemma-4-Uncensored:latest") == 600.0


def test_body_action_no_token_watchdog_learns_slow_first_token(monkeypatch, tmp_path):
    from Applications import sifta_talk_to_alice_widget as talk
    from System.swarm_stigmergic_timeout_policy import record_timeout_outcome

    monkeypatch.delenv("SIFTA_BRAIN_NO_TOKEN_TIMEOUT_S", raising=False)
    monkeypatch.delenv("SIFTA_BODY_ACTION_CORTEX_NO_TOKEN_TIMEOUT_S", raising=False)
    state = tmp_path / ".sifta_state"
    monkeypatch.setattr(talk, "_STATE_DIR", state)
    record_timeout_outcome(
        "grok:grok-4.3",
        outcome="first_token",
        timeout_s=45,
        elapsed_s=20.0,
        first_token_latency_s=20.0,
        state_dir=state,
    )

    text = "display Madison Beer video on your hardware body"

    assert talk._owner_effector_requires_cortex_first(text) is True
    assert talk._is_fast_browser_action_cortex_turn(text) is False
    assert talk._brain_no_token_watchdog_for_owner_turn_s(text, model="grok:grok-4.3") > 20.0


def test_brain_worker_respects_local_first_candidate_order():
    from Applications import sifta_talk_to_alice_widget as talk

    worker = talk._BrainWorker(
        "mimo:mimo-cli-default",
        [{"role": "user", "content": "Alice, can you hear me?"}],
        model_candidates=[
            "krishairnd/Gemma-4-Uncensored:latest",
            "mimo:mimo-cli-default",
            "alice-m5-cortex-8b-6.3gb:latest",
        ],
    )

    assert worker.first_candidate_model() == "krishairnd/Gemma-4-Uncensored:latest"
    assert worker._model == "krishairnd/Gemma-4-Uncensored:latest"
    assert worker._model_candidates[:3] == [
        "krishairnd/Gemma-4-Uncensored:latest",
        "mimo:mimo-cli-default",
        "alice-m5-cortex-8b-6.3gb:latest",
    ]


def test_ollama_failover_uses_next_model_when_primary_empty(monkeypatch):
    from Applications import sifta_talk_to_alice_widget as talk

    def fake_urlopen(req, timeout=None):
        payload = json.loads((req.data or b"{}").decode("utf-8"))
        model = str(payload.get("model", ""))
        if model == "primary-empty":
            return _FakeFailoverResponse([
                json.dumps({"message": {"content": ""}, "done": True}).encode(),
            ])
        if model == "alice-m5-cortex-8b-6.3gb:latest":
            return _FakeFailoverResponse([
                json.dumps({"message": {"content": "Alice recovered."}, "done": False}).encode(),
                json.dumps({"done": True}).encode(),
            ])
        return _FakeFailoverResponse([json.dumps({"done": True}).encode()])

    worker = talk._BrainWorker(
        "primary-empty",
        [{"role": "user", "content": "Alice, can you hear me?"}],
        model_candidates=["primary-empty", "alice-m5-cortex-8b-6.3gb:latest"],
    )
    done: list[str] = []
    failed: list[str] = []
    worker.done.connect(done.append)
    worker.failed.connect(failed.append)
    monkeypatch.setenv("SIFTA_OLLAMA_MAX_ATTEMPTS", "1")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    worker.run()

    assert done == ["Alice recovered."]
    assert failed == []


def test_ollama_failover_reports_failed_receipt_when_all_candidates_empty(monkeypatch, tmp_path):
    from Applications import sifta_talk_to_alice_widget as talk

    def fake_urlopen(req, timeout=None):
        return _FakeFailoverResponse([
            json.dumps({
                "message": {"content": ""},
                "done": True,
                "done_reason": "stop",
            }).encode()
        ])

    worker = talk._BrainWorker(
        "primary-empty",
        [{"role": "user", "content": "Alice, can you hear me?"}],
        model_candidates=["primary-empty", "alice-m5-cortex-8b-6.3gb:latest"],
    )
    done: list[str] = []
    failed: list[str] = []
    worker.done.connect(done.append)
    worker.failed.connect(failed.append)
    monkeypatch.setenv("SIFTA_OLLAMA_MAX_ATTEMPTS", "1")
    monkeypatch.setattr(talk, "_STATE_DIR", tmp_path / ".sifta_state")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    worker.run()

    assert done == []
    assert len(failed) == 1
    assert failed[0].startswith("Body status: cortex returned empty after retries")
    assert "no Alice voice was posted" in failed[0]
    assert "context_chars=" in failed[0]
    rows = [
        json.loads(line)
        for line in (tmp_path / ".sifta_state" / "stigmergic_timeout_policy.jsonl").read_text().splitlines()
    ]
    row = rows[-1]
    assert row["truth_label"] == "FAILED"
    assert row["outcome"] == "empty_output_failed"
    assert row["model"] == worker._model
    assert row["model"] in failed[0]
    assert row["context_chars"] >= len("Alice, can you hear me?")
    assert row["context_messages"] == 1
    assert row["finish_reason"] == "stop"
