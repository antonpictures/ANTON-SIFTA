#!/usr/bin/env python3
"""
Standalone anticipatory stigmergy demo.

Two local swarms move toward each other, write future occupancy traces, and
receive collision-risk / surprise pressure from the premonition field.
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

from System.swarm_stigmergic_premonition import (  # noqa: E402
    PremonitionConfig,
    StigmergicPremonitionField,
)


@dataclass
class PremonitionDemoAgent:
    pos: np.ndarray
    velocity: np.ndarray
    reward: float = 0.0

    def step(self, field: StigmergicPremonitionField) -> None:
        future_density, surprise = field.sense(np.array([self.pos], dtype=np.float32))[0]
        avoidance = np.array([-self.velocity[1], self.velocity[0]], dtype=np.float32)
        steer = 0.01 * np.tanh(future_density) * avoidance
        damp = 1.0 / (1.0 + 0.2 * surprise)
        self.pos = np.clip(self.pos + (self.velocity + steer) * damp, 0.0, 1.0)


def _build_agents(n_agents: int) -> list[PremonitionDemoAgent]:
    half = max(1, n_agents // 2)
    agents: list[PremonitionDemoAgent] = []
    for idx in range(half):
        y = 0.35 + (0.30 * idx / max(half - 1, 1))
        agents.append(
            PremonitionDemoAgent(
                pos=np.array([0.15, y], dtype=np.float32),
                velocity=np.array([0.018, 0.0], dtype=np.float32),
            )
        )
    for idx in range(n_agents - half):
        y = 0.35 + (0.30 * idx / max(n_agents - half - 1, 1))
        agents.append(
            PremonitionDemoAgent(
                pos=np.array([0.85, y], dtype=np.float32),
                velocity=np.array([-0.018, 0.0], dtype=np.float32),
            )
        )
    return agents


def run_demo(
    *,
    n_agents: int = 12,
    steps: int = 80,
    glyph_every: int = 20,
    seed: int = 555,
    clear: bool = True,
) -> dict:
    _ = np.random.default_rng(seed)  # reserved for future stochastic steering.
    field = StigmergicPremonitionField(
        PremonitionConfig(grid_size=64, horizon=10, decay=0.955, diffusion=0.03)
    )
    agents = _build_agents(n_agents)

    for step in range(steps):
        for agent in agents:
            agent.step(field)
        positions = np.array([agent.pos for agent in agents], dtype=np.float32)
        rewards = field.step(positions)
        for agent, reward in zip(agents, rewards):
            agent.reward += float(reward)

        if glyph_every and step % glyph_every == 0:
            if clear:
                print("\033[H\033[J", end="")
            print(field.glyph("future"))
            print(
                f"\nstep={step} future={field.future.max():.4f} "
                f"surprise={field.surprise.max():.4f}"
            )

    return {
        "future_max": float(field.future.max()),
        "surprise_max": float(field.surprise.max()),
        "reward_total": float(sum(agent.reward for agent in agents)),
        "glyph": field.glyph("future"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local stigmergic premonition demo")
    parser.add_argument("--agents", type=int, default=12)
    parser.add_argument("--steps", type=int, default=80)
    parser.add_argument("--glyph-every", type=int, default=20)
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
        f"\nPASS future={result['future_max']:.6f} "
        f"surprise={result['surprise_max']:.6f} "
        f"reward_total={result['reward_total']:.6f}"
    )


if __name__ == "__main__":
    main()
