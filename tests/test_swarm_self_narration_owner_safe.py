from __future__ import annotations

import json
import sys
import types


def test_self_narration_heavy_model_requires_explicit_opt_in(monkeypatch):
    from System import swarm_self_narration_organ as organ

    monkeypatch.setenv(
        "SIFTA_SELF_NARRATION_MODEL",
        "alice-m5-cortex-8b-6.3gb:latest",
    )
    monkeypatch.delenv("SIFTA_SELF_NARRATION_ALLOW_HEAVY_MODEL", raising=False)

    assert organ._self_narration_model() == organ._SAFE_CORTEX_MODEL

    monkeypatch.setenv("SIFTA_SELF_NARRATION_ALLOW_HEAVY_MODEL", "1")

    assert organ._self_narration_model() == "alice-m5-cortex-8b-6.3gb:latest"


def test_self_narration_ollama_payload_is_bounded(monkeypatch):
    from System import swarm_self_narration_organ as organ

    calls: dict[str, object] = {}

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def read(self) -> bytes:
            return b'{"response": "I am tracking a quiet state."}'

    def fake_urlopen(req, timeout=None):
        calls["timeout"] = timeout
        calls["body"] = json.loads(req.data.decode("utf-8"))
        return _Response()

    monkeypatch.setenv(
        "SIFTA_SELF_NARRATION_MODEL",
        "alice-gemma4-e2b-cortex-5.1b-4.4gb:latest",
    )
    monkeypatch.delenv("SIFTA_SELF_NARRATION_KEEP_ALIVE", raising=False)
    monkeypatch.delenv("SIFTA_OLLAMA_KEEP_ALIVE", raising=False)
    monkeypatch.setenv("SIFTA_SELF_NARRATION_NUM_CTX", "8192")
    monkeypatch.setenv("SIFTA_SELF_NARRATION_NUM_PREDICT", "999")
    monkeypatch.setenv("SIFTA_SELF_NARRATION_TIMEOUT_S", "99")
    monkeypatch.setattr(organ.urllib.request, "urlopen", fake_urlopen)

    assert organ._call_cortex("Sentence:") == "I am tracking a quiet state."

    body = calls["body"]
    assert isinstance(body, dict)
    assert body["model"] == "alice-gemma4-e2b-cortex-5.1b-4.4gb:latest"
    assert body["keep_alive"] == "15s"
    assert body["options"]["num_ctx"] == 2048
    assert body["options"]["num_predict"] == 96
    assert calls["timeout"] == 30.0


def test_self_narration_empty_cortex_response_sets_backoff(monkeypatch):
    from System import swarm_self_narration_organ as organ

    receipts: list[dict] = []
    calls: list[str] = []
    fake_gate = types.SimpleNamespace(
        request_processing_clearance=lambda estimated_cost_stgm: {
            "ok": True,
            "clearance_id": "test-clearance",
            "clearance_hash": "hash",
            "signals": {},
        },
    )

    monkeypatch.setitem(sys.modules, "System.swarm_ambient_consciousness", fake_gate)
    monkeypatch.setenv("SIFTA_SELF_NARRATION_FAILURE_BACKOFF_S", "60")
    monkeypatch.setattr(organ, "_read_recent_app_focus", lambda: {})
    monkeypatch.setattr(organ, "_read_recent_verdicts", lambda: [])
    monkeypatch.setattr(organ, "_read_recent_ambient_text", lambda: [])
    monkeypatch.setattr(organ, "_read_recent_journal_lines", lambda: [])
    monkeypatch.setattr(organ, "_self_narration_model", lambda: organ._SAFE_CORTEX_MODEL)
    monkeypatch.setattr(organ, "_call_cortex", lambda prompt: calls.append(prompt) or "")
    monkeypatch.setattr(
        organ.SelfNarrationOrgan,
        "_append_receipt",
        lambda _self, receipt: receipts.append(dict(receipt)),
    )

    instance = organ.SelfNarrationOrgan()

    first = instance.tick_once()
    second = instance.tick_once()

    assert len(calls) == 1
    assert first["decision"] == "skip_cortex_empty"
    assert first["backoff_s"] == 60.0
    assert second["decision"] == "skip_cortex_backoff"
    assert second["backoff_remaining_s"] > 0
    assert [row["decision"] for row in receipts] == [
        "skip_cortex_empty",
        "skip_cortex_backoff",
    ]
