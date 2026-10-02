#!/usr/bin/env python3
"""
cell_morphology_ingest_daemon.py — folder watcher for microscope camera.

Watches a configured directory for new image files (PNG, JPG, TIFF),
calls the cell_morphology organ's ingest_frame() on each new frame,
and logs the trajectory drift. Runs as a long-lived daemon.

Usage:
    python3 System/cell_morphology_ingest_daemon.py --watch-dir /path/to/microscope/captures
    python3 System/cell_morphology_ingest_daemon.py --watch-dir ./captures --interval 2 --ext png,jpg,tiff
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from System.swarm_cell_morphology_organ import ingest_frame, trajectory


def _parse_exts(s: str) -> tuple[str, ...]:
    return tuple(f".{e.strip().lstrip('.').lower()}" for e in s.split(",") if e.strip())


def main() -> int:
    ap = argparse.ArgumentParser(description="Cell morphology ingest daemon")
    ap.add_argument("--watch-dir", required=True, help="Directory to watch for new frames")
    ap.add_argument("--interval", type=float, default=2.0, help="Polling interval seconds")
    ap.add_argument("--ext", default="png,jpg,jpeg,tiff,tif", help="Comma-separated extensions")
    ap.add_argument("--log-file", help="Optional JSONL log file for trajectory snapshots")
    ap.add_argument("--once", action="store_true", help="Process existing files once and exit")
    args = ap.parse_args()

    watch_dir = Path(args.watch_dir).expanduser().resolve()
    if not watch_dir.exists():
        print(f"watch dir does not exist: {watch_dir}", file=sys.stderr)
        return 1
    if not watch_dir.is_dir():
        print(f"watch dir is not a directory: {watch_dir}", file=sys.stderr)
        return 1

    exts = _parse_exts(args.ext)
    seen: set[str] = set()
    log_path = Path(args.log_file).expanduser().resolve() if args.log_file else None

    print(f"[cell_morphology_daemon] watching {watch_dir} (exts={exts}, interval={args.interval}s)")

    def process_new_files() -> int:
        processed = 0
        for p in sorted(watch_dir.iterdir()):
            if not p.is_file():
                continue
            if p.suffix.lower() not in exts:
                continue
            key = f"{p.name}:{p.stat().st_mtime_ns}"
            if key in seen:
                continue
            seen.add(key)
            print(f"[cell_morphology_daemon] ingesting {p.name}...")
            res = ingest_frame(str(p))
            if res.get("ok"):
                traj = trajectory(limit=100)
                drift = traj.get("drift")
                print(f"  status={res['status']} metrics={res['metrics']} drift={drift}")
                if log_path and drift:
                    log_path.write_text(
                        log_path.read_text() + json.dumps({
                            "ts": time.time(),
                            "frame": p.name,
                            "drift": drift,
                            "n_points": traj.get("n", 0),
                        }) + "\n"
                    ) if log_path.exists() else log_path.write_text(
                        json.dumps({
                            "ts": time.time(),
                            "frame": p.name,
                            "drift": drift,
                            "n_points": traj.get("n", 0),
                        }) + "\n"
                    )
            else:
                print(f"  failed: {res.get('error')}")
            processed += 1
        return processed

    if args.once:
        return 0 if process_new_files() >= 0 else 1

    try:
        while True:
            process_new_files()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n[cell_morphology_daemon] stopped")
        return 0


if __name__ == "__main__":
    sys.exit(main())
