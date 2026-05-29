#!/usr/bin/env python3
"""Append-only freshness loop for Alice's stigmergic pheromone field.

The older `swarm_pheromone_field.py` organ owns the spatial 32x32 chemical
grid. This module adds a ledger-freshness layer: every tick samples hot
JSONL substrates, computes which ones changed or stalled, appends one row to
`.sifta_state/pheromone_field.jsonl`, and optionally deposits a light trace
into the existing grid.

No model calls. No owner approval gate. Receipts are the evidence.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"

TRUTH_LABEL = "PHEROMONE_FRESHNESS_LOOP_V1"
_LEDGER = "pheromone_field.jsonl"
_STATE_FILE = "pheromone_freshness_state.json"

DEFAULT_LEDGER_NAMES = (
    "alice_conversation.jsonl",
    "work_receipts.jsonl",
    "agent_arm_receipts.jsonl",
    "matrix_terminal_process_trace.jsonl",
    "episodic_diary.jsonl",
    "unified_field_slo.jsonl",
    "organ_field_vector.jsonl",
    "visceral_field.jsonl",
    "unknowns_ledger.jsonl",
)


def _tail_lines(path: Path, *, max_bytes: int = 128_000, max_lines: int = 200) -> list[str]:
    if not path.exists():
        return []
    try:
        with path.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - max_bytes))
            return f.read().decode("utf-8", errors="replace").splitlines()[-max_lines:]
    except Exception:
        return []


def _load_state(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def _write_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, sort_keys=True) + "\n", encoding="utf-8")


def _ledger_sample(path: Path, ledger_name: str, previous: dict[str, Any], now: float) -> dict[str, Any]:
    exists = path.exists()
    size = 0
    mtime = None
    age_s = None
    lines: list[str] = []
    if exists:
        try:
            stat = path.stat()
            size = int(stat.st_size)
            mtime = float(stat.st_mtime)
            age_s = max(0.0, now - mtime)
            lines = _tail_lines(path)
        except OSError:
            exists = False
    prior = previous.get(ledger_name) if isinstance(previous, dict) else {}
    if not isinstance(prior, dict):
        prior = {}
    prior_size = int(prior.get("size_bytes") or 0)
    prior_line_count = int(prior.get("line_count_tail") or 0)
    line_count_tail = len([line for line in lines if line.strip()])
    delta_bytes = max(0, size - prior_size)
    delta_lines_est = max(0, line_count_tail - prior_line_count)
    age_component = 0.0 if age_s is None else max(0.0, 1.0 - min(age_s, 3600.0) / 3600.0)
    delta_component = min(1.0, (delta_bytes / 8192.0) + (delta_lines_est / 20.0))
    density_component = min(1.0, line_count_tail / 80.0)
    activity_score = round(0.55 * delta_component + 0.30 * age_component + 0.15 * density_component, 4)
    stalled = bool(exists and (age_s or 0.0) > 3600.0 and delta_bytes == 0)
    return {
        "ledger": ledger_name,
        "exists": bool(exists),
        "size_bytes": size,
        "mtime": mtime,
        "age_s": round(age_s, 3) if age_s is not None else None,
        "line_count_tail": line_count_tail,
        "delta_bytes": delta_bytes,
        "delta_lines_est": delta_lines_est,
        "activity_score": activity_score,
        "stalled": stalled,
    }


def sample_ledger_freshness(
    state_dir: Path | str = _STATE_DIR,
    *,
    ledger_names: tuple[str, ...] | None = None,
    now: float | None = None,
    top_n: int = 5,
    update_state: bool = False,
) -> dict[str, Any]:
    """Sample hot ledgers and return the strongest freshness gradients."""
    root = Path(state_dir)
    now = float(now if now is not None else time.time())
    names = ledger_names or DEFAULT_LEDGER_NAMES
    state_path = root / _STATE_FILE
    previous = _load_state(state_path)
    samples = [
        _ledger_sample(root / name, name, previous, now)
        for name in names
    ]
    samples.sort(
        key=lambda row: (
            float(row.get("activity_score") or 0.0),
            int(row.get("delta_bytes") or 0),
            int(row.get("line_count_tail") or 0),
        ),
        reverse=True,
    )
    selected = samples[: max(1, int(top_n))]
    hottest = [row["ledger"] for row in selected if float(row.get("activity_score") or 0.0) > 0.0]
    stalled = [row["ledger"] for row in samples if row.get("stalled")][: max(0, int(top_n))]
    gradient_note = (
        f"active={', '.join(hottest[:3]) or 'none'}; "
        f"stalled={', '.join(stalled[:3]) or 'none'}"
    )
    result = {
        "ts": now,
        "truth_label": TRUTH_LABEL,
        "sampled_ledgers": selected,
        "hottest_ledgers": hottest,
        "stalled_ledgers": stalled,
        "gradient_note": gradient_note,
    }
    if update_state:
        new_state = {
            row["ledger"]: {
                "size_bytes": row.get("size_bytes", 0),
                "mtime": row.get("mtime"),
                "line_count_tail": row.get("line_count_tail", 0),
                "last_sample_ts": now,
            }
            for row in samples
        }
        _write_state(state_path, new_state)
    return result


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    line = json.dumps(row, sort_keys=True) + "\n"
    try:
        from System.jsonl_file_lock import append_line_locked

        append_line_locked(path, line)
    except Exception:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(line)


def write_freshness_tick(
    state_dir: Path | str = _STATE_DIR,
    *,
    now: float | None = None,
    top_n: int = 5,
) -> dict[str, Any]:
    """Append one pheromone freshness row and refresh the previous-state cache."""
    root = Path(state_dir)
    row = sample_ledger_freshness(root, now=now, top_n=top_n, update_state=True)
    _append_jsonl(root / _LEDGER, row)
    try:
        from System.swarm_pheromone_field import update_pheromone_field

        for item in row.get("sampled_ledgers", [])[:3]:
            score = float(item.get("activity_score") or 0.0)
            if score > 0.0:
                update_pheromone_field(
                    {
                        "action": f"ledger_freshness:{item.get('ledger')}",
                        "td_value": min(1.0, score),
                    }
                )
    except Exception:
        pass
    return row


def _latest_row(path: Path) -> dict[str, Any]:
    for line in reversed(_tail_lines(path, max_lines=40)):
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict) and row.get("truth_label") == TRUTH_LABEL:
            return row
    return {}


def summary_for_prompt(
    state_dir: Path | str = _STATE_DIR,
    *,
    max_items: int = 5,
) -> str:
    """Return the latest freshness field summary for Alice's cortex."""
    root = Path(state_dir)
    row = _latest_row(root / _LEDGER)
    if not row:
        return "PHEROMONE FRESHNESS FIELD: no append-only freshness ticks yet."
    sampled = row.get("sampled_ledgers") or []
    bits = []
    for item in sampled[:max_items]:
        ledger = item.get("ledger")
        age = item.get("age_s")
        score = item.get("activity_score")
        stalled = " stalled" if item.get("stalled") else ""
        bits.append(f"{ledger}:score={score} age_s={age}{stalled}")
    return (
        "PHEROMONE FRESHNESS FIELD (append-only ledger gradient):\n"
        f"- truth_label={row.get('truth_label')} ts={row.get('ts')}\n"
        f"- gradient={row.get('gradient_note')}\n"
        f"- sampled={'; '.join(bits) if bits else 'none'}"
    )


def run_periodic_loop(
    *,
    state_dir: Path | str = _STATE_DIR,
    interval_s: float = 60.0,
    stop_event: Any = None,
) -> None:
    """Simple loop for daemon callers; Talk normally drives this by QTimer."""
    while True:
        if stop_event is not None and getattr(stop_event, "is_set", lambda: False)():
            return
        write_freshness_tick(state_dir)
        time.sleep(max(1.0, float(interval_s)))


__all__ = [
    "TRUTH_LABEL",
    "DEFAULT_LEDGER_NAMES",
    "sample_ledger_freshness",
    "write_freshness_tick",
    "summary_for_prompt",
    "run_periodic_loop",
]
