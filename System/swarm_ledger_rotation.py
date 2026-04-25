#!/usr/bin/env python3
"""
System/swarm_ledger_rotation.py

Explicit JSONL rotation for high-volume sensory ledgers.

This is not REM sleep. It is an operator-triggered optimization pass for
append-only ledgers whose recent tail is sufficient for live control loops.
Evicted rows are archived as gzip before the source ledger is compacted.
"""

from __future__ import annotations

from dataclasses import dataclass
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import time
from typing import Dict, Iterable, List, Optional

from System.canonical_schemas import assert_payload_keys
from System.jsonl_file_lock import append_line_locked, tail_compact_locked

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_ARCHIVE = _REPO / "Archive" / "Ledger_Rotation"
_ROTATION_LEDGER = _STATE / "ledger_rotation.jsonl"
_MODULE_VERSION = "swarm_ledger_rotation.v1"


@dataclass(frozen=True)
class RotationPolicy:
    ledger_name: str
    keep_last: int
    min_bytes: int
    reason: str


DEFAULT_POLICIES: Dict[str, RotationPolicy] = {
    "visual_stigmergy.jsonl": RotationPolicy(
        "visual_stigmergy.jsonl",
        keep_last=10_000,
        min_bytes=64 * 1024 * 1024,
        reason="raw photon saliency; live loops consume the tail",
    ),
    "pheromone_log.jsonl": RotationPolicy(
        "pheromone_log.jsonl",
        keep_last=10_000,
        min_bytes=64 * 1024 * 1024,
        reason="high-volume pheromone trace; recent gradients matter most",
    ),
    "network_topology.jsonl": RotationPolicy(
        "network_topology.jsonl",
        keep_last=5_000,
        min_bytes=16 * 1024 * 1024,
        reason="derived network snapshots; archive old topology frames",
    ),
}


def _sha256_lines(lines: Iterable[str]) -> str:
    h = hashlib.sha256()
    for line in lines:
        h.update(line.encode("utf-8", errors="replace"))
    return h.hexdigest()


def _archive_evicted(
    *,
    archive_dir: Path,
    ledger_name: str,
    evicted_lines: List[str],
    now: float,
) -> Dict[str, object]:
    sha = _sha256_lines(evicted_lines)
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / f"{ledger_name}.{int(now)}.{sha[:12]}.jsonl.gz"
    with gzip.open(archive_path, "wt", encoding="utf-8") as f:
        f.writelines(evicted_lines)
    return {
        "archive_path": str(archive_path),
        "archive_sha256": sha,
        "archived_lines": len(evicted_lines),
        "archive_bytes": archive_path.stat().st_size,
    }


def rotate_ledger(
    policy: RotationPolicy,
    *,
    state_dir: Optional[Path] = None,
    archive_dir: Optional[Path] = None,
    rotation_ledger: Optional[Path] = None,
    dry_run: bool = False,
    now: Optional[float] = None,
) -> Dict[str, object]:
    base = Path(state_dir) if state_dir is not None else _STATE
    archive_base = Path(archive_dir) if archive_dir is not None else _ARCHIVE
    audit = Path(rotation_ledger) if rotation_ledger is not None else _ROTATION_LEDGER
    path = base / policy.ledger_name
    t = time.time() if now is None else float(now)
    before_bytes = path.stat().st_size if path.exists() else 0

    row: Dict[str, object] = {
        "event": "ledger_rotation",
        "schema": "SIFTA_LEDGER_ROTATION_V1",
        "module_version": _MODULE_VERSION,
        "ledger_name": policy.ledger_name,
        "dry_run": bool(dry_run),
        "before_bytes": int(before_bytes),
        "after_bytes": int(before_bytes),
        "keep_last": int(policy.keep_last),
        "kept_lines": 0,
        "archived_lines": 0,
        "archive_path": "",
        "archive_sha256": "",
        "archive_bytes": 0,
        "reason": policy.reason,
        "ts": t,
    }

    if before_bytes < policy.min_bytes or not path.exists():
        row["reason"] = f"skip: below min_bytes ({policy.reason})"
        return row

    if dry_run:
        row["reason"] = f"dry_run: would keep last {policy.keep_last} lines ({policy.reason})"
        return row

    kept_count, evicted_lines = tail_compact_locked(path, policy.keep_last)
    after_bytes = path.stat().st_size if path.exists() else 0
    row["after_bytes"] = int(after_bytes)
    row["kept_lines"] = int(kept_count)
    if evicted_lines:
        archive = _archive_evicted(
            archive_dir=archive_base,
            ledger_name=policy.ledger_name,
            evicted_lines=evicted_lines,
            now=t,
        )
        row.update(archive)
    assert_payload_keys("ledger_rotation.jsonl", row, strict=True)
    append_line_locked(audit, json.dumps(row, sort_keys=True) + "\n")
    return row


def rotate_default_ledgers(
    *,
    state_dir: Optional[Path] = None,
    archive_dir: Optional[Path] = None,
    dry_run: bool = False,
) -> List[Dict[str, object]]:
    return [
        rotate_ledger(policy, state_dir=state_dir, archive_dir=archive_dir, dry_run=dry_run)
        for policy in DEFAULT_POLICIES.values()
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--ledger", choices=sorted(DEFAULT_POLICIES), default=None)
    args = parser.parse_args()
    if args.ledger:
        rows = [rotate_ledger(DEFAULT_POLICIES[args.ledger], dry_run=args.dry_run)]
    else:
        rows = rotate_default_ledgers(dry_run=args.dry_run)
    print(json.dumps(rows, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
