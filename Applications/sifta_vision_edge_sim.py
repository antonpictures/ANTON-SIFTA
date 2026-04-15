#!/usr/bin/env python3
"""
sifta_vision_edge_sim.py — Stigmergic edge detection on a noisy pixel matrix
============================================================================

Thousands of lightweight swimmers sense 3x3 gradients, deposit pheromones on
edges, evaporate noise, and trace structure from the bottom up.

Simulation-only economy: micro UTILITY_MINT lines go to `.sifta/vision/sim_ledger.jsonl`
(not `repair_log.jsonl`).

Run:
  python3 Applications/sifta_vision_edge_sim.py --ticks 8000
  python3 Applications/sifta_vision_edge_sim.py --headless --ticks 50000 --width 512 --height 512
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Dict

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
_SYS = REPO_ROOT / "System"
SYS_DIR = REPO_ROOT / "System"
if str(SYS_DIR) not in sys.path:
    sys.path.insert(0, str(SYS_DIR))

from vision_processor_worker import VisionConfig, VisionProcessorWorker, synth_topography  # noqa: E402


class JsonlOut:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if str(SYS_DIR) not in sys.path:
            sys.path.insert(0, str(SYS_DIR))
        from ledger_append import append_jsonl_line

        self._append = append_jsonl_line

    def append(self, row: Dict[str, Any]) -> None:
        self._append(self.path, row)


def _mint_edge_work(ledger: JsonlOut, owner_id: str, amount: float, tick: int, edge_hits: int) -> None:
    ledger.append(
        {
            "event": "UTILITY_MINT",
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "miner_id": owner_id,
            "amount_stgm": float(amount),
            "reason": "STIGMERGIC_EDGE_HIT",
            "tick": tick,
            "edge_hits_batch": edge_hits,
        }
    )


def run_headless(
    img: np.ndarray,
    cfg: VisionConfig,
    ticks: int,
    out_dir: Path,
    metrics_every: int,
    mint_every_edges: int,
) -> int:
    worker = VisionProcessorWorker(img, cfg)
    metrics = JsonlOut(out_dir / "metrics.jsonl")
    econ = JsonlOut(out_dir / "sim_ledger.jsonl")
    owners = ["ARCHITECT_M5", "M1THER", "HERMES", "ANTIALICE"]
    pending_edges = 0
    mint_accum = 0

    for t in range(1, ticks + 1):
        m = worker.step()
        pending_edges += int(m["edge_hits_now"])
        mint_accum += int(m["edge_hits_now"])

        if mint_accum >= mint_every_edges:
            batches = mint_accum // mint_every_edges
            mint_accum -= batches * mint_every_edges
            owner = owners[t % len(owners)]
            _mint_edge_work(econ, owner, 0.02 * batches, worker.tick, mint_every_edges * batches)

        if t % metrics_every == 0 or t == 1:
            metrics.append(
                {
                    "ts": int(time.time()),
                    "tick": t,
                    "w": worker.w,
                    "h": worker.h,
                    "swimmers": cfg.swimmers,
                    **{k: m[k] for k in m if k != "tick"},
                }
            )

    print(
        f"[VISION] ticks={ticks} size={worker.w}x{worker.h} swimmers={cfg.swimmers} "
        f"edge_hits_total={worker.edge_hits_total} pher_peak={float(np.max(worker.pher)):.4f} out={out_dir}"
    )
    return 0


def run_visual(
    img: np.ndarray,
    cfg: VisionConfig,
    ticks: int,
    out_dir: Path,
    metrics_every: int,
    mint_every_edges: int,
    render_every: int,
) -> int:
    import sys

    if str(_SYS) not in sys.path:
        sys.path.insert(0, str(_SYS))
    import matplotlib

    try:
        matplotlib.use("MacOSX")
    except Exception:
        pass
    import matplotlib.pyplot as plt
    from sim_lab_theme import (
        apply_matplotlib_lab_style,
        cmap_terrain_lab,
        ensure_matplotlib,
        neon_suptitle,
        style_axis_lab,
    )

    ensure_matplotlib("Stigmergic Edge Vision")
    apply_matplotlib_lab_style()

    worker = VisionProcessorWorker(img, cfg)
    metrics = JsonlOut(out_dir / "metrics.jsonl")
    econ = JsonlOut(out_dir / "sim_ledger.jsonl")
    owners = ["ARCHITECT_M5", "M1THER", "HERMES", "ANTIALICE"]
    mint_accum = 0

    gx = np.abs(np.diff(worker.img, axis=1, prepend=worker.img[:, :1]))
    gy = np.abs(np.diff(worker.img, axis=0, prepend=worker.img[:1, :]))
    grad_mag = np.sqrt(gx * gx + gy * gy)

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.canvas.manager.set_window_title("SIFTA — Stigmergic Edge Vision")
    neon_suptitle(
        fig,
        "DISTRIBUTED VISION LAB",
        "topography | τ edges | RGB fusion | |∇I| oracle (ground-truth contrast)",
    )

    tmap = cmap_terrain_lab()
    im0 = axes[0, 0].imshow(worker.img, cmap=tmap, vmin=0, vmax=1, interpolation="nearest")
    style_axis_lab(axes[0, 0], "Drop zone (noisy topo)")
    axes[0, 0].axis("off")

    ph_max = 2.5
    im1 = axes[0, 1].imshow(worker.pher, cmap="magma", vmin=0, vmax=ph_max, interpolation="nearest")
    style_axis_lab(axes[0, 1], "Emergent τ skeleton (swarm-found)")
    axes[0, 1].axis("off")

    blend = np.stack(
        [
            worker.img,
            np.clip(worker.pher / max(ph_max, 1e-6), 0, 1),
            0.25 * np.ones_like(worker.img),
        ],
        axis=-1,
    )
    im2 = axes[1, 0].imshow(blend, interpolation="nearest")
    sc = axes[1, 0].scatter(worker.sx, worker.sy, s=1, c="#73daca", alpha=0.4, linewidths=0)
    style_axis_lab(axes[1, 0], "Swimmers × structure (RGB)")
    axes[1, 0].axis("off")

    im3 = axes[1, 1].imshow(grad_mag, cmap="inferno", interpolation="nearest")
    style_axis_lab(axes[1, 1], "|∇I| reference (contrast)")
    axes[1, 1].axis("off")

    hud = fig.text(0.5, 0.02, "", ha="center", color="#bb9af7", fontsize=10, family="monospace")
    plt.colorbar(im0, ax=axes[0, 0], fraction=0.046, pad=0.04)
    plt.colorbar(im1, ax=axes[0, 1], fraction=0.046, pad=0.04)
    plt.colorbar(im3, ax=axes[1, 1], fraction=0.046, pad=0.04)
    fig.tight_layout(rect=[0, 0.04, 1, 0.92])

    plt.ion()
    for t in range(1, ticks + 1):
        m = worker.step()
        mint_accum += int(m["edge_hits_now"])
        if mint_accum >= mint_every_edges:
            batches = mint_accum // mint_every_edges
            mint_accum -= batches * mint_every_edges
            owner = owners[t % len(owners)]
            _mint_edge_work(econ, owner, 0.02 * batches, worker.tick, mint_every_edges * batches)

        if t % metrics_every == 0 or t == 1:
            metrics.append(
                {
                    "ts": int(time.time()),
                    "tick": t,
                    "w": worker.w,
                    "h": worker.h,
                    "swimmers": cfg.swimmers,
                    **{k: v for k, v in m.items() if k != "tick"},
                }
            )

        if t % max(1, render_every) == 0 or t == 1 or t == ticks:
            vmax = max(float(np.percentile(worker.pher, 99.5)), 0.5)
            im1.set_clim(0, vmax)
            im1.set_data(worker.pher)
            blend = np.stack(
                [
                    worker.img,
                    np.clip(worker.pher / max(vmax, 1e-6), 0, 1),
                    0.25 * np.ones_like(worker.img),
                ],
                axis=-1,
            )
            im2.set_data(blend)
            sc.set_offsets(np.c_[worker.sx, worker.sy])
            hud.set_text(
                f"tick {t}/{ticks}  edges/step {m['edge_hits_now']}  "
                f"τ_peak {m['pher_peak']:.3f}  Σ_edges {m['edge_hits_total']}"
            )
            fig.canvas.draw_idle()
            plt.pause(0.001)

    plt.ioff()
    plt.show()
    print(
        f"[VISION] ticks={ticks} edge_hits_total={worker.edge_hits_total} out={out_dir}"
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Stigmergic edge detection simulation")
    ap.add_argument("--width", type=int, default=320)
    ap.add_argument("--height", type=int, default=320)
    ap.add_argument("--swimmers", type=int, default=1200)
    ap.add_argument("--ticks", type=int, default=12000)
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--edge-threshold", type=float, default=0.18)
    ap.add_argument("--evaporation", type=float, default=0.015)
    ap.add_argument("--deposit-edge", type=float, default=1.4)
    ap.add_argument("--metrics-every", type=int, default=400)
    ap.add_argument("--mint-every-edges", type=int, default=5000, help="Batch edge hits before sim UTILITY_MINT")
    ap.add_argument("--render-every", type=int, default=80)
    ap.add_argument("--headless", action="store_true", help="No GUI (SSH / batch)")
    ap.add_argument("--out", type=str, default=str(REPO_ROOT / ".sifta" / "vision"))
    args = ap.parse_args()

    w, h = int(args.width), int(args.height)
    img = synth_topography(w, h, int(args.seed))
    cfg = VisionConfig(
        width=w,
        height=h,
        swimmers=int(args.swimmers),
        edge_threshold=float(args.edge_threshold),
        evaporation=float(args.evaporation),
        deposit_edge=float(args.deposit_edge),
        seed=int(args.seed),
    )

    out_dir = Path(args.out).expanduser()

    if args.headless:
        return run_headless(
            img,
            cfg,
            int(args.ticks),
            out_dir,
            int(args.metrics_every),
            int(args.mint_every_edges),
        )
    return run_visual(
        img,
        cfg,
        int(args.ticks),
        out_dir,
        int(args.metrics_every),
        int(args.mint_every_edges),
        int(args.render_every),
    )


if __name__ == "__main__":
    raise SystemExit(main())
