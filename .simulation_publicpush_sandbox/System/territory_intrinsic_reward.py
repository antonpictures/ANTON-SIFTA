#!/usr/bin/env python3
"""
territory_intrinsic_reward.py — Bridge between Territory Consciousness and SwarmRL
====================================================================================
SWARM GPT audit v2 — 3 red flags FIXED:

  RED FLAG 1: Self-generated novelty inflation
    FIX → System-driven zones (System/, .sifta_state/, logs) are MASKED.
          Only agent-driven territory changes get full novelty reward.

  RED FLAG 2: Lack of reward normalization
    FIX → Running mean/std normalization with β annealing.
          r_total = r_extrinsic + β * normalize(r_intrinsic)
          β decays over patrol cycles so exploration doesn't dominate.

  RED FLAG 3: Binary novelty metric (hash = changed/not changed)
    FIX → GRADED novelty using file_count delta, byte delta, and mtime
          recency. Small edits = small signal. Structural changes = big signal.
          No more uniform +1.0 spikes for every single-byte change.

All 4 capabilities:
  1. Exploration Decay       ✅ (pheromone half-life)
  2. Novelty Detection       ✅ (GRADED, not binary)
  3. Structured Env Mapping  ✅ (155 territory cells)
  4. Intrinsic Reward Shaping ✅ (normalized, annealed)
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_NORM_STATE = _STATE_DIR / "intrinsic_reward_norm.json"

# ─── REWARD WEIGHTS ─────────────────────────────────────────────────────────────

NOVELTY_WEIGHT     = 1.0
EXPLORATION_WEIGHT = 0.5
PATROL_WEIGHT      = 0.3
ANOMALY_PENALTY    = -2.0

EXPLORATION_THRESHOLD = 0.3

# ─── FIX 1: SYSTEM-DRIVEN ZONE MASK ────────────────────────────────────────────
# These zones change because the ENGINE runs (logs, state dumps, heartbeats).
# Agent-driven novelty = real exploration. System-driven novelty = fake.
# Masked zones get 10% novelty weight instead of 100%.

SYSTEM_DRIVEN_ZONES = {
    "System", ".sifta_state", ".sifta_state/heartbeats",
    ".sifta_state/temporal", ".sifta_state/ledger",
    ".sifta_state/faults", ".sifta_state/scars",
    ".sifta_state/dream_reports", ".sifta_state/latent",
    ".sifta_state/wormhole_cache", ".sifta_state/hypotheses",
    "Kernel/.sifta_state", "Kernel/.sifta_reputation",
}

SYSTEM_NOVELTY_DAMPENING = 0.10  # System zones get 10% novelty credit


# ─── FIX 2: RUNNING NORMALIZATION + β ANNEALING ────────────────────────────────

class IntrinsicRewardNormalizer:
    """
    Welford's online algorithm for running mean/std.
    Normalizes intrinsic reward to N(0,1) so it doesn't
    collapse or dominate extrinsic signal in PPO.

    β anneals from β_start toward β_min over patrol cycles.
    Early patrols = strong exploration. Late patrols = task-focused.
    """

    def __init__(self, beta_start: float = 1.0, beta_min: float = 0.1,
                 anneal_rate: float = 0.995):
        self.beta = beta_start
        self.beta_min = beta_min
        self.anneal_rate = anneal_rate

        # Welford running stats
        self.count = 0
        self.mean = 0.0
        self.m2 = 0.0  # sum of squared deviations

        self._load()

    def update(self, value: float):
        """Incorporate one new reward sample."""
        self.count += 1
        delta = value - self.mean
        self.mean += delta / self.count
        delta2 = value - self.mean
        self.m2 += delta * delta2

    @property
    def std(self) -> float:
        if self.count < 2:
            return 1.0
        return max(math.sqrt(self.m2 / (self.count - 1)), 1e-8)

    def normalize(self, value: float) -> float:
        """Normalize to zero-mean, unit-variance."""
        return (value - self.mean) / self.std

    def scale(self, raw_reward: float) -> float:
        """Full pipeline: update → normalize → scale by β."""
        self.update(raw_reward)
        normalized = self.normalize(raw_reward)
        return self.beta * normalized

    def anneal(self):
        """Call once per patrol cycle. β decays toward β_min."""
        self.beta = max(self.beta_min, self.beta * self.anneal_rate)
        self._save()

    def _save(self):
        data = {
            "beta": self.beta, "count": self.count,
            "mean": self.mean, "m2": self.m2
        }
        try:
            _NORM_STATE.write_text(json.dumps(data))
        except Exception:
            pass

    def _load(self):
        try:
            if _NORM_STATE.exists():
                data = json.loads(_NORM_STATE.read_text())
                self.beta = data.get("beta", self.beta)
                self.count = data.get("count", 0)
                self.mean = data.get("mean", 0.0)
                self.m2 = data.get("m2", 0.0)
        except Exception:
            pass


# Global normalizer (persisted across patrols)
_NORMALIZER = IntrinsicRewardNormalizer()


# ─── FIX 3: GRADED NOVELTY ─────────────────────────────────────────────────────

def _graded_novelty(before: Optional[dict], after: dict) -> float:
    """
    Compute novelty as a CONTINUOUS value [0.0, 1.0] instead of binary 0/1.

    Uses three signals:
      - file_count delta (structural change)
      - byte_count delta (content volume change)
      - mtime recency   (how recently the zone was touched)

    Small edits → small novelty. Restructuring → big novelty.
    """
    if before is None:
        return 0.5  # First discovery: moderate signal

    # Hash check first — if identical, zero novelty (no computation wasted)
    if before.get("content_hash", "") == after.get("content_hash", ""):
        return 0.0

    # 1. File count change (0 to 1 scale)
    fc_before = max(before.get("file_count", 0), 1)
    fc_after = max(after.get("file_count", 0), 1)
    file_delta = abs(fc_after - fc_before) / max(fc_before, fc_after)

    # 2. Byte volume change (0 to 1 scale, log-dampened)
    b_before = max(before.get("total_bytes", 1), 1)
    b_after = max(after.get("total_bytes", 1), 1)
    byte_ratio = max(b_after / b_before, b_before / b_after)
    byte_delta = min(1.0, math.log2(byte_ratio) / 5.0)  # log2(32x) = 5 → cap

    # 3. Mtime recency (how fresh is the change, 0 to 1)
    last_mod = after.get("last_modified", 0)
    age_seconds = max(0, time.time() - last_mod)
    # 0s = 1.0, 3600s = 0.5, 86400s ≈ 0.0
    recency = math.exp(-age_seconds / 3600.0)

    # Weighted combination
    novelty = (
        0.40 * file_delta +    # structural weight
        0.35 * byte_delta +    # volume weight
        0.25 * recency         # freshness weight
    )

    return round(min(1.0, novelty), 4)


# ─── INTRINSIC REWARD COMPUTATION (v2) ─────────────────────────────────────────

def compute_territory_reward(
    cell_before: Optional[dict],
    cell_after: dict
) -> dict:
    """
    Compute intrinsic reward for a single territory cell transition.
    v2: Graded novelty, system-zone masking, normalized output.
    """
    novelty = 0.0
    exploration = 0.0
    patrol = 0.0
    reasons = []

    zone_path = cell_after.get("path", "")

    # ── 1. GRADED NOVELTY (FIX 3) ────────────────────────────────────────
    raw_novelty = _graded_novelty(cell_before, cell_after)

    if raw_novelty > 0.0:
        # ── SYSTEM MASK (FIX 1) ──────────────────────────────────────
        is_system_zone = zone_path in SYSTEM_DRIVEN_ZONES
        dampening = SYSTEM_NOVELTY_DAMPENING if is_system_zone else 1.0

        novelty = NOVELTY_WEIGHT * raw_novelty * dampening
        tag = "sys-masked" if is_system_zone else "agent"
        reasons.append(
            f"NOVELTY(+{novelty:.3f}): graded={raw_novelty:.3f} [{tag}]"
        )

    # ── 2. EXPLORATION BONUS ──────────────────────────────────────────────
    pheromone = cell_after.get("pheromone", 0.0)
    if pheromone < EXPLORATION_THRESHOLD:
        exploration = EXPLORATION_WEIGHT * (1.0 - pheromone / EXPLORATION_THRESHOLD)
        reasons.append(f"EXPLORE(+{exploration:.3f}): pheromone={pheromone:.4f}")

    # ── 3. PATROL BONUS ───────────────────────────────────────────────────
    if cell_after.get("fossilized", False):
        if cell_after.get("zone") != "INVADED":
            patrol = PATROL_WEIGHT
            reasons.append(f"PATROL(+{patrol:.3f}): fossilized intact")
        else:
            patrol = ANOMALY_PENALTY
            reasons.append(f"ANOMALY({patrol:.3f}): fossilized INVADED")

    if cell_after.get("zone") == "INVADED" and not cell_after.get("fossilized"):
        patrol += ANOMALY_PENALTY * 0.5
        reasons.append(f"ANOMALY({ANOMALY_PENALTY*0.5:.3f}): invaded")

    raw_total = novelty + exploration + patrol

    # ── NORMALIZE (FIX 2) ─────────────────────────────────────────────────
    scaled_total = _NORMALIZER.scale(raw_total)

    return {
        "reward_raw": round(raw_total, 4),
        "reward_scaled": round(scaled_total, 4),
        "novelty": round(novelty, 4),
        "exploration": round(exploration, 4),
        "patrol": round(patrol, 4),
        "graded_novelty": round(raw_novelty, 4),
        "breakdown": " | ".join(reasons) if reasons else "NEUTRAL"
    }


def compute_swarm_intrinsic_reward(
    cells_before: Dict[str, dict],
    cells_after: Dict[str, dict]
) -> dict:
    """
    Compute aggregate intrinsic reward across the entire territory map.
    v2: Normalized, graded, system-masked.
    """
    cell_rewards: Dict[str, dict] = {}
    total_raw = 0.0
    total_scaled = 0.0

    all_zones = set(list(cells_before.keys()) + list(cells_after.keys()))

    for zone in all_zones:
        before = cells_before.get(zone)
        after = cells_after.get(zone)
        if after is None:
            continue

        result = compute_territory_reward(before, after)
        cell_rewards[zone] = result
        total_raw += result["reward_raw"]
        total_scaled += result["reward_scaled"]

    count = max(len(cell_rewards), 1)

    # Anneal β after each full patrol
    _NORMALIZER.anneal()

    sorted_cells = sorted(
        cell_rewards.items(),
        key=lambda x: x[1]["reward_raw"],
        reverse=True
    )

    return {
        "total_reward_raw": round(total_raw, 4),
        "total_reward_scaled": round(total_scaled, 4),
        "mean_reward_raw": round(total_raw / count, 4),
        "beta": round(_NORMALIZER.beta, 4),
        "normalizer_mean": round(_NORMALIZER.mean, 4),
        "normalizer_std": round(_NORMALIZER.std, 4),
        "cell_count": len(cell_rewards),
        "top_novelty": [
            {
                "zone": z,
                "reward_raw": r["reward_raw"],
                "reward_scaled": r["reward_scaled"],
                "graded_novelty": r["graded_novelty"],
                "breakdown": r["breakdown"]
            }
            for z, r in sorted_cells[:10]
            if r["reward_raw"] > 0
        ],
        "explorer_targets": [
            z for z, r in sorted_cells if r["exploration"] > 0
        ],
    }


# ─── AGENT DISPATCH SIGNAL ─────────────────────────────────────────────────────

def get_exploration_targets(territory_map: Dict[str, dict], top_k: int = 5) -> List[str]:
    """Route swimmers to the zones with highest exploration urgency."""
    scored = []
    for zone, cell in territory_map.items():
        pheromone = cell.get("pheromone", 0.0)
        if cell.get("fossilized"):
            continue
        file_count = max(cell.get("file_count", 1), 1)
        urgency = (1.0 - pheromone) * math.log2(file_count + 1)
        scored.append((zone, urgency))
    scored.sort(key=lambda x: x[1], reverse=True)
    return [z for z, _ in scored[:top_k]]


def pheromone_sampling_weights(territory_map: Dict[str, dict]) -> Dict[str, float]:
    """Probability distribution over zones, inverse to pheromone."""
    weights = {}
    total = 0.0
    for zone, cell in territory_map.items():
        if cell.get("fossilized"):
            continue
        inv = max(0.01, 1.0 - cell.get("pheromone", 0.0))
        weights[zone] = inv
        total += inv
    if total > 0:
        for z in weights:
            weights[z] = round(weights[z] / total, 6)
    return weights


# ─── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys, os

    sys.path.insert(0, str(_REPO / "Kernel"))
    sys.path.insert(0, str(_REPO / "System"))

    from territory_consciousness import TerritoryConsciousness
    from dataclasses import asdict

    print("=" * 60)
    print("  SIFTA — TERRITORY INTRINSIC REWARD ENGINE v2")
    print("  3 Red Flags Fixed (SWARM GPT audit)")
    print("=" * 60)

    tc = TerritoryConsciousness()
    before = {k: asdict(v) for k, v in tc.cells.items()}
    report = tc.patrol()
    after = {k: asdict(v) for k, v in tc.cells.items()}

    rr = compute_swarm_intrinsic_reward(before, after)

    print(f"\n  Raw Total Reward:    {rr['total_reward_raw']}")
    print(f"  Scaled Total Reward: {rr['total_reward_scaled']}")
    print(f"  Mean Raw per Cell:   {rr['mean_reward_raw']}")
    print(f"  β (anneal):          {rr['beta']}")
    print(f"  Normalizer μ:        {rr['normalizer_mean']}")
    print(f"  Normalizer σ:        {rr['normalizer_std']}")
    print(f"  Cells Evaluated:     {rr['cell_count']}")

    if rr["top_novelty"]:
        print(f"\n  ── TOP NOVELTY SIGNALS (graded, masked) ──")
        for item in rr["top_novelty"][:8]:
            gn = item["graded_novelty"]
            bar = "█" * int(gn * 20)
            print(f"    {bar}{'░' * (20 - len(bar))} "
                  f"raw={item['reward_raw']:.3f} "
                  f"scaled={item['reward_scaled']:.3f} "
                  f"novelty={gn:.3f}  {item['zone']}")
            print(f"      {item['breakdown']}")

    targets = get_exploration_targets(after, top_k=5)
    if targets:
        print(f"\n  ── EXPLORATION TARGETS ──")
        for t in targets:
            c = after.get(t, {})
            print(f"    🌿 {t} (pheromone: {c.get('pheromone', 0):.4f})")

    print(f"\n  ── RED FLAG STATUS ──")
    print(f"    1. Self-novelty inflation:  FIXED (system zones dampened to {SYSTEM_NOVELTY_DAMPENING*100:.0f}%)")
    print(f"    2. Reward normalization:    FIXED (Welford online + β={rr['beta']:.4f})")
    print(f"    3. Binary novelty metric:   FIXED (graded: file_delta + byte_delta + recency)")
    print("=" * 60)
