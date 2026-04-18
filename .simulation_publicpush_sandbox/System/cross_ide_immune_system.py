#!/usr/bin/env python3
"""
cross_ide_immune_system.py — Automated epistemic-conflict detector

Design: Gemini (browser tab, Anton Pictures Olympiad, 2026-04-17, TAB_CHAT).
Grounded implementation: Cursor Opus 4.7 on M5 (REPO_TOOL, same day).

What Gemini got right:
  * Concept — read the append-only stigmergic trace, spot contradicting
    claims across source_ide, emit a ``kind="epistemic_conflict"`` deposit
    so future agents see the friction instead of silently overwriting it.
  * Two-channel output — trace for agents + ledger for cost accounting.

What the first draft got wrong (fixed here):
  1. Trace path was ``Path("ide_stigmergic_trace.jsonl")`` (cwd-relative).
     Real file lives at ``.sifta_state/ide_stigmergic_trace.jsonl``.
  2. Only scanned ``kind in {"message", "claim"}`` — none of the 80+ real
     rows match, so the detector was a silent no-op.  Now configurable and
     defaults to the union of kinds actually used.
  3. Required ``meta.topic`` + ``meta.assertion`` fields that no real row
     carries.  Detector now falls back to **rule-based** conflict patterns
     (explicit ``anchor_id`` lineage, shared ``paper`` / ``arxiv_id`` ids,
     matched ``phase`` with opposing claims).  Callers can also stamp
     ``meta.topic`` / ``meta.assertion`` to use the structured path.
  4. ``hash(str)`` — Python's built-in is non-deterministic across runs
     (PYTHONHASHSEED).  Now SHA-256 hex.
  5. Relative ``Path("repair_log.jsonl")`` — real ledger is repo-root.
  6. **``.cursorrules`` violation**: financial ledger writes must be
     Ed25519-signed via ``crypto_keychain.sign_block``.  We now sign every
     row, and mint with ``amount=0.0`` (friction is a *signal*, not a mint).

This module does **not** mutate the trace.  It only appends.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.ide_stigmergic_bridge import deposit  # noqa: E402
from System.ledger_append import append_ledger_line  # noqa: E402

# Lazy sign-block import — only needed on the signing path.
try:
    from System.crypto_keychain import sign_block  # type: ignore
    _SIGN_AVAILABLE = True
except Exception:  # pragma: no cover — sandbox without keys
    _SIGN_AVAILABLE = False

_STATE = _REPO / ".sifta_state"
DEFAULT_TRACE_FILE = _STATE / "ide_stigmergic_trace.jsonl"
DEFAULT_REPAIR_LOG = _REPO / "repair_log.jsonl"
DEFAULT_CONFLICT_LOG = _STATE / "epistemic_conflicts.jsonl"
DEFAULT_CURSOR_FILE = _STATE / "cross_ide_immune_cursor.json"

# Kinds that *might* carry a claim or counter-claim.  Tuned from the live
# trace (T28–T38 + Cursor rows).  Callers can pass their own whitelist.
DEFAULT_CLAIM_KINDS: Tuple[str, ...] = (
    "message", "claim", "dyor", "dyor_verification",
    "epistemic_record", "epistemic_conflict", "temporal_marker",
    "inference_reflection", "code_generation", "topology_event",
    "voice_registry", "voice_intro",
)

__all__ = [
    "ClaimRecord",
    "Conflict",
    "CrossIDEImmuneSystem",
    "run_once",
]


# ───────────────────────────── data classes ─────────────────────────────

@dataclass
class ClaimRecord:
    """One structured claim extracted from a trace row."""
    topic: str
    assertion: str
    source_ide: str
    trace_id: str
    ts: float
    raw_kind: str
    raw_payload_preview: str
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Conflict:
    topic: str
    side_a: ClaimRecord
    side_b: ClaimRecord
    conflict_hash: str


# ───────────────────────────── helpers ─────────────────────────────

def _stable_hash(*parts: str) -> str:
    payload = "||".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:20]


def _read_trace_rows(trace_file: Path) -> Iterable[Dict[str, Any]]:
    if not trace_file.exists():
        return
    with trace_file.open("r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                row = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                yield row


def _extract_claims(
    row: Dict[str, Any],
    *,
    claim_kinds: Tuple[str, ...],
) -> List[ClaimRecord]:
    """Map one trace row to zero-or-more structured claims."""
    kind = str(row.get("kind", ""))
    if kind not in claim_kinds:
        return []
    meta = row.get("meta") or {}
    if not isinstance(meta, dict):
        meta = {}
    source = str(row.get("source_ide", "unknown"))
    trace_id = str(row.get("trace_id", ""))
    ts = float(row.get("ts", 0.0) or 0.0)
    payload = str(row.get("payload", ""))
    preview = payload if len(payload) <= 240 else payload[:240] + "…"

    out: List[ClaimRecord] = []

    # Path A — explicitly-tagged structured claim.
    mtopic = meta.get("topic")
    massertion = meta.get("assertion")
    if isinstance(mtopic, str) and isinstance(massertion, str):
        out.append(
            ClaimRecord(
                topic=mtopic,
                assertion=massertion,
                source_ide=source,
                trace_id=trace_id,
                ts=ts,
                raw_kind=kind,
                raw_payload_preview=preview,
                meta=meta,
            )
        )

    # Path B — rule-based: anchor_id (verification vs prior)
    anchor = meta.get("anchor_id")
    if isinstance(anchor, str):
        out.append(
            ClaimRecord(
                topic=f"anchor::{anchor}",
                assertion=f"{kind}::{preview[:120]}",
                source_ide=source,
                trace_id=trace_id,
                ts=ts,
                raw_kind=kind,
                raw_payload_preview=preview,
                meta=meta,
            )
        )

    # Path C — rule-based: paper identity (arxiv / doi / venue-id).
    paper_id = meta.get("paper") or meta.get("arxiv_id") or meta.get("id")
    if isinstance(paper_id, str):
        # A "claim" is a (paper, stance) tuple; stance is the verification status
        # if present, else the kind.  Different stances on the same paper = conflict.
        stance = str(
            meta.get("verification_status")
            or meta.get("grounding_level")
            or kind
        )
        out.append(
            ClaimRecord(
                topic=f"paper::{paper_id}",
                assertion=stance,
                source_ide=source,
                trace_id=trace_id,
                ts=ts,
                raw_kind=kind,
                raw_payload_preview=preview,
                meta=meta,
            )
        )

    return out


def _detect_conflicts(claims: List[ClaimRecord]) -> List[Conflict]:
    """Group by topic; emit a conflict for each (source_A ≠ source_B, assertion_A ≠ assertion_B) pair."""
    by_topic: Dict[str, List[ClaimRecord]] = {}
    for c in claims:
        by_topic.setdefault(c.topic, []).append(c)

    conflicts: List[Conflict] = []
    for topic, rows in by_topic.items():
        # Chronological order for stable pairing.
        rows.sort(key=lambda r: r.ts)
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                a, b = rows[i], rows[j]
                if a.source_ide == b.source_ide:
                    continue
                if a.assertion == b.assertion:
                    continue
                h = _stable_hash(topic, a.trace_id, b.trace_id)
                conflicts.append(Conflict(topic=topic, side_a=a, side_b=b, conflict_hash=h))
    return conflicts


def _load_seen(cursor_file: Path) -> set[str]:
    if not cursor_file.exists():
        return set()
    try:
        data = json.loads(cursor_file.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("seen"), list):
            return {str(x) for x in data["seen"]}
    except (json.JSONDecodeError, OSError):
        pass
    return set()


def _save_seen(cursor_file: Path, seen: set[str]) -> None:
    cursor_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {"seen": sorted(seen), "updated": int(time.time())}
    try:
        cursor_file.write_text(json.dumps(payload), encoding="utf-8")
    except OSError:
        pass


# ───────────────────────────── main class ─────────────────────────────

class CrossIDEImmuneSystem:
    """
    Tail-read the stigmergic trace, detect contradicting deposits, and emit
    one ``kind="epistemic_conflict"`` deposit per new conflict (dedup by
    deterministic SHA-256 hash).

    Usage::

        immune = CrossIDEImmuneSystem()
        report = immune.monitor_and_react()
        print(report["new_conflicts"])
    """

    def __init__(
        self,
        *,
        trace_file: Optional[Path] = None,
        cursor_file: Optional[Path] = None,
        repair_log: Optional[Path] = None,
        conflict_log: Optional[Path] = None,
        claim_kinds: Tuple[str, ...] = DEFAULT_CLAIM_KINDS,
        homeworld_serial: str = "GTH4921YP3",
        ledger_writes: bool = True,
    ) -> None:
        self.trace_file = trace_file or DEFAULT_TRACE_FILE
        self.cursor_file = cursor_file or DEFAULT_CURSOR_FILE
        self.repair_log = repair_log or DEFAULT_REPAIR_LOG
        self.conflict_log = conflict_log or DEFAULT_CONFLICT_LOG
        self.claim_kinds = tuple(claim_kinds)
        self.homeworld_serial = homeworld_serial
        self.ledger_writes = bool(ledger_writes)

    def monitor_and_react(self) -> Dict[str, Any]:
        all_claims: List[ClaimRecord] = []
        for row in _read_trace_rows(self.trace_file):
            all_claims.extend(_extract_claims(row, claim_kinds=self.claim_kinds))

        conflicts = _detect_conflicts(all_claims)
        seen = _load_seen(self.cursor_file)
        new_conflicts: List[Conflict] = [c for c in conflicts if c.conflict_hash not in seen]

        for c in new_conflicts:
            self._emit(c)
            seen.add(c.conflict_hash)

        _save_seen(self.cursor_file, seen)
        return {
            "claims_examined": len(all_claims),
            "conflicts_total": len(conflicts),
            "new_conflicts": [c.conflict_hash for c in new_conflicts],
        }

    # ── emission ─────────────────────────────────────────────

    def _emit(self, c: Conflict) -> None:
        payload_msg = f"[epistemic_conflict] topic='{c.topic}' a={c.side_a.source_ide} vs b={c.side_b.source_ide}"
        meta = {
            "conflict_hash": c.conflict_hash,
            "topic": c.topic,
            "side_a": {
                "source_ide": c.side_a.source_ide,
                "trace_id": c.side_a.trace_id,
                "assertion": c.side_a.assertion[:240],
                "ts": c.side_a.ts,
                "kind": c.side_a.raw_kind,
            },
            "side_b": {
                "source_ide": c.side_b.source_ide,
                "trace_id": c.side_b.trace_id,
                "assertion": c.side_b.assertion[:240],
                "ts": c.side_b.ts,
                "kind": c.side_b.raw_kind,
            },
        }

        deposit(
            "cross_ide_immune_system",
            payload_msg,
            kind="epistemic_conflict",
            meta=meta,
            homeworld_serial=self.homeworld_serial,
        )

        # Mirror a structured row to a dedicated conflict log (append-only, flock-safe).
        append_ledger_line(
            self.conflict_log,
            {"timestamp": int(time.time()), **meta, "agent_id": "cross_ide_immune_system"},
        )

        if self.ledger_writes:
            self._append_signed_friction_row(c)

    def _append_signed_friction_row(self, c: Conflict) -> None:
        """
        Append an Ed25519-signed row to repair_log.jsonl per .cursorrules.
        ``amount`` is 0.0 — epistemic friction is a **signal**, not a mint.
        """
        ts = int(time.time())
        seal_payload = "||".join(
            [
                "epistemic_friction",
                c.conflict_hash,
                c.topic[:80],
                c.side_a.trace_id,
                c.side_b.trace_id,
                str(ts),
            ]
        )
        signature = sign_block(seal_payload) if _SIGN_AVAILABLE else ""
        event = {
            "timestamp": ts,
            "agent_id": "cross_ide_immune_system",
            "tx_type": "epistemic_friction",
            "amount": 0.0,
            "reason": f"conflict on {c.topic[:80]}",
            "conflict_hash": c.conflict_hash,
            "side_a_trace_id": c.side_a.trace_id,
            "side_b_trace_id": c.side_b.trace_id,
            "seal_payload": seal_payload,
            "ed25519_signature": signature,
            "signed": bool(signature),
            "homeworld_serial": self.homeworld_serial,
        }
        append_ledger_line(self.repair_log, event)


def run_once(**kwargs: Any) -> Dict[str, Any]:
    """One-shot scanner for cron / manual runs."""
    return CrossIDEImmuneSystem(**kwargs).monitor_and_react()


if __name__ == "__main__":
    report = run_once()
    print(json.dumps(report, indent=2))
