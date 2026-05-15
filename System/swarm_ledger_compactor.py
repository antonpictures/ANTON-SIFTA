#!/usr/bin/env python3
"""
System/swarm_ledger_compactor.py
══════════════════════════════════════════════════════════════════════════════
Tournament §9.C — bounded ledger compaction + hourly summary rollup.

Cowork 2026-05-12 — Architect GO ("CODE IT ALL").

Why this organ exists
─────────────────────
JSONL ledgers grow without bound. `kernel_process_table.jsonl` was already at
106 MB when I probed earlier. A heartbeat that tails a multi-GB file once
per tick burns clock + DRAM + NVM for no signal gain. Per the covenant
§7.10.2 "bits are physical" and §9.B "joule savings are HYPOTHESIS until
measured", this organ reduces the BYTES Alice has to read to know her own
recent past.

What it does
─────────────
For each registered target (path, max_bytes, summary_path):
  1. If file_size <= max_bytes → no-op (cheap stat check, no IO).
  2. Else:
     a. Read all rows (or chunked stream for very big files).
     b. Split into "keep-recent" (newest max_bytes/2 worth) and "summarize".
     c. For "summarize" rows, group by hour and emit one summary row per hour
        into the summary_path. Summary fields: hour, count, top_wake_reasons,
        mean_schedule_ms (if present), delta_sum (if present).
     d. Atomically replace the raw file with just the "keep-recent" tail.
  3. Write a LEDGER_COMPACTION receipt to .sifta_state/ledger_compaction.jsonl
     with bytes_before, bytes_after, rows_summarized.

Truth label: LEDGER_COMPACTION_V1.

Gated by env: SIFTA_LEDGER_COMPACT_ENABLE in ("1", "true", "yes", "on").
Disabled by default at module level (so importing is harmless); the run_*
functions are no-ops when disabled.

Reversible: all summary rows append to summary_path; raw files keep their
recent tail. If you regret a compaction, the raw history below max_bytes is
gone, but the hourly summary remains.
"""
from __future__ import annotations

import json
import os
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_REPO_ROOT = Path(__file__).resolve().parent.parent
_STATE = _REPO_ROOT / ".sifta_state"
TRUTH_LABEL = "LEDGER_COMPACTION_V1"
SCHEMA_VERSION = "ledger_compaction.v1"

# ── Default compaction targets ─────────────────────────────────────────────
# (path, max_bytes_before_compact, summary_path).
# Easy to extend at runtime via add_target().
_DEFAULT_TARGETS: List[Tuple[Path, int, Path]] = [
    (_STATE / "visual_stigmergy.jsonl",
     2 * 1024 * 1024,                                # 2 MiB cap
     _STATE / "visual_stigmergy_summary.jsonl"),
    (_STATE / "face_detection_events.jsonl",
     2 * 1024 * 1024,
     _STATE / "face_detection_summary.jsonl"),
    (_STATE / "kernel_process_table.jsonl",
     32 * 1024 * 1024,                               # generous — heartbeat is hot
     _STATE / "kernel_process_table_summary.jsonl"),
]


def enabled() -> bool:
    """Honest gate. Off by default to keep imports cheap and behavior preserved."""
    return os.environ.get("SIFTA_LEDGER_COMPACT_ENABLE", "").strip().lower() in (
        "1", "true", "yes", "on",
    )


def _hour_bucket(ts: float) -> str:
    """ISO hour bucket UTC, e.g. '2026-05-12T15'. Stable for grouping."""
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%Y-%m-%dT%H")
    except Exception:
        return "unknown_hour"


def _summarize_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Group rows by ISO hour and emit one summary row per hour."""
    by_hour: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        ts = r.get("ts") or r.get("t") or r.get("timestamp")
        if ts is None:
            continue
        by_hour[_hour_bucket(ts)].append(r)

    summaries: List[Dict[str, Any]] = []
    for hour, hour_rows in sorted(by_hour.items()):
        n = len(hour_rows)
        wake_reasons = Counter()
        schedule_ms_sum = 0.0
        schedule_ms_n = 0
        delta_sum = 0.0
        delta_n = 0
        for r in hour_rows:
            wr = r.get("wake_reason") or r.get("why") or r.get("kind")
            if wr:
                wake_reasons[str(wr)] += 1
            sm = r.get("schedule_ms")
            if isinstance(sm, (int, float)):
                schedule_ms_sum += float(sm)
                schedule_ms_n += 1
            d = r.get("delta")
            if isinstance(d, (int, float)):
                delta_sum += float(d)
                delta_n += 1
        summaries.append({
            "kind": "LEDGER_HOUR_SUMMARY",
            "truth": "OBSERVED",
            "hour": hour,
            "count": n,
            "top_wake_reasons": dict(wake_reasons.most_common(5)),
            "mean_schedule_ms": (schedule_ms_sum / schedule_ms_n) if schedule_ms_n else None,
            "delta_sum": round(delta_sum, 6) if delta_n else None,
            "delta_n": delta_n,
            "schema_version": SCHEMA_VERSION,
            "ts": time.time(),
        })
    return summaries


def _read_all_rows(path: Path) -> List[Dict[str, Any]]:
    """Read every line of a JSONL file, skipping malformed rows. OK for files
    a few hundred MB; for true GB-class files we'd stream — left as a TODO
    when an OBSERVED need arises."""
    rows: List[Dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
    except OSError:
        pass
    return rows


def _tail_bytes(path: Path, n_bytes: int) -> str:
    """Return the last ~n_bytes of a file, aligned to the start of a line."""
    try:
        size = path.stat().st_size
        offset = max(0, size - n_bytes)
        with path.open("rb") as f:
            f.seek(offset)
            chunk = f.read().decode("utf-8", errors="ignore")
        # drop the (potentially partial) first line
        nl = chunk.find("\n")
        if nl != -1 and offset > 0:
            chunk = chunk[nl + 1:]
        return chunk
    except OSError:
        return ""


def compact_one(target: Path, max_bytes: int, summary_path: Path) -> Dict[str, Any]:
    """Compact one ledger. Returns a receipt dict (whether or not work happened)."""
    result: Dict[str, Any] = {
        "kind": "LEDGER_COMPACTION",
        "truth": "OBSERVED",
        "target": str(target.relative_to(_REPO_ROOT)) if target.is_absolute() and str(target).startswith(str(_REPO_ROOT)) else str(target),
        "schema_version": SCHEMA_VERSION,
        "ts": time.time(),
        "ok": True,
    }
    try:
        if not target.exists():
            result["status"] = "missing"
            result["bytes_before"] = 0
            result["bytes_after"] = 0
            result["rows_summarized"] = 0
            return result

        bytes_before = target.stat().st_size
        result["bytes_before"] = bytes_before

        if bytes_before <= max_bytes:
            result["status"] = "below_threshold"
            result["bytes_after"] = bytes_before
            result["rows_summarized"] = 0
            return result

        all_rows = _read_all_rows(target)
        if not all_rows:
            result["status"] = "no_parseable_rows"
            result["bytes_after"] = bytes_before
            result["rows_summarized"] = 0
            return result

        # Keep the newest half-of-max as recent tail; summarize the rest.
        keep_tail_bytes = max_bytes // 2
        recent_chunk = _tail_bytes(target, keep_tail_bytes)
        recent_rows: List[Dict[str, Any]] = []
        for line in recent_chunk.splitlines():
            try:
                recent_rows.append(json.loads(line))
            except Exception:
                continue
        # Anything in all_rows that's NOT in recent_rows (by ts identity) gets summarized.
        recent_ts = {r.get("ts") for r in recent_rows if r.get("ts") is not None}
        to_summarize = [r for r in all_rows if r.get("ts") not in recent_ts]
        summaries = _summarize_rows(to_summarize)

        # Atomically replace raw file with the recent tail (bytes-faithful).
        tmp = target.with_suffix(target.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            f.write(recent_chunk)
            if recent_chunk and not recent_chunk.endswith("\n"):
                f.write("\n")
        os.replace(str(tmp), str(target))

        # Append summaries
        if summaries:
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            with summary_path.open("a", encoding="utf-8") as f:
                for s in summaries:
                    f.write(json.dumps(s) + "\n")

        result["status"] = "compacted"
        result["bytes_after"] = target.stat().st_size
        result["rows_summarized"] = len(to_summarize)
        result["hour_summaries_written"] = len(summaries)
    except Exception as e:
        result["ok"] = False
        result["status"] = "error"
        result["error"] = f"{type(e).__name__}: {e}"
    return result


def run_pass(targets: Optional[List[Tuple[Path, int, Path]]] = None) -> List[Dict[str, Any]]:
    """Run one compaction pass over all targets. Returns receipts."""
    if not enabled():
        return [{"kind": "LEDGER_COMPACTION", "status": "disabled", "ts": time.time()}]
    if targets is None:
        targets = _DEFAULT_TARGETS
    receipts: List[Dict[str, Any]] = []
    for path, max_bytes, summary_path in targets:
        receipts.append(compact_one(path, max_bytes, summary_path))
    # Write all receipts to the ledger of compactions
    try:
        rec_path = _STATE / "ledger_compaction.jsonl"
        rec_path.parent.mkdir(parents=True, exist_ok=True)
        with rec_path.open("a", encoding="utf-8") as f:
            for r in receipts:
                f.write(json.dumps(r) + "\n")
    except Exception:
        pass
    return receipts


def add_target(path: Path, max_bytes: int, summary_path: Path) -> None:
    """Register a new compaction target at runtime."""
    _DEFAULT_TARGETS.append((path, max_bytes, summary_path))


if __name__ == "__main__":
    # CLI: `python3 -m System.swarm_ledger_compactor` — runs one pass and prints receipts.
    if not enabled():
        print("[ledger_compactor] SIFTA_LEDGER_COMPACT_ENABLE is OFF — no-op.")
        print("[ledger_compactor] Set SIFTA_LEDGER_COMPACT_ENABLE=1 to run.")
    receipts = run_pass()
    for r in receipts:
        print(json.dumps(r))
