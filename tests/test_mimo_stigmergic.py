from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from System.swarm_mimo_stigmergic import (
    DEFAULT_MIMO_CLI_MODEL,
    PHEROMONE_LEDGER,
    TRACE_LEDGER,
    build_stigmergic_prompt,
    mimo_stigmergic_call,
    mimo_stigmergic_summary,
    read_field_state,
)


def _append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def test_mimo_call_reads_field_and_writes_receipts_without_cli(tmp_path, monkeypatch):
    state = tmp_path / ".sifta_state"
    _append(
        state / "ide_stigmergic_trace.jsonl",
        {"ts": 1.0, "organ": "pdf_forge", "summary": "owner asked for flyer proof"},
    )
    _append(
        state / "alice_conversation.jsonl",
        {"ts": 2.0, "content": "fix the PDF forge receipt path"},
    )

    monkeypatch.setattr(shutil, "which", lambda name: None)

    receipt = mimo_stigmergic_call(
        "repair the PDF forge",
        intent="repair pdf forge",
        driving_organ="test",
        state_dir=state,
    )

    assert receipt.ok is False
    assert receipt.pheromone_deposited is True
    assert receipt.field_traces_read == 1
    assert receipt.corrections_read == 1

    trace_rows = (state / TRACE_LEDGER).read_text(encoding="utf-8").splitlines()
    pheromone_rows = (state / PHEROMONE_LEDGER).read_text(encoding="utf-8").splitlines()
    assert len(trace_rows) == 1
    assert len(pheromone_rows) == 1

    for ledger in (
        "work_receipts.jsonl",
        "agent_arm_receipts.jsonl",
        "ide_stigmergic_trace.jsonl",
        "episodic_diary.jsonl",
    ):
        assert (state / ledger).exists(), ledger


def test_mimo_call_defaults_to_free_auto_model_flag(tmp_path, monkeypatch):
    state = tmp_path / ".sifta_state"
    captured = {}

    class _Proc:
        returncode = 0
        stdout = "MIMO_OK"
        stderr = ""

    def fake_run(cmd, *args, **kwargs):
        if cmd and cmd[0] == "/tmp/mimo":
            captured["cmd"] = cmd
        return _Proc()

    monkeypatch.setattr(shutil, "which", lambda name: "/tmp/mimo" if name == "mimo" else None)
    monkeypatch.setattr(subprocess, "run", fake_run)

    receipt = mimo_stigmergic_call(
        "say hi",
        intent="free auto default proof",
        driving_organ="test",
        state_dir=state,
    )

    assert receipt.ok is True
    assert receipt.model == DEFAULT_MIMO_CLI_MODEL
    assert captured["cmd"][captured["cmd"].index("-m") + 1] == DEFAULT_MIMO_CLI_MODEL


def test_second_prompt_contains_prior_mimo_trace(tmp_path):
    state = tmp_path / ".sifta_state"
    _append(
        state / TRACE_LEDGER,
        {
            "ts": 3.0,
            "intent": "repair pdf forge",
            "ok": False,
            "driving_organ": "test",
        },
    )

    field = read_field_state(state_dir=state)
    assert field["prior_mimo_actions"][0]["intent"] == "repair pdf forge"

    prompt = build_stigmergic_prompt("next repair", state_dir=state)
    assert "Last MiMo action" in prompt
    assert "repair pdf forge" in prompt

    summary = mimo_stigmergic_summary(state_dir=state)
    assert summary["total_calls"] == 1
    assert summary["fail"] == 1
