#!/usr/bin/env python3
"""
System/stigmergic_tail_reader.py — Rotation-Safe Incremental JSONL Reader
══════════════════════════════════════════════════════════════════════════════
Generic pheromone trail reader for swimmers. Any swimmer can "follow" any
JSONL file's new entries without re-reading the entire file.

KEY SAFETY: Handles log rotation (swarm_log_rotation.py overwrites active
files, which invalidates byte offsets). When the file shrinks below the
stored watermark, the offset resets to 0 — no lost data, no crash.

This is the generic extraction of the pattern CP2F built into
swarm_chat_relay.py (_iter_new_rows + watermarks), now available to
all swimmers.

Literature anchors (CP2F DYOR IDE123):
  - O'Neil et al. — LSM-Tree (Acta Informatica 1996) — append + bounded
    working set + tiered storage
  - Kreps — "The Log" (essay) — immutable ordered log + consumer offset
  - Chandy & Lamport — "Distributed Snapshots" (ACM TOCS 1985) — offset
    alone is insufficient under concurrency; partial-line guard needed

Failure modes addressed:
  1. Partial final line (writer mid-append) → buffer until newline
  2. Rotation / truncate → offset RESET (file shrank)
  3. Unicode → JSONL = line-delimited UTF-8 discipline
  4. Corrupt lines → skip, don't crash

Usage:
    reader = StigmergicTailReader("immune_sentinel_patrols.jsonl")
    new_rows = reader.read_new()  # returns List[dict]
    # ... process rows ...
    # watermark auto-persisted

Architect policy (2026-04-18):
  Swimmers are SOFTWARE agents on DISK. This reader is how they follow
  each other's pheromone trails — the chemotaxis gradient the Architect
  visualized.
══════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_WATERMARK_DIR = _STATE / "tail_reader_watermarks"

MODULE_VERSION = "2026-04-18.v1"


class StigmergicTailReader:
    """
    Rotation-safe incremental reader for any JSONL pheromone trail.

    Each reader instance tracks one file. The watermark (byte offset) is
    persisted to disk so it survives process restarts. When the target file
    shrinks (due to log rotation), the offset auto-resets to 0.

    Parameters:
        target:         JSONL file to follow (relative to .sifta_state/ or absolute)
        reader_id:      unique name for this reader's watermark (defaults to filename)
        filter_fn:      optional predicate — only rows where filter_fn(row) is True
        max_rows:       cap per read_new() call to avoid flooding
    """

    def __init__(
        self,
        target: str | Path,
        reader_id: Optional[str] = None,
        filter_fn: Optional[Callable[[Dict[str, Any]], bool]] = None,
        max_rows: int = 100,
    ):
        # Resolve target path
        t = Path(target)
        if not t.is_absolute():
            t = _STATE / t
        self._target = t
        self._reader_id = reader_id or t.name
        self._filter_fn = filter_fn
        self._max_rows = max_rows
        self._watermark_path = _WATERMARK_DIR / f"{self._reader_id}.cursor"

    def _read_watermark(self) -> int:
        """Load persisted byte offset."""
        if not self._watermark_path.exists():
            return 0
        try:
            return int(self._watermark_path.read_text(encoding="utf-8").strip() or "0")
        except (ValueError, OSError):
            return 0

    def _write_watermark(self, offset: int) -> None:
        """Persist byte offset to disk."""
        self._watermark_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._watermark_path.write_text(str(int(offset)), encoding="utf-8")
        except OSError:
            pass

    def reset(self) -> None:
        """Reset watermark — next read_new() re-reads from start."""
        if self._watermark_path.exists():
            self._watermark_path.unlink(missing_ok=True)

    def read_new(self) -> List[Dict[str, Any]]:
        """
        Read new JSONL rows since last watermark.

        Returns list of parsed dicts. Watermark auto-advances.
        Handles:
          - File doesn't exist → empty list
          - File shrank (rotation) → reset to 0, read from start
          - Partial last line → skip it, don't advance watermark past it
          - Corrupt JSON → skip line, continue
        """
        if not self._target.exists():
            return []

        try:
            file_size = self._target.stat().st_size
        except OSError:
            return []

        offset = self._read_watermark()

        # ROTATION SAFETY: if file shrank, reset offset
        if offset > file_size:
            offset = 0

        rows: List[Dict[str, Any]] = []
        last_good_offset = offset

        try:
            with self._target.open("r", encoding="utf-8") as f:
                f.seek(offset)
                while len(rows) < self._max_rows:
                    line = f.readline()
                    if not line:
                        break

                    current_pos = f.tell()

                    # Partial line guard: if line doesn't end with newline,
                    # the writer may be mid-append. Don't advance past it.
                    if not line.endswith("\n"):
                        break

                    stripped = line.strip()
                    if not stripped:
                        last_good_offset = current_pos
                        continue

                    try:
                        row = json.loads(stripped)
                    except json.JSONDecodeError:
                        # Corrupt line — skip, advance offset past it
                        last_good_offset = current_pos
                        continue

                    if not isinstance(row, dict):
                        last_good_offset = current_pos
                        continue

                    # Apply optional filter
                    if self._filter_fn and not self._filter_fn(row):
                        last_good_offset = current_pos
                        continue

                    rows.append(row)
                    last_good_offset = current_pos

        except OSError:
            pass

        # Persist watermark
        self._write_watermark(last_good_offset)
        return rows

    @property
    def target_file(self) -> Path:
        return self._target

    @property
    def watermark_offset(self) -> int:
        return self._read_watermark()


# ── Convenience: common trail readers ──────────────────────────────────────

def create_immune_reader() -> StigmergicTailReader:
    """Follow the immune sentinel patrol log."""
    return StigmergicTailReader("immune_sentinel_patrols.jsonl", reader_id="immune_patrol")

def create_antibody_reader() -> StigmergicTailReader:
    """Follow the antibody ledger."""
    return StigmergicTailReader("stigmergic_antibodies.jsonl", reader_id="antibody_trail")

def create_outreach_reader() -> StigmergicTailReader:
    """Follow the outreach events log."""
    return StigmergicTailReader("outreach_events.jsonl", reader_id="outreach_trail")

def create_spinal_reflex_reader() -> StigmergicTailReader:
    """Follow the spinal reflex intercept log."""
    return StigmergicTailReader("spinal_reflex_intercepts.jsonl", reader_id="spinal_reflex_trail")

def create_work_receipt_reader() -> StigmergicTailReader:
    """Follow the work receipts ledger."""
    return StigmergicTailReader("work_receipts.jsonl", reader_id="work_receipt_trail")


# ── CLI smoke test ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        target = sys.argv[1]
    else:
        target = "ide_stigmergic_trace.jsonl"

    reader = StigmergicTailReader(target)
    print(f"\n=== STIGMERGIC TAIL READER (Rotation-Safe) ===")
    print(f"  Target:    {reader.target_file}")
    print(f"  Watermark: byte {reader.watermark_offset}")
    print()

    rows = reader.read_new()
    print(f"  New rows:  {len(rows)}")
    for i, row in enumerate(rows[:5]):
        kind = row.get("kind", row.get("type", "?"))
        ts = row.get("ts", 0)
        print(f"    [{i}] kind={kind}  ts={ts}")
    if len(rows) > 5:
        print(f"    ... and {len(rows) - 5} more")

    print(f"\n  Watermark after read: byte {reader.watermark_offset}")
    print()
