#!/usr/bin/env python3
"""
Live standalone loop for StigmergicEntropyGate.

Use this when the Mesa harness is unavailable or when you just want to see the
swarm write its first memory:

    PYTHONPATH=. python3 Utilities/stigmergic_entropy_gate_demo.py --steps 200 --glyph-every 25
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

from swarmrl.tasks.stigmergic_entropy_gate import (  # noqa: E402
    EntropyGateConfig,
    StigmergicEntropyGate,
)


@dataclass
class DemoAgent:
    pos: np.ndarray
    heading: float
    reward: float = 0.0

    def step(self, rng: np.random.Generator, task: StigmergicEntropyGate) -> None:
        self.heading += float(rng.normal(0.0, 0.35))
        sensory = task.sense_field(self.pos)
        speed = 0.012 + 0.018 * np.tanh(sensory)
        delta = np.array([math.cos(self.heading), math.sin(self.heading)], dtype=np.float32)
        self.pos = np.clip(self.pos + speed * delta, 0.0, 1.0)


def build_agents(n_agents: int, rng: np.random.Generator) -> list[DemoAgent]:
    return [
        DemoAgent(
            pos=rng.uniform(0.05, 0.95, size=2).astype(np.float32),
            heading=float(rng.uniform(0.0, 2.0 * math.pi)),
        )
        for _ in range(n_agents)
    ]


def run_demo(
    *,
    n_agents: int = 32,
    steps: int = 200,
    glyph_every: int = 25,
    seed: int = 555,
    clear: bool = True,
) -> dict:
    rng = np.random.default_rng(seed)
    task = StigmergicEntropyGate(
        EntropyGateConfig(
            deposit_strength=0.2,
            decay=0.97,
        )
    )
    agents = build_agents(n_agents, rng)

    for step in range(steps):
        for agent in agents:
            agent.step(rng, task)

        positions = np.array([agent.pos for agent in agents], dtype=np.float32)
        rewards = task.step(positions)
        for agent, reward in zip(agents, rewards):
            agent.reward += float(reward)

        if glyph_every and step % glyph_every == 0:
            if clear:
                print("\033[H\033[J", end="")
            print(task.glyph())
            print(f"\nstep={step} field_max={task.field.max():.6f}")

    return {
        "agents": n_agents,
        "steps": steps,
        "field_max": float(task.field.max()),
        "reward_total": float(sum(agent.reward for agent in agents)),
        "glyph": task.glyph(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run live stigmergic entropy gate demo")
    parser.add_argument("--agents", type=int, default=32)
    parser.add_argument("--steps", type=int, default=200)
    parser.add_argument("--glyph-every", type=int, default=25)
    parser.add_argument("--seed", type=int, default=555)
    parser.add_argument("--no-clear", action="store_true")
    args = parser.parse_args()

    result = run_demo(
        n_agents=args.agents,
        steps=args.steps,
        glyph_every=args.glyph_every,
        seed=args.seed,
        clear=not args.no_clear,
    )
    print(
        f"\nPASS field_max={result['field_max']:.6f} "
        f"reward_total={result['reward_total']:.6f}"
    )


if __name__ == "__main__":
    main()
