#!/usr/bin/env python3
"""
Standalone immune quorum demo.

Runs a local in-memory wound/repair simulation and prints signal, danger,
repair, or composite glyphs. No hardware spreading, no process control.
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

from System.swarm_immune_quorum import (  # noqa: E402
    ImmuneQuorumConfig,
    SwarmImmuneQuorum,
)


@dataclass
class ImmuneDemoAgent:
    pos: np.ndarray
    heading: float
    reward: float = 0.0

    def step(self, rng: np.random.Generator, quorum: SwarmImmuneQuorum) -> None:
        signal, danger, repair = quorum.sense(np.array([self.pos], dtype=np.float32))[0]
        self.heading += float(rng.normal(0.0, 0.22))
        # Danger recruits motion; repair damps it after the wound starts healing.
        speed = 0.006 + 0.018 * np.tanh(danger + signal) / (1.0 + repair)
        delta = np.array([math.cos(self.heading), math.sin(self.heading)], dtype=np.float32)
        self.pos = np.clip(self.pos + speed * delta, 0.0, 1.0)


def _build_agents(n_agents: int, rng: np.random.Generator) -> list[ImmuneDemoAgent]:
    return [
        ImmuneDemoAgent(
            pos=rng.uniform(0.44, 0.56, size=2).astype(np.float32),
            heading=float(rng.uniform(0.0, 2.0 * math.pi)),
        )
        for _ in range(n_agents)
    ]


def run_demo(
    *,
    n_agents: int = 32,
    steps: int = 120,
    glyph_every: int = 20,
    mode: str = "composite",
    seed: int = 555,
    clear: bool = True,
) -> dict:
    rng = np.random.default_rng(seed)
    quorum = SwarmImmuneQuorum(ImmuneQuorumConfig(grid_size=64, decay=0.982, diffusion=0.04))
    agents = _build_agents(n_agents, rng)
    wound = np.array([[0.5, 0.5]], dtype=np.float32)

    for step in range(steps):
        if step in {1, steps // 2}:
            quorum.inject_damage(wound, radius=0.16)
        for agent in agents:
            agent.step(rng, quorum)
        positions = np.array([agent.pos for agent in agents], dtype=np.float32)
        rewards = quorum.step(positions)
        for agent, reward in zip(agents, rewards):
            agent.reward += float(reward)

        if glyph_every and step % glyph_every == 0:
            if clear:
                print("\033[H\033[J", end="")
            print(quorum.glyph(mode))  # type: ignore[arg-type]
            print(
                f"\nstep={step} signal={quorum.signal.max():.4f} "
                f"danger={quorum.danger.max():.4f} repair={quorum.repair.max():.4f}"
            )

    return {
        "signal_max": float(quorum.signal.max()),
        "danger_max": float(quorum.danger.max()),
        "repair_max": float(quorum.repair.max()),
        "reward_total": float(sum(agent.reward for agent in agents)),
        "glyph": quorum.glyph(mode),  # type: ignore[arg-type]
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local immune quorum demo")
    parser.add_argument("--agents", type=int, default=32)
    parser.add_argument("--steps", type=int, default=120)
    parser.add_argument("--glyph-every", type=int, default=20)
    parser.add_argument("--mode", choices=["composite", "danger", "repair", "signal"], default="composite")
    parser.add_argument("--seed", type=int, default=555)
    parser.add_argument("--no-clear", action="store_true")
    args = parser.parse_args()

    result = run_demo(
        n_agents=args.agents,
        steps=args.steps,
        glyph_every=args.glyph_every,
        mode=args.mode,
        seed=args.seed,
        clear=not args.no_clear,
    )
    print(
        f"\nPASS signal={result['signal_max']:.6f} "
        f"danger={result['danger_max']:.6f} "
        f"repair={result['repair_max']:.6f} "
        f"reward_total={result['reward_total']:.6f}"
    )


if __name__ == "__main__":
    main()
