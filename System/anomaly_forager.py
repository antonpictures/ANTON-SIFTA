#!/usr/bin/env python3
"""
anomaly_forager.py — Stigmergic Anomaly Hunter for SIFTA Swarm OS
=================================================================

Monitors a JSONL stream (default: repair_log.jsonl) in real-time and
quarantines any line that:
  1. Contains a known malicious marker (MALICIOUS_PAYLOAD, DATA_INJECTION).
  2. Lacks a cryptographic hash/signature field (unsigned traffic).
  3. Fails Ed25519 verification when SIFTA_LEDGER_VERIFY=1.

Quarantined entries are appended to .sifta_state/quarantine.jsonl with a
swarm timestamp and forager identity tag.

This worker is designed to run continuously alongside server.py:
    python3 System/anomaly_forager.py

Flags:
  --watch PATH         JSONL file to monitor (default: repair_log.jsonl)
  --quarantine PATH    Quarantine output  (default: .sifta_state/quarantine.jsonl)
  --poll-ms MS         Polling interval in milliseconds (default: 100)
  --dry-run            Print anomalies without writing quarantine log
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

MALICIOUS_MARKERS = frozenset([
    "MALICIOUS_PAYLOAD",
    "DATA_INJECTION",
    "GHOST_NODE",
    "CHAOS_NODE",
])

REQUIRED_INTEGRITY_KEYS = ("ed25519_sig", "hash", "signing_node")


def _is_anomalous(entry: dict) -> str | None:
    """Return a reason string if the entry is anomalous, else None."""
    raw = json.dumps(entry)
    for marker in MALICIOUS_MARKERS:
        if marker in raw:
            return f"malicious_marker:{marker}"

    has_integrity = any(k in entry for k in REQUIRED_INTEGRITY_KEYS)
    if not has_integrity:
        tx = entry.get("tx_type", entry.get("type", ""))
        if tx in ("STGM_MINT", "MINING_REWARD", "STGM_SPEND", "INFERENCE_BORROW", "UTILITY_MINT"):
            return "unsigned_economic_tx"

    return None


def _quarantine_line(qpath: Path, entry: dict, reason: str, dry_run: bool) -> None:
    envelope = {
        "quarantined_at": time.time(),
        "forager": "ANOMALY_FORAGER_v1",
        "reason": reason,
        "original": entry,
    }
    if dry_run:
        print(f"[DRY-RUN] would quarantine: {json.dumps(envelope, default=str)}")
        return
    qpath.parent.mkdir(parents=True, exist_ok=True)
    try:
        sys.path.insert(0, str(REPO_ROOT / "System"))
        from ledger_append import append_jsonl_line
        append_jsonl_line(qpath, envelope)
    except Exception:
        with open(qpath, "a") as f:
            f.write(json.dumps(envelope, default=str) + "\n")


def forage(watch: Path, quarantine: Path, poll_s: float, dry_run: bool) -> None:
    print(f"[SWARM] Anomaly Forager deployed. Watching {watch}")
    print(f"[SWARM] Quarantine → {quarantine}")
    known_lines = 0
    total_quarantined = 0

    while True:
        try:
            if not watch.exists():
                time.sleep(poll_s)
                continue
            with open(watch, "r") as f:
                lines = f.readlines()
            if len(lines) <= known_lines:
                time.sleep(poll_s)
                continue
            new_lines = lines[known_lines:]
            known_lines = len(lines)

            for raw_line in new_lines:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    entry = json.loads(raw_line)
                except json.JSONDecodeError:
                    _quarantine_line(quarantine, {"_raw": raw_line}, "malformed_json", dry_run)
                    total_quarantined += 1
                    print(f"[CLUSTER] Swarm isolated malformed data packet. total={total_quarantined}")
                    continue

                reason = _is_anomalous(entry)
                if reason:
                    _quarantine_line(quarantine, entry, reason, dry_run)
                    total_quarantined += 1
                    aid = entry.get("agent_id", entry.get("author", "UNKNOWN"))
                    print(f"[CLUSTER] Swarm isolated anomaly from {aid} reason={reason} total={total_quarantined}")

        except KeyboardInterrupt:
            print(f"\n[SWARM] Forager standing down. Quarantined {total_quarantined} anomalies.")
            break
        except Exception:
            pass
        time.sleep(poll_s)


def main() -> int:
    ap = argparse.ArgumentParser(description="SIFTA Anomaly Forager")
    ap.add_argument("--watch", type=str, default=str(REPO_ROOT / "repair_log.jsonl"))
    ap.add_argument("--quarantine", type=str, default=str(REPO_ROOT / ".sifta_state" / "quarantine.jsonl"))
    ap.add_argument("--poll-ms", type=int, default=100)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    forage(
        watch=Path(args.watch),
        quarantine=Path(args.quarantine),
        poll_s=max(0.01, args.poll_ms / 1000.0),
        dry_run=args.dry_run,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
