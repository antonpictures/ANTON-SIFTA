#!/usr/bin/env python3
"""
System/swarm_allostatic_load.py
══════════════════════════════════════════════════════════════════════════════
Event 102 — Allostatic Load Regulator

Biology:
  Short stress is adaptive; repeated stress accumulates as *allostatic load*.
  Chronic load suppresses exploration and biases repair/rest (McEwen 1998).

SIFTA:
  Rolling window over `body_brain_memory.jsonl` (metabolic_mode + td_value)
  produces a scalar load in [0, 1] and a coarse policy for downstream
  organs. Truth label is explicit simulation, not clinical measurement.

Truth label: SIMULATED_ALLOSTATIC_LOAD
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from System.jsonl_file_lock import append_line_locked

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
BODY_MEMORY = _STATE_DIR / "body_brain_memory.jsonl"
ALLOSTATIC_LEDGER = _STATE_DIR / "allostatic_load.jsonl"

TRUTH_LABEL = "SIMULATED_ALLOSTATIC_LOAD"
WINDOW_DEFAULT = 40


def clamp01(x: Any, default: float = 0.0) -> float:
    try:
        return max(0.0, min(1.0, float(x)))
    except Exception:
        return default


def _paths(state_dir: Optional[Path] = None) -> tuple[Path, Path]:
    base = Path(state_dir) if state_dir is not None else _STATE_DIR
    return base / "body_brain_memory.jsonl", base / "allostatic_load.jsonl"


def read_tail(path: Path, n: int = WINDOW_DEFAULT) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    rows: List[Dict[str, Any]] = []
    for line in lines[-n:]:
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def metabolic_mode_to_stress(mode: str) -> float:
    """Map metabolic_mode string (from MetabolicHomeostat) to [0, 1] stress."""
    s = str(mode).upper()
    if "CRITICAL" in s or "STARV" in s:
        return 1.0
    if "RED" in s:
        return 0.9
    if "YELLOW" in s or "AMBER" in s or "ORANGE" in s:
        return 0.55
    if "SLEEP" in s or "CONSERVE" in s:
        return 0.7
    if "GREEN" in s:
        return 0.15
    return 0.25


def td_value_to_stress(td: Any) -> float:
    """Higher stress when TD signal is poor (negative or flat bad)."""
    try:
        v = float(td)
    except (TypeError, ValueError):
        return 0.35
    if v < 0.0:
        return clamp01(0.45 + min(1.0, abs(v)) * 0.35)
    if v < 0.5:
        return 0.32
    return 0.12


def compute_allostatic_load(
    *,
    state_dir: Optional[Path] = None,
    window: int = WINDOW_DEFAULT,
) -> Dict[str, Any]:
    body_path, _ = _paths(state_dir)
    rows = read_tail(body_path, n=window)

    if not rows:
        load = 0.0
    else:
        stresses: List[float] = []
        for row in rows:
            mode = row.get("metabolic_mode", row.get("danger_state", "GREEN_GROW"))
            td = row.get("td_value", row.get("value", 0.0))
            stresses.append(
                0.65 * metabolic_mode_to_stress(str(mode))
                + 0.35 * td_value_to_stress(td)
            )
        load = sum(stresses) / len(stresses)

    load = clamp01(load)
    if load > 0.75:
        policy = "FORCE_REST_REPAIR"
    elif load > 0.45:
        policy = "SUPPRESS_EXPLORATION"
    else:
        policy = "ALLOW_GROWTH"

    return {
        "ts": time.time(),
        "truth_label": TRUTH_LABEL,
        "window": len(rows),
        "allostatic_load": load,
        "policy": policy,
        "drive_modifiers": {
            "explore": 0.25 if policy == "FORCE_REST_REPAIR" else 0.6 if policy == "SUPPRESS_EXPLORATION" else 1.1,
            "experiment": 0.2 if policy == "FORCE_REST_REPAIR" else 0.7,
            "repair": 1.6 if policy == "FORCE_REST_REPAIR" else 1.2,
            "rest": 1.7 if policy == "FORCE_REST_REPAIR" else 1.1,
            "learn": 0.7 if policy == "FORCE_REST_REPAIR" else 1.0,
        },
    }


def write_allostatic_load(*, state_dir: Optional[Path] = None) -> Dict[str, Any]:
    _, ledger_path = _paths(state_dir)
    row = compute_allostatic_load(state_dir=state_dir)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    append_line_locked(ledger_path, json.dumps(row, sort_keys=True) + "\n")
    return row


if __name__ == "__main__":
    print(json.dumps(write_allostatic_load(), indent=2, sort_keys=True))
