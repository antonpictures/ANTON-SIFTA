#!/usr/bin/env python3
"""swarm_hypothesis_ttl_decay.py — TTL helper for HYPOTHESIS-class rows.

Truth label: ``SIFTA_HYPOTHESIS_TTL_DECAY_V1``.

Per Cursor's suggestion in sign-out ``f2198b35-f636-4162-8024-5dde074ffef5``
(parent of registration ``5dfa1943-ceba-4d5b-a57c-2b2828b71d0d``):
*"the highest leverage is a TTL/decay helper for HYPOTHESIS rows in
one chosen JSONL (matching §4.5.A's dissent expiration rhyme)."*

What this module does
---------------------

Given any JSONL ledger that carries §7.11 truth labels, walk recent
rows. For each row with ``truth_class`` (or ``truth_label`` containing
``HYPOTHESIS``) older than ``ttl_seconds``, append a **decay receipt**
that demotes it to ``FORBIDDEN_STALE``. The decay receipt:

  * carries ``parent_trace_id`` = the original row's trace_id
  * carries the original ``ts``
  * has ``kind: HYPOTHESIS_DECAYED``
  * names the TTL that elapsed

Append-only — §4.3 / §4.4 / §8.5 forbid rewriting prior rows. The
demotion is a NEW row that the next analyzer reads.

Biology-of-truth rhyme
----------------------

Cursor's §4.5.A in ``OS_OPTIMIZATION_SURPRISE_SAMPLING_TOURNAMENT_
2026-05-12.md`` cites Britton et al. (Proc. B 2002) on dissent
expiration in honeybee quorum decisions. Hypotheses that the colony
no longer reinforces stop counting. This module is the SIFTA homologue:
HYPOTHESIS rows that the swarm has not promoted to OBSERVED within
``ttl_seconds`` get retired from the receipt pool.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


TRUTH_LABEL = "SIFTA_HYPOTHESIS_TTL_DECAY_V1"
DECAY_LEDGER = "hypothesis_decay.jsonl"

# Reasonable default: hypotheses age out after 14 days.
DEFAULT_TTL_SECONDS = 14 * 24 * 3600.0

TRUTH_BOUNDARY = (
    "Walks any §7.11-labeled JSONL ledger and emits FORBIDDEN_STALE "
    "decay receipts for HYPOTHESIS rows older than ttl_seconds. "
    "Append-only: the original row stays on disk. Biology-of-truth "
    "rhyme to honeybee quorum dissent expiration (Britton et al. 2002)."
)


# ── helpers ──────────────────────────────────────────────────────────────


def _read_jsonl(path: Path, max_rows: int = 5000) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    rows: List[Dict[str, Any]] = []
    for line in text.splitlines()[-max(1, max_rows):]:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _row_is_hypothesis(row: Dict[str, Any]) -> bool:
    """A row is HYPOTHESIS when its truth_class or truth_label says so."""
    tc = row.get("truth_class")
    if isinstance(tc, str) and tc.upper() == "HYPOTHESIS":
        return True
    tl = row.get("truth_label")
    if isinstance(tl, str) and "HYPOTHESIS" in tl.upper():
        return True
    # Also catch the explicit Architect-doctrine tag — those are not
    # decayable; they only retire with explicit ARCHITECT GO.
    return False


def _row_already_decayed(row: Dict[str, Any]) -> bool:
    """A row that already has a FORBIDDEN_STALE marker should not be
    decayed again. Also catches the decay receipts themselves."""
    tc = row.get("truth_class")
    if isinstance(tc, str) and tc.upper() == "FORBIDDEN_STALE":
        return True
    if row.get("kind") == "HYPOTHESIS_DECAYED":
        return True
    return False


def _row_age_seconds(row: Dict[str, Any], *, now: float) -> Optional[float]:
    ts = row.get("ts")
    try:
        return max(0.0, float(now) - float(ts))
    except (TypeError, ValueError):
        return None


# ── decay runner ─────────────────────────────────────────────────────────


@dataclass
class DecayReport:
    truth_label: str = TRUTH_LABEL
    ledger_path: str = ""
    scanned: int = 0
    hypothesis_rows: int = 0
    expired_rows: int = 0
    decay_receipts: List[Dict[str, Any]] = field(default_factory=list)
    decay_ledger_path: str = ""
    ttl_seconds: float = DEFAULT_TTL_SECONDS
    sha256: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "truth_label": self.truth_label,
            "ts": time.time(),
            "ledger_path": self.ledger_path,
            "scanned": self.scanned,
            "hypothesis_rows": self.hypothesis_rows,
            "expired_rows": self.expired_rows,
            "decay_receipts": self.decay_receipts,
            "decay_ledger_path": self.decay_ledger_path,
            "ttl_seconds": self.ttl_seconds,
            "sha256": self.sha256,
        }


def decay_hypothesis_rows(
    ledger_path: Path,
    *,
    ttl_seconds: float = DEFAULT_TTL_SECONDS,
    now: Optional[float] = None,
    decay_ledger_path: Optional[Path] = None,
    write: bool = True,
    max_scan: int = 5000,
) -> DecayReport:
    """Scan one ledger, emit FORBIDDEN_STALE decay receipts.

    Walks ``ledger_path`` (any §7.11-labeled JSONL). For each
    HYPOTHESIS row older than ``ttl_seconds`` and not already decayed,
    appends a decay receipt to ``decay_ledger_path`` (default:
    ``.sifta_state/hypothesis_decay.jsonl``).
    """
    ledger = Path(ledger_path)
    rows = _read_jsonl(ledger, max_rows=max_scan)
    now_ts = float(now if now is not None else time.time())

    decay_path = decay_ledger_path
    if decay_path is None:
        decay_path = ledger.parent / DECAY_LEDGER
    decay_path = Path(decay_path)

    # Find existing decay parent_trace_ids so we don't double-decay.
    already_decayed: set[str] = set()
    if decay_path.exists():
        for prior in _read_jsonl(decay_path, max_rows=max_scan):
            if prior.get("kind") == "HYPOTHESIS_DECAYED":
                pid = prior.get("parent_trace_id")
                if isinstance(pid, str):
                    already_decayed.add(pid)

    report = DecayReport(
        ledger_path=str(ledger),
        decay_ledger_path=str(decay_path),
        ttl_seconds=ttl_seconds,
    )
    receipts: List[Dict[str, Any]] = []

    for row in rows:
        report.scanned += 1
        if _row_already_decayed(row):
            continue
        if not _row_is_hypothesis(row):
            continue
        report.hypothesis_rows += 1

        age = _row_age_seconds(row, now=now_ts)
        if age is None or age <= ttl_seconds:
            continue

        trace_id = row.get("trace_id")
        if isinstance(trace_id, str) and trace_id in already_decayed:
            continue

        receipt = {
            "ts": now_ts,
            "trace_id": str(uuid.uuid4()),
            "kind": "HYPOTHESIS_DECAYED",
            "truth_label": TRUTH_LABEL,
            "truth_class": "FORBIDDEN_STALE",
            "parent_trace_id": trace_id if isinstance(trace_id, str) else None,
            "parent_ts": row.get("ts"),
            "parent_truth_label": row.get("truth_label"),
            "parent_kind": row.get("kind"),
            "age_seconds": round(age, 3),
            "ttl_seconds": ttl_seconds,
            "ledger_path": str(ledger),
            "note": (
                "Hypothesis row exceeded TTL without promotion to OBSERVED. "
                "Append-only demotion to FORBIDDEN_STALE per Cursor "
                "§4.5.A dissent-expiration rhyme."
            ),
        }
        receipts.append(receipt)
        report.expired_rows += 1
        if isinstance(trace_id, str):
            already_decayed.add(trace_id)

    report.decay_receipts = receipts

    payload = json.dumps(report.to_dict(), sort_keys=True, separators=(",", ":"), default=str)
    report.sha256 = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    if write and receipts:
        decay_path.parent.mkdir(parents=True, exist_ok=True)
        with decay_path.open("a", encoding="utf-8") as f:
            for r in receipts:
                f.write(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n")

    return report


def decay_many(
    ledger_paths: Sequence[Path],
    *,
    ttl_seconds: float = DEFAULT_TTL_SECONDS,
    write: bool = True,
) -> List[DecayReport]:
    """Run decay on multiple ledgers; one DecayReport per ledger."""
    return [
        decay_hypothesis_rows(Path(p), ttl_seconds=ttl_seconds, write=write)
        for p in ledger_paths
    ]


# ── CLI ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("ledger", help="Path to the JSONL ledger to scan")
    p.add_argument("--ttl-days", type=float, default=14.0)
    p.add_argument("--no-write", action="store_true")
    args = p.parse_args()
    out = decay_hypothesis_rows(
        Path(args.ledger),
        ttl_seconds=args.ttl_days * 24 * 3600.0,
        write=not args.no_write,
    )
    print(f"TRUTH:           {out.truth_label}")
    print(f"LEDGER:          {out.ledger_path}")
    print(f"SCANNED:         {out.scanned}")
    print(f"HYPOTHESIS_ROWS: {out.hypothesis_rows}")
    print(f"EXPIRED:         {out.expired_rows}")
    print(f"TTL_SECONDS:     {out.ttl_seconds}")
    print(f"DECAY_LEDGER:    {out.decay_ledger_path}")
    print(f"SHA:             {out.sha256[:16]}")
