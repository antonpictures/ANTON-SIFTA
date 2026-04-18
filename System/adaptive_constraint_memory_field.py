#!/usr/bin/env python3
"""
System/adaptive_constraint_memory_field.py — Vector 12: ACMF
══════════════════════════════════════════════════════════════════════
Memory evolution under constraint pressure.

Memory doesn't just get selected (CWMS) or stored with resonance
(Trophallaxis). It EVOLVES its own importance based on:

    1. Usage success  → reinforce(trace_id, +reward)
    2. Decision failure → reinforce(trace_id, -reward)
    3. Pressure-dependent forgetting → decay_under_pressure(λ)

The feedback loop:

    constraints (λ) → memory selection → action (gatekeeper)
         ↓                                       ↓
    memory evolution  ←←←←←←  reward  ←←←←←←  outcome

Fitness state lives in .sifta_state/memory_fitness.json (composable
overlay). The memory_ledger.jsonl remains append-only and unmutated.

Uses rewrite_text_locked from jsonl_file_lock.py for concurrent
IDE safety (see: Cursor crash PID 23070, 09:36:07).
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

_RESERVED = frozenset(
    {"schema_version", "overlay", "updated_ts", "traces", "description"}
)

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.jsonl_file_lock import read_text_locked, read_write_json_locked, rewrite_text_locked

_STATE_DIR = _REPO / ".sifta_state"
_STATE_DIR.mkdir(parents=True, exist_ok=True)
FITNESS_FILE = _STATE_DIR / "memory_fitness.json"


def _normalize_top_level(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """
    Accept Cursor nested schema or Antigravity flat {trace_id: entry}.
    Returns the inner traces map only (trace_id -> entry dict).
    """
    if not isinstance(data, dict):
        return {}
    if "traces" in data and isinstance(data["traces"], dict):
        inner = dict(data["traces"])
    else:
        inner = {
            k: v
            for k, v in data.items()
            if k not in _RESERVED and isinstance(v, dict)
        }
    out: dict[str, dict[str, Any]] = {}
    for tid, entry in inner.items():
        if not isinstance(entry, dict):
            continue
        if tid in _RESERVED:
            continue
        out[str(tid)] = entry
    return out


def _wrap_nested(traces: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Write shape compatible with memory_fitness_overlay.py."""
    return {
        "schema_version": 1,
        "overlay": "memory_fitness_acmf_v1",
        "traces": traces,
        "updated_ts": time.time(),
    }


class MemoryFitnessEntry:
    """Mutable fitness state for a single PheromoneTrace, keyed by trace_id."""

    def __init__(
        self,
        fitness: float = 1.0,
        usage_count: int = 0,
        total_reward: float = 0.0,
        last_used: float = 0.0,
    ):
        self.fitness = fitness
        self.usage_count = usage_count
        self.total_reward = total_reward
        self.last_used = last_used

    def to_dict(self) -> dict:
        ts = float(self.last_used)
        return {
            "fitness": round(self.fitness, 6),
            "usage_count": self.usage_count,
            "total_reward": round(self.total_reward, 6),
            "last_used": ts,
            "last_used_ts": ts,
        }

    @staticmethod
    def from_dict(d: dict) -> "MemoryFitnessEntry":
        return MemoryFitnessEntry(
            fitness=float(d.get("fitness", 1.0)),
            usage_count=int(d.get("usage_count", 0)),
            total_reward=float(d.get("total_reward", 0.0)),
            last_used=float(d.get("last_used", d.get("last_used_ts", 0.0))),
        )


class AdaptiveConstraintMemoryField:
    """
    The evolutionary overlay on top of the Stigmergic Memory Bus.

    Does NOT read or write memory_ledger.jsonl.
    Operates exclusively on .sifta_state/memory_fitness.json.
    """

    def __init__(self):
        self._cache: Dict[str, MemoryFitnessEntry] = {}
        self._load()

    def _load(self):
        """Load fitness state from disk (locked read). Tolerates mixed schemas."""
        raw = read_text_locked(FITNESS_FILE, encoding="utf-8", errors="replace")
        if not raw.strip():
            self._cache = {}
            return
        try:
            data = json.loads(raw)
            if not isinstance(data, dict):
                self._cache = {}
                return
            flat = _normalize_top_level(data)
            self._cache = {}
            for tid, entry in flat.items():
                if isinstance(entry, dict):
                    self._cache[tid] = MemoryFitnessEntry.from_dict(entry)
        except (json.JSONDecodeError, TypeError):
            self._cache = {}

    def _persist(self):
        """Write fitness state to disk (locked rewrite, nested schema)."""
        traces = {tid: entry.to_dict() for tid, entry in self._cache.items()}
        payload = _wrap_nested(traces)
        content = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
        rewrite_text_locked(FITNESS_FILE, content, encoding="utf-8")

    def get_fitness(self, trace_id: str) -> float:
        """Returns the fitness multiplier for a trace. Default 1.0 (neutral)."""
        entry = self._cache.get(trace_id)
        if entry is None:
            return 1.0
        return entry.fitness

    def fitness_boost(self, trace_id: str) -> float:
        """
        Multiplier for CWMS rerank (same bounds as memory_fitness_overlay):
        neutral at fitness=1.0 → 1.0; sqrt curve; clamp [0.25, 2.0].
        """
        f = self.get_fitness(trace_id)
        return max(0.25, min(2.0, math.sqrt(max(0.01, f))))

    def reinforce(self, trace_id: str, reward: float):
        """
        Called after a decision outcome.
        Positive reward → strengthen memory.
        Negative reward → weaken memory.

        Atomic merge into nested overlay (compatible with memory_fitness_overlay).
        """
        tid = str(trace_id)
        now = time.time()

        def _up(data: Dict[str, Any]) -> Dict[str, Any]:
            if not isinstance(data, dict):
                data = {}
            flat = _normalize_top_level(data)
            row = dict(flat.get(tid, {}))
            entry = MemoryFitnessEntry.from_dict(row)
            entry.usage_count += 1
            entry.last_used = now
            entry.total_reward += reward
            entry.fitness += 0.1 * reward
            entry.fitness = max(0.1, entry.fitness)
            flat[tid] = entry.to_dict()
            return _wrap_nested(flat)

        read_write_json_locked(FITNESS_FILE, _up, encoding="utf-8")
        self._load()

    def decay_under_pressure(self, lambda_norm: float):
        """
        Pressure-dependent forgetting across all tracked memories.

        Under HIGH λ (system stressed):
          - Low-fitness memories decay faster (they failed under stress)
          - High-fitness memories are preserved (they proved useful)

        Under LOW λ (system relaxed):
          - All memories decay uniformly and slowly
          - The swarm can afford to keep diverse memories alive
        """
        if not self._cache:
            return

        for tid, entry in self._cache.items():
            # Base time decay: all memories slowly lose fitness
            entry.fitness *= 0.998

            # Pressure-dependent culling
            if lambda_norm > 0.5 and entry.fitness < 0.5:
                # Under stress, weak memories die faster
                entry.fitness *= 0.95
            elif lambda_norm > 0.7 and entry.fitness < 1.0:
                # Under severe stress, even mediocre memories feel pressure
                entry.fitness *= 0.97

            # Floor
            entry.fitness = max(0.1, entry.fitness)

        self._persist()

    def prune(self, min_fitness: float = 0.12):
        """Remove entries that have decayed below the survival threshold."""
        before = len(self._cache)
        self._cache = {
            tid: e for tid, e in self._cache.items()
            if e.fitness >= min_fitness
        }
        pruned = before - len(self._cache)
        if pruned > 0:
            self._persist()
        return pruned

    def report(self) -> dict:
        """Summary statistics for the fitness overlay."""
        if not self._cache:
            return {"total_tracked": 0, "mean_fitness": 0.0, "strongest": None}

        fitnesses = [e.fitness for e in self._cache.values()]
        strongest_tid = max(self._cache, key=lambda t: self._cache[t].fitness)
        return {
            "total_tracked": len(self._cache),
            "mean_fitness": round(sum(fitnesses) / len(fitnesses), 4),
            "max_fitness": round(max(fitnesses), 4),
            "min_fitness": round(min(fitnesses), 4),
            "strongest_trace": strongest_tid,
            "total_reinforcements": sum(e.usage_count for e in self._cache.values()),
        }


# ─── CLI / Self-Test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("═" * 65)
    print("  VECTOR 12: ADAPTIVE CONSTRAINT MEMORY FIELD (ACMF)")
    print("  'Memory evolves under pressure. The fit survive.'")
    print("═" * 65 + "\n")

    acmf = AdaptiveConstraintMemoryField()

    # Simulate: 3 memories with different outcomes
    print("  [1] Reinforcing trace_A with +2.0 reward (good decision)")
    acmf.reinforce("trace_A", reward=+2.0)

    print("  [2] Reinforcing trace_B with -1.5 reward (bad decision)")
    acmf.reinforce("trace_B", reward=-1.5)

    print("  [3] Reinforcing trace_C with +0.5 reward (mild success)")
    acmf.reinforce("trace_C", reward=+0.5)

    print(f"\n  Fitness boosts:")
    print(f"    trace_A: {acmf.fitness_boost('trace_A'):.4f} (strong)")
    print(f"    trace_B: {acmf.fitness_boost('trace_B'):.4f} (weak)")
    print(f"    trace_C: {acmf.fitness_boost('trace_C'):.4f} (moderate)")

    # Simulate pressure decay
    print(f"\n  [4] Applying pressure-dependent decay (λ_norm=0.8, severe stress)")
    acmf.decay_under_pressure(lambda_norm=0.8)

    print(f"\n  Fitness after pressure:")
    print(f"    trace_A: {acmf.get_fitness('trace_A'):.4f}")
    print(f"    trace_B: {acmf.get_fitness('trace_B'):.4f} (under stress, weak → dying)")
    print(f"    trace_C: {acmf.get_fitness('trace_C'):.4f}")

    print(f"\n  Report: {json.dumps(acmf.report(), indent=4)}")
    print(f"\n  ✅ ACMF ONLINE — Memory evolves. The fit survive. 🐜⚡")
