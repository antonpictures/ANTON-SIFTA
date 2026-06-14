"""MiMo CLI transport — parse + auth error paths."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from System.swarm_gemini_brain import (  # noqa: E402
    _parse_mimo_run_json_output,
    stream_chat,
)


def test_parse_mimo_run_json_output_extracts_text():
    raw = (
        '{"type":"step_start"}\n'
        '{"type":"text","part":{"type":"text","text":"Hello MiMo"}}\n'
        '{"type":"step_finish"}\n'
    )
    assert _parse_mimo_run_json_output(raw) == "Hello MiMo"


def test_mimo_stream_reports_missing_cli(monkeypatch):
    monkeypatch.setattr("System.swarm_gemini_brain._mimo_cli_binary", lambda: None)
    events = list(stream_chat("mimo:mimo-cli-default", [{"role": "user", "content": "ping"}]))
    assert events[0][0] == "error"
    assert "not on PATH" in events[0][1]


def test_mimo_stream_surfaces_auth_errors(monkeypatch):
    class _Proc:
        returncode = 1
        stdout = ""
        stderr = "missing credential for provider openai"

    monkeypatch.setattr("System.swarm_gemini_brain._mimo_cli_binary", lambda: "/tmp/mimo")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Proc())

    events = list(stream_chat("mimo:mimo-cli-default", [{"role": "user", "content": "ping"}]))
    assert events[0][0] == "error"
    assert "mimo providers" in events[0][1].lower()