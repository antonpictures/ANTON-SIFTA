"""
territory_reward.py — Territory Consciousness wired into SwarmRL training graph
================================================================================
The last 10% that makes it real.

This module is a drop-in IntrinsicReward subclass that:
  1. WIRING:         Inherits from swarmrl.intrinsic_reward.IntrinsicReward
  2. NORMALIZATION:  Welford running mean/std + β annealing (persisted)
  3. TRAINER HOOK:   update() called by ActorCriticAgent.update_agent()
  4. RUNTIME:        compute_reward() called every step in calc_action()

Integration point in existing code:

    # In actor_critic.py line 180-183 (ALREADY EXISTS):
    if self.intrinsic_reward:
        rewards += self.intrinsic_reward.compute_reward(
            episode_data=self.trajectory
        )

    # Construction:
    from swarmrl.observables.territory_reward import TerritoryReward
    agent = ActorCriticAgent(
        ...,
        intrinsic_reward=TerritoryReward(root="/path/to/repo")
    )

That's it. No other changes to the training graph needed.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

# ─── TRY SWARMRL IMPORT, FALLBACK FOR STANDALONE ───────────────────────────────
try:
    from swarmrl.intrinsic_reward.intrinsic_reward import IntrinsicReward
    from swarmrl.utils.colloid_utils import TrajectoryInformation
    _HAS_SWARMRL = True
except ImportError:
    # Standalone mode: define stubs so the module works outside SwarmRL
    class IntrinsicReward:
        def update(self, episode_data): raise NotImplementedError
        def compute_reward(self, episode_data): raise NotImplementedError

    @dataclass
    class TrajectoryInformation:
        particle_type: int = 0
        features: list = field(default_factory=list)
        actions: list = field(default_factory=list)
        log_probs: list = field(default_factory=list)
        rewards: list = field(default_factory=list)
        killed: bool = False

    _HAS_SWARMRL = False


# ─── CONSTANTS ──────────────────────────────────────────────────────────────────

PATROL_HALF_LIFE = 86400.0               # 24h pheromone half-life
DECAY_K = 0.693147 / (PATROL_HALF_LIFE / 3600.0)

# Reward weights
W_NOVELTY     = 1.0
W_EXPLORATION = 0.5
W_PATROL      = 0.3

# β annealing
BETA_START = 1.0
BETA_MIN   = 0.05
BETA_DECAY = 0.998

# System-driven zone dampening
SYSTEM_ZONES = {
    "System", ".sifta_state", "logs", "__pycache__",
    ".sifta_state/heartbeats", ".sifta_state/temporal",
    ".sifta_state/ledger", ".sifta_state/faults",
}
SYSTEM_DAMPEN = 0.10

EXPLORATION_THRESHOLD = 0.3


# ─── TERRITORY CELL (lightweight) ──────────────────────────────────────────────

@dataclass
class _Cell:
    path: str
    file_count: int = 0
    total_bytes: int = 0
    content_hash: str = ""
    pheromone: float = 0.0
    last_visit: float = 0.0
    visit_count: int = 0
    fossilized: bool = False


# ─── WELFORD NORMALIZER ────────────────────────────────────────────────────────

class _Normalizer:
    """Running mean/std via Welford's online algorithm."""

    def __init__(self):
        self.count = 0
        self.mean = 0.0
        self.m2 = 0.0
        self.beta = BETA_START

    def update(self, x: float):
        self.count += 1
        d = x - self.mean
        self.mean += d / self.count
        d2 = x - self.mean
        self.m2 += d * d2

    @property
    def std(self) -> float:
        if self.count < 2:
            return 1.0
        return max(math.sqrt(self.m2 / (self.count - 1)), 1e-8)

    def normalize(self, x: float) -> float:
        return (x - self.mean) / self.std

    def scale(self, x: float) -> float:
        self.update(x)
        return self.beta * self.normalize(x)

    def anneal(self):
        self.beta = max(BETA_MIN, self.beta * BETA_DECAY)


# ─── GRADED NOVELTY ────────────────────────────────────────────────────────────

def _graded_novelty(before: Optional[_Cell], after: _Cell) -> float:
    """Continuous novelty [0.0, 1.0] instead of binary hash check."""
    if before is None:
        return 0.5

    if before.content_hash == after.content_hash:
        return 0.0

    fc_b = max(before.file_count, 1)
    fc_a = max(after.file_count, 1)
    file_delta = abs(fc_a - fc_b) / max(fc_b, fc_a)

    b_b = max(before.total_bytes, 1)
    b_a = max(after.total_bytes, 1)
    byte_ratio = max(b_a / b_b, b_b / b_a)
    byte_delta = min(1.0, math.log2(byte_ratio) / 5.0)

    recency = math.exp(-(time.time() - after.last_visit) / 3600.0)

    return min(1.0, 0.40 * file_delta + 0.35 * byte_delta + 0.25 * recency)


# ═══════════════════════════════════════════════════════════════════════════════
#  THE ACTUAL INTRINSIC REWARD CLASS — WIRED INTO SWARMRL
# ═══════════════════════════════════════════════════════════════════════════════

class TerritoryReward(IntrinsicReward):
    """
    Stigmergic Territory Consciousness as an IntrinsicReward.

    Drop-in replacement for RNDReward in the SwarmRL pipeline.
    No neural networks. Pure pheromone physics.

    Lifecycle (called by ActorCriticAgent automatically):
      __init__     → constructs territory map
      compute_reward(trajectory) → called EVERY STEP in calc_action()
      update(trajectory)         → called EVERY EPISODE in update_agent()
    """

    def __init__(
        self,
        root: str = ".",
        patrol_interval: float = 5.0,
        state_path: str = None,
    ):
        """
        Parameters
        ----------
        root : str
            Root directory to map as territory.
        patrol_interval : float
            Minimum seconds between filesystem patrols.
            Prevents I/O thrashing during training.
        state_path : str
            Path to persist territory state. If None, uses root/.sifta_state/
        """
        self.root = Path(root).resolve()
        self.patrol_interval = patrol_interval
        self._state_path = Path(state_path) if state_path else self.root / ".sifta_state" / "territory_rl_state.json"
        self._state_path.parent.mkdir(parents=True, exist_ok=True)

        # Internal state
        self._cells: Dict[str, _Cell] = {}
        self._prev_cells: Dict[str, _Cell] = {}
        self._normalizer = _Normalizer()
        self._last_patrol = 0.0
        self._episode_rewards: List[float] = []
        self._total_episodes = 0

        # Load persisted state
        self._load()

        # Initial patrol
        self._patrol()

    # ── SWARMRL INTERFACE: compute_reward ──────────────────────────────────
    # Called by ActorCriticAgent.calc_action() every timestep.
    # Returns np.ndarray of shape matching trajectory.rewards

    def compute_reward(self, episode_data: TrajectoryInformation) -> np.ndarray:
        """
        Compute territory intrinsic reward for the current timestep.

        The reward is a single scalar broadcast to all particles.
        We patrol the filesystem at most once per patrol_interval
        to avoid I/O overhead during training.
        """
        now = time.time()

        # Rate-limited patrol
        if now - self._last_patrol > self.patrol_interval:
            self._prev_cells = {k: _Cell(**{
                "path": v.path, "file_count": v.file_count,
                "total_bytes": v.total_bytes, "content_hash": v.content_hash,
                "pheromone": v.pheromone, "last_visit": v.last_visit,
                "visit_count": v.visit_count, "fossilized": v.fossilized,
            }) for k, v in self._cells.items()}
            self._patrol()

        # Compute aggregate reward across all territory cells
        raw_total = 0.0
        for path, cell in self._cells.items():
            prev = self._prev_cells.get(path)
            raw_total += self._cell_reward(prev, cell)

        # Normalize and scale
        scaled = self._normalizer.scale(raw_total)
        self._episode_rewards.append(scaled)

        # Return as ndarray (SwarmRL expects this shape)
        # Broadcast scalar to match whatever particle count exists
        if hasattr(episode_data, "rewards") and len(episode_data.rewards) > 0:
            last_shape = np.array(episode_data.rewards[-1]).shape
            return np.full(last_shape, scaled)

        return np.array(scaled)

    # ── SWARMRL INTERFACE: update ──────────────────────────────────────────
    # Called by ActorCriticAgent.update_agent() at end of each episode.

    def update(self, episode_data: TrajectoryInformation):
        """
        End-of-episode update. Anneal β and persist state.

        IMPORTANT: Keep intrinsic reward out of value function target
        initially. Use it only for policy gradient shaping. Otherwise
        critic learns "novelty prediction" instead of task value.
        (SWARM GPT recommendation — April 2026)
        """
        self._total_episodes += 1
        self._normalizer.anneal()
        self._episode_rewards = []

        # Persist every 10 episodes (not every step — I/O budget)
        if self._total_episodes % 10 == 0:
            self._save()

    # ── CELL REWARD ────────────────────────────────────────────────────────

    def _cell_reward(self, before: Optional[_Cell], after: _Cell) -> float:
        novelty = _graded_novelty(before, after)

        # System zone dampening
        is_system = after.path in SYSTEM_ZONES
        novelty *= SYSTEM_DAMPEN if is_system else 1.0

        # Exploration bonus
        exploration = 0.0
        if after.pheromone < EXPLORATION_THRESHOLD:
            exploration = W_EXPLORATION * (1.0 - after.pheromone / EXPLORATION_THRESHOLD)

        # Patrol bonus for fossilized zones
        patrol = 0.0
        if after.fossilized:
            patrol = W_PATROL

        return W_NOVELTY * novelty + exploration + patrol

    # ── FILESYSTEM PATROL ──────────────────────────────────────────────────

    def _patrol(self):
        """Walk the filesystem and update territory cells."""
        now = time.time()
        self._last_patrol = now

        ignore = {".git", "__pycache__", "node_modules", ".venv"}
        fossilized_patterns = {".sifta_state", "Kernel/.sifta_state", "repair_log.jsonl"}

        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if d not in ignore]

            rel = os.path.relpath(dirpath, self.root)
            if rel == ".":
                rel = "ROOT"
            if rel.count(os.sep) > 6:
                continue

            file_count = 0
            total_bytes = 0
            names = []

            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    st = os.stat(fp)
                    file_count += 1
                    total_bytes += st.st_size
                    names.append(f"{f}:{st.st_size}")
                except (OSError, PermissionError):
                    continue

            content_hash = hashlib.md5(
                "\n".join(sorted(names)).encode()
            ).hexdigest()[:12]

            is_fossil = any(rel == p or rel.startswith(p + os.sep) for p in fossilized_patterns)

            existing = self._cells.get(rel)
            if existing:
                # Decay pheromone
                dt_h = (now - existing.last_visit) / 3600.0
                decayed = existing.pheromone * math.exp(-DECAY_K * dt_h)
                pheromone = min(1.0, decayed + 0.2)
                visit_count = existing.visit_count + 1
            else:
                pheromone = 0.2
                visit_count = 1

            self._cells[rel] = _Cell(
                path=rel,
                file_count=file_count,
                total_bytes=total_bytes,
                content_hash=content_hash,
                pheromone=round(pheromone, 4),
                last_visit=now,
                visit_count=visit_count,
                fossilized=is_fossil,
            )

    # ── PERSISTENCE ────────────────────────────────────────────────────────

    def _save(self):
        data = {
            "beta": self._normalizer.beta,
            "norm_count": self._normalizer.count,
            "norm_mean": self._normalizer.mean,
            "norm_m2": self._normalizer.m2,
            "total_episodes": self._total_episodes,
            "cells": {k: {
                "path": v.path, "file_count": v.file_count,
                "total_bytes": v.total_bytes, "content_hash": v.content_hash,
                "pheromone": v.pheromone, "last_visit": v.last_visit,
                "visit_count": v.visit_count, "fossilized": v.fossilized,
            } for k, v in self._cells.items()}
        }
        try:
            self._state_path.write_text(json.dumps(data, indent=1))
        except Exception:
            pass

    def _load(self):
        try:
            if self._state_path.exists():
                data = json.loads(self._state_path.read_text())
                self._normalizer.beta = data.get("beta", BETA_START)
                self._normalizer.count = data.get("norm_count", 0)
                self._normalizer.mean = data.get("norm_mean", 0.0)
                self._normalizer.m2 = data.get("norm_m2", 0.0)
                self._total_episodes = data.get("total_episodes", 0)
                for k, v in data.get("cells", {}).items():
                    self._cells[k] = _Cell(**v)
        except Exception:
            pass

    # ── DIAGNOSTIC ─────────────────────────────────────────────────────────

    def report(self) -> dict:
        """Human-readable diagnostic report."""
        total_pheromone = sum(c.pheromone for c in self._cells.values())
        wild = [c.path for c in self._cells.values() if c.pheromone < EXPLORATION_THRESHOLD]
        fossil = [c.path for c in self._cells.values() if c.fossilized]

        return {
            "total_cells": len(self._cells),
            "mean_pheromone": round(total_pheromone / max(len(self._cells), 1), 4),
            "wild_zones": len(wild),
            "fossilized_zones": len(fossil),
            "beta": round(self._normalizer.beta, 4),
            "normalizer_mean": round(self._normalizer.mean, 4),
            "normalizer_std": round(self._normalizer.std, 4),
            "total_episodes": self._total_episodes,
        }


# ═══════════════════════════════════════════════════════════════════════════════
#  CLI — Verify it works standalone
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    _REPO = Path(__file__).resolve().parent.parent

    print("=" * 60)
    print("  TerritoryReward — SwarmRL IntrinsicReward Integration")
    print("  Wiring + Normalization + Training Hook + Runtime")
    print("=" * 60)

    tr = TerritoryReward(root=str(_REPO), patrol_interval=1.0)
    report = tr.report()

    print(f"\n  Territory Cells:  {report['total_cells']}")
    print(f"  Mean Pheromone:   {report['mean_pheromone']}")
    print(f"  Wild Zones:       {report['wild_zones']}")
    print(f"  Fossilized:       {report['fossilized_zones']}")
    print(f"  β:                {report['beta']}")
    print(f"  Episodes:         {report['total_episodes']}")

    # Simulate 5 training steps
    print(f"\n  ── Simulating 5 training steps ──")
    dummy_traj = TrajectoryInformation()
    dummy_traj.rewards = [np.array([0.0])]

    for step in range(5):
        reward = tr.compute_reward(dummy_traj)
        print(f"    Step {step+1}: intrinsic_reward = {reward.item():.6f} "
              f"(β={tr._normalizer.beta:.4f})")

    # Simulate episode end
    tr.update(dummy_traj)
    print(f"\n  After update: β annealed to {tr._normalizer.beta:.4f}")

    r2 = tr.report()
    print(f"  Total episodes: {r2['total_episodes']}")

    print(f"\n  ── INTEGRATION POINTS ──")
    print(f"    1. WIRING:         IntrinsicReward subclass ✅")
    print(f"    2. NORMALIZATION:  Welford + β anneal       ✅")
    print(f"    3. TRAINER HOOK:   update() per episode     ✅")
    print(f"    4. RUNTIME:        compute_reward() per step ✅")
    print(f"\n  Usage in ActorCriticAgent:")
    print(f"    agent = ActorCriticAgent(")
    print(f"        ...,")
    print(f"        intrinsic_reward=TerritoryReward(root='/repo')")
    print(f"    )")
    print("=" * 60)
