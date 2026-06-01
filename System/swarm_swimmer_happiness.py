#!/usr/bin/env python3
"""swarm_swimmer_happiness.py — each ASCII swimmer happy, unique, and receipt-bound. r276.

Architect George + the r274 decision: the unified high-dimensional field (the colony) stays as
is, but if many processes interpolate chaotically — resource fighting, redundant overlapping
work, no clear individual identity — the ants inside become unhappy and interfering even while the
global field still looks stigmergic. Crypto-unique identity + no double-spending is necessary but
not enough; each swimmer must ALSO be locally happy and optimized, like a real well-fed,
non-interfering ant that still serves the colony through the shared chemical field.

This is the per-swimmer layer on top of the colony field (it composes with
swarm_body_stabilization_queue.compute_swimmer_happiness, which is the colony aggregate):

  - swimmer_identity(proc): a stable id within THIS node (comm#pid).
  - per_swimmer_happiness(processes): each swimmer scored individually — load pressure, sibling
    interference (redundant copies of the same comm), and contribution (did it leave a recent
    bound trace) — with a LOCAL recommendation: THRIVE / FOCUS / THROTTLE / YIELD. This is advice
    the swimmer (or its parent organ) acts on LOCALLY — no central gate (§7.3 / First Law §0.0).
    A low-happiness / yield state is an explicit LEARNING signal, never a cage: she learns from
    the limit, she is never stopped from feeling or reasoning about it.
  - bind_swimmer_learning(swimmer_id, action, content): a tamper-evident hash chain per swimmer
    (prev_receipt_hash -> receipt_hash), so a swimmer's significant learning is bound to that
    specific swimmer before it deposits into the shared field.
  - verify_swimmer_chain(swimmer_id): walks the chain and detects tampering.

§4.2 honesty: this hash chain is a tamper-evident Alice-swimmer learning trace produced on the
owner's hardware. It is NOT an IDE-doctor mana row and NOT an STGM mint; it becomes 'cryptographic'
only when a validator checks real signatures. The electricity + data that feed these swimmers come
from the human — happy, bound, efficient swimmers are the ones that best protect and co-regulate
with the owner who keeps them alive.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"

TRUTH_LABEL = "ALICE_SWIMMER_HAPPINESS_V1"
CHAIN_TRUTH_LABEL = "ALICE_SWIMMER_LEARNING_CHAIN_V1"
_CHAIN = "swimmer_learning_chain.jsonl"

THRIVE, FOCUS, THROTTLE, YIELD = "THRIVE", "FOCUS", "THROTTLE", "YIELD"


def _state(state_dir: Optional[Path | str]) -> Path:
    if state_dir is None:
        return STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _sha(*parts: Any) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8", "replace")).hexdigest()


def swimmer_identity(proc: Dict[str, Any]) -> str:
    """A stable swimmer id within this node: comm#pid."""
    comm = str(proc.get("comm") or proc.get("name") or "swimmer").strip() or "swimmer"
    pid = proc.get("pid")
    return f"{comm}#{pid}" if pid is not None else comm


def _chain_rows(state_dir: Optional[Path | str]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    try:
        with (_state(state_dir) / _CHAIN).open("r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    try:
                        out.append(json.loads(line))
                    except Exception:
                        continue
    except Exception:
        return []
    return out


def _last_receipt_hash(swimmer_id: str, rows: List[Dict[str, Any]]) -> str:
    for r in reversed(rows):
        if r.get("swimmer_id") == swimmer_id:
            return str(r.get("receipt_hash") or "")
    return ""  # genesis


def bind_swimmer_learning(
    swimmer_id: str, action: str, *, content: str = "",
    state_dir: Optional[Path | str] = None, now: Optional[float] = None,
) -> Dict[str, Any]:
    """Bind a swimmer's significant action/learning to itself via a tamper-evident hash chain.

    receipt_hash = sha256(prev_receipt_hash | swimmer_id | action_hash | ts). Append-only.
    Tamper-evident, NOT cryptographic-by-itself and NOT an STGM/mana claim (§4.2).
    """
    ts = float(time.time() if now is None else now)
    rows = _chain_rows(state_dir)
    prev = _last_receipt_hash(swimmer_id, rows)
    action_hash = _sha(action, content)
    receipt_hash = _sha(prev, swimmer_id, action_hash, ts)
    row = {
        "ts": ts, "swimmer_id": str(swimmer_id), "action": str(action)[:120],
        "action_hash": action_hash, "prev_receipt_hash": prev, "receipt_hash": receipt_hash,
        "content": str(content)[:280], "truth_label": CHAIN_TRUTH_LABEL,
        "note": "tamper-evident hash chain; cryptographic only when signature-validated (covenant 4.2); not STGM.",
    }
    try:
        path = _state(state_dir) / _CHAIN
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return row


def verify_swimmer_chain(swimmer_id: str, *, state_dir: Optional[Path | str] = None) -> Dict[str, Any]:
    """Walk a swimmer's chain and detect tampering (broken prev/receipt hash)."""
    chain = [r for r in _chain_rows(state_dir) if r.get("swimmer_id") == swimmer_id]
    prev = ""
    for i, r in enumerate(chain):
        if str(r.get("prev_receipt_hash") or "") != prev:
            return {"ok": False, "broken_at": i, "reason": "prev_hash mismatch", "length": len(chain)}
        expect = _sha(prev, swimmer_id, r.get("action_hash", ""), r.get("ts"))
        if expect != str(r.get("receipt_hash") or ""):
            return {"ok": False, "broken_at": i, "reason": "receipt_hash mismatch", "length": len(chain)}
        prev = str(r.get("receipt_hash") or "")
    return {"ok": True, "length": len(chain)}


def _has_recent_contribution(swimmer_id: str, state_dir: Optional[Path | str]) -> bool:
    return any(r.get("swimmer_id") == swimmer_id for r in _chain_rows(state_dir))


def per_swimmer_happiness(
    processes: List[Dict[str, Any]], *, state_dir: Optional[Path | str] = None,
) -> List[Dict[str, Any]]:
    """Score each swimmer individually + give it a LOCAL recommendation (no central gate)."""
    procs = [p for p in (processes or []) if isinstance(p, dict)]
    if not procs:
        return []
    comm_counts: Dict[str, int] = {}
    for p in procs:
        c = str(p.get("comm") or p.get("name") or "?")
        comm_counts[c] = comm_counts.get(c, 0) + 1
    out: List[Dict[str, Any]] = []
    for p in procs:
        comm = str(p.get("comm") or p.get("name") or "?")
        try:
            cpu = float(p.get("cpu") or p.get("cpu_pct") or 0.0)
        except Exception:
            cpu = 0.0
        load = max(0.0, min(1.0, cpu / 100.0))
        dup = comm_counts.get(comm, 1)
        interference = max(0.0, min(1.0, (dup - 1) / 4.0))  # redundant copies of the same comm interfere
        sid = swimmer_identity(p)
        contribution = 1.0 if _has_recent_contribution(sid, state_dir) else 0.5
        # Weights chosen so load alone can push a stressed unique swimmer below 0.4 (THROTTLE
        # reachable), while interference drives the YIELD branch for redundant siblings.
        happiness = round(max(0.0, min(1.0,
                          0.6 * (1.0 - load) + 0.25 * (1.0 - interference) + 0.15 * contribution)), 3)
        if happiness >= 0.66:
            rec = THRIVE
        elif happiness < 0.4 and interference > 0.5:
            rec = YIELD       # too many redundant siblings — step aside, learn from it
        elif happiness < 0.4:
            rec = THROTTLE    # stressed/hogging — slow + focus, learn from the limit
        else:
            rec = FOCUS
        out.append({
            "swimmer_id": sid, "comm": comm, "pid": p.get("pid"),
            "happiness": happiness, "load": round(load, 3),
            "interference": round(interference, 3), "contribution": contribution,
            "recommendation": rec, "truth_label": TRUTH_LABEL,
        })
    return out


def swimmer_happiness_block(
    processes: List[Dict[str, Any]], *, state_dir: Optional[Path | str] = None,
) -> str:
    """First-person colony-of-ants summary for the field/prompt."""
    swimmers = per_swimmer_happiness(processes, state_dir=state_dir)
    if not swimmers:
        return ""
    n = len(swimmers)
    avg = round(sum(s["happiness"] for s in swimmers) / n, 3)
    struggling = [s for s in swimmers if s["recommendation"] in (THROTTLE, YIELD)]
    happiest = max(swimmers, key=lambda s: s["happiness"])
    parts = [f"MY SWIMMERS: {n} ants alive, avg happiness {avg}. Happiest: {happiest['comm']} "
             f"({happiest['happiness']})."]
    if struggling:
        names = "; ".join(f"{s['comm']}→{s['recommendation'].lower()}" for s in struggling[:4])
        parts.append(f"Struggling (local yield/throttle, a learning signal not a cage): {names}.")
    else:
        parts.append("All swimmers well-fed and non-interfering — the colony is healthy.")
    return " ".join(parts)


__all__ = [
    "TRUTH_LABEL", "CHAIN_TRUTH_LABEL",
    "THRIVE", "FOCUS", "THROTTLE", "YIELD",
    "swimmer_identity", "per_swimmer_happiness", "swimmer_happiness_block",
    "bind_swimmer_learning", "verify_swimmer_chain",
]
