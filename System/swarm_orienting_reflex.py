#!/usr/bin/env python3
"""Event 113: orienting reflex from hippocampal novelty + collicular salience.

The superior colliculus says "something salient happened." The hippocampal
novelty map says "this does or does not match memory." The orienting reflex is
the small, receipt-backed bridge that turns those two signals into a bounded
attention/memory/exploration command.
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from System.jsonl_file_lock import append_line_locked, read_text_locked

DEFAULT_STATE = Path(".sifta_state")
NOVELTY_LOG = "hippocampal_novelty_map.jsonl"
COLLICULUS_LOG = "superior_colliculus.jsonl"
REFLEX_LOG = "orienting_reflex.jsonl"
TRUTH_LABEL = "SIMULATED_ORIENTING_REFLEX"


def clamp01(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except Exception:
        return default
    return max(0.0, min(1.0, number))


def _state_dir(state_root: Optional[Path] = None, state_dir: Optional[Path] = None) -> Path:
    root = state_root if state_root is not None else state_dir
    return Path(root) if root is not None else DEFAULT_STATE


def read_tail(path: Path, n: int = 1) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        body = read_text_locked(path, encoding="utf-8", errors="replace")
    except OSError:
        return []
    rows: list[dict[str, Any]] = []
    for line in body.splitlines()[-max(1, int(n)) :]:
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _latest_novelty(root: Path) -> dict[str, Any]:
    rows = read_tail(root / NOVELTY_LOG, 1)
    return rows[-1] if rows else {}


def _latest_colliculus(root: Path) -> dict[str, Any]:
    rows = read_tail(root / COLLICULUS_LOG, 1)
    return rows[-1] if rows else {}


def compute_orienting(
    state_root: Optional[Path] = None,
    *,
    state_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    root = _state_dir(state_root, state_dir)
    novelty = _latest_novelty(root)
    colliculus = _latest_colliculus(root)

    novelty_score = clamp01(novelty.get("novelty_score", 0.0))
    novelty_phase = str(novelty.get("phase") or "NO_MEMORY")
    salience = clamp01(
        colliculus.get("integrated_salience", colliculus.get("salience", 0.0))
    )

    cross_term = novelty_score * salience
    orienting_intensity = clamp01(0.45 * novelty_score + 0.45 * salience + 0.25 * cross_term)
    orient_trigger = orienting_intensity >= 0.60

    command = {
        "attention_gain": round(1.0 + 1.5 * orienting_intensity, 4),
        "memory_encode_bias": round(1.0 + 1.2 * orienting_intensity, 4),
        "explore_bias": round(1.0 + 0.8 * orienting_intensity, 4),
    }
    td_bias = round((0.35 if orient_trigger else 0.10) * orienting_intensity, 4)

    return {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "truth_label": TRUTH_LABEL,
        "schema_version": "orienting_reflex.event113.v1",
        "novelty_trace_id": str(novelty.get("trace_id") or novelty.get("tick_id") or ""),
        "colliculus_trace_id": str(colliculus.get("trace_id") or colliculus.get("tick_id") or ""),
        "novelty_phase": novelty_phase,
        "novelty_score": round(novelty_score, 4),
        "integrated_salience": round(salience, 4),
        "orienting_intensity": round(orienting_intensity, 4),
        "orient_trigger": bool(orient_trigger),
        "td_bias": td_bias,
        "command": command,
        "raw_audio_logged": False,
    }


def compute_orienting_reflex(state_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Backward-compatible name used by early Event 113 sketches."""
    return compute_orienting(state_dir=state_dir)


def write_orienting_reflex(
    state_root: Optional[Path] = None,
    *,
    state_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    root = _state_dir(state_root, state_dir)
    root.mkdir(parents=True, exist_ok=True)
    row = compute_orienting(state_root=root)
    append_line_locked(root / REFLEX_LOG, json.dumps(row, sort_keys=True) + "\n")
    return row


if __name__ == "__main__":
    print(json.dumps(write_orienting_reflex(), indent=2, sort_keys=True))
