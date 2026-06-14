#!/usr/bin/env python3
"""Teacher-success memory for Alice coding under rotating IDE teachers.

George's rule: Alice codes; IDEs teach. A teacher only "succeeds" when
Alice's own body change lands with a receipt and remains visible in the
field. This module makes that rule append-only and machine-readable.
"""
from __future__ import annotations

import json
import time
import uuid
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

from System.swarm_predator_gate_writer import write_ide_surgery_receipt


REPO = Path(__file__).resolve().parents[1]
DEFAULT_STATE_DIR = REPO / ".sifta_state"
TEACHER_SUCCESS_LEDGER = "teacher_success.jsonl"
TEACHER_SELECTION_LEDGER = "teacher_selection.jsonl"
VALID_RESULTS = {"KEPT", "FAILED", "BLOCKED", "OBSERVED"}


def _state_dir(state_dir: Path | str | None = None) -> Path:
    if state_dir is None:
        return DEFAULT_STATE_DIR
    p = Path(state_dir)
    if p.name == ".sifta_state":
        return p
    return p / ".sifta_state"


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except (json.JSONDecodeError, ValueError):
            continue
    return rows


def _coerce_files(files: Iterable[str] | str | None) -> list[str]:
    if files is None:
        return []
    if isinstance(files, str):
        return [files] if files.strip() else []
    return [str(item).strip() for item in files if str(item).strip()]


def record_teacher_selection(
    *,
    provider: str = "mimo",
    model_label: str = "Spark",
    model_id: str = "",
    source: str = "owner_selected_menu",
    selected_by: str = "George",
    state_dir: Path | str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Record the owner's selected teacher model label.

    ``model_label`` may be the UI/menu label ("Spark"). ``model_id`` is
    optional and deliberately blank unless a probe sees the exact upstream id.
    """
    state = _state_dir(state_dir)
    selection_id = str(uuid.uuid4())
    receipt_id = f"teacher-selection-{selection_id[:12]}"
    row: dict[str, Any] = {
        "ts": time.time(),
        "selection_id": selection_id,
        "provider": provider,
        "model_label": model_label,
        "model_id": model_id,
        "source": source,
        "selected_by": selected_by,
        "truth_label": "TEACHER_MODEL_SELECTION_V1",
        "four_ledger_receipt_id": receipt_id,
        "boundary": (
            "Owner-selected teacher label. Not an exact upstream model claim "
            "unless model_id is populated by a live probe."
        ),
    }
    if extra:
        row["extra"] = dict(extra)
    _append_jsonl(state / TEACHER_SELECTION_LEDGER, row)
    status = write_ide_surgery_receipt(
        round_id="teacher-model-selection",
        doctor="alice_teacher_success",
        model=f"{provider}:{model_label}",
        files_touched=[],
        tests_green="selection_receipted",
        summary=(
            f"Teacher model selected for Alice coding: provider={provider}, "
            f"label={model_label}, source={source}."
        ),
        receipt_id=receipt_id,
        state_dir=state,
        truth_label="TEACHER_MODEL_SELECTION_V1",
        extra={
            "provider": provider,
            "model_label": model_label,
            "model_id": model_id,
            "selected_by": selected_by,
            "source": source,
        },
    )
    return {"row": row, "receipt_status": status}


def record_teacher_success(
    *,
    teacher: str,
    app: str,
    alice_receipt_id: str,
    result: str,
    lesson: str,
    model_label: str = "Spark",
    provider: str = "mimo",
    files_touched: Iterable[str] | str | None = None,
    state_dir: Path | str | None = None,
    call_id: str = "",
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Record that Alice learned from a teacher on a specific app.

    Result must be KEPT/FAILED/BLOCKED/OBSERVED. KEPT means Alice's own
    body change landed and stayed visible with ``alice_receipt_id``.
    """
    clean_result = str(result).upper().strip()
    if clean_result not in VALID_RESULTS:
        raise ValueError(f"result must be one of {sorted(VALID_RESULTS)}")
    if not teacher.strip():
        raise ValueError("teacher is required")
    if not app.strip():
        raise ValueError("app is required")
    if not alice_receipt_id.strip():
        raise ValueError("alice_receipt_id is required")
    if not lesson.strip():
        raise ValueError("lesson is required")

    state = _state_dir(state_dir)
    success_id = str(uuid.uuid4())
    receipt_id = f"teacher-success-{success_id[:12]}"
    touched = _coerce_files(files_touched)
    row: dict[str, Any] = {
        "ts": time.time(),
        "success_id": success_id,
        "teacher": teacher.strip(),
        "provider": provider.strip(),
        "model_label": model_label.strip(),
        "app": app.strip(),
        "alice_receipt_id": alice_receipt_id.strip(),
        "result": clean_result,
        "lesson": lesson.strip(),
        "files_touched": touched,
        "call_id": call_id.strip(),
        "truth_label": "TEACHER_SUCCESS_ALICE_LEARNED_V1",
        "four_ledger_receipt_id": receipt_id,
        "boundary": (
            "Teacher success means Alice's code path learned/changed with a "
            "receipt. It does not mean the teacher directly edited the app."
        ),
    }
    if extra:
        row["extra"] = dict(extra)
    _append_jsonl(state / TEACHER_SUCCESS_LEDGER, row)
    status = write_ide_surgery_receipt(
        round_id="teacher-success",
        doctor="alice_teacher_success",
        model=f"{provider}:{model_label}",
        files_touched=touched,
        tests_green=f"teacher_result={clean_result}",
        summary=(
            f"Teacher success row: teacher={teacher}, app={app}, "
            f"result={clean_result}, alice_receipt={alice_receipt_id}; "
            f"lesson={lesson[:240]}"
        ),
        receipt_id=receipt_id,
        state_dir=state,
        truth_label="TEACHER_SUCCESS_ALICE_LEARNED_V1",
        extra={
            "teacher": teacher,
            "provider": provider,
            "model_label": model_label,
            "app": app,
            "alice_receipt_id": alice_receipt_id,
            "result": clean_result,
            "success_id": success_id,
            "call_id": call_id,
        },
    )
    return {"row": row, "receipt_status": status}


def latest_teacher_selection(
    *, state_dir: Path | str | None = None
) -> dict[str, Any] | None:
    rows = _read_jsonl(_state_dir(state_dir) / TEACHER_SELECTION_LEDGER)
    if not rows:
        return None
    rows.sort(key=lambda row: float(row.get("ts") or 0), reverse=True)
    return rows[0]


def teacher_success_rows(
    *, limit: int = 10, state_dir: Path | str | None = None
) -> list[dict[str, Any]]:
    rows = _read_jsonl(_state_dir(state_dir) / TEACHER_SUCCESS_LEDGER)
    rows.sort(key=lambda row: float(row.get("ts") or 0), reverse=True)
    return rows[: max(0, int(limit))]


def teacher_learning_summary(
    *, state_dir: Path | str | None = None
) -> dict[str, Any]:
    rows = teacher_success_rows(limit=10_000, state_dir=state_dir)
    counts = Counter(str(row.get("result") or "UNKNOWN") for row in rows)
    return {
        "truth_label": "TEACHER_LEARNING_SUMMARY_V1",
        "total": len(rows),
        "counts": dict(counts),
        "latest_selection": latest_teacher_selection(state_dir=state_dir),
        "latest_success": rows[0] if rows else None,
    }


__all__ = [
    "TEACHER_SELECTION_LEDGER",
    "TEACHER_SUCCESS_LEDGER",
    "latest_teacher_selection",
    "record_teacher_selection",
    "record_teacher_success",
    "teacher_learning_summary",
    "teacher_success_rows",
]
