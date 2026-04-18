#!/usr/bin/env python3
"""
sifta_urban_resilience_sim.py — Urban resilience (traffic + disaster drones)
=============================================================================

Two coupled stigmergic layers on one grid:
- **Traffic**: vehicles on roads (left city), sense congestion, deposit/follow traces.
- **Disaster**: drones in a rubble-strewn zone (right), breadcrumbs avoid re-covering
  the same ground; coverage and frontier exploration tighten as rubble rises.

This is a local simulation stress test — no external services.

Outputs under `.sifta/urban/` (metrics + simulation-only UTILITY_MINT), not `repair_log.jsonl`.

Run:
  python3 Applications/sifta_urban_resilience_sim.py --ticks 8000
  python3 Applications/sifta_urban_resilience_sim.py --headless --stress --ticks 50000
"""
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
_SYS = REPO_ROOT / "System"
SYS_DIR = REPO_ROOT / "System"
if str(SYS_DIR) not in sys.path:
    sys.path.insert(0, str(SYS_DIR))


@dataclass
class UrbanConfig:
    width: int = 112
    height: int = 72
    split_fraction: float = 0.52
    road_stride: int = 5
    rubble_frac: float = 0.36
    n_vehicles: int = 380
    n_drones: int = 140
    evap_road: float = 0.018
    evap_drone: float = 0.022
    deposit_road: float = 0.9
    deposit_drone: float = 1.1
    explore_traffic: float = 0.12
    explore_drone: float = 0.1
    congestion_penalty: float = 2.5
    revisit_penalty: float = 3.0
    frontier_bonus: float = 2.0
    seed: int = 4242


class JsonlOut:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        from ledger_append import append_jsonl_line

        self._append = append_jsonl_line

    def append(self, row: Dict[str, Any]) -> None:
        self._append(self.path, row)


def _neighbors4(y: int, x: int, h: int, w: int) -> List[Tuple[int, int]]:
    out: List[Tuple[int, int]] = []
    if y > 0:
        out.append((y - 1, x))
    if y < h - 1:
        out.append((y + 1, x))
    if x > 0:
        out.append((y, x - 1))
    if x < w - 1:
        out.append((y, x + 1))
    return out


def build_world(cfg: UrbanConfig) -> Dict[str, np.ndarray]:
    rng = np.random.default_rng(cfg.seed)
    h, w = int(cfg.height), int(cfg.width)
    split = max(3, int(w * float(cfg.split_fraction)))

    # Urban roads: grid + jitter connectors
    road = np.zeros((h, w), dtype=np.bool_)
    stride = max(3, int(cfg.road_stride))
    for y in range(0, h, stride):
        road[y, :split] = True
    for x in range(0, split, stride):
        road[:, x] = True
    # random shortcuts
    for _ in range(max(8, h * w // 800)):
        y = int(rng.integers(2, h - 2))
        x = int(rng.integers(2, max(3, split - 2)))
        if split - x > 6:
            ln = int(rng.integers(4, min(20, split - x)))
            road[y, x : x + ln] = True
        x2 = int(rng.integers(2, max(3, split - 2)))
        y2 = int(rng.integers(2, h - 2))
        if h - y2 > 6:
            ln2 = int(rng.integers(4, min(12, h - y2)))
            road[y2 : y2 + ln2, x2] = True

    # Buildings = not road in urban
    building = np.zeros((h, w), dtype=np.bool_)
    building[:, :split] = ~road[:, :split]

    # Disaster zone: passable floor + rubble
    disaster_open = np.zeros((h, w), dtype=np.bool_)
    disaster_open[:, split:] = True
    rubble = (rng.random((h, w)) < float(cfg.rubble_frac))
    rubble[:, :split] = False
    disaster_open &= ~rubble

    # Ensure depot and band into disaster
    depot_y, depot_x = h // 2, split
    if depot_x >= w:
        depot_x = w - 2
    disaster_open[depot_y, depot_x] = True
    disaster_open[depot_y, depot_x - 1] = True
    # carve a corridor from split-1 to split
    road[depot_y, split - 3 : split + 1] = True
    building[depot_y, split - 3 : split] = False
    disaster_open[depot_y, split : split + 3] = True

    # Flood-fill disaster from depot to prune unreachable rubble pockets (optional cleanup)
    reachable = np.zeros((h, w), dtype=np.bool_)
    stack = [(depot_y, depot_x)]
    reachable[depot_y, depot_x] = True
    while stack:
        cy, cx = stack.pop()
        for ny, nx in _neighbors4(cy, cx, h, w):
            if nx < split:
                continue
            if not disaster_open[ny, nx] or reachable[ny, nx]:
                continue
            reachable[ny, nx] = True
            stack.append((ny, nx))
    disaster_open &= reachable | (np.arange(w)[None, :] < split)

    # Intersections: road cells with >= 3 road neighbors (urban)
    isect = np.zeros((h, w), dtype=np.bool_)
    for y in range(1, h - 1):
        for x in range(1, split - 1):
            if not road[y, x]:
                continue
            rn = sum(1 for ny, nx in _neighbors4(y, x, h, w) if road[ny, nx])
            if rn >= 3:
                isect[y, x] = True

    return {
        "road": road,
        "building": building,
        "disaster_open": disaster_open,
        "split": split,
        "depot": (depot_y, depot_x),
        "intersection": isect,
        "rubble": rubble,
    }


class UrbanResilienceSim:
    def __init__(self, cfg: UrbanConfig) -> None:
        self.cfg = cfg
        self.rng = np.random.default_rng(cfg.seed)
        self.world = build_world(cfg)
        self.h, self.w = int(cfg.height), int(cfg.width)
        self.split = int(self.world["split"])
        dy, dx = self.world["depot"]
        self.depot = (int(dy), int(dx))

        self.road = self.world["road"]
        self.disaster_open = self.world["disaster_open"]
        self.isect = self.world["intersection"]

        self.pher_road = np.zeros((self.h, self.w), dtype=np.float32)
        self.pher_drone = np.zeros((self.h, self.w), dtype=np.float32)
        self.visited = np.zeros((self.h, self.w), dtype=np.int32)
        self.light_phase = 0

        self.disaster_passable_count = int(np.sum(self.disaster_open[:, self.split :]))

        # Vehicles: positions on road (urban)
        ry, rx = np.where(self.road[:, : self.split])
        if len(ry) == 0:
            raise RuntimeError("no roads generated")
        pick = self.rng.choice(len(ry), size=min(cfg.n_vehicles, len(ry)), replace=True)
        self.vy = ry[pick].astype(np.int32)
        self.vx = rx[pick].astype(np.int32)

        # Drones: start near depot in disaster
        dy, dx = self.depot
        d_positions = [(dy, dx)]
        for ny, nx in _neighbors4(dy, dx, self.h, self.w):
            if nx >= self.split and self.disaster_open[ny, nx]:
                d_positions.append((ny, nx))
        if len(d_positions) < max(4, cfg.n_drones // 10):
            oy, ox = np.where(self.disaster_open)
            for i in range(min(len(oy), 50)):
                d_positions.append((int(oy[i]), int(ox[i])))
        pick_d = self.rng.choice(len(d_positions), size=min(cfg.n_drones, len(d_positions)), replace=True)
        self.dy = np.array([d_positions[i][0] for i in pick_d], dtype=np.int32)
        self.dx = np.array([d_positions[i][1] for i in pick_d], dtype=np.int32)

        self.tick = 0
        self.total_vehicle_moves = 0
        self.total_drone_moves = 0
        self.jam_events = 0

    def _traffic_light_allows(self, y: int, x: int, ny: int, nx: int) -> bool:
        if not self.isect[y, x]:
            return True
        # Alternate NS vs EW every 14 ticks (stylised coordination)
        ns_ok = (self.light_phase % 28) < 14
        if ny != y:
            return ns_ok
        return not ns_ok

    def _step_vehicles(self) -> None:
        cfg = self.cfg
        occ = np.zeros((self.h, self.w), dtype=np.int32)
        for i in range(len(self.vy)):
            occ[int(self.vy[i]), int(self.vx[i])] += 1

        new_y = self.vy.copy()
        new_x = self.vx.copy()
        for i in range(len(self.vy)):
            y, x = int(self.vy[i]), int(self.vx[i])
            cand = []
            for ny, nx in _neighbors4(y, x, self.h, self.w):
                if nx >= self.split or not self.road[ny, nx]:
                    continue
                if not self._traffic_light_allows(y, x, ny, nx):
                    continue
                cong = int(occ[ny, nx])
                ph = float(self.pher_road[ny, nx])
                score = (1.0 + ph * 0.4) * np.exp(-cfg.congestion_penalty * 0.08 * cong)
                cand.append((ny, nx, score))
            if not cand:
                continue
            if self.rng.random() < cfg.explore_traffic:
                j = int(self.rng.integers(0, len(cand)))
            else:
                s = np.array([c[2] for c in cand], dtype=np.float64)
                s = s / (s.sum() + 1e-12)
                j = int(self.rng.choice(len(cand), p=s))
            ny, nx = cand[j][0], cand[j][1]
            old_occ = int(occ[y, x])
            if old_occ > 4:
                self.jam_events += 1
            occ[y, x] -= 1
            occ[ny, nx] += 1
            new_y[i], new_x[i] = ny, nx
            self.pher_road[ny, nx] += float(cfg.deposit_road) / (1.0 + 0.15 * occ[ny, nx])
            self.total_vehicle_moves += 1
        self.vy, self.vx = new_y, new_x
        self.pher_road *= 1.0 - float(cfg.evap_road)

    def _step_drones(self) -> None:
        cfg = self.cfg
        docc = np.zeros((self.h, self.w), dtype=np.int32)
        for i in range(len(self.dy)):
            docc[int(self.dy[i]), int(self.dx[i])] += 1

        new_y = self.dy.copy()
        new_x = self.dx.copy()
        for i in range(len(self.dy)):
            y, x = int(self.dy[i]), int(self.dx[i])
            cand = []
            for ny, nx in _neighbors4(y, x, self.h, self.w):
                if nx < self.split or not self.disaster_open[ny, nx]:
                    continue
                visits = int(self.visited[ny, nx])
                unex = 0
                for n2y, n2x in _neighbors4(ny, nx, self.h, self.w):
                    if n2x < self.split or not self.disaster_open[n2y, n2x]:
                        continue
                    if self.visited[n2y, n2x] == 0:
                        unex += 1
                ph = float(self.pher_drone[ny, nx])
                crowd = int(docc[ny, nx])
                score = (
                    cfg.frontier_bonus * unex
                    + 0.35 * ph
                    - cfg.revisit_penalty * 0.08 * visits
                    - 0.4 * crowd
                )
                cand.append((ny, nx, score))
            if not cand:
                continue
            if self.rng.random() < cfg.explore_drone:
                j = int(self.rng.integers(0, len(cand)))
            else:
                s = np.array([max(0.01, c[2]) for c in cand], dtype=np.float64)
                s = s / (s.sum() + 1e-12)
                j = int(self.rng.choice(len(cand), p=s))
            ny, nx = cand[j][0], cand[j][1]
            docc[y, x] -= 1
            docc[ny, nx] += 1
            new_y[i], new_x[i] = ny, nx
            self.visited[ny, nx] += 1
            self.pher_drone[ny, nx] += float(cfg.deposit_drone) / (1.0 + 0.2 * self.visited[ny, nx])
            self.total_drone_moves += 1
        self.dy, self.dx = new_y, new_x
        self.pher_drone *= 1.0 - float(cfg.evap_drone)

    def step(self) -> Dict[str, float]:
        self.tick += 1
        self.light_phase += 1
        self._step_vehicles()
        self._step_drones()

        sub = self.visited[:, self.split :]
        open_sub = self.disaster_open[:, self.split :]
        explored = int(np.sum((sub > 0) & open_sub))
        cov = explored / max(1, self.disaster_passable_count)

        occ_max = 0
        for y in range(self.h):
            for x in range(min(self.split, self.w)):
                if not self.road[y, x]:
                    continue
                c = int(np.sum((self.vy == y) & (self.vx == x)))
                occ_max = max(occ_max, c)

        return {
            "tick": float(self.tick),
            "coverage": float(cov),
            "explored_cells": float(explored),
            "jam_events": float(self.jam_events),
            "vehicle_moves": float(self.total_vehicle_moves),
            "drone_moves": float(self.total_drone_moves),
            "road_pher_peak": float(np.max(self.pher_road)),
            "drone_pher_peak": float(np.max(self.pher_drone)),
            "max_stack": float(occ_max),
        }


def run_headless(cfg: UrbanConfig, ticks: int, out_dir: Path, metrics_every: int) -> int:
    sim = UrbanResilienceSim(cfg)
    metrics = JsonlOut(out_dir / "metrics.jsonl")
    econ = JsonlOut(out_dir / "sim_ledger.jsonl")
    owners = ["ARCHITECT_M5", "M1THER", "HERMES", "ANTIALICE"]

    for t in range(1, ticks + 1):
        m = sim.step()
        if m["coverage"] >= 0.85 and t % metrics_every == 0:
            econ.append(
                {
                    "event": "UTILITY_MINT",
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "miner_id": owners[t % len(owners)],
                    "amount_stgm": 0.05,
                    "reason": "URBAN_COVERAGE_MILESTONE",
                    "coverage": m["coverage"],
                    "tick": t,
                }
            )
        if t % metrics_every == 0 or t == 1:
            metrics.append({"ts": int(time.time()), **{k: float(v) for k, v in m.items()}})

    print(
        f"[URBAN] ticks={ticks} coverage={m['coverage']*100:.1f}% jam_events={sim.jam_events} "
        f"veh_moves={sim.total_vehicle_moves} drone_moves={sim.total_drone_moves} out={out_dir}"
    )
    return 0


def run_visual(cfg: UrbanConfig, ticks: int, out_dir: Path, metrics_every: int, render_every: int) -> int:
    import sys

    if str(_SYS) not in sys.path:
        sys.path.insert(0, str(_SYS))
    import matplotlib

    try:
        matplotlib.use("MacOSX")
    except Exception:
        pass
    import matplotlib.pyplot as plt
    from sim_lab_theme import apply_matplotlib_lab_style, ensure_matplotlib, neon_suptitle

    ensure_matplotlib("Urban Resilience Simulator")
    apply_matplotlib_lab_style()

    sim = UrbanResilienceSim(cfg)
    metrics = JsonlOut(out_dir / "metrics.jsonl")
    econ = JsonlOut(out_dir / "sim_ledger.jsonl")
    owners = ["ARCHITECT_M5", "M1THER", "HERMES", "ANTIALICE"]
    milestone_sent = False

    fig, axes = plt.subplots(2, 2, figsize=(13, 10))
    fig.canvas.manager.set_window_title("SIFTA — Urban Resilience Simulator")
    neon_suptitle(
        fig,
        "URBAN RESILIENCE LAB",
        "traffic τ · congestion · disaster coverage · drone breadcrumbs",
    )
    for ax in axes.flat:
        ax.set_facecolor("#121620")

    # RGB base map
    rgb = np.zeros((sim.h, sim.w, 3), dtype=np.float32)
    rgb[:, :, 0] = 0.06
    rgb[:, :, 1] = 0.07
    rgb[:, :, 2] = 0.12
    rgb[sim.world["building"], 0] = 0.04
    rgb[sim.world["building"], 1] = 0.05
    rgb[sim.world["building"], 2] = 0.08
    rgb[sim.road, 0] = 0.15
    rgb[sim.road, 1] = 0.16
    rgb[sim.road, 2] = 0.22
    rub = sim.world["rubble"] & (np.arange(sim.w)[None, :] >= sim.split)
    rgb[rub, 0] = 0.35
    rgb[rub, 1] = 0.12
    rgb[rub, 2] = 0.08
    do = sim.disaster_open & (np.arange(sim.w)[None, :] >= sim.split)
    rgb[do, 0] = 0.12
    rgb[do, 1] = 0.18
    rgb[do, 2] = 0.14
    im_main = axes[0, 0].imshow(rgb, origin="upper", interpolation="nearest")
    v_sc = axes[0, 0].scatter(sim.vx, sim.vy, s=6, c="#7aa2f7", alpha=0.85, label="Vehicles")
    d_sc = axes[0, 0].scatter(sim.dx, sim.dy, s=10, c="#bb9af7", alpha=0.9, marker="^", label="Drones")
    axes[0, 0].axvline(sim.split - 0.5, color="#f7768e", linewidth=1.2, alpha=0.7)
    axes[0, 0].set_title("City ⟷ Disaster — swimmers", color="#c0caf5", fontsize=10)
    axes[0, 0].legend(loc="upper right", fontsize=7, facecolor="#1a1b36", labelcolor="#c0caf5")
    axes[0, 0].axis("off")

    pr = np.clip(sim.pher_road / max(1e-6, np.max(sim.pher_road) or 1.0), 0, 1)
    im_pr = axes[0, 1].imshow(pr, cmap="plasma", vmin=0, vmax=1, interpolation="nearest")
    axes[0, 1].set_title("Traffic traces (stigmergic)", color="#c0caf5", fontsize=10)
    axes[0, 1].axis("off")

    cov_layer = np.zeros((sim.h, sim.w), dtype=np.float32)
    cov_layer[:, sim.split :] = np.clip(sim.visited[:, sim.split :].astype(np.float32) / 8.0, 0, 1)
    im_cov = axes[1, 0].imshow(cov_layer, cmap="viridis", vmin=0, vmax=1, interpolation="nearest")
    axes[1, 0].set_title("Disaster coverage (visited intensity)", color="#c0caf5", fontsize=10)
    axes[1, 0].axis("off")

    pd = np.clip(sim.pher_drone / max(1e-6, np.max(sim.pher_drone) or 1.0), 0, 1)
    im_pd = axes[1, 1].imshow(pd, cmap="magma", vmin=0, vmax=1, interpolation="nearest")
    axes[1, 1].set_title("Drone breadcrumbs", color="#c0caf5", fontsize=10)
    axes[1, 1].axis("off")

    hud = fig.suptitle("", color="#bb9af7", fontsize=11, fontfamily="monospace")
    plt.tight_layout(rect=[0, 0, 1, 0.93])

    plt.ion()
    for t in range(1, ticks + 1):
        m = sim.step()
        if m["coverage"] >= 0.85 and not milestone_sent:
            milestone_sent = True
            econ.append(
                {
                    "event": "UTILITY_MINT",
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "miner_id": owners[t % len(owners)],
                    "amount_stgm": 0.05,
                    "reason": "URBAN_COVERAGE_MILESTONE",
                    "coverage": m["coverage"],
                    "tick": t,
                }
            )
        if t % metrics_every == 0 or t == 1:
            metrics.append({"ts": int(time.time()), **{k: float(v) for k, v in m.items()}})

        if t % max(1, render_every) == 0 or t == 1 or t == ticks:
            rgb_u = rgb.copy()
            ly, lx = np.where(sim.isect)
            for iy, ix in zip(ly, lx):
                phase = (sim.light_phase % 28) < 14
                rgb_u[iy, ix, 0] = 0.2 + (0.25 if phase else 0.35)
                rgb_u[iy, ix, 1] = 0.35 if phase else 0.15
                rgb_u[iy, ix, 2] = 0.2
            im_main.set_data(rgb_u)
            v_sc.set_offsets(np.c_[sim.vx, sim.vy])
            d_sc.set_offsets(np.c_[sim.dx, sim.dy])
            pr = np.clip(sim.pher_road / max(1e-6, np.percentile(sim.pher_road[sim.road], 99) or 1.0), 0, 1)
            im_pr.set_data(pr)
            cov_layer[:, sim.split :] = np.clip(sim.visited[:, sim.split :].astype(np.float32) / 10.0, 0, 1)
            im_cov.set_data(cov_layer)
            pd = np.clip(
                sim.pher_drone / max(1e-6, np.percentile(sim.pher_drone[sim.disaster_open], 99) or 1.0),
                0,
                1,
            )
            im_pd.set_data(pd)
            hud.set_text(
                f"URBAN RESILIENCE  t={t}/{ticks}  coverage={m['coverage']*100:.1f}%  "
                f"jams={int(m['jam_events'])}  max_stack={m['max_stack']:.0f}  "
                f"road_φ={m['road_pher_peak']:.1f}  drone_φ={m['drone_pher_peak']:.1f}"
            )
            fig.canvas.draw_idle()
            plt.pause(0.001)

    plt.ioff()
    plt.show()
    print(f"[URBAN] done coverage={m['coverage']*100:.1f}% out={out_dir}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Urban resilience stigmergic simulator")
    ap.add_argument("--ticks", type=int, default=15000)
    ap.add_argument("--width", type=int, default=112)
    ap.add_argument("--height", type=int, default=72)
    ap.add_argument("--vehicles", type=int, default=380)
    ap.add_argument("--drones", type=int, default=140)
    ap.add_argument("--rubble", type=float, default=0.36)
    ap.add_argument("--seed", type=int, default=4242)
    ap.add_argument("--stress", action="store_true", help="Hard preset: more agents, more rubble, tighter roads")
    ap.add_argument("--metrics-every", type=int, default=500)
    ap.add_argument("--render-every", type=int, default=120)
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--out", type=str, default=str(REPO_ROOT / ".sifta" / "urban"))
    args = ap.parse_args()

    rubble = float(args.rubble)
    stride = 5
    nv, nd = int(args.vehicles), int(args.drones)
    if args.stress:
        rubble = min(0.52, rubble + 0.12)
        stride = 6
        nv = int(nv * 1.35)
        nd = int(nd * 1.25)

    cfg = UrbanConfig(
        width=int(args.width),
        height=int(args.height),
        road_stride=stride,
        rubble_frac=rubble,
        n_vehicles=nv,
        n_drones=nd,
        seed=int(args.seed),
    )

    out_dir = Path(args.out).expanduser()
    if args.headless:
        return run_headless(cfg, int(args.ticks), out_dir, int(args.metrics_every))
    return run_visual(cfg, int(args.ticks), out_dir, int(args.metrics_every), int(args.render_every))


if __name__ == "__main__":
    raise SystemExit(main())
