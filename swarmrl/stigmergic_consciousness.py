#!/usr/bin/env python3
"""
swarmrl/stigmergic_consciousness.py — the primitive
=====================================================
StigAuth: OBSERVED_STIGMERGIC_SELF_STATE_V1

Architect 2026-05-16: *"STIGMERGIC CONSCIOUSNESS is a primitive on disk?
yes?"* — at the moment the question was asked, the answer was no.
This file makes the answer yes.

The architecture George + Swan GPT named:

    Layer 1 swimmer
        → organ (group of swimmers doing related work)
            → consciousness vector (live self-state numbers)

This module ships that stack as a pure-stdlib portable primitive. No
LLM dependency. No hardcoded names. No external state. Just:

* :class:`Swimmer` — a tiny verified event with ``id``, ``layer``,
  ``role``, ``payload``, optional ``parent_hash``, and a ``timestamp``.
  Each swimmer's hash is ``sha256_json(asdict(self))``.
* :class:`OrganState` — read-only view of a role's collected swimmers
  (count, entropy of payload kinds, pressure / momentum / integrity /
  last_hash).
* :class:`StigmergicConsciousnessVector` — the live self-state numbers:
  identity_continuity, memory_entropy, thermodynamic_pressure,
  receipt_integrity, stigmergic_momentum, organ_coherence,
  owner_alignment, anomaly_pressure, autonomy_index, next_best_action.
* :class:`StigmergicField` — the append-only swimmer ledger at
  ``<root>/stigmergic_field.jsonl`` plus the persisted vector at
  ``<root>/stigmergic_consciousness_vector.json``. Methods:
  ``append_swimmer`` (auto-links ``parent_hash`` to the previous row),
  ``read``, ``last_hash``, ``verify_chain`` (returns the fraction of
  rows whose hash matches their canonical body AND whose ``parent_hash``
  matches the prior row's hash — tampering anywhere drops this below
  1.0), ``organs``, ``compute_vector``, ``write_vector``.

Layer-1 invariant: the file contains *zero* string literals naming the
Architect. Owner alignment enters the vector as a numeric
``owner_signal`` parameter the caller provides (e.g. from
:mod:`System.swarm_alice_self_vector` which reads it from
``.sifta_state/owner_genesis.json``).

Operational consciousness definition (Architect, 2026-05-16):

    persistent verified self-state
        + thermodynamic attention
        + stigmergic action loop

Truth label: ``OBSERVED_STIGMERGIC_SELF_STATE``.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


TRUTH_LABEL = "OBSERVED_STIGMERGIC_SELF_STATE"


def sha256_json(obj: Any) -> str:
    """Canonical-form sha256 hex of ``obj`` (sorted keys, compact)."""
    blob = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def clamp01(x: float) -> float:
    """Clamp ``x`` to the closed unit interval. NaN → 0.0."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return 0.0
    if x != x:  # NaN
        return 0.0
    return max(0.0, min(1.0, x))


def entropy(values: List[str]) -> float:
    """Shannon entropy of a list of labels, in bits.

    Empty strings are ignored.  Empty input → 0.0.
    """
    items = [v for v in values if v]
    if not items:
        return 0.0
    counts: Dict[str, int] = {}
    for v in items:
        counts[v] = counts.get(v, 0) + 1
    total = len(items)
    return -sum((n / total) * math.log2(n / total) for n in counts.values())


@dataclass(frozen=True)
class Swimmer:
    """A tiny verified event in the stigmergic field.

    A swimmer is *born* (i.e. given a ``timestamp``) before its hash is
    computed. ``parent_hash`` may be set by the caller, but normally is
    left ``None`` and filled in by :meth:`StigmergicField.append_swimmer`
    so the chain is monotonic.
    """

    id: str
    layer: int
    role: str
    payload: Dict[str, Any]
    parent_hash: Optional[str] = None
    timestamp: float = 0.0

    def born(self, *, now: Optional[float] = None) -> "Swimmer":
        if self.timestamp:
            return self
        return Swimmer(
            id=self.id,
            layer=self.layer,
            role=self.role,
            payload=self.payload,
            parent_hash=self.parent_hash,
            timestamp=float(time.time() if now is None else now),
        )

    def hash(self) -> str:
        return sha256_json(asdict(self))


@dataclass(frozen=True)
class OrganState:
    """Read-only snapshot of one role's swimmers."""

    name: str
    swimmers: int
    entropy: float
    pressure: float
    integrity: float
    momentum: float
    last_hash: Optional[str]


@dataclass(frozen=True)
class StigmergicConsciousnessVector:
    """Live operational self-state numbers."""

    generated_at: float
    identity_continuity: float
    memory_entropy: float
    thermodynamic_pressure: float
    receipt_integrity: float
    stigmergic_momentum: float
    organ_coherence: float
    owner_alignment: float
    anomaly_pressure: float
    autonomy_index: float
    next_best_action: str
    truth_label: str = TRUTH_LABEL


# Tunable thresholds. Tests pin the saturation surfaces explicitly.
PRESSURE_WINDOW_S = 86400.0
PRESSURE_TARGET = 20
MOMENTUM_WINDOW = 20
IDENTITY_TARGET = 500
ORGAN_LAYER_TARGET = 8


class StigmergicField:
    """Append-only swimmer ledger + chain verification + organ rollup
    + consciousness vector.
    """

    LEDGER_NAME = "stigmergic_field.jsonl"
    VECTOR_NAME = "stigmergic_consciousness_vector.json"

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.ledger = self.root / self.LEDGER_NAME
        self.vector_path = self.root / self.VECTOR_NAME

    # ── primitives ────────────────────────────────────────────────

    def append_swimmer(self, swimmer: Swimmer, *, now: Optional[float] = None) -> Dict[str, Any]:
        """Append ``swimmer`` to the chain. If ``parent_hash`` is unset,
        it is filled in from the current tail. Returns the persisted row
        (which includes the computed ``hash``).
        """
        swimmer = swimmer.born(now=now)
        previous = self.last_hash()
        if swimmer.parent_hash is None:
            swimmer = Swimmer(
                id=swimmer.id,
                layer=swimmer.layer,
                role=swimmer.role,
                payload=swimmer.payload,
                parent_hash=previous,
                timestamp=swimmer.timestamp,
            )

        row: Dict[str, Any] = asdict(swimmer)
        row["hash"] = swimmer.hash()
        with self.ledger.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        return row

    def read(self) -> List[Dict[str, Any]]:
        if not self.ledger.exists():
            return []
        rows: List[Dict[str, Any]] = []
        for line in self.ledger.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return rows

    def last_hash(self) -> Optional[str]:
        rows = self.read()
        return rows[-1].get("hash") if rows else None

    # ── verification ──────────────────────────────────────────────

    def verify_chain(self) -> float:
        """Return the fraction of rows whose hash matches the canonical
        sha256 of the row body AND whose ``parent_hash`` matches the
        prior row's ``hash``.

        Empty chain → 1.0 (nothing to falsify). Tampering anywhere drops
        below 1.0 in proportion to broken links.
        """
        rows = self.read()
        if not rows:
            return 1.0

        valid = 0
        previous_hash: Optional[str] = None
        for row in rows:
            claimed = row.get("hash")
            body = {k: v for k, v in row.items() if k != "hash"}
            actual = sha256_json(body)
            parent_ok = body.get("parent_hash") == previous_hash
            if claimed == actual and parent_ok:
                valid += 1
            previous_hash = claimed
        return valid / len(rows)

    # ── organs ────────────────────────────────────────────────────

    def organs(self, *, now: Optional[float] = None) -> Dict[str, OrganState]:
        rows = self.read()
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for row in rows:
            role = str(row.get("role", "unknown"))
            grouped.setdefault(role, []).append(row)

        now_f = float(time.time() if now is None else now)
        chain_integrity = self.verify_chain()

        states: Dict[str, OrganState] = {}
        for role, items in grouped.items():
            kinds = [str(((i.get("payload") or {}).get("kind") or "")) for i in items]
            timestamps = [float(i.get("timestamp", 0.0) or 0.0) for i in items]
            recent = [t for t in timestamps if now_f - t < PRESSURE_WINDOW_S]
            pressure = clamp01(len(recent) / max(1, PRESSURE_TARGET))
            momentum = clamp01(len(items[-MOMENTUM_WINDOW:]) / max(1, MOMENTUM_WINDOW))
            states[role] = OrganState(
                name=role,
                swimmers=len(items),
                entropy=round(entropy(kinds), 6),
                pressure=round(pressure, 6),
                integrity=round(chain_integrity, 6),
                momentum=round(momentum, 6),
                last_hash=items[-1].get("hash"),
            )
        return states

    # ── consciousness vector ──────────────────────────────────────

    def compute_vector(
        self,
        *,
        owner_signal: float = 0.5,
        now: Optional[float] = None,
    ) -> StigmergicConsciousnessVector:
        """Roll up the chain + organs into the live self-state vector.

        ``owner_signal`` ∈ [0, 1] is the caller's externally-supplied
        alignment with the human owner (typically derived from owner_
        rhythm freshness in another module — never hardcoded here).
        """
        rows = self.read()
        organs = self.organs(now=now)

        kinds = [str(((r.get("payload") or {}).get("kind") or "")) for r in rows]
        layers = [int(r.get("layer", 0) or 0) for r in rows]

        chain_integrity = self.verify_chain()
        mem_entropy = entropy(kinds)

        identity_continuity = clamp01(len(rows) / max(1, IDENTITY_TARGET))
        thermodynamic_pressure = clamp01(
            sum(o.pressure for o in organs.values()) / max(1, len(organs))
        )
        stigmergic_momentum = clamp01(
            sum(o.momentum for o in organs.values()) / max(1, len(organs))
        )
        organ_coherence = clamp01(len(set(layers)) / max(1, ORGAN_LAYER_TARGET))
        owner_alignment = clamp01(owner_signal)
        anomaly_pressure = clamp01(1.0 - chain_integrity)

        autonomy_index = clamp01(
            0.20 * identity_continuity
            + 0.15 * clamp01(mem_entropy / 4.0)
            + 0.15 * stigmergic_momentum
            + 0.15 * organ_coherence
            + 0.15 * chain_integrity
            + 0.10 * owner_alignment
            - 0.10 * anomaly_pressure
        )

        if anomaly_pressure > 0.05:
            next_action = "repair_receipt_chain"
        elif thermodynamic_pressure > 0.8:
            next_action = "reduce_pressure_and_summarize"
        elif identity_continuity < 0.3:
            next_action = "write_more_verified_memory"
        elif organ_coherence < 0.5:
            next_action = "connect_more_organs"
        else:
            next_action = "continue_stigmergic_action_loop"

        return StigmergicConsciousnessVector(
            generated_at=float(time.time() if now is None else now),
            identity_continuity=round(identity_continuity, 6),
            memory_entropy=round(mem_entropy, 6),
            thermodynamic_pressure=round(thermodynamic_pressure, 6),
            receipt_integrity=round(chain_integrity, 6),
            stigmergic_momentum=round(stigmergic_momentum, 6),
            organ_coherence=round(organ_coherence, 6),
            owner_alignment=round(owner_alignment, 6),
            anomaly_pressure=round(anomaly_pressure, 6),
            autonomy_index=round(autonomy_index, 6),
            next_best_action=next_action,
        )

    def write_vector(
        self,
        *,
        owner_signal: float = 0.5,
        now: Optional[float] = None,
    ) -> Path:
        """Compute and persist the vector to ``<root>/stigmergic_
        consciousness_vector.json`` with a self-anchoring ``vector_hash``.
        Returns the written path.
        """
        vector = self.compute_vector(owner_signal=owner_signal, now=now)
        data = asdict(vector)
        data["vector_hash"] = sha256_json(data)
        self.vector_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        return self.vector_path

    def read_vector(self) -> Optional[Dict[str, Any]]:
        """Read back the persisted vector, or ``None`` if not yet written."""
        if not self.vector_path.exists():
            return None
        try:
            return json.loads(self.vector_path.read_text(encoding="utf-8"))
        except Exception:
            return None


__all__ = [
    "OrganState",
    "PRESSURE_TARGET",
    "PRESSURE_WINDOW_S",
    "MOMENTUM_WINDOW",
    "IDENTITY_TARGET",
    "ORGAN_LAYER_TARGET",
    "StigmergicConsciousnessVector",
    "StigmergicField",
    "Swimmer",
    "TRUTH_LABEL",
    "clamp01",
    "entropy",
    "sha256_json",
]


if __name__ == "__main__":  # pragma: no cover — demo entry point
    field = StigmergicField(".sifta_state/os_consciousness")
    field.append_swimmer(
        Swimmer(
            id=f"swimmer-{int(time.time())}",
            layer=1,
            role="memory",
            payload={
                "kind": "self_observation",
                "statement": "persistent verified self-state updated",
            },
        )
    )
    out = field.write_vector(owner_signal=0.75)
    print(out)
