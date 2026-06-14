from __future__ import annotations

import json
import py_compile
from pathlib import Path

from System.swarm_predator_gate_writer import CANONICAL_LEDGERS
from System.swarm_teacher_success import (
    TEACHER_SELECTION_LEDGER,
    TEACHER_SUCCESS_LEDGER,
    latest_teacher_selection,
    record_teacher_selection,
    record_teacher_success,
    teacher_learning_summary,
    teacher_success_rows,
)


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_teacher_selection_records_owner_spark_label_without_exact_model_claim(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"

    result = record_teacher_selection(
        provider="mimo",
        model_label="Spark",
        source="owner_selected_mimo_menu",
        state_dir=state,
    )

    row = result["row"]
    assert row["truth_label"] == "TEACHER_MODEL_SELECTION_V1"
    assert row["provider"] == "mimo"
    assert row["model_label"] == "Spark"
    assert row["model_id"] == ""
    assert "exact upstream model claim" in row["boundary"]
    assert latest_teacher_selection(state_dir=state)["selection_id"] == row["selection_id"]

    rows = _jsonl(state / TEACHER_SELECTION_LEDGER)
    assert rows[-1]["selection_id"] == row["selection_id"]
    for ledger in CANONICAL_LEDGERS:
        assert (state / ledger).exists()
        assert result["receipt_status"][ledger] == "ok"


def test_teacher_success_records_alice_learning_and_summarizes(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    record_teacher_selection(
        provider="mimo",
        model_label="Spark",
        source="owner_selected_mimo_menu",
        state_dir=state,
    )

    result = record_teacher_success(
        teacher="MiMo Spark",
        provider="mimo",
        model_label="Spark",
        app="Applications/sifta_we_code_together.py",
        alice_receipt_id="r1142-grok-mimo-spark-alice-coded-learning-memory",
        result="KEPT",
        lesson="Alice learned to show teacher-success rows from a real ledger.",
        files_touched=["Applications/sifta_we_code_together.py"],
        state_dir=state,
        call_id="4c035938-13a2-4a57-915c-f2e968a8cf27",
    )

    row = result["row"]
    assert row["truth_label"] == "TEACHER_SUCCESS_ALICE_LEARNED_V1"
    assert row["result"] == "KEPT"
    assert row["teacher"] == "MiMo Spark"
    assert row["alice_receipt_id"].startswith("r1142")
    assert "does not mean the teacher directly edited" in row["boundary"]

    rows = teacher_success_rows(limit=5, state_dir=state)
    assert rows[0]["success_id"] == row["success_id"]
    summary = teacher_learning_summary(state_dir=state)
    assert summary["total"] == 1
    assert summary["counts"] == {"KEPT": 1}
    assert summary["latest_selection"]["model_label"] == "Spark"
    assert summary["latest_success"]["lesson"].startswith("Alice learned")

    ledger_rows = _jsonl(state / TEACHER_SUCCESS_LEDGER)
    assert ledger_rows[-1]["four_ledger_receipt_id"].startswith("teacher-success-")
    for ledger in CANONICAL_LEDGERS:
        assert (state / ledger).exists()
        assert result["receipt_status"][ledger] == "ok"


def test_teacher_success_module_compiles() -> None:
    py_compile.compile("System/swarm_teacher_success.py", doraise=True)
