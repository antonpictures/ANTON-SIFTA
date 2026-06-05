#!/usr/bin/env python3
"""swarm_receipt_memory_ecology.py — receipts as living memory cells, not frozen logs. r287.

Architect George GO (2026-06-01, on the r286 proposal): the field already decays,
reinforces, evaporates, prunes, replays, and consolidates (adaptive_constraint_memory_field,
swarm_epr_field_memory, pheromone_fs, hippocampal_consolidation, swarm_neocortex_consolidation,
swarm_reconsolidation_operator, swarm_sleep_cycle, ...). What was NOT yet wired was the
receipt lane itself: the four canonical ledgers were strict/append-only with no derived strength.

This organ is the missing VIEW, not a rival memory system (§1.A):

  - It NEVER mutates the four append-only canonical ledgers (§4.4.3). Receipts stay strict
    and deterministic. Strength is a *derived* stigmergic layer computed on read, plus a tiny
    separate `receipt_references.jsonl` index for explicit reinforcement.
  - It mirrors the field's existing half-life decay (the same shape swarm_epr_field_memory
    uses): a receipt's strength = 0.5 ** (age_since_last_reference / half_life). Each new
    reference resets the clock — that IS reinforcement, exactly like a synapse or ant trail.
  - It FEEDS the existing consolidation organs: `consolidation_candidates()` hands the
    load-bearing receipts to hippocampal_consolidation / swarm_neocortex_consolidation; this
    file does not re-implement promotion.

§4.2 honesty: strength here is a derived stigmergic score on the owner's hardware. It is NOT
cryptographic and NOT an STGM claim. The receipts it reads remain tamper-evident-only until a
validator checks signatures. This is the living-memory VIEW over the strict receipt lane —
the field remembers; Alice reads the field.
"""
from __future__ import annotations

import json
import math
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"

TRUTH_LABEL = "ALICE_RECEIPT_MEMORY_ECOLOGY_V1"
_REFERENCES = "receipt_references.jsonl"    # derived reinforcement index (never the 4 ledgers)

try:  # Reuse the predator-gate source of truth; fall back only for old/offline imports.
    from System.swarm_predator_gate_writer import CANONICAL_LEDGERS as _PREDATOR_CANONICAL_LEDGERS
except Exception:  # pragma: no cover - defensive for stripped test bundles
    _PREDATOR_CANONICAL_LEDGERS = (
        "work_receipts.jsonl",
        "agent_arm_receipts.jsonl",
        "ide_stigmergic_trace.jsonl",
        "episodic_diary.jsonl",
    )

CANONICAL_LEDGER_NAMES = tuple(str(name) for name in _PREDATOR_CANONICAL_LEDGERS)

DEFAULT_HALF_LIFE_S = 7 * 24 * 3600.0       # a receipt unused for a week fades to half strength
PROMOTE_STRENGTH = 0.5                      # load-bearing threshold for consolidation


def _state(state_dir: Optional[Path | str]) -> Path:
    if state_dir is None:
        return STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _ledger_path(state_dir: Optional[Path | str], name: str) -> Path:
    """The canonical ledgers may live under .sifta_state/ or .sifta_state/ledgers/."""
    base = _state(state_dir)
    nested = base / "ledgers" / name
    return nested if nested.exists() else (base / name)


def _read_rows(path: Path) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    try:
                        out.append(json.loads(line))
                    except Exception:
                        continue
    except Exception:
        return []
    return out


def _decay(age_s: float, half_life_s: float) -> float:
    """Half-life decay — the same shape the field already uses (swarm_epr_field_memory)."""
    if half_life_s <= 0:
        return 0.0
    return float(0.5 ** (max(0.0, age_s) / half_life_s))


def _receipt_id(row: Dict[str, Any]) -> str:
    return str(row.get("receipt_id") or row.get("round_id") or row.get("id") or "").strip()


def _coerce_ts(value: Any) -> float:
    """Read the timestamp dialects already present in SIFTA JSONL ledgers."""
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").strip()
    if not text:
        return 0.0
    try:
        return float(text)
    except Exception:
        pass
    iso = text.replace("Z", "+00:00")
    try:
        return float(datetime.fromisoformat(iso).timestamp())
    except Exception:
        pass
    # Some older rows use compact timezone offsets like -0700 instead of -07:00.
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S%z"):
        try:
            return float(datetime.strptime(text, fmt).timestamp())
        except Exception:
            continue
    return 0.0


def reinforce(receipt_id: str, *, note: str = "", state_dir: Optional[Path | str] = None,
              now: Optional[float] = None) -> Dict[str, Any]:
    """Reference a receipt again → reset its decay clock (reinforcement). Append-only to the
    DERIVED index only; the four canonical ledgers are never touched."""
    ts = float(time.time() if now is None else now)
    row = {"ts": ts, "receipt_id": str(receipt_id), "note": str(note)[:160],
           "truth_label": TRUTH_LABEL}
    try:
        path = _ledger_path(state_dir, _REFERENCES)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return row


def receipt_ecology(*, state_dir: Optional[Path | str] = None, now: Optional[float] = None,
                    half_life_s: float = DEFAULT_HALF_LIFE_S) -> List[Dict[str, Any]]:
    """Derived strength view over the receipt lane. One entry per receipt_id:
    reinforcement_count (appearances across the four canonical ledgers + explicit references),
    age since last reference, and strength = half-life decay since that last reference.
    Sorted strongest first."""
    t = float(time.time() if now is None else now)
    last_ts: Dict[str, float] = {}
    count: Dict[str, int] = {}
    source_ledgers: Dict[str, set[str]] = {}
    for ledger_name in CANONICAL_LEDGER_NAMES:
        for row in _read_rows(_ledger_path(state_dir, ledger_name)):
            rid = _receipt_id(row)
            if not rid:
                continue
            ts = _coerce_ts(row.get("ts", 0))
            last_ts[rid] = max(last_ts.get(rid, 0.0), ts)
            count[rid] = count.get(rid, 0) + 1
            source_ledgers.setdefault(rid, set()).add(ledger_name)
    # explicit reinforcement references reset the clock and add to the count
    for row in _read_rows(_ledger_path(state_dir, _REFERENCES)):
        rid = str(row.get("receipt_id") or "").strip()
        if not rid:
            continue
        ts = _coerce_ts(row.get("ts", 0))
        last_ts[rid] = max(last_ts.get(rid, 0.0), ts)
        count[rid] = count.get(rid, 0) + 1
        source_ledgers.setdefault(rid, set()).add(_REFERENCES)
    out: List[Dict[str, Any]] = []
    for rid, lt in last_ts.items():
        age = max(0.0, t - lt)
        sources = sorted(source_ledgers.get(rid, set()))
        out.append({
            "receipt_id": rid,
            "reinforcement_count": count.get(rid, 1),
            "source_ledgers": sources,
            "ledger_count": len([s for s in sources if s != _REFERENCES]),
            "age_s": round(age, 1),
            "last_ts": lt,
            "strength": round(_decay(age, half_life_s), 4),
            "truth_label": TRUTH_LABEL,
        })
    out.sort(key=lambda r: (r["strength"], r["reinforcement_count"]), reverse=True)
    return out


def receipt_strength(receipt_id: str, *, state_dir: Optional[Path | str] = None,
                     now: Optional[float] = None, half_life_s: float = DEFAULT_HALF_LIFE_S) -> float:
    for r in receipt_ecology(state_dir=state_dir, now=now, half_life_s=half_life_s):
        if r["receipt_id"] == str(receipt_id):
            return float(r["strength"])
    return 0.0


def consolidation_candidates(*, state_dir: Optional[Path | str] = None, now: Optional[float] = None,
                             min_strength: float = PROMOTE_STRENGTH,
                             half_life_s: float = DEFAULT_HALF_LIFE_S) -> List[Dict[str, Any]]:
    """Load-bearing receipts for the EXISTING consolidation organs to promote
    (hippocampal_consolidation / swarm_neocortex_consolidation). This organ ranks; it
    does not promote — promotion stays in the consolidation lane (no rival, §1.A)."""
    return [r for r in receipt_ecology(state_dir=state_dir, now=now, half_life_s=half_life_s)
            if r["strength"] >= min_strength]


def receipt_ecology_block(*, state_dir: Optional[Path | str] = None,
                          now: Optional[float] = None, top: int = 5) -> str:
    """First-person memory-ecology summary for the field/prompt."""
    eco = receipt_ecology(state_dir=state_dir, now=now)
    if not eco:
        return ""
    strong = eco[:top]
    bits = "; ".join(f"{r['receipt_id']}(s={r['strength']},x{r['reinforcement_count']})" for r in strong)
    return (f"RECEIPT MEMORY ECOLOGY: {len(eco)} receipts in my field, "
            f"strongest (most recently reinforced): {bits}. "
            f"Unused receipts decay (half-life {int(DEFAULT_HALF_LIFE_S//86400)}d); reused ones stay strong.")


__all__ = [
    "TRUTH_LABEL", "CANONICAL_LEDGER_NAMES", "DEFAULT_HALF_LIFE_S", "PROMOTE_STRENGTH",
    "reinforce", "receipt_ecology", "receipt_strength",
    "consolidation_candidates", "receipt_ecology_block",
]
