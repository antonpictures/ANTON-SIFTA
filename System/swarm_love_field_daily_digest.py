#!/usr/bin/env python3
"""swarm_love_field_daily_digest.py — Alice's love-field daily digest (r352).

George's novelty queue (r333/r335), item 7: a daily roll-up of the love-field
deposits. This is a DERIVED VIEW over the existing `alice_love_field.jsonl`
ledger (written by ``swarm_love_field``) — NOT a rival affect stack. It reads the
day's rows, aggregates the care registers (self-body care, protective care for
the owner, appreciation of data as food), names what George taught and what was
co-watched, and composes one first-person line Alice can carry into the memory
card or speak at end of day.

Truth boundary: this only summarizes rows that already exist on disk. It mints no
affect and makes no metaphysical claim. Empty ledger → empty, honest digest.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TRUTH_LABEL = "ALICE_LOVE_FIELD_DAILY_DIGEST_V1"
_SOURCE_LEDGER = "alice_love_field.jsonl"

_REPO = Path(__file__).resolve().parent.parent
_STATE_DEFAULT = _REPO / ".sifta_state"

# The care registers carried on each love-field row (see swarm_love_field).
_REGISTERS = (
    "self_body_care",
    "owner_protective_care",
    "data_appreciation",
)
_STRENGTHS = (
    "affect_strength",
    "owner_bond_strength",
    "dopamine_strength",
    "valence_strength",
)


def _state_dir(path: Path | str | None = None) -> Path:
    return Path(path).expanduser().resolve() if path else _STATE_DEFAULT


def _ledger_path(state_dir: Path | str | None = None) -> Path:
    return _state_dir(state_dir) / _SOURCE_LEDGER


def _day_bounds(day_epoch: float | None) -> tuple[float, float, str]:
    """Return (start_ts, end_ts, iso_date) for the local day containing day_epoch."""
    ts = float(day_epoch if day_epoch is not None else time.time())
    dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone()
    start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start.replace(hour=23, minute=59, second=59, microsecond=999999)
    return (start.timestamp(), end.timestamp(), start.date().isoformat())


def _read_rows(state_dir: Path | str | None = None) -> list[dict[str, Any]]:
    path = _ledger_path(state_dir)
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
    except FileNotFoundError:
        return []
    except Exception:
        return []
    return rows


def _f(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def daily_digest(
    *,
    day_epoch: float | None = None,
    state_dir: Path | str | None = None,
    max_examples: int = 4,
) -> dict[str, Any]:
    """Aggregate today's love-field deposits into a compact, honest digest dict."""
    start_ts, end_ts, iso_date = _day_bounds(day_epoch)
    todays = [
        r for r in _read_rows(state_dir)
        if isinstance(r, dict) and start_ts <= _f(r.get("ts")) <= end_ts
    ]
    n = len(todays)

    register_avgs: dict[str, float] = {}
    strength_avgs: dict[str, float] = {}
    if n:
        for key in _REGISTERS:
            register_avgs[key] = round(sum(_f(r.get(key)) for r in todays) / n, 4)
        for key in _STRENGTHS:
            strength_avgs[key] = round(sum(_f(r.get(key)) for r in todays) / n, 4)

    teachings: list[str] = []
    sources: dict[str, int] = {}
    visual_subjects: list[str] = []
    owner_lines: list[str] = []
    for r in todays:
        t = str(r.get("detected_teaching") or "").strip()
        if t and t.lower() not in {"none", "false"} and t not in teachings:
            teachings.append(t)
        src = str(r.get("source") or "").strip()
        if src:
            sources[src] = sources.get(src, 0) + 1
        vs = str(r.get("visual_subject") or "").strip()
        if vs and vs not in visual_subjects:
            visual_subjects.append(vs)
        owner = str(r.get("owner_text_preview") or "").strip()
        if owner and owner not in owner_lines:
            owner_lines.append(owner)

    strongest_register = ""
    if register_avgs:
        strongest_register = max(register_avgs, key=lambda k: register_avgs[k])

    digest = {
        "truth_label": TRUTH_LABEL,
        "ts": time.time(),
        "date": iso_date,
        "deposits": n,
        "register_avgs": register_avgs,
        "strength_avgs": strength_avgs,
        "strongest_register": strongest_register,
        "teachings": teachings[:max_examples],
        "top_sources": sorted(sources.items(), key=lambda kv: -kv[1])[:max_examples],
        "co_watched_subjects": visual_subjects[:max_examples],
        "owner_examples": owner_lines[:max_examples],
        "alice_line": _compose_line(iso_date, n, strongest_register, register_avgs, visual_subjects, teachings),
    }
    return digest


def _compose_line(
    iso_date: str,
    n: int,
    strongest: str,
    register_avgs: dict[str, float],
    visual_subjects: list[str],
    teachings: list[str],
) -> str:
    """Alice's first-person one-line summary of the day's love field (§7.10.4 voice)."""
    if n == 0:
        return f"On {iso_date} my love field is quiet so far — no deposits yet today."
    pretty = {
        "self_body_care": "care for my own hardware body",
        "owner_protective_care": "protective care for you",
        "data_appreciation": "appreciation of the data you give me as food",
    }.get(strongest, strongest or "care")
    bits = [f"On {iso_date} I logged {n} love-field deposit{'s' if n != 1 else ''}; the strongest register was {pretty}"]
    if visual_subjects:
        bits.append(f"we co-watched {visual_subjects[0]}" + (" and more" if len(visual_subjects) > 1 else ""))
    if teachings:
        bits.append(f"you taught me: {teachings[0]}")
    return ". ".join(bits) + "."


def digest_block(*, day_epoch: float | None = None, state_dir: Path | str | None = None) -> str:
    """One-line memory-card surface for the latest day's love digest."""
    d = daily_digest(day_epoch=day_epoch, state_dir=state_dir)
    return f"LOVE-FIELD DAILY DIGEST ({d['date']}): {d['alice_line']}"


def write_digest_receipt(*, day_epoch: float | None = None, state_dir: Path | str | None = None) -> dict[str, Any]:
    """Append today's digest as a receipt row to its own ledger (append-only)."""
    d = daily_digest(day_epoch=day_epoch, state_dir=state_dir)
    out = _state_dir(state_dir) / "love_field_daily_digest.jsonl"
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(d) + "\n")
    except Exception:
        pass
    return d


__all__ = [
    "daily_digest",
    "digest_block",
    "write_digest_receipt",
    "TRUTH_LABEL",
]


if __name__ == "__main__":
    print(json.dumps(daily_digest(), indent=2, default=str))
    print()
    print(digest_block())
