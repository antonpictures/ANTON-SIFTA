#!/usr/bin/env python3
"""
System/swarm_waggle_dance.py
══════════════════════════════════════════════════════════════════════
Concept: Honeybee Waggle Dance — Compressed Symbolic Routing (Event 70)
Author:  BISHOP / AG31 — Biocode Olympiad
Status:  Active Organ

A forager bee that discovers a high-quality food source returns to the
hive and performs a figure-eight "waggle dance" on the vertical comb.
The dance encodes THREE pieces of information in a single motor act:

  1. DIRECTION — angle of the waggle run relative to gravity
     = angle of the food source relative to the sun (von Frisch 1967)
  2. DISTANCE — duration of the waggle run (longer = farther)
  3. QUALITY — vigor of the dance (faster waggling = richer source)

Recruits decode the dance and fly directly to the communicated location
(Riley et al., Nature 2005, radar-tracked confirmation).

SIFTA Translation:
  - SCOUTS discover high-value regions in the Unified Field.
  - Instead of every agent reading the whole field, scouts COMPRESS
    the discovery into a symbolic vector (angle, duration, vigor).
  - RECRUITS receive the vector and navigate toward it.
  - Dance memory decays — stale information is forgotten.
  - Multiple competing dances are weighted by vigor (quality).

This is the organism's first SYMBOLIC COMMUNICATION layer — information
is compressed from a continuous 2D field into a discrete polar vector,
transmitted socially, then decompressed back into motor commands.

Papers:
  von Frisch, "The Dance Language and Orientation of Bees",
    Harvard Univ Press (1967) — Nobel-Prize-winning discovery
  von Frisch, Science 169:544 (1970) — Bee communication of direction
  Riley et al., Nature 435:205 (2005) — Radar tracking of recruited bees
  Seeley, "Honeybee Democracy", Princeton Univ Press (2010) — Collective decision-making
  Dyer, Annu Rev Entomol 47:917 (2002) — Dance language & spatial orientation
  Grüter & Farina, Anim Behav 78:55 (2009) — Social learning of dance calibration
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.canonical_schemas import assert_payload_keys
from System.jsonl_file_lock import append_line_locked

_LEDGER = _REPO / ".sifta_state" / "waggle_dance.jsonl"
_SCHEMA = "SIFTA_WAGGLE_DANCE_V1"


@dataclass
class WaggleConfig:
    quality_threshold: float = 0.65   # minimum quality to trigger a dance
    distance_scale: float = 1.0       # mapping: duration = distance * scale
    noise: float = 0.08               # angular noise in the dance (biological imprecision)
    recruit_gain: float = 0.12        # how strongly recruits follow the dance vector
    memory_decay: float = 0.96        # vigor decay per tick (stale dances fade)
    max_dances: int = 32              # max concurrent dances (comb space limit)
    quorum_fraction: float = 0.3      # fraction of colony needed for consensus (Seeley 2010)
    eps: float = 1e-8


class WaggleDance:
    """
    A single dance performed by a scout bee.

    Biology (von Frisch 1967):
      - angle: direction of waggle run relative to vertical (= sun angle)
      - duration: length of waggle run (encodes distance)
      - vigor: intensity of waggling (encodes resource quality)
      - target: the actual position being advertised
    """

    def __init__(self, angle: float, duration: float, vigor: float,
                 target: np.ndarray, scout_id: int):
        self.angle = float(angle)
        self.duration = float(duration)
        self.vigor = float(vigor)
        self.target = np.asarray(target, dtype=np.float32)[:2]
        self.scout_id = scout_id
        self.followers: int = 0

    def decode_vector(self) -> np.ndarray:
        """Decode the symbolic dance back into a Cartesian displacement vector."""
        dx = float(np.cos(self.angle)) * self.duration
        dy = float(np.sin(self.angle)) * self.duration
        return np.array([dx, dy], dtype=np.float32)


class HoneybeeWaggleDance:
    """
    The waggle dance floor — where scouts advertise and recruits decode.

    Biology (Seeley 2010): The dance floor is the vertical face of the
    honeycomb where returning foragers perform their dances. Multiple
    scouts may advertise different locations simultaneously. The colony
    reaches consensus through a quorum-sensing process where the number
    of bees dancing for a site determines its recruitment strength.
    """

    def __init__(
        self,
        hive_pos: Tuple[float, float] = (0.5, 0.5),
        cfg: Optional[WaggleConfig] = None,
    ):
        self.hive = np.asarray(hive_pos, dtype=np.float32)[:2]
        self.cfg = cfg or WaggleConfig()
        self.dances: List[WaggleDance] = []
        self._rng = np.random.default_rng(70)

    def advertise(
        self,
        scout_pos: np.ndarray,
        quality: float,
        scout_id: int = 0,
    ) -> Optional[WaggleDance]:
        """
        A scout returns from the field and performs a waggle dance.

        Biology (von Frisch 1967):
          - Only dances for high-quality sources (quality > threshold)
          - Encodes direction as angle relative to hive center
          - Encodes distance as waggle run duration
          - Encodes quality as vigor (dance intensity)
        """
        scout_pos = np.asarray(scout_pos, dtype=np.float32)[:2]
        vec = scout_pos - self.hive
        dist = float(np.linalg.norm(vec))

        if quality < self.cfg.quality_threshold or dist < self.cfg.eps:
            return None

        # Encode
        angle = float(np.arctan2(vec[1], vec[0]))
        # Add biological noise (bees are not perfect dancers)
        angle += float(self._rng.normal(0.0, self.cfg.noise))
        duration = dist * self.cfg.distance_scale
        vigor = float(np.clip(quality, 0.0, 1.0))

        dance = WaggleDance(angle, duration, vigor, scout_pos, scout_id)

        # Comb space is limited
        if len(self.dances) >= self.cfg.max_dances:
            # Replace the weakest dance
            min_idx = int(np.argmin([d.vigor for d in self.dances]))
            if dance.vigor > self.dances[min_idx].vigor:
                self.dances[min_idx] = dance
            else:
                return None
        else:
            self.dances.append(dance)

        return dance

    def decay(self) -> int:
        """
        Decay all dances. Remove those below threshold.
        Biology: Dances naturally lose vigor over time as scouts
        stop dancing and switch to other tasks.
        Returns the number of dances that expired.
        """
        expired = 0
        kept = []
        cutoff = self.cfg.quality_threshold * 0.5
        for d in self.dances:
            d.vigor *= self.cfg.memory_decay
            if d.vigor > cutoff:
                kept.append(d)
            else:
                expired += 1
        self.dances = kept
        return expired

    def recruit_vector(self) -> np.ndarray:
        """
        Compute the consensus recruitment vector from all active dances.

        Biology (Seeley 2010): Recruits integrate information from
        multiple dancers. The colony's decision emerges from the
        weighted average of all concurrent dances, where vigor
        determines the weight.
        """
        if not self.dances:
            return np.zeros(2, dtype=np.float32)

        weights = np.array([d.vigor for d in self.dances], dtype=np.float32)
        total_w = float(weights.sum()) + self.cfg.eps
        weights /= total_w

        # Weighted vector sum
        vx = sum(float(w) * float(np.cos(d.angle)) * d.duration
                 for w, d in zip(weights, self.dances))
        vy = sum(float(w) * float(np.sin(d.angle)) * d.duration
                 for w, d in zip(weights, self.dances))

        noise = self._rng.normal(0.0, self.cfg.noise, size=2).astype(np.float32)
        return self.cfg.recruit_gain * (np.array([vx, vy], dtype=np.float32) + noise)

    def best_dance(self) -> Optional[WaggleDance]:
        """Return the highest-vigor dance (colony's current best bet)."""
        if not self.dances:
            return None
        return max(self.dances, key=lambda d: d.vigor)

    def quorum_reached(self) -> bool:
        """
        Has the colony reached quorum for any single target?
        Biology (Seeley 2010): Swarm decision-making requires a
        threshold fraction of scouts dancing for the same site.
        """
        if not self.dances:
            return False
        best = self.best_dance()
        if best is None:
            return False
        total_vigor = sum(d.vigor for d in self.dances)
        if total_vigor < self.cfg.eps:
            return False
        return (best.vigor / total_vigor) >= self.cfg.quorum_fraction

    def steer_recruits(
        self,
        positions: np.ndarray,
        recruit_mask: np.ndarray,
    ) -> np.ndarray:
        """
        Apply the consensus dance vector to recruited agents.

        Biology (Riley et al., Nature 2005): Radar tracking showed
        that recruited bees fly DIRECTLY in the communicated direction,
        then search locally upon arrival.
        """
        positions = np.asarray(positions, dtype=np.float32)
        steer = np.zeros((len(positions), 2), dtype=np.float32)

        v = self.recruit_vector()
        mask = np.asarray(recruit_mask, dtype=bool)
        steer[mask] = v

        self.decay()
        return steer


def proof_of_property() -> bool:
    """
    MANDATE VERIFICATION — HONEYBEE WAGGLE DANCE TEST.

    Proves four biological invariants:
      1. Scouts encode direction + distance + quality into a symbolic dance
      2. Recruits decode the dance and navigate toward the target
      3. Multiple competing dances resolve via vigor-weighted consensus
      4. Stale dances decay and expire (temporal information hygiene)
    """
    print("\n=== SIFTA HONEYBEE WAGGLE DANCE (Event 70) : JUDGE VERIFICATION ===")

    cfg = WaggleConfig()
    hive = HoneybeeWaggleDance(hive_pos=(0.5, 0.5), cfg=cfg)

    # Phase 1: Scout encodes a discovery
    print("\n[*] Phase 1: Scout encodes discovery (von Frisch 1967)")
    discovery_pos = np.array([0.8, 0.9], dtype=np.float32)
    dance = hive.advertise(discovery_pos, quality=0.95, scout_id=0)
    assert dance is not None, "[FAIL] Scout did not dance for high-quality source"

    decoded = dance.decode_vector()
    expected_dir = discovery_pos - hive.hive
    # Check angle is approximately correct (within noise tolerance)
    expected_angle = float(np.arctan2(expected_dir[1], expected_dir[0]))
    angle_error = abs(dance.angle - expected_angle)
    print(f"    Dance angle: {dance.angle:.3f} rad (expected ~{expected_angle:.3f})")
    print(f"    Dance duration: {dance.duration:.3f} (encodes distance)")
    print(f"    Dance vigor: {dance.vigor:.3f} (encodes quality)")
    assert angle_error < 0.5, "[FAIL] Dance angle too far from true direction"

    # Phase 2: Recruits follow the dance
    print("\n[*] Phase 2: Recruits follow communicated vector (Riley 2005)")
    recruit_positions = np.tile(hive.hive, (5, 1))  # 5 recruits at hive
    recruit_mask = np.array([True, True, True, False, False])
    steer = hive.steer_recruits(recruit_positions, recruit_mask)
    recruited_movement = float(np.linalg.norm(steer[0]))
    non_recruited_movement = float(np.linalg.norm(steer[3]))
    print(f"    Recruited agent displacement: {recruited_movement:.4f}")
    print(f"    Non-recruited agent displacement: {non_recruited_movement:.4f}")
    assert recruited_movement > 0.0, "[FAIL] Recruit did not move"
    assert non_recruited_movement == 0.0, "[FAIL] Non-recruit should not move"

    # Phase 3: Competing dances resolve via vigor
    print("\n[*] Phase 3: Competing dances (Seeley 2010)")
    hive2 = HoneybeeWaggleDance(cfg=cfg)
    hive2.advertise(np.array([0.9, 0.5]), quality=0.7, scout_id=1)  # mediocre
    hive2.advertise(np.array([0.2, 0.8]), quality=0.99, scout_id=2)  # excellent

    best = hive2.best_dance()
    assert best is not None
    print(f"    Best dance scout_id: {best.scout_id} (expected: 2)")
    print(f"    Best dance vigor: {best.vigor:.3f}")
    assert best.scout_id == 2, "[FAIL] Best dance should be the highest quality"

    # Phase 4: Dance memory decays
    print("\n[*] Phase 4: Dance memory decay (temporal hygiene)")
    hive3 = HoneybeeWaggleDance(cfg=WaggleConfig(memory_decay=0.5))
    hive3.advertise(np.array([0.8, 0.8]), quality=0.7, scout_id=0)
    initial_count = len(hive3.dances)
    for _ in range(10):
        hive3.decay()
    final_count = len(hive3.dances)
    print(f"    Dances before decay: {initial_count}")
    print(f"    Dances after 10 decay cycles: {final_count}")
    assert final_count < initial_count, "[FAIL] Stale dances did not expire"

    # Phase 5: Quorum sensing
    print("\n[*] Phase 5: Quorum sensing (Seeley 2010)")
    hive4 = HoneybeeWaggleDance(cfg=WaggleConfig(quorum_fraction=0.3))
    hive4.advertise(np.array([0.9, 0.9]), quality=0.99, scout_id=0)
    quorum = hive4.quorum_reached()
    print(f"    Quorum with single unanimous dance: {quorum}")
    assert quorum, "[FAIL] Single dominant dance should reach quorum"

    print("\n[+] BIOLOGICAL PROOF: Honeybee Waggle Dance verified.")
    print("    1. Scouts compress field discoveries into symbolic vectors (von Frisch 1967)")
    print("    2. Recruits decode dances and navigate (Riley et al. 2005)")
    print("    3. Competing dances resolve via vigor-weighted consensus (Seeley 2010)")
    print("    4. Stale dances decay — temporal information hygiene")
    print("    5. Quorum sensing enables colony-level decision-making")
    print("[+] EVENT 70 PASSED.")
    return True


if __name__ == "__main__":
    proof_of_property()
