#!/usr/bin/env python3
"""Plot Vector 11 ablation metrics from .sifta_state/vector11_ablation_metrics.jsonl."""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from pathlib import Path

# Headless / sandbox-safe defaults (avoid GUI backend and ~/.matplotlib write issues)
os.environ.setdefault("MPLBACKEND", "Agg")
import matplotlib

matplotlib.use(os.environ["MPLBACKEND"])
import matplotlib.pyplot as plt


def load_metrics(path: Path) -> dict[str, list[tuple[int, dict]]]:
    by_scenario: dict[str, list[tuple[int, dict]]] = defaultdict(list)
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            by_scenario[row["scenario"]].append((row["step"], row))
    return dict(by_scenario)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(description="Plot Vector 11 ablation JSONL.")
    ap.add_argument(
        "--input",
        type=Path,
        default=root / ".sifta_state" / "vector11_ablation_metrics.jsonl",
        help="Path to vector11_ablation_metrics.jsonl",
    )
    ap.add_argument(
        "--output-dir",
        type=Path,
        default=root / "Documents" / "vector11_runs",
        help="Directory for PNG output",
    )
    args = ap.parse_args()

    data = load_metrics(args.input)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # --- Figure 1: λ pressure and τ by scenario ---
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    colors = {
        "baseline_tau_only": "#2ecc71",
        "static_duals": "#3498db",
        "full_graph_dual": "#e74c3c",
    }
    for scenario, series in sorted(data.items()):
        steps = [s for s, _ in series]
        penalty = [r["total_lambda_penalty"] for _, r in series]
        tau = [r["tau"] for _, r in series]
        c = colors.get(scenario, None)
        axes[0].plot(steps, penalty, label=scenario, color=c, linewidth=0.8, alpha=0.9)
        axes[1].plot(steps, tau, label=scenario, color=c, linewidth=0.8, alpha=0.9)

    axes[0].set_ylabel("total_lambda_penalty")
    axes[0].set_title("Vector 11 ablation — λ pressure")
    axes[0].legend(loc="upper right", fontsize=8)
    axes[0].grid(True, alpha=0.3)

    axes[1].set_ylabel("τ (threshold)")
    axes[1].set_xlabel("step")
    axes[1].set_title("τ trajectory (distribution-shift stress in shared telemetry)")
    axes[1].grid(True, alpha=0.3)

    fig.tight_layout()
    out1 = args.output_dir / "vector11_lambda_tau.png"
    fig.savefig(out1, dpi=150)
    plt.close(fig)

    # --- Figure 2: violation magnitudes (mean abs) ---
    fig2, ax = plt.subplots(figsize=(10, 4))
    for scenario, series in sorted(data.items()):
        steps = [s for s, _ in series]
        vmean = []
        for _, r in series:
            v = r["violations"]
            vmean.append(
                (abs(v["congestion"]) + abs(v["safety"]) + abs(v["energy"])) / 3.0
            )
        c = colors.get(scenario, None)
        ax.plot(steps, vmean, label=scenario, color=c, linewidth=0.8, alpha=0.9)
    ax.set_xlabel("step")
    ax.set_ylabel("mean |violation| (3 constraints)")
    ax.set_title("Constraint slack under ablation (higher = more stress)")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True, alpha=0.3)
    fig2.tight_layout()
    out2 = args.output_dir / "vector11_violation_stress.png"
    fig2.savefig(out2, dpi=150)
    plt.close(fig2)

    print(f"Wrote {out1}")
    print(f"Wrote {out2}")


if __name__ == "__main__":
    main()
