#!/usr/bin/env python3
"""
stress_all_simulations.py — repeat headless runs for every Swarm OS simulation

Default: 50 iterations each (override with --iterations).
Uses small grids / tick counts so the full matrix finishes in reasonable wall time.

Does not run sifta_arena.py (needs Ollama / tournament harness).

Usage:
  cd ~/Music/ANTON_SIFTA
  python3 scripts/stress_all_simulations.py
  python3 scripts/stress_all_simulations.py --iterations 5 --dry-run
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PY = sys.executable


def _run(name: str, argv: list[str], dry: bool) -> tuple[bool, float, str]:
    cmd = [PY] + argv
    if dry:
        print(f"  [dry-run] {' '.join(cmd)}")
        return True, 0.0, ""
    t0 = time.perf_counter()
    p = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True, timeout=600)
    dt = time.perf_counter() - t0
    ok = p.returncode == 0
    tail = (p.stderr or p.stdout or "")[-400:]
    return ok, dt, tail


def main() -> int:
    ap = argparse.ArgumentParser(description="Stress-test all SIFTA simulations (headless).")
    ap.add_argument("--iterations", type=int, default=50)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    n = max(1, int(args.iterations))

    # (name, argv template with seed placeholder {i})
    suites: list[tuple[str, list[str]]] = [
        (
            "logistics",
            [
                "Applications/sifta_logistics_swarm_sim.py",
                "--headless",
                "--ticks",
                "350",
                "--grid",
                "72",
                "--agents",
                "56",
                "--metrics-every",
                "120",
                "--seed",
                "{seed}",
                "--out",
                ".sifta/stress/logistics",
            ],
        ),
        (
            "crucible",
            [
                "Applications/sifta_crucible_swarm_sim.py",
                "--headless",
                "--ticks",
                "400",
                "--agents",
                "64",
                "--seed",
                "{seed}",
            ],
        ),
        (
            "vision",
            [
                "Applications/sifta_vision_edge_sim.py",
                "--headless",
                "--ticks",
                "280",
                "--width",
                "88",
                "--height",
                "88",
                "--swimmers",
                "320",
                "--seed",
                "{seed}",
                "--out",
                ".sifta/stress/vision",
            ],
        ),
        (
            "urban",
            [
                "Applications/sifta_urban_resilience_sim.py",
                "--headless",
                "--ticks",
                "320",
                "--width",
                "52",
                "--height",
                "40",
                "--vehicles",
                "90",
                "--drones",
                "40",
                "--seed",
                "{seed}",
                "--out",
                ".sifta/stress/urban",
            ],
        ),
        (
            "warehouse",
            [
                "Applications/sifta_warehouse_test.py",
                "--headless",
                "--ticks",
                "800",
                "--out",
                ".sifta/stress/warehouse",
            ],
        ),
        (
            "cyborg",
            ["Applications/sifta_cyborg_sim.py", "--ticks", "80"],
        ),
        (
            "colloid",
            ["Applications/sifta_colloid_sim.py", "--demo", "--max-frames", "240"],
        ),
    ]

    print(f"[STRESS] repo={REPO} iterations={n} suites={len(suites)}")
    failed = 0
    for name, tmpl in suites:
        print(f"\n=== {name} ===")
        times: list[float] = []
        for i in range(n):
            argv = [s.format(seed=1000 + i) if "{seed}" in s else s for s in tmpl]
            ok, dt, err = _run(name, argv, args.dry_run)
            times.append(dt)
            if not ok:
                failed += 1
                print(f"  FAIL iter={i+1}/{n} after {dt:.2f}s")
                if err.strip():
                    print(err.strip()[-500:])
            elif (i + 1) % 10 == 0 or i == 0:
                print(f"  iter {i+1}/{n} last {dt:.2f}s")
        if times:
            print(f"  ok  mean={sum(times)/len(times):.3}s  max={max(times):.3}s  total={sum(times):.1f}s")

    print(f"\n[STRESS] done failures={failed} / {n * len(suites)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
