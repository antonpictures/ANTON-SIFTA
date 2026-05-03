#!/usr/bin/env python3
# System/swarm_concept_context_builder.py

from __future__ import annotations
import json, time
from pathlib import Path
from typing import Any

STATE = Path(".sifta_state")
MAX_TAIL_BYTES = 256 * 1024
MAX_VALUE_CHARS = 360


def _sources(state_dir: Path | None = None) -> dict[str, Path]:
    root = Path(state_dir) if state_dir is not None else STATE
    return {
        "now": root / "situated_time.jsonl",
        "day_segments": root / "architect_day_segments.jsonl",
        "episodic_diary": root / "episodic_diary.jsonl",
        "health": root / "nightly_health.jsonl",
        "body": root / "body_brain_memory.jsonl",
        "regime": root / "regime_shifts.jsonl",
        "media_shazam": root / "media_shazam_guesses.jsonl",
    }


SOURCES = _sources()


def _tail_lines(path: Path, *, max_bytes: int = MAX_TAIL_BYTES) -> list[bytes]:
    if not path.exists():
        return []
    try:
        with path.open("rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            start = max(0, size - max(1, int(max_bytes)))
            fh.seek(start)
            data = fh.read()
    except OSError:
        return []

    lines = data.splitlines()
    if start > 0 and lines:
        # Drop the partial first line when we seek into the middle of a ledger.
        lines = lines[1:]
    return lines


def read_tail(path: Path, n: int = 5, *, max_bytes: int = MAX_TAIL_BYTES) -> list[dict[str, Any]]:
    """Read at most the tail window of a JSONL ledger and return the last n rows."""
    rows = []
    for line in _tail_lines(path, max_bytes=max_bytes):
        try:
            row = json.loads(line.decode("utf-8", errors="replace"))
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows[-max(1, int(n)) :]


def _compact_value(value: Any, *, max_chars: int = MAX_VALUE_CHARS) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
        except Exception:
            text = str(value)
    if len(text) > max_chars:
        return text[: max(0, max_chars - 1)] + "…"
    return text


def compact_row(row: dict[str, Any], *, max_value_chars: int = MAX_VALUE_CHARS) -> dict[str, Any]:
    keys = [
        "ts", "timestamp", "local_date", "start_minute", "end_minute",
        "label", "location", "media_context", "summary", "phase",
        "regime", "danger_state", "selected_drive", "action",
        "composite_score", "truth_label", "start_time", "end_time", "context_tags",
        "primary_category", "confidence", "source_type", "source_label",
        "acoustic_scene", "acoustic_scene_confidence", "title_guess",
        "channel_guess", "source_work", "director", "evidence_terms",
    ]
    return {k: _compact_value(row[k], max_chars=max_value_chars) for k in keys if k in row}


def build_concept_context(
    max_rows_per_source: int = 5,
    *,
    state_dir: Path | None = None,
    max_tail_bytes: int = MAX_TAIL_BYTES,
    max_value_chars: int = MAX_VALUE_CHARS,
) -> str:
    packet = {
        "generated_ts": time.time(),
        "truth_label": "CONCEPT_CONTEXT_PACKET",
        "note": "Facts from ledgers. LLM should reason over concepts; no regex intent guessing.",
        "sources": {},
    }

    for name, path in _sources(state_dir).items():
        rows = [
            compact_row(r, max_value_chars=max_value_chars)
            for r in read_tail(path, max_rows_per_source, max_bytes=max_tail_bytes)
        ]
        if rows:
            packet["sources"][name] = rows

    try:
        from System.swarm_concept_budget_gate import compress_packet
        packet = compress_packet(packet, state_dir=state_dir)
    except Exception:
        pass

    return (
        "### SIFTA CONCEPT CONTEXT\n"
        "Use these ledger facts as grounded memory. "
        "Do not invent facts not present here.\n"
        + json.dumps(packet, indent=2, sort_keys=True)
    )

if __name__ == "__main__":
    print(build_concept_context())
