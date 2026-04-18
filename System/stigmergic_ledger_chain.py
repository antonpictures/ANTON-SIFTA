#!/usr/bin/env python3
"""
stigmergic_ledger_chain.py — Tamper-evident append-only JSONL (hash chain)
════════════════════════════════════════════════════════════════════════════

Maps loosely to “information is scrambled but not arbitrarily destroyed” (black-hole
information debates; **not** a physics claim): each row commits to the previous row’s
hash so later edits to history break the chain.

**Distinct from** generic `ide_stigmergic_bridge.deposit()` — use this when the Architect
wants **cryptographic continuity** on a dedicated ledger path (audits, agent receipts).

Literature anchors: DYOR §15 (Landauer 1961 irreversible ops; Reynolds 1987 local rules).
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from System.jsonl_file_lock import append_line_locked

_REPO = Path(__file__).resolve().parent.parent
DEFAULT_LEDGER_PATH = _REPO / ".sifta_state" / "stigmergic_chain_ledger.jsonl"

_GENESIS = "0" * 64


def _canonical(obj: Dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _tail_last_line(path: Path, max_bytes: int = 65536) -> Optional[str]:
    if not path.exists():
        return None
    with path.open("rb") as f:
        f.seek(0, 2)
        size = f.tell()
        if size == 0:
            return None
        chunk = min(max_bytes, size)
        f.seek(size - chunk)
        raw = f.read().decode("utf-8", errors="replace")
    for line in reversed(raw.splitlines()):
        s = line.strip()
        if s:
            return s
    return None


def append_linked_row(
    payload: Dict[str, Any],
    *,
    path: Path = DEFAULT_LEDGER_PATH,
    ts: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Append one JSONL object with chain_seq, chain_prev, chain_hash, event_id, ts.
    `payload` must be JSON-serializable; chain fields are added by this function.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    last_line = _tail_last_line(path)
    prev_hash = _GENESIS
    seq = 0
    if last_line:
        try:
            last = json.loads(last_line)
            prev_hash = str(last.get("chain_hash", _GENESIS))
            seq = int(last.get("chain_seq", -1)) + 1
        except (json.JSONDecodeError, TypeError, ValueError):
            prev_hash = _GENESIS
            seq = 0

    now = time.time() if ts is None else float(ts)
    body_core = {
        "payload": payload,
        "chain_seq": seq,
        "chain_prev": prev_hash,
        "event_id": str(uuid.uuid4()),
        "ts": now,
    }
    digest = hashlib.sha256(
        (_canonical({"prev": prev_hash, "seq": seq, "payload": payload})).encode("utf-8")
    ).hexdigest()
    row = {**body_core, "chain_hash": digest}
    append_line_locked(path, _canonical(row) + "\n")
    return row


def verify_chain(path: Path = DEFAULT_LEDGER_PATH, *, max_rows: int = 100_000) -> Tuple[bool, List[str]]:
    """Linear scan: recompute hashes; return (ok, error_messages)."""
    errs: List[str] = []
    if not path.exists():
        return True, []
    prev = _GENESIS
    seq_expect = 0
    count = 0
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            count += 1
            if count > max_rows:
                errs.append(f"verify_chain: row limit {max_rows} exceeded")
                return False, errs
            try:
                row = json.loads(line)
            except json.JSONDecodeError as e:
                errs.append(f"line {count}: JSON error {e}")
                prev = _GENESIS
                continue
            if int(row.get("chain_seq", -1)) != seq_expect:
                errs.append(f"line {count}: chain_seq expected {seq_expect} got {row.get('chain_seq')}")
            if str(row.get("chain_prev", "")) != prev:
                errs.append(f"line {count}: chain_prev mismatch")
            payload = row.get("payload")
            recomputed = hashlib.sha256(
                (_canonical({"prev": prev, "seq": row.get('chain_seq'), "payload": payload})).encode(
                    "utf-8"
                )
            ).hexdigest()
            if recomputed != row.get("chain_hash"):
                errs.append(f"line {count}: chain_hash recomputation mismatch")
            prev = str(row.get("chain_hash", _GENESIS))
            seq_expect += 1
    return len(errs) == 0, errs


__all__ = ["DEFAULT_LEDGER_PATH", "append_linked_row", "verify_chain"]
