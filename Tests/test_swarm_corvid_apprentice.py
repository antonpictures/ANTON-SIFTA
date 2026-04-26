import json

from System.swarm_corvid_apprentice import CorvidTask, SwarmCorvidApprentice
from System.swarm_adapter_pheromone_scorer import LEDGERS


def test_corvid_uses_chat_think_false_payload(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def read(self):
            return json.dumps({"message": {"content": "urgent_health"}}).encode("utf-8")

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["timeout"] = timeout
        captured["payload"] = json.loads(req.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    corvid = SwarmCorvidApprentice(timeout_s=3.0, max_tokens=32)
    response, latency = corvid._call_ollama("Classify this")

    assert response == "urgent_health"
    assert latency >= 0.0
    assert captured["url"].endswith("/api/chat")
    assert captured["timeout"] == 3.0
    assert captured["payload"]["think"] is False
    assert captured["payload"]["stream"] is False
    assert captured["payload"]["options"]["num_predict"] == 32


def test_corvid_trace_is_structured_and_prompt_free(tmp_path, monkeypatch):
    def fake_call(_prompt):
        return "command", 0.01

    monkeypatch.setattr(SwarmCorvidApprentice, "_call_ollama", lambda self, prompt: fake_call(prompt))

    ledger = tmp_path / "corvid.jsonl"
    corvid = SwarmCorvidApprentice(ledger_path=ledger)
    result = corvid.classify("push this code to github")

    assert result.success is True
    assert result.task == CorvidTask.CLASSIFY
    row = json.loads(ledger.read_text(encoding="utf-8").strip())
    assert row["event_kind"] == "CORVID_APPRENTICE_TASK"
    assert row["task"] == "classify"
    assert row["success"] is True
    assert row["input_len"] > 0
    assert "input_text" not in row
    assert "response" not in row


def test_corvid_ledger_participates_in_pheromone_scorer():
    names = {path.name for path in LEDGERS}

    assert "corvid_apprentice_trace.jsonl" in names
