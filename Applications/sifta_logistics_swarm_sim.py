#!/usr/bin/env python3
"""
sifta_logistics_swarm_sim.py — Stigmergic Logistics Swarm (CPU-only)
====================================================================

Goal: prove "spatial state evaluation" overnight on M1 (8GB) without GPUs.

Model:
- 2D grid with friction + obstacles
- Pheromone matrix that evaporates
- N swimmers (agents) perform ant-colony routing:
  depot -> delivery -> depot, depositing pheromone on return
- Dynamic congestion: periodically perturb friction/obstacles to force re-route

Economy (simulation ledger):
- Per completed roundtrip, mint a small UTILITY_MINT to swimmer owner id.
- Per step, "spend" micro-cost is only used for scoring; we do NOT write
  micro-txs to the real ledger.

Outputs:
- Metrics JSONL (headless) to .sifta/logistics/metrics.jsonl
- Optional matplotlib visualization (lightweight; default off)

Run:
  python3 Applications/sifta_logistics_swarm_sim.py --demo
  python3 Applications/sifta_logistics_swarm_sim.py --ticks 200000 --agents 256 --grid 256
"""

from __future__ import annotations

import argparse
import json
import os
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
SYS_DIR = REPO_ROOT / "System"


def _now() -> int:
    return int(time.time())


class JsonlOut:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # locked append
        import sys

        if str(SYS_DIR) not in sys.path:
            sys.path.insert(0, str(SYS_DIR))
        from ledger_append import append_jsonl_line  # type: ignore

        self._append = append_jsonl_line

    def append(self, row: Dict[str, Any]) -> None:
        self._append(self.path, row)


@dataclass
class Config:
    grid: int = 256
    agents: int = 256
    deliveries: int = 6
    obstacle_pct: float = 0.06
    evap: float = 0.004
    deposit: float = 2.0
    explore: float = 0.18
    congestion_every: int = 4000
    metrics_every: int = 200
    seed: int = 1337


def _rand_free_cell(blocked: np.ndarray, rng: np.random.Generator) -> Tuple[int, int]:
    n = blocked.shape[0]
    while True:
        x = int(rng.integers(0, n))
        y = int(rng.integers(0, n))
        if not blocked[x, y]:
            return x, y


def _neighbors4(x: int, y: int, n: int) -> List[Tuple[int, int]]:
    out = []
    if x > 0:
        out.append((x - 1, y))
    if x < n - 1:
        out.append((x + 1, y))
    if y > 0:
        out.append((x, y - 1))
    if y < n - 1:
        out.append((x, y + 1))
    return out


def _choose_move(
    x: int,
    y: int,
    n: int,
    blocked: np.ndarray,
    pher: np.ndarray,
    friction: np.ndarray,
    target: Tuple[int, int],
    explore: float,
    rng: np.random.Generator,
) -> Tuple[int, int]:
    cand = []
    for nx, ny in _neighbors4(x, y, n):
        if blocked[nx, ny]:
            continue
        # Heuristic: prefer lower friction and higher pheromone
        p = float(pher[nx, ny])
        f = float(friction[nx, ny])
        dist = abs(nx - target[0]) + abs(ny - target[1])
        score = (1.0 + p) / (1.0 + f) / (1.0 + 0.25 * dist)
        cand.append((nx, ny, score))
    if not cand:
        return x, y
    if rng.random() < explore:
        nx, ny, _ = cand[int(rng.integers(0, len(cand)))]
        return nx, ny
    scores = np.array([c[2] for c in cand], dtype=np.float64)
    s = float(scores.sum())
    if s <= 0:
        nx, ny, _ = max(cand, key=lambda t: t[2])
        return nx, ny
    probs = scores / s
    idx = int(rng.choice(len(cand), p=probs))
    nx, ny, _ = cand[idx]
    return nx, ny


def _inject_congestion(blocked: np.ndarray, friction: np.ndarray, rng: np.random.Generator) -> Dict[str, Any]:
    n = blocked.shape[0]
    # flip a small patch of obstacles and randomize friction in a strip
    patch = max(4, n // 32)
    x0 = int(rng.integers(0, n - patch))
    y0 = int(rng.integers(0, n - patch))
    sub = blocked[x0 : x0 + patch, y0 : y0 + patch]
    # toggle ~35% cells in patch
    mask = rng.random(sub.shape) < 0.35
    sub[mask] = ~sub[mask]

    # friction wave
    x1 = int(rng.integers(0, n))
    width = max(2, n // 64)
    xs = slice(max(0, x1 - width), min(n, x1 + width))
    friction[xs, :] = 0.2 + 2.2 * rng.random((friction[xs, :].shape[0], n), dtype=np.float32)
    return {"patch": [x0, y0, patch], "wave_x": x1, "wave_w": width}


def _mint_sim_reward(ledger: JsonlOut, owner_id: str, amount: float, reason: str) -> None:
    ledger.append(
        {
            "event": "UTILITY_MINT",
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "miner_id": owner_id,
            "amount_stgm": float(amount),
            "reason": reason,
        }
    )


def run(cfg: Config, ticks: int, out_dir: Path, demo: bool = False) -> int:
    rng = np.random.default_rng(cfg.seed)
    random.seed(cfg.seed)

    out_dir.mkdir(parents=True, exist_ok=True)
    metrics = JsonlOut(out_dir / "metrics.jsonl")
    econ = JsonlOut(out_dir / "sim_ledger.jsonl")

    n = int(cfg.grid)
    # RAM control: float32 matrices
    pher = np.zeros((n, n), dtype=np.float32)
    friction = (0.2 + 0.8 * rng.random((n, n), dtype=np.float32)).astype(np.float32)
    blocked = (rng.random((n, n)) < float(cfg.obstacle_pct))

    depot = (n // 2, n // 2)
    blocked[depot[0], depot[1]] = False

    deliveries: List[Tuple[int, int]] = []
    for _ in range(int(cfg.deliveries)):
        x, y = _rand_free_cell(blocked, rng)
        deliveries.append((x, y))

    # agent state
    ax = np.full((cfg.agents,), depot[0], dtype=np.int32)
    ay = np.full((cfg.agents,), depot[1], dtype=np.int32)
    phase = np.zeros((cfg.agents,), dtype=np.int8)  # 0 going to delivery, 1 returning
    target_idx = rng.integers(0, len(deliveries), size=(cfg.agents,), dtype=np.int32)
    steps = np.zeros((cfg.agents,), dtype=np.int32)
    cost = np.zeros((cfg.agents,), dtype=np.float32)

    # "owners" for demo bookkeeping
    owners = ["ARCHITECT_M1", "ARCHITECT_M5", "M1THER", "HERMES"]
    agent_owner = np.array([owners[i % len(owners)] for i in range(cfg.agents)], dtype=object)

    completed = 0
    start_ts = _now()

    for t in range(1, ticks + 1):
        # evaporation
        pher *= (1.0 - float(cfg.evap))

        for i in range(cfg.agents):
            tx, ty = deliveries[int(target_idx[i])]
            target = (tx, ty) if phase[i] == 0 else depot

            nx, ny = _choose_move(
                int(ax[i]),
                int(ay[i]),
                n,
                blocked,
                pher,
                friction,
                target,
                float(cfg.explore),
                rng,
            )

            # apply move
            ax[i], ay[i] = nx, ny
            steps[i] += 1
            cost[i] += float(friction[nx, ny])

            # reached checkpoint?
            if phase[i] == 0 and (nx, ny) == (tx, ty):
                phase[i] = 1
            elif phase[i] == 1 and (nx, ny) == depot:
                # completed roundtrip: deposit pheromone proportional to efficiency
                eff = 1.0 / max(1.0, float(cost[i]))
                pher[nx, ny] += float(cfg.deposit) * eff * 50.0
                completed += 1
                owner = str(agent_owner[i])
                _mint_sim_reward(econ, owner, 0.05, "LOGISTICS_ROUNDTRIP")

                # reset for next job
                phase[i] = 0
                target_idx[i] = int(rng.integers(0, len(deliveries)))
                steps[i] = 0
                cost[i] = 0.0

        # dynamic congestion injection
        cong = None
        if cfg.congestion_every > 0 and t % int(cfg.congestion_every) == 0:
            cong = _inject_congestion(blocked, friction, rng)

        # metrics
        if t % int(cfg.metrics_every) == 0 or t == 1:
            # crude efficiency proxy: pheromone peak and average friction around depot
            peak = float(np.max(pher))
            local = friction[depot[0] - 2 : depot[0] + 3, depot[1] - 2 : depot[1] + 3]
            local_f = float(np.mean(local))
            row = {
                "ts": _now(),
                "t": t,
                "grid": n,
                "agents": int(cfg.agents),
                "deliveries": len(deliveries),
                "completed_roundtrips": int(completed),
                "pheromone_peak": peak,
                "local_friction": local_f,
                "evap": float(cfg.evap),
                "explore": float(cfg.explore),
            }
            if cong:
                row["congestion"] = cong
            metrics.append(row)

    dur = max(1, _now() - start_ts)
    print(
        f"[LOGISTICS] ticks={ticks} grid={n} agents={cfg.agents} completed={completed} "
        f"rate={completed/dur:.2f}/s out={out_dir}"
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--ticks", type=int, default=10000)
    ap.add_argument("--grid", type=int, default=256)
    ap.add_argument("--agents", type=int, default=256)
    ap.add_argument("--deliveries", type=int, default=6)
    ap.add_argument("--obstacle-pct", type=float, default=0.06)
    ap.add_argument("--evap", type=float, default=0.004)
    ap.add_argument("--deposit", type=float, default=2.0)
    ap.add_argument("--explore", type=float, default=0.18)
    ap.add_argument("--congestion-every", type=int, default=4000)
    ap.add_argument("--metrics-every", type=int, default=200)
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--out", type=str, default=str(REPO_ROOT / ".sifta" / "logistics"))
    args = ap.parse_args()

    cfg = Config(
        grid=args.grid,
        agents=args.agents,
        deliveries=args.deliveries,
        obstacle_pct=args.obstacle_pct,
        evap=args.evap,
        deposit=args.deposit,
        explore=args.explore,
        congestion_every=args.congestion_every,
        metrics_every=args.metrics_every,
        seed=args.seed,
    )

    out_dir = Path(args.out).expanduser()
    return run(cfg, int(args.ticks), out_dir, demo=bool(args.demo))


if __name__ == "__main__":
    raise SystemExit(main())

