#!/usr/bin/env python3
"""
System/stigmergic_entropy.py — Environment-Conditioned Entropy Adaptation
══════════════════════════════════════════════════════════════════════════

Novel contribution (beyond standard PPO):
    Instead of scheduling entropy from a scalar (λ → c_e),
    adapt entropy from COLLECTIVE BEHAVIOR TRACES.

    Entropy becomes a function of *what the swarm did*, not *what step we're on*.

Two modes coexist:
    1. lagrangian_entropy_controller.py — λ-scheduled (Perplexity spec)
    2. THIS FILE — trace-conditioned (SwarmGPT/Cursor spec)

    Mode 1 is the floor/ceiling. Mode 2 operates within those bounds.

Provenance:
    - Spec: SwarmGPT fresh tab (2026-04-17T12:14)
    - Implementation: Antigravity (DeepMind IDE)
    - Audit: All five models converged on PPO entropy as the bridge point
    - Integration: reads from StigmergicMemoryBus traces, writes to entropy_schedule.jsonl
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, List, Optional

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.jsonl_file_lock import append_line_locked


# ═══════════════════════════════════════════════════════════════════
# STIGMERGIC TRACE BUFFER
# ═══════════════════════════════════════════════════════════════════

@dataclass
class StigmergicEvent:
    """One pheromone drop from one agent at one timestep."""
    step: int
    agent_id: int
    entropy: float       # policy entropy at this step
    reward: float        # reward received
    action_std: float    # action distribution width


class StigmergicBuffer:
    """
    Lightweight shared environment trace.
    Ants leaving pheromones, but for RL logs.
    Ring buffer — oldest entries evicted first.
    """

    def __init__(self, maxlen: int = 1000):
        self.maxlen = maxlen
        self.buffer: List[StigmergicEvent] = []

    def log(self, event: StigmergicEvent):
        self.buffer.append(event)
        if len(self.buffer) > self.maxlen:
            self.buffer.pop(0)

    def mean_entropy(self) -> float:
        if not self.buffer:
            return 0.0
        return sum(e.entropy for e in self.buffer) / len(self.buffer)

    def mean_reward(self) -> float:
        if not self.buffer:
            return 0.0
        return sum(e.reward for e in self.buffer) / len(self.buffer)

    def mean_action_std(self) -> float:
        if not self.buffer:
            return 0.0
        return sum(e.action_std for e in self.buffer) / len(self.buffer)

    def size(self) -> int:
        return len(self.buffer)

    def save(self, path: Path | str):
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w") as f:
            json.dump([asdict(e) for e in self.buffer], f, indent=2)


# ═══════════════════════════════════════════════════════════════════
# STIGMERGIC ENTROPY CONTROLLER
# ═══════════════════════════════════════════════════════════════════

class StigmergicEntropyController:
    """
    Adjusts entropy coefficient based on collective behavior traces.

    Core idea:
        - high reward + low entropy → reduce exploration (exploit what works)
        - low reward + low entropy → increase exploration (stuck, need to search)
        - high entropy → stabilize (already exploring enough)

    The output is bounded by [c_e_floor, c_e_ceiling] to prevent
    destabilization. These bounds can come from the λ-scheduled controller.
    """

    def __init__(
        self,
        base_entropy: float = 0.01,
        exploration_gain: float = 1.5,
        exploitation_bias: float = 0.5,
        c_e_floor: float = 1e-5,
        c_e_ceiling: float = 0.05,
    ):
        self.base_entropy = base_entropy
        self.exploration_gain = exploration_gain
        self.exploitation_bias = exploitation_bias
        self.c_e_floor = c_e_floor
        self.c_e_ceiling = c_e_ceiling

    def compute_entropy_coef(self, buffer: StigmergicBuffer) -> float:
        """
        Read the collective trace and compute the adapted entropy coefficient.
        """
        mean_entropy = buffer.mean_entropy()
        mean_reward = buffer.mean_reward()

        # Pressure signals (both in [0, 1] range for stable math)
        stability_pressure = max(0.0, min(1.0, 1.0 - mean_entropy))
        performance_pressure = max(0.0, min(1.0, 1.0 - mean_reward))

        entropy_coeff = self.base_entropy * (
            self.exploration_gain * performance_pressure
            + self.exploitation_bias * stability_pressure
        )

        return float(max(self.c_e_floor, min(entropy_coeff, self.c_e_ceiling)))


# ═══════════════════════════════════════════════════════════════════
# TRAINER HOOK (SwarmRL integration point)
# ═══════════════════════════════════════════════════════════════════

def update_entropy(
    loss_fn: Any,
    controller: StigmergicEntropyController,
    buffer: StigmergicBuffer,
    step: int,
    log_to_telemetry: bool = True,
) -> float:
    """
    Refresh entropy coefficient from trace buffer before each episode.
    Optionally logs to .sifta_state/entropy_schedule.jsonl.
    """
    new_coef = controller.compute_entropy_coef(buffer)
    loss_fn.entropy_coefficient = new_coef

    if log_to_telemetry:
        _STATE = _REPO / ".sifta_state"
        _STATE.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": time.time(),
            "iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "step": step,
            "entropy_coefficient": round(new_coef, 8),
            "mean_reward": round(buffer.mean_reward(), 6),
            "mean_entropy": round(buffer.mean_entropy(), 6),
            "mean_action_std": round(buffer.mean_action_std(), 6),
            "buffer_size": buffer.size(),
            "source": "stigmergic_entropy_controller",
        }
        append_line_locked(
            _STATE / "entropy_schedule.jsonl",
            json.dumps(entry) + "\n",
        )

    return new_coef


# ═══════════════════════════════════════════════════════════════════
# Self-Test: Simulated Rollout
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("═" * 65)
    print("  STIGMERGIC ENTROPY — Trace-Conditioned Adaptation Test")
    print("═" * 65)
    print()

    buffer = StigmergicBuffer(maxlen=200)
    controller = StigmergicEntropyController()

    class MockPPO:
        entropy_coefficient = 0.01

    mock = MockPPO()

    print(f"  {'Step':>5}  {'c_e':>10}  {'mean_R':>8}  {'mean_H':>8}  {'Regime':>12}")
    print("  " + "─" * 54)

    for step in range(100):
        # Simulated agent behavior — performance improves over time
        reward = min(1.0, 0.1 + step * 0.008 + (step % 7) * 0.01)
        entropy = max(0.05, 0.5 - step * 0.004 + (step % 5) * 0.01)

        buffer.log(StigmergicEvent(
            step=step,
            agent_id=0,
            entropy=entropy,
            reward=reward,
            action_std=0.1 + entropy * 0.3,
        ))

        if step % 10 == 0:
            coef = update_entropy(mock, controller, buffer, step, log_to_telemetry=False)
            mr = buffer.mean_reward()
            mh = buffer.mean_entropy()
            regime = "EXPLORE" if coef > 0.008 else ("NARROW" if coef > 0.003 else "EXPLOIT")
            print(f"  {step:>5}  {coef:>10.6f}  {mr:>8.3f}  {mh:>8.3f}  {regime:>12}")

    print()
    print(f"  Final c_e: {mock.entropy_coefficient:.6f}")
    print(f"  Buffer: {buffer.size()} events")
    print()

    # Show the key comparison
    print("  COMPARISON: λ-scheduled vs trace-conditioned")
    print("  " + "─" * 54)
    print("  │ PPO default      │ fixed c_e = 0.01           │")
    print("  │ PPO + time decay  │ c_e(t) = schedule(step)    │")
    print("  │ Perplexity spec   │ c_e(λ) = 0.01·e^(-2λ)     │")
    print("  │ THIS FILE         │ c_e(traces) = f(R̄, H̄)     │")
    print("  " + "─" * 54)
    print()
    print("  ✅ Entropy adapts to WHAT THE SWARM DID, not what step we're on.")
