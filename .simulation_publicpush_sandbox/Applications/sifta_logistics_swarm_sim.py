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
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519

REPO_ROOT = Path(__file__).resolve().parent.parent
SYS_DIR = REPO_ROOT / "System"

GOODFELLAS_LORE = (
    "GOODFELLAS CHECK: \"Hey, did you see that? Two ... just stole my truck. "
    "Can you f believe that?\" — in this sim, the immune membrane rejects forged waybills. "
    "The territory is the law. The ledger remembers."
)


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
    hijack_rate: float = 0.002  # per-tick probability of a forged completion attempt (simulated)


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


class WaybillKeys:
    """Simulation-only keys for delivery waybills (anti 'stolen truck' completion forging)."""

    def __init__(self, owners: List[str], seed: int) -> None:
        rng = np.random.default_rng(seed + 777)
        self._priv: Dict[str, ed25519.Ed25519PrivateKey] = {}
        for o in owners:
            # deterministic-ish: derive key from rng bytes to keep demos repeatable
            sk = ed25519.Ed25519PrivateKey.generate()
            self._priv[o] = sk

    def sign(self, owner: str, payload: str) -> bytes:
        return self._priv[owner].sign(payload.encode("utf-8"))

    def verify(self, owner: str, payload: str, sig: bytes) -> bool:
        try:
            self._priv[owner].public_key().verify(sig, payload.encode("utf-8"))
            return True
        except InvalidSignature:
            return False


def _waybill_payload(owner: str, agent_idx: int, delivery: Tuple[int, int], depot: Tuple[int, int], issued_at: int) -> str:
    return f"WAYBILL::OWNER[{owner}]::AGENT[{agent_idx}]::DELIV[{delivery[0]},{delivery[1]}]::DEPOT[{depot[0]},{depot[1]}]::TS[{issued_at}]"


def run(
    cfg: Config,
    ticks: int,
    out_dir: Path,
    demo: bool = False,
    visual: bool = False,
    render_every: int = 200,
) -> int:
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
    waybill_keys = WaybillKeys(owners, cfg.seed)

    # per-agent waybill state (issued at delivery, verified at depot)
    wb_sig: List[bytes | None] = [None for _ in range(cfg.agents)]
    wb_issued: np.ndarray = np.zeros((cfg.agents,), dtype=np.int64)

    hijack_attempts = 0
    hijack_blocked = 0

    completed = 0
    start_ts = _now()

    print(f"[LOGISTICS] {GOODFELLAS_LORE}")
    ui = None
    peak_history: List[float] = []
    completed_history: List[float] = []
    if visual:
        try:
            import sys

            if str(SYS_DIR) not in sys.path:
                sys.path.insert(0, str(SYS_DIR))
            import matplotlib.pyplot as plt  # type: ignore
            from sim_lab_theme import (  # type: ignore
                LAB_BAD,
                LAB_CYAN,
                LAB_OK,
                apply_matplotlib_lab_style,
                cmap_pheromone,
                ensure_matplotlib,
                legend_lab,
                neon_suptitle,
                sparkline_update,
                style_axis_lab,
            )

            ensure_matplotlib("Logistics Swarm — or use --headless")
            apply_matplotlib_lab_style()
            plt.ion()
            fig = plt.figure(figsize=(11, 9))
            gs = fig.add_gridspec(2, 2, height_ratios=[5, 1.1], width_ratios=[3, 1])
            axp = fig.add_subplot(gs[0, :])
            ax_peak = fig.add_subplot(gs[1, 0])
            ax_done = fig.add_subplot(gs[1, 1])
            style_axis_lab(axp, "")
            style_axis_lab(ax_peak, "")
            style_axis_lab(ax_done, "")
            neon_suptitle(
                fig,
                "SIFTA LOGISTICS — STIGMERGIC LAB",
                "pheromone field + waybill verification + live traces",
            )
            ph_cmap = cmap_pheromone()
            img = axp.imshow(pher, cmap=ph_cmap, vmin=0.0, vmax=2.5, interpolation="nearest")
            obs_xy = np.argwhere(blocked)
            if len(obs_xy) > 0:
                obs_sc = axp.scatter(obs_xy[:, 1], obs_xy[:, 0], s=1, c=LAB_CYAN, alpha=0.2)
            else:
                obs_sc = None
            del_sc = axp.scatter(
                [d[1] for d in deliveries],
                [d[0] for d in deliveries],
                s=72,
                c=LAB_OK,
                marker="s",
                label="Deliveries",
                edgecolors="#b4f28a",
                linewidths=0.4,
            )
            dep_sc = axp.scatter(
                [depot[1]],
                [depot[0]],
                s=100,
                c=LAB_BAD,
                marker="*",
                label="Depot",
                edgecolors="#ff9494",
                linewidths=0.5,
            )
            ag_sc = axp.scatter(ay, ax, s=9, c="#7aa2f7", alpha=0.85, label="Swimmers", linewidths=0)
            title = axp.set_title("field + agents", color="#c0caf5", fontsize=10)
            legend_lab(axp, loc="upper right", fontsize=7)
            axp.set_xticks([])
            axp.set_yticks([])
            plt.colorbar(img, ax=axp, fraction=0.035, pad=0.02, label="τ trace")
            fig.tight_layout(rect=[0, 0, 1, 0.93])
            ui = {
                "plt": plt,
                "fig": fig,
                "ax": axp,
                "ax_peak": ax_peak,
                "ax_done": ax_done,
                "img": img,
                "ag_sc": ag_sc,
                "title": title,
                "obs_sc": obs_sc,
                "del_sc": del_sc,
                "dep_sc": dep_sc,
                "peak_hist": peak_history,
                "done_hist": completed_history,
            }
        except Exception as e:
            print(f"[LOGISTICS] visual mode unavailable, continuing headless: {e}")
            ui = None

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
                # issue a signed waybill at delivery pickup
                owner = str(agent_owner[i])
                issued_at = _now()
                wb_issued[i] = issued_at
                payload = _waybill_payload(owner, i, (tx, ty), depot, issued_at)
                wb_sig[i] = waybill_keys.sign(owner, payload)
            elif phase[i] == 1 and (nx, ny) == depot:
                # verify waybill at depot — prevents "stolen truck" forged completions
                owner = str(agent_owner[i])
                sig = wb_sig[i]
                issued_at = int(wb_issued[i])
                payload = _waybill_payload(owner, i, (tx, ty), depot, issued_at)
                ok_waybill = bool(sig) and waybill_keys.verify(owner, payload, sig) and (abs(_now() - issued_at) < 6 * 3600)
                if ok_waybill:
                    # completed roundtrip: deposit pheromone proportional to efficiency
                    eff = 1.0 / max(1.0, float(cost[i]))
                    pher[nx, ny] += float(cfg.deposit) * eff * 50.0
                    completed += 1
                    _mint_sim_reward(econ, owner, 0.05, "LOGISTICS_ROUNDTRIP")
                else:
                    hijack_blocked += 1

                # reset for next job
                phase[i] = 0
                target_idx[i] = int(rng.integers(0, len(deliveries)))
                steps[i] = 0
                cost[i] = 0.0
                wb_sig[i] = None
                wb_issued[i] = 0

        # simulated hijack attempts: forged completion claims (should be rejected)
        if cfg.hijack_rate > 0 and rng.random() < float(cfg.hijack_rate):
            hijack_attempts += 1
            victim = int(rng.integers(0, cfg.agents))
            # attacker tries to claim victim completion with wrong owner or invalid signature
            wrong_owner = str(owners[(victim + 1) % len(owners)])
            payload = _waybill_payload(wrong_owner, victim, deliveries[int(target_idx[victim])], depot, _now())
            forged_sig = b"\x00" * 64
            if not waybill_keys.verify(wrong_owner, payload, forged_sig):
                hijack_blocked += 1

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
                "hijack_attempts": int(hijack_attempts),
                "hijack_blocked": int(hijack_blocked),
            }
            if cong:
                row["congestion"] = cong
            metrics.append(row)

        if ui and (t % max(1, int(render_every)) == 0 or t == 1 or t == ticks):
            ui["img"].set_data(pher)
            ui["img"].set_clim(0.0, max(0.5, float(np.percentile(pher, 99.5))))
            ui["ag_sc"].set_offsets(np.c_[ay, ax])
            ui["title"].set_text(
                f"t={t}/{ticks}  roundtrips={completed}  hijack_block={hijack_blocked}/{hijack_attempts}  peak_τ={float(np.max(pher)):.2f}"
            )
            ph = float(np.max(pher))
            ui["peak_hist"].append(ph)
            ui["done_hist"].append(float(completed))
            if len(ui["peak_hist"]) > 320:
                ui["peak_hist"].pop(0)
                ui["done_hist"].pop(0)
            sparkline_update(ui["ax_peak"], ui["peak_hist"], color=LAB_CYAN, ylabel="peak τ")
            sparkline_update(ui["ax_done"], ui["done_hist"], color=LAB_OK, ylabel="Σ trips")
            ui["fig"].canvas.draw_idle()
            ui["plt"].pause(0.001)

    dur = max(1, _now() - start_ts)
    print(
        f"[LOGISTICS] ticks={ticks} grid={n} agents={cfg.agents} completed={completed} "
        f"rate={completed/dur:.2f}/s hijack_blocked={hijack_blocked} out={out_dir}"
    )
    if ui:
        try:
            ui["plt"].ioff()
            ui["plt"].show()
        except Exception:
            pass
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
    ap.add_argument("--hijack-rate", type=float, default=0.002, help="Probability per tick of a forged completion attempt.")
    ap.add_argument("--visual", action="store_true", help="Enable live matplotlib visualization.")
    ap.add_argument("--headless", action="store_true", help="Force no GUI (default if --visual not set).")
    ap.add_argument("--render-every", type=int, default=200, help="UI refresh cadence in ticks.")
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
        hijack_rate=args.hijack_rate,
    )

    out_dir = Path(args.out).expanduser()
    visual = bool(args.visual) and not bool(args.headless)
    return run(
        cfg,
        int(args.ticks),
        out_dir,
        demo=bool(args.demo),
        visual=visual,
        render_every=int(args.render_every),
    )


if __name__ == "__main__":
    raise SystemExit(main())

