#!/usr/bin/env python3
"""
sifta_warehouse_test.py — one-click warehouse logistics validation

Runs a preset logistics swarm scenario and reports whether the swarm is
converging (finding territory/paths) while blocking forged transport claims.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sifta_logistics_swarm_sim import Config, run


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticks", type=int, default=120000, help="Simulation ticks (default watch run).")
    ap.add_argument("--headless", action="store_true", help="Disable live matplotlib graphics.")
    ap.add_argument("--render-every", type=int, default=120, help="Graphics refresh cadence in ticks.")
    ap.add_argument("--out", type=str, default=".sifta/logistics")
    args = ap.parse_args()

    out_dir = Path(args.out).expanduser()
    cfg = Config(
        grid=192,
        agents=50,
        deliveries=6,
        obstacle_pct=0.06,
        evap=0.004,
        deposit=2.0,
        explore=0.18,
        congestion_every=8000,
        metrics_every=2000,
        seed=1337,
        hijack_rate=0.02,
    )
    rc = run(
        cfg,
        int(args.ticks),
        out_dir,
        demo=False,
        visual=not bool(args.headless),
        render_every=int(args.render_every),
    )

    metrics_path = out_dir / "metrics.jsonl"
    if metrics_path.exists():
        lines = metrics_path.read_text(encoding="utf-8").splitlines()
        if lines:
            last = json.loads(lines[-1])
            done = int(last.get("completed_roundtrips", 0))
            blocked = int(last.get("hijack_blocked", 0))
            attempts = int(last.get("hijack_attempts", 0))
            print(
                "[WAREHOUSE_TEST] "
                f"completed_roundtrips={done} hijack_blocked={blocked}/{attempts}"
            )
            if done > 0 and blocked >= attempts:
                print("[WAREHOUSE_TEST] PASS: transport routes converged and hijack forgeries were blocked.")
            else:
                print("[WAREHOUSE_TEST] WARN: check congestion/explore parameters and rerun.")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())

