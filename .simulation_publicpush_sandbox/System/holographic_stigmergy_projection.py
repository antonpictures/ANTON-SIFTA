#!/usr/bin/env python3
"""
holographic_stigmergy_projection.py — Boundary trace → compact digest (metaphor only)
══════════════════════════════════════════════════════════════════════════════════════

**Not quantum gravity.** This is a **software analogue** of the idea that a
lower-dimensional boundary can encode information sufficient to constrain
“bulk” behavior: here the **boundary** is the tail of `ide_stigmergic_trace.jsonl`,
and the **bulk** is the implicit swarm state agents infer when they forage traces.

Physics anchors (peer-reviewed / arXiv) live in DYOR §14:
  't Hooft (1993); Susskind (1995); Susskind–Thorlacius–Uglum (1993);
  Maldacena & Susskind ER=EPR (2013).

Use `boundary_digest()` before expensive merges or to stamp handoffs.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_TRACE = _REPO / ".sifta_state" / "ide_stigmergic_trace.jsonl"


def _read_last_lines(path: Path, max_lines: int, max_tail_bytes: int = 2_097_152) -> List[str]:
    if not path.exists() or max_lines <= 0:
        return []
    with path.open("rb") as f:
        f.seek(0, 2)
        size = f.tell()
        if size == 0:
            return []
        chunk = min(max_tail_bytes, size)
        f.seek(size - chunk)
        raw = f.read().decode("utf-8", errors="replace")
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    return lines[-max_lines:]


@dataclass(frozen=True)
class BoundaryProjection:
    """Cryptographic summary of recent boundary deposits (JSONL tail)."""

    digest_hex: str
    lines_hashed: int
    last_ts: Optional[float]
    trace_path: str

    def to_dict(self) -> dict:
        return {
            "digest_hex": self.digest_hex,
            "lines_hashed": self.lines_hashed,
            "last_ts": self.last_ts,
            "trace_path": self.trace_path,
        }


def boundary_digest(
    trace_path: Path = _DEFAULT_TRACE,
    *,
    max_lines: int = 256,
) -> BoundaryProjection:
    """
    SHA-256 over UTF-8 bytes of the last `max_lines` non-empty JSONL rows.
    Optionally reads last row's `ts` field for staleness checks.
    """
    lines = _read_last_lines(trace_path, max_lines)
    payload = ("\n".join(lines)).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    last_ts: Optional[float] = None
    if lines:
        try:
            last_ts = float(json.loads(lines[-1]).get("ts", 0))
        except (json.JSONDecodeError, TypeError, ValueError):
            last_ts = None
    return BoundaryProjection(
        digest_hex=digest,
        lines_hashed=len(lines),
        last_ts=last_ts,
        trace_path=str(trace_path),
    )


def digest_pair(
    a: Path = _DEFAULT_TRACE,
    b: Path = _DEFAULT_TRACE,
    *,
    max_lines: int = 256,
) -> Tuple[BoundaryProjection, BoundaryProjection]:
    """Compare two trace files (e.g. primary vs mirror) by boundary digest."""
    return boundary_digest(a, max_lines=max_lines), boundary_digest(b, max_lines=max_lines)


__all__ = ["BoundaryProjection", "boundary_digest", "digest_pair"]
