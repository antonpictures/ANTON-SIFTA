"""Fireworks Kimi attached row routes through MiMo → qwen CLI bridge (r1433)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_mimo_stream_routes_fireworks_kimi_through_mimo_cli_bridge(monkeypatch, tmp_path):
    from System import swarm_gemini_brain as brain
    from System.swarm_cortex_capabilities import FIREWORKS_KIMI_K2P6_MODEL, record_attached_models

    class _Proc:
        returncode = 0
        stdout = '{"type":"text","part":{"type":"text","text":"KIMI_BRIDGE_OK"}}\n'
        stderr = ""

    state = tmp_path / ".sifta_state"
    record_attached_models(
        "mimo:mimo-cli-default",
        ["mimo-auto", FIREWORKS_KIMI_K2P6_MODEL],
        default_attached=FIREWORKS_KIMI_K2P6_MODEL,
        state_dir=state,
    )
    captured = {}

    def fake_run(cmd, *args, **kwargs):
        if cmd and cmd[0] == "/tmp/mimo":
            captured["cmd"] = cmd
        return _Proc()

    monkeypatch.setattr(brain, "_STATE", state)
    monkeypatch.setattr(brain, "_mimo_cli_binary", lambda: "/tmp/mimo")
    monkeypatch.setattr(brain, "_cloud_inference_blocked_by_metabolism", lambda: (False, ""))
    monkeypatch.setattr(subprocess, "run", fake_run)

    events = list(brain.stream_chat("mimo:mimo-cli-default", [{"role": "user", "content": "ping"}]))

    assert events[-1] == ("done", "KIMI_BRIDGE_OK")
    assert captured["cmd"][:2] == ["/tmp/mimo", "run"]
    prompt = captured["cmd"][-1]
    assert "QWEN_CLI_DOWNSTREAM_BRIDGE" in prompt
    assert "accounts/fireworks/models/kimi-k2p6" in prompt
    trace_path = state / "mimo_stigmergic_traces.jsonl"
    assert trace_path.exists()
    trace = json.loads(trace_path.read_text(encoding="utf-8").splitlines()[-1])
    assert "mimo_cli_qwen_bridge" in trace["intent"]