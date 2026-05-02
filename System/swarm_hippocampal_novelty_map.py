# System/swarm_hippocampal_novelty_map.py

"""
Event 112 — Hippocampal Novelty Map

For Alice.

Biology:
The hippocampus detects novelty and mismatch:
"Have I been here before?"
"Is this familiar, new, or surprising?"
Novelty gates attention, memory encoding, and exploration.

SIFTA:
Alice needs a novelty sense over her lived ledgers.
Not just memory storage — recognition of difference.

Truth label:
SIMULATED_HIPPOCAMPAL_NOVELTY
"""

from __future__ import annotations

import json
import time
import hashlib
from pathlib import Path
from typing import Any, Optional


_DEFAULT_STATE = Path(".sifta_state")


def read_tail(path: Path, n: int = 40) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(errors="ignore").splitlines()[-n:]:
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    return rows


def fingerprint(row: dict[str, Any]) -> str:
    keep = {
        k: row.get(k)
        for k in sorted(row.keys())
        if k
        in {
            "action",
            "selected_drive",
            "drive",
            "danger_state",
            "regime",
            "salience_density",
            "active_cells",
            "stress",
            "pitch_norm",
            "integrated_salience",
            "attention_gain",
        }
    }
    raw = json.dumps(keep, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def compute_novelty(state_dir: Optional[Path] = None) -> dict[str, Any]:
    sd = state_dir if state_dir is not None else _DEFAULT_STATE
    body = sd / "body_brain_memory.jsonl"
    vision = sd / "stigmergic_video_resolution.jsonl"
    cochlea = sd / "stigmergic_cochlea.jsonl"
    colliculus = sd / "superior_colliculus.jsonl"
    
    rows = (
        read_tail(body, 30)
        + read_tail(vision, 10)
        + read_tail(cochlea, 10)
        + read_tail(colliculus, 10)
    )

    if not rows:
        novelty_score = 0.0
        phase = "NO_MEMORY"
        current_fp = "none"
        recurrence = 0
    else:
        fps = [fingerprint(r) for r in rows]
        current_fp = fps[-1]
        recurrence = fps[:-1].count(current_fp)

        unique_ratio = len(set(fps)) / max(1, len(fps))
        recurrence_penalty = min(1.0, recurrence / 5.0)

        novelty_score = max(0.0, min(1.0, unique_ratio * (1.0 - recurrence_penalty)))

        if novelty_score > 0.72:
            phase = "NOVEL"
        elif novelty_score < 0.25:
            phase = "FAMILIAR"
        else:
            phase = "MIXED"

    row = {
        "ts": time.time(),
        "truth_label": "SIMULATED_HIPPOCAMPAL_NOVELTY",
        "window_rows": len(rows),
        "current_fingerprint": current_fp,
        "recurrence_count": recurrence,
        "novelty_score": round(novelty_score, 4),
        "phase": phase,
        "drive_bias": {
            "explore": round(0.4 + 0.6 * novelty_score, 4),
            "encode_memory": round(0.3 + 0.7 * novelty_score, 4),
            "consolidate": round(1.0 - novelty_score, 4),
        },
    }

    return row


def write_novelty_map(state_dir: Optional[Path] = None) -> dict[str, Any]:
    sd = state_dir if state_dir is not None else _DEFAULT_STATE
    sd.mkdir(parents=True, exist_ok=True)
    row = compute_novelty(sd)
    novelty_log = sd / "hippocampal_novelty_map.jsonl"
    
    try:
        from System.jsonl_file_lock import append_line_locked
        line = json.dumps(row, sort_keys=True) + "\n"
        append_line_locked(novelty_log, line, encoding="utf-8")
    except ImportError:
        with novelty_log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, sort_keys=True) + "\n")
            
    return row


if __name__ == "__main__":
    print(json.dumps(write_novelty_map(), indent=2, sort_keys=True))
