#!/usr/bin/env python3
# System/swarm_concept_budget_gate.py

from __future__ import annotations
import json, time, hashlib
from pathlib import Path
from typing import Any

STATE = Path(".sifta_state")
BUDGET_LOG = STATE / "concept_context_budget.jsonl"

MAX_CHARS = 6000
STALE_AFTER_S = 6 * 60 * 60

def score_row(row: dict[str, Any]) -> float:
    ts = row.get("ts", row.get("timestamp", time.time()))
    try:
        age = max(0.0, time.time() - float(ts))
    except Exception:
        age = 0.0

    freshness = max(0.0, 1.0 - age / STALE_AFTER_S)
    truth = 1.0 if row.get("truth_label") else 0.6
    density = min(1.0, len(json.dumps(row, default=str)) / 800.0)
    return 0.55 * freshness + 0.30 * truth + 0.15 * density

def _budget_log(state_dir: Path | None = None) -> Path:
    root = Path(state_dir) if state_dir is not None else STATE
    return root / "concept_context_budget.jsonl"


def compress_packet(
    packet: dict[str, Any],
    max_chars: int = MAX_CHARS,
    *,
    state_dir: Path | None = None,
    write_receipt: bool = True,
) -> dict[str, Any]:
    sources = packet.get("sources", {})
    flat = []

    for source, rows in sources.items():
        for row in rows:
            flat.append((score_row(row), source, row))

    flat.sort(key=lambda x: x[0], reverse=True)

    kept = {}
    dropped = 0

    for _, source, row in flat:
        trial = dict(packet)
        trial_sources = {k: list(v) for k, v in kept.items()}
        trial_sources.setdefault(source, []).append(row)
        trial["sources"] = trial_sources

        if len(json.dumps(trial, default=str)) <= max_chars:
            kept = trial_sources
        else:
            dropped += 1

    packet["sources"] = kept
    packet["budget"] = {
        "max_chars": max_chars,
        "kept_rows": sum(len(v) for v in kept.values()),
        "dropped_rows": dropped,
        "packet_hash": hashlib.sha256(json.dumps(packet, sort_keys=True, default=str).encode()).hexdigest()[:16],
    }

    if write_receipt:
        log = _budget_log(state_dir)
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": time.time(),
                "truth_label": "CONCEPT_BUDGET_GATE",
                **packet["budget"],
            }, sort_keys=True) + "\n")

    return packet
