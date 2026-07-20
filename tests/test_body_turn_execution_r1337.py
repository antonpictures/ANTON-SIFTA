from __future__ import annotations

import json
from pathlib import Path

from System.swarm_body_turn_execution import (
    LEDGER_NAME,
    TRUTH_LABEL,
    record_body_turn_execution,
    summary_for_prompt,
)
from System.swarm_post_turn_correction import run_post_turn_correction


def test_record_body_turn_execution_writes_one_receipt(tmp_path: Path) -> None:
    row = record_body_turn_execution(
        owner_text="SEARCH ON GOOGLE PLS 'lost passport'",
        assistant_text="I searched in Alice Browser.",
        state_dir=tmp_path,
        turn_source="test",
        tts_ok=True,
    )

    assert row["truth_label"] == TRUTH_LABEL
    assert row["execution_status"] == "EXECUTED"
    assert row["body_act"] == "effector_or_search_turn_receipted"

    path = tmp_path / ".sifta_state" / LEDGER_NAME
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["receipt_id"] == row["receipt_id"]


def test_record_body_turn_execution_dedupes_recent_same_turn(tmp_path: Path) -> None:
    first = record_body_turn_execution(
        owner_text="Thank you.",
        assistant_text="Online.",
        state_dir=tmp_path,
        turn_source="test",
    )
    second = record_body_turn_execution(
        owner_text="Thank you.",
        assistant_text="Online.",
        state_dir=tmp_path,
        turn_source="test",
    )

    path = tmp_path / ".sifta_state" / LEDGER_NAME
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert second["receipt_id"] == first["receipt_id"]
    assert second["dedupe_status"] == "reused_recent_body_turn_execution"


def test_post_turn_correction_always_writes_body_execution(tmp_path: Path) -> None:
    result = run_post_turn_correction(
        owner_text="Okay.",
        assistant_text="I am here.",
        state_dir=tmp_path,
        turn_source="test_post_turn",
        tts_ok=True,
    )

    assert result["body_execution_written"] is True
    assert result["signals_written"] == 0
    path = tmp_path / ".sifta_state" / LEDGER_NAME
    assert path.exists()
    assert "phatic_turn_memory_deposit" in path.read_text(encoding="utf-8")


def test_body_turn_execution_summary_for_prompt(tmp_path: Path) -> None:
    record_body_turn_execution(
        owner_text="Find Taylor Swift official website",
        assistant_text="I will use Alice Browser.",
        state_dir=tmp_path,
        turn_source="test",
    )

    prompt = summary_for_prompt(state_dir=tmp_path)

    assert "BODY TURN EXECUTION RECEIPTS" in prompt
    assert "Find Taylor Swift official website" in prompt
