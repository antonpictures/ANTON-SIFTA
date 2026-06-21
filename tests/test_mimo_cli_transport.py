"""MiMo CLI transport — parse + auth error paths."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from System.swarm_gemini_brain import (  # noqa: E402
    _is_teacher_cli_history_noise,
    _looks_like_mimo_cli_tool_envelope_output,
    _parse_mimo_run_json_output,
    _to_teacher_cli_prompt,
)
from System import swarm_gemini_brain as brain  # noqa: E402


def _pin_mimo_auto_state(tmp_path: Path, monkeypatch) -> None:
    from System.swarm_cortex_capabilities import record_attached_models

    state = tmp_path / ".sifta_state"
    record_attached_models(
        "mimo:mimo-cli-default",
        ["mimo-auto"],
        default_attached="mimo-auto",
        state_dir=state,
    )
    monkeypatch.setattr(brain, "_STATE", state)


def test_parse_mimo_run_json_output_extracts_text():
    raw = (
        '{"type":"step_start"}\n'
        '{"type":"text","part":{"type":"text","text":"Hello MiMo"}}\n'
        '{"type":"step_finish"}\n'
    )
    assert _parse_mimo_run_json_output(raw) == "Hello MiMo"


def test_parse_mimo_run_json_output_ignores_tool_use_envelopes():
    raw = (
        '{"type":"step_start"}\n'
        '{"type":"tool_use","tool":"bash","part":{"type":"tool","tool":"bash"}}\n'
    )
    assert _parse_mimo_run_json_output(raw) == ""
    assert _looks_like_mimo_cli_tool_envelope_output(raw) is True


def test_teacher_cli_history_skips_kimi_failure_and_tool_envelopes():
    assert _is_teacher_cli_history_noise("Kimi WebBridge failed: No current window") is True
    assert _is_teacher_cli_history_noise('{"type":"tool_use","tool":"bash"}') is True
    assert _is_teacher_cli_history_noise("I read your shirt from local OCR.") is False
    prompt = _to_teacher_cli_prompt(
        [
            {"role": "assistant", "content": "Kimi WebBridge failed: No current window"},
            {"role": "user", "content": "what letters on my shirt?"},
            {"role": "assistant", "content": "Receipt-backed grounded line."},
        ],
        teacher="MiMo",
    )
    assert "Kimi WebBridge failed" not in prompt
    assert "Receipt-backed grounded line." in prompt
    assert "what letters on my shirt?" in prompt


def test_mimo_stream_reports_missing_cli(monkeypatch, tmp_path):
    _pin_mimo_auto_state(tmp_path, monkeypatch)
    monkeypatch.setattr("System.swarm_gemini_brain._mimo_cli_binary", lambda: None)
    events = list(brain.stream_chat("mimo:mimo-cli-default", [{"role": "user", "content": "ping"}]))
    assert events[0][0] == "error"
    assert "not on PATH" in events[0][1]


def test_mimo_stream_surfaces_auth_errors(monkeypatch, tmp_path):
    _pin_mimo_auto_state(tmp_path, monkeypatch)

    class _Proc:
        returncode = 1
        stdout = ""
        stderr = "missing credential for provider openai"

    monkeypatch.setattr("System.swarm_gemini_brain._mimo_cli_binary", lambda: "/tmp/mimo")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Proc())

    events = list(brain.stream_chat("mimo:mimo-cli-default", [{"role": "user", "content": "ping"}]))
    errors = [payload for kind, payload in events if kind == "error"]
    assert errors
    assert "mimo providers" in errors[0].lower()
