#!/usr/bin/env python3
"""
crucible_stress_test.py — The Attacker Node for the 10-Minute Crucible
======================================================================

This script acts as the adversary.  It is intended to run from M1 Mac Mini
against the M5 server, but works locally too (localhost:8000).

What it does:
  1. DDoS wave — fire 100 concurrent POST requests per second at /api/messenger/send.
     Tracks 200 (accepted) vs 429 (rate-limited) responses.
  2. Anomaly injection — periodically injects unsigned, marker-tagged poison lines
     directly into .sifta_state/repair_log.jsonl (bypassing the API to simulate
     local disk intrusion that the anomaly_forager must catch).

Run from M1:
    python3 tests/crucible_stress_test.py --target http://192.168.1.100:8000

Run locally:
    python3 tests/crucible_stress_test.py --target http://127.0.0.1:8000

Flags:
  --target URL     M5 server base URL
  --api-key KEY    SIFTA_API_KEY (default: swarm2025)
  --duration SEC   How long the onslaught lasts (default: 600 = 10 min)
  --wave-size N    Concurrent requests per wave (default: 100)
  --inject-prob F  Probability of poison injection per wave (default: 0.3)
  --local-ledger   Path to repair_log.jsonl for direct poison injection
  --dry-run        Print intent but don't actually fire
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LEDGER = REPO_ROOT / "repair_log.jsonl"


def _inject_poison(ledger_path: Path, dry_run: bool) -> None:
    """Write one unsigned, marker-tagged record directly to the ledger file."""
    poison = {
        "timestamp": time.time(),
        "agent_id": "GHOST_NODE",
        "tx_type": "DATA_INJECTION",
        "payload": f"MALICIOUS_PAYLOAD_X{random.randint(10, 99)}",
    }
    if dry_run:
        print(f"  [DRY-RUN] would inject: {json.dumps(poison)}")
        return
    with open(ledger_path, "a") as f:
        f.write(json.dumps(poison) + "\n")


async def _ddos_wave(session, url: str, headers: dict, worker_id: int) -> int:
    payload = {"message": f"Stress packet {worker_id}", "sender": "CHAOS_NODE"}
    try:
        async with session.post(url, headers=headers, json=payload) as resp:
            return resp.status
    except Exception:
        return 500


async def the_crucible(
    target: str,
    api_key: str,
    duration: int,
    wave_size: int,
    inject_prob: float,
    ledger_path: Path,
    dry_run: bool,
) -> None:
    try:
        import aiohttp
    except ImportError:
        print("aiohttp not installed. pip install aiohttp  or run in --dry-run mode.")
        return

    url = f"{target.rstrip('/')}/api/messenger/send"
    headers = {"Authorization": f"Bearer {api_key}"}
    print(f"INITIATING {duration}s CRUCIBLE against {url}")
    print(f"  wave_size={wave_size}  inject_prob={inject_prob}  dry_run={dry_run}")

    start = time.time()
    total_ok = 0
    total_blocked = 0
    total_error = 0
    total_injected = 0
    wave_num = 0

    async with aiohttp.ClientSession() as session:
        while time.time() - start < duration:
            wave_num += 1
            if dry_run:
                print(f"  [DRY-RUN] wave {wave_num}: {wave_size} requests")
            else:
                tasks = [_ddos_wave(session, url, headers, i) for i in range(wave_size)]
                results = await asyncio.gather(*tasks)
                ok = sum(1 for r in results if r == 200)
                blocked = sum(1 for r in results if r == 429)
                err = len(results) - ok - blocked
                total_ok += ok
                total_blocked += blocked
                total_error += err

            if random.random() < inject_prob:
                _inject_poison(ledger_path, dry_run)
                total_injected += 1
                if not dry_run:
                    print(f"  [POISON] Anomaly injected #{total_injected}")

            elapsed = int(time.time() - start)
            if wave_num % 10 == 0:
                print(
                    f"  [{elapsed}s/{duration}s] waves={wave_num} "
                    f"ok={total_ok} blocked={total_blocked} err={total_error} "
                    f"injected={total_injected}"
                )
            await asyncio.sleep(1)

    print("\nCRUCIBLE COMPLETE.")
    print(f"  Duration: {int(time.time()-start)}s  Waves: {wave_num}")
    print(f"  API accepted: {total_ok}  Rate-limited: {total_blocked}  Errors: {total_error}")
    print(f"  Poison injected: {total_injected}")
    print("  Check .sifta_state/quarantine.jsonl for forager captures.")


def main() -> int:
    ap = argparse.ArgumentParser(description="SIFTA Crucible Stress Test (Attacker)")
    ap.add_argument("--target", type=str, default="http://127.0.0.1:8000")
    ap.add_argument("--api-key", type=str, default="swarm2025")
    ap.add_argument("--duration", type=int, default=600)
    ap.add_argument("--wave-size", type=int, default=100)
    ap.add_argument("--inject-prob", type=float, default=0.3)
    ap.add_argument("--local-ledger", type=str, default=str(DEFAULT_LEDGER))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    asyncio.run(
        the_crucible(
            target=args.target,
            api_key=args.api_key,
            duration=args.duration,
            wave_size=args.wave_size,
            inject_prob=args.inject_prob,
            ledger_path=Path(args.local_ledger),
            dry_run=args.dry_run,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
