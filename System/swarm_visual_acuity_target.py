#!/usr/bin/env python3
"""Canonical target for Alice eye acuity.

This is the receipt-backed control plane for the acuity slider in
``sifta_what_alice_sees_widget.py``. It changes the stigmergic visual grid
size, not the physical camera sensor mode.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from System.swarm_visual_acuity_budget import (
    build_visual_acuity_budget,
    clamp_acuity,
    configured_default_acuity,
)

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
TARGET_JSON = _STATE / "active_visual_acuity.json"
COMMAND_LEDGER = _STATE / "visual_acuity_commands.jsonl"
VISUAL_LEDGER = _STATE / "visual_stigmergy.jsonl"

DEFAULT_ACUITY_STEP = 2


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _latest_visual_grid_size(state_dir: Path) -> int | None:
    path = state_dir / VISUAL_LEDGER.name
    if not path.exists():
        return None
    try:
        with path.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - 131072))
            lines = fh.read().splitlines()
    except OSError:
        return None
    for raw in reversed(lines):
        try:
            row = json.loads(raw.decode("utf-8", "replace"))
        except Exception:
            continue
        if not isinstance(row, dict):
            continue
        value = row.get("grid_size")
        if value is None:
            payload = row.get("payload")
            if isinstance(payload, dict):
                value = payload.get("grid_size")
        try:
            return int(value)
        except Exception:
            continue
    return None


def read_acuity_target(*, state_dir: Path | str = _STATE) -> dict[str, Any]:
    return _read_json(Path(state_dir) / TARGET_JSON.name)


def current_acuity(*, state_dir: Path | str = _STATE) -> int:
    state = Path(state_dir)
    target = read_acuity_target(state_dir=state)
    if target.get("grid_size") is not None:
        return clamp_acuity(target.get("grid_size"))
    latest = _latest_visual_grid_size(state)
    if latest is not None:
        return clamp_acuity(latest)
    return configured_default_acuity()


def write_acuity_target(
    grid_size: Any,
    *,
    state_dir: Path | str = _STATE,
    writer: str = "unknown",
    reason: str = "",
    source_text: str = "",
    write_ledger: bool = True,
) -> dict[str, Any]:
    state = Path(state_dir)
    budget = build_visual_acuity_budget(grid_size)
    row = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "truth_label": "VISUAL_ACUITY_TARGET_V1",
        "grid_size": budget.grid_size,
        "total_cells": budget.total_cells,
        "source_thumb_px": budget.source_thumb_px,
        "swimmer_budget": budget.swimmer_budget,
        "writer": writer,
        "reason": reason,
        "source_text_preview": str(source_text or "")[:220],
        "note": "Controls stigmergic visual acuity grid; does not change the physical camera sensor mode.",
    }
    if write_ledger:
        state.mkdir(parents=True, exist_ok=True)
        (state / TARGET_JSON.name).write_text(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        _append_jsonl(state / COMMAND_LEDGER.name, row)
    return row


def step_acuity(
    direction: str,
    *,
    state_dir: Path | str = _STATE,
    step: int = DEFAULT_ACUITY_STEP,
    writer: str = "unknown",
    source_text: str = "",
    write_ledger: bool = True,
) -> dict[str, Any]:
    current = current_acuity(state_dir=state_dir)
    sign = -1 if str(direction).lower() in {"down", "decrease", "lower", "reduce"} else 1
    target = clamp_acuity(current + (sign * max(1, int(step))))
    return write_acuity_target(
        target,
        state_dir=state_dir,
        writer=writer,
        reason=f"{direction}:{current}->{target}",
        source_text=source_text,
        write_ledger=write_ledger,
    )


def summary_for_prompt(row: dict[str, Any]) -> str:
    if not row:
        return "VISUAL ACUITY RECEIPT: none"
    return (
        "VISUAL ACUITY COMMAND RECEIPT:\n"
        f"- grid_size={row.get('grid_size')} total_cells={row.get('total_cells')} "
        f"source_thumb={row.get('source_thumb_px')}px swimmers={row.get('swimmer_budget')}\n"
        "- this changes Alice's stigmergic photon grid, not the physical camera sensor mode."
    )


__all__ = [
    "COMMAND_LEDGER",
    "TARGET_JSON",
    "current_acuity",
    "read_acuity_target",
    "step_acuity",
    "summary_for_prompt",
    "write_acuity_target",
]
