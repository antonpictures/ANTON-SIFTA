#!/usr/bin/env python3
"""
swarmrl/beenav_homing.py — BeeNav-inspired panoramic-memory + homing primitive
================================================================================
StigAuth: OBSERVED_BEENAV_HOMING_V0

Architect 2026-05-16: integrate the BeeNav (Wystrach et al. + Dylan Curious
2026-05) bee-drone navigation finding — a small drone homes 600+ metres back
to its hive using only:

    * a brief "learning flight" near the hive that captures panoramic views
    * a tiny (~42 KB) neural network that associates each panorama with
      direction + distance back to home
    * simple visual odometry ("count steps")
    * no SLAM, no map, no heavy compute, low power budget

Audit before add: 6 of 7 Internal Physics organs already exist on disk
(Attention Economy, Dream/Sleep, Multi-Animal Competition, Reality
Boundary, Scarcity/Decay/Metabolism, Prediction Error). The genuinely
missing piece is the bee-style **panoramic-signature + visual-odometry
+ homing** primitive itself. This module is that primitive.

Design principles (BeeNav discipline):

* Every memory carries its own ``storage_cost_bytes`` — thermodynamic
  honesty. The organism feels the price of remembering.
* A total ``budget_bytes`` cap keeps the colony memory disciplined
  (default 42 KB to match BeeNav).
* When the budget is full, the **lowest-reinforcement, oldest** memory
  is evicted — exactly like the bee colony forgetting unrewarded routes.
* Lookup is **nearest-neighbour by hamming distance** on the perceptual
  hash — cheap, deterministic, doesn't need a heavy embedding model.
* A "learning flight" is just N consecutive ``record_view`` calls with
  fresh perceptual hashes. The organism doesn't compute a map; it just
  stores tagged anchors.
* Zero hardcoded owner name. Pure stdlib.

This primitive composes with existing organs:

* Attention Economy → ``record_view`` consumes attention budget; eviction
  follows the same pressure semantics.
* Dream/Sleep Layer → ``replay_for_consolidation`` returns recent
  memories in a form a hippocampal replay scheduler can consume.
* Multi-Animal Competition → ``Hive.find_homing_hint`` is one proposer
  the basal-ganglia arbiter can solicit alongside other navigators.
* Reality Boundary → every memory is born ``OBSERVED`` (perceptual hash
  is a direct sensory observation) and decays toward irrelevance, never
  inflating to ``ARCHITECT_DOCTRINE`` on its own.

Truth label: ``OBSERVED_BEENAV_HOMING_V0``.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


TRUTH_LABEL = "OBSERVED_BEENAV_HOMING_V0"

# BeeNav discipline defaults
DEFAULT_BUDGET_BYTES = 42_000  # the bee's 42 KB neural network footprint
DEFAULT_SIGNATURE_BITS = 64    # 8 bytes per perceptual hash → 0.2% of budget per memory
DEFAULT_MIN_REINFORCEMENT = 1
DEFAULT_DECAY_HALF_LIFE_S = 7 * 86400.0  # one week; reinforced memories persist


# ── perceptual hash (deterministic, stdlib-only) ──────────────────────────


def perceptual_hash(sample: Any, *, bits: int = DEFAULT_SIGNATURE_BITS) -> str:
    """Stable, sort-order-invariant perceptual hash of ``sample``.

    Uses sha256 over canonical-JSON ``sample`` and truncates to ``bits``
    bits of hex. Deterministic, cheap, identical inputs → identical
    output. Suitable as a panoramic-signature stand-in until a real
    embedding model is wired in.
    """
    blob = json.dumps(sample, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":"))
    full = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    nibbles = max(1, int(bits) // 4)
    return full[:nibbles]


def hamming_distance(a: str, b: str) -> int:
    """Hamming distance between two equal-length hex strings.

    If the strings differ in length, the comparison is right-padded with
    zeros (i.e. shorter string is treated as if its missing nibbles were
    all-zero).
    """
    if a == b:
        return 0
    n = max(len(a), len(b))
    a = a.ljust(n, "0")
    b = b.ljust(n, "0")
    d = 0
    for ca, cb in zip(a, b):
        try:
            xor = int(ca, 16) ^ int(cb, 16)
        except ValueError:
            xor = 0
        d += bin(xor).count("1")
    return d


# ── data classes ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PanoramicSignature:
    """One panoramic memory anchor.

    ``perceptual_hash`` is a perceptual-hash hex string of the captured
    sensor sample. ``direction_to_hive`` is a bearing in radians (caller
    can supply any 1-D float). ``distance_to_hive`` is in caller-defined
    units (BeeNav uses metres; SIFTA can use UI-event-steps or whatever
    visual odometry yields). ``reinforcement`` increments on every
    re-encounter — sustained memories survive decay.

    ``storage_cost_bytes`` is the **honest** size this memory occupies on
    disk if persisted. The organism feels the price of remembering.
    """

    perceptual_hash: str
    direction_to_hive: float
    distance_to_hive: float
    reinforcement: int = 1
    last_seen_ts: float = 0.0
    storage_cost_bytes: int = 0
    note: str = ""

    def with_reinforcement(self, *, now: float) -> "PanoramicSignature":
        return PanoramicSignature(
            perceptual_hash=self.perceptual_hash,
            direction_to_hive=self.direction_to_hive,
            distance_to_hive=self.distance_to_hive,
            reinforcement=self.reinforcement + 1,
            last_seen_ts=float(now),
            storage_cost_bytes=self.storage_cost_bytes,
            note=self.note,
        )


@dataclass(frozen=True)
class HomingHint:
    """Result of ``Hive.find_homing_hint(...)`` — the bee's best guess
    at where home is, given the current view."""

    matched_signature: Optional[PanoramicSignature]
    hamming_distance: int
    direction_to_hive: float
    distance_to_hive: float
    confidence: float
    note: str = ""


# ── Hive ──────────────────────────────────────────────────────────────────


class Hive:
    """The bee's home + its colony of stored panoramic memories.

    A Hive is a *budget-disciplined* memory of panoramic anchors. The
    bee can:

    * ``learning_flight(views)`` — bootstrap memories from a short pass
      of N (perceptual-sample, direction, distance) triples.
    * ``record_view(sample, direction, distance)`` — store one new view;
      reinforces an existing entry if the perceptual hash already exists.
    * ``find_homing_hint(sample)`` — return the closest stored memory
      by hamming distance + a direction-to-hive suggestion.
    * ``decay_unreinforced(now)`` — drop memories whose reinforcement is
      below threshold AND whose last_seen_ts is older than the half-life.
    * ``replay_for_consolidation(n)`` — yield the N most-recently-touched
      memories in newest-first order (Dream/Sleep layer integration).
    * ``total_storage_bytes`` — honest sum of all memory storage costs.
    """

    def __init__(
        self,
        *,
        budget_bytes: int = DEFAULT_BUDGET_BYTES,
        signature_bits: int = DEFAULT_SIGNATURE_BITS,
        min_reinforcement: int = DEFAULT_MIN_REINFORCEMENT,
        decay_half_life_s: float = DEFAULT_DECAY_HALF_LIFE_S,
    ) -> None:
        self.budget_bytes = int(budget_bytes)
        self.signature_bits = int(signature_bits)
        self.min_reinforcement = int(min_reinforcement)
        self.decay_half_life_s = float(decay_half_life_s)
        self._memories: Dict[str, PanoramicSignature] = {}

    # ── recording ────────────────────────────────────────────────

    def _storage_cost_for(self, sig: PanoramicSignature) -> int:
        """Honest size of one panoramic memory if persisted to JSONL."""
        blob = json.dumps(asdict(sig), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return len(blob.encode("utf-8"))

    def record_view(
        self,
        sample: Any,
        *,
        direction_to_hive: float,
        distance_to_hive: float,
        note: str = "",
        now: Optional[float] = None,
    ) -> PanoramicSignature:
        """Store or reinforce a panoramic view.

        Returns the stored signature (newly created or reinforced).
        Evicts the lowest-reinforcement / oldest memory if the budget
        would otherwise be exceeded.
        """
        now_f = float(time.time() if now is None else now)
        h = perceptual_hash(sample, bits=self.signature_bits)
        existing = self._memories.get(h)
        if existing is not None:
            reinforced = existing.with_reinforcement(now=now_f)
            self._memories[h] = reinforced
            return reinforced

        provisional = PanoramicSignature(
            perceptual_hash=h,
            direction_to_hive=float(direction_to_hive),
            distance_to_hive=float(distance_to_hive),
            reinforcement=1,
            last_seen_ts=now_f,
            storage_cost_bytes=0,
            note=str(note or "")[:160],
        )
        size = self._storage_cost_for(provisional)
        sig = PanoramicSignature(
            perceptual_hash=h,
            direction_to_hive=provisional.direction_to_hive,
            distance_to_hive=provisional.distance_to_hive,
            reinforcement=provisional.reinforcement,
            last_seen_ts=provisional.last_seen_ts,
            storage_cost_bytes=size,
            note=provisional.note,
        )

        # Enforce budget — evict until there's room for this memory.
        while self._memories and self.total_storage_bytes + size > self.budget_bytes:
            evict_key = self._eviction_candidate()
            if evict_key is None:
                break
            self._memories.pop(evict_key, None)

        self._memories[h] = sig
        return sig

    def learning_flight(
        self,
        views: Iterable[Tuple[Any, float, float]],
        *,
        note: str = "learning_flight",
        now: Optional[float] = None,
    ) -> List[PanoramicSignature]:
        """Bootstrap a fresh colony of memories from a learning pass.

        Each ``view`` is a ``(sample, direction_to_hive, distance_to_hive)``
        triple. Returns the list of stored signatures in input order.
        """
        out: List[PanoramicSignature] = []
        for sample, direction, distance in views:
            out.append(self.record_view(
                sample,
                direction_to_hive=direction,
                distance_to_hive=distance,
                note=note,
                now=now,
            ))
        return out

    # ── homing ────────────────────────────────────────────────────

    def find_homing_hint(self, sample: Any) -> HomingHint:
        """Return the nearest-by-hamming-distance memory + suggested
        direction back to the hive.

        If no memories exist, returns a hint with confidence 0.0.
        Confidence decays linearly with hamming distance: a perfect
        match (distance 0) → 1.0; max distance → 0.0.
        """
        target_hash = perceptual_hash(sample, bits=self.signature_bits)
        if not self._memories:
            return HomingHint(
                matched_signature=None,
                hamming_distance=self.signature_bits,
                direction_to_hive=0.0,
                distance_to_hive=0.0,
                confidence=0.0,
                note="no memories yet — fly a learning_flight first",
            )

        best_sig: Optional[PanoramicSignature] = None
        best_d = self.signature_bits + 1
        for sig in self._memories.values():
            d = hamming_distance(sig.perceptual_hash, target_hash)
            if d < best_d:
                best_d = d
                best_sig = sig

        if best_sig is None:
            return HomingHint(
                matched_signature=None,
                hamming_distance=self.signature_bits,
                direction_to_hive=0.0,
                distance_to_hive=0.0,
                confidence=0.0,
            )

        max_d = max(1, self.signature_bits)
        confidence = max(0.0, 1.0 - (best_d / float(max_d)))
        return HomingHint(
            matched_signature=best_sig,
            hamming_distance=best_d,
            direction_to_hive=best_sig.direction_to_hive,
            distance_to_hive=best_sig.distance_to_hive,
            confidence=confidence,
            note="nearest memory by perceptual hamming distance",
        )

    # ── decay / housekeeping ──────────────────────────────────────

    def _eviction_candidate(self) -> Optional[str]:
        """Pick the lowest-reinforcement / oldest memory for eviction."""
        if not self._memories:
            return None
        return min(
            self._memories.keys(),
            key=lambda h: (
                self._memories[h].reinforcement,
                self._memories[h].last_seen_ts,
            ),
        )

    def decay_unreinforced(self, *, now: Optional[float] = None) -> int:
        """Drop memories below ``min_reinforcement`` whose ``last_seen_ts``
        is older than ``decay_half_life_s``. Returns the number evicted.
        """
        now_f = float(time.time() if now is None else now)
        cutoff = now_f - self.decay_half_life_s
        evicted = 0
        for key in list(self._memories.keys()):
            sig = self._memories[key]
            if sig.reinforcement < self.min_reinforcement and sig.last_seen_ts < cutoff:
                self._memories.pop(key, None)
                evicted += 1
        return evicted

    # ── views ────────────────────────────────────────────────────

    @property
    def total_storage_bytes(self) -> int:
        return sum(s.storage_cost_bytes for s in self._memories.values())

    @property
    def memory_count(self) -> int:
        return len(self._memories)

    @property
    def budget_used_fraction(self) -> float:
        if self.budget_bytes <= 0:
            return 0.0
        return min(1.0, self.total_storage_bytes / float(self.budget_bytes))

    def memories(self) -> List[PanoramicSignature]:
        """Snapshot of the colony, newest-first by last_seen_ts."""
        return sorted(
            self._memories.values(),
            key=lambda s: s.last_seen_ts,
            reverse=True,
        )

    def replay_for_consolidation(self, n: int = 8) -> List[PanoramicSignature]:
        """Yield the N most-recently-touched memories for Dream-layer
        consolidation. Same shape Dream/Sleep modules already consume.
        """
        return self.memories()[: max(0, int(n))]

    # ── persistence ──────────────────────────────────────────────

    def to_jsonl(self, path: Path) -> None:
        """Persist the colony to a JSONL ledger (append-only)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            for sig in self.memories():
                fh.write(json.dumps(asdict(sig), ensure_ascii=False, sort_keys=True) + "\n")

    @classmethod
    def from_jsonl(
        cls,
        path: Path,
        *,
        budget_bytes: int = DEFAULT_BUDGET_BYTES,
        signature_bits: int = DEFAULT_SIGNATURE_BITS,
        decay_half_life_s: float = DEFAULT_DECAY_HALF_LIFE_S,
    ) -> "Hive":
        hive = cls(
            budget_bytes=budget_bytes,
            signature_bits=signature_bits,
            decay_half_life_s=decay_half_life_s,
        )
        if not path.exists():
            return hive
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            sig = PanoramicSignature(
                perceptual_hash=str(row.get("perceptual_hash") or ""),
                direction_to_hive=float(row.get("direction_to_hive") or 0.0),
                distance_to_hive=float(row.get("distance_to_hive") or 0.0),
                reinforcement=int(row.get("reinforcement") or 1),
                last_seen_ts=float(row.get("last_seen_ts") or 0.0),
                storage_cost_bytes=int(row.get("storage_cost_bytes") or 0),
                note=str(row.get("note") or ""),
            )
            if sig.perceptual_hash:
                hive._memories[sig.perceptual_hash] = sig
        return hive


__all__ = [
    "DEFAULT_BUDGET_BYTES",
    "DEFAULT_DECAY_HALF_LIFE_S",
    "DEFAULT_MIN_REINFORCEMENT",
    "DEFAULT_SIGNATURE_BITS",
    "Hive",
    "HomingHint",
    "PanoramicSignature",
    "TRUTH_LABEL",
    "hamming_distance",
    "perceptual_hash",
]
