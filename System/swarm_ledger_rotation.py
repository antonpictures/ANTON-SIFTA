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
import os
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
    "sensory_attention_ledger.jsonl": RotationPolicy(
        "sensory_attention_ledger.jsonl",
        keep_last=20_000,
        min_bytes=64 * 1024 * 1024,
        reason="resident attention decisions; recent leases and evidence matter most",
    ),
    "sensor_lane_journal.jsonl": RotationPolicy(
        "sensor_lane_journal.jsonl",
        keep_last=10_000,
        min_bytes=64 * 1024 * 1024,
        reason="derived sensor summaries; daily markdown and receipts preserve older meaning",
    ),
    "journal_schedule_receipts.jsonl": RotationPolicy(
        "journal_schedule_receipts.jsonl",
        keep_last=10_000,
        min_bytes=64 * 1024 * 1024,
        reason="life-journal receipt stream; recent receipt tail is enough for live prompts",
    ),
    "global_segment_index.jsonl": RotationPolicy(
        "global_segment_index.jsonl",
        keep_last=5_000,
        min_bytes=32 * 1024 * 1024,
        reason="derived segment index snapshots; latest JSON carries the live view",
    ),
    "motor_pulses.jsonl": RotationPolicy(
        "motor_pulses.jsonl",
        keep_last=30_000,
        min_bytes=32 * 1024 * 1024,
        reason="heartbeat pulse trace; live organs consume the recent rhythm tail",
    ),
    "alice_first_person_journal.jsonl": RotationPolicy(
        "alice_first_person_journal.jsonl",
        keep_last=20_000,
        min_bytes=32 * 1024 * 1024,
        reason="first-person witness rows; daily journals preserve older narrative",
    ),
    "camera_unified_field_proof.jsonl": RotationPolicy(
        "camera_unified_field_proof.jsonl",
        keep_last=10_000,
        min_bytes=16 * 1024 * 1024,
        reason="camera proof snapshots; latest proofs drive current truth claims",
    ),
    "architect_screen_gaze_balance.jsonl": RotationPolicy(
        "architect_screen_gaze_balance.jsonl",
        keep_last=10_000,
        min_bytes=16 * 1024 * 1024,
        reason="gaze proxy samples; current EMA and recent samples are live control state",
    ),
    "active_eye_identity_frames.jsonl": RotationPolicy(
        "active_eye_identity_frames.jsonl",
        keep_last=10_000,
        min_bytes=8 * 1024 * 1024,
        reason="identity-frame receipts; image path plus recent sha anchors are sufficient live state",
    ),
    "app_focus.jsonl": RotationPolicy(
        "app_focus.jsonl",
        keep_last=20_000,
        min_bytes=16 * 1024 * 1024,
        reason="active-app focus trace; current app and recent transitions feed Alice's prompt",
    ),
    "unified_stigmergic_field.jsonl": RotationPolicy(
        "unified_stigmergic_field.jsonl",
        keep_last=10_000,
        min_bytes=16 * 1024 * 1024,
        reason="derived field snapshots; recent field vectors carry live coupling state",
    ),
    "network_topology.jsonl": RotationPolicy(
        "network_topology.jsonl",
        keep_last=5_000,
        min_bytes=16 * 1024 * 1024,
        reason="derived network snapshots; archive old topology frames",
    ),
    "kernel_process_table.jsonl": RotationPolicy(
        "kernel_process_table.jsonl",
        keep_last=20_000,
        min_bytes=64 * 1024 * 1024,
        reason="hot kernel heartbeats; live table consumes snapshot plus recent tail",
    ),
    "fractal_pheromone_field.jsonl": RotationPolicy(
        "fractal_pheromone_field.jsonl",
        keep_last=5_000,
        min_bytes=256 * 1024 * 1024,
        reason="giant pheromone trace; recent gradients matter for live walkers",
    ),
    "browser_page_state.jsonl": RotationPolicy(
        "browser_page_state.jsonl",
        keep_last=15_000,
        min_bytes=128 * 1024 * 1024,
        reason="browser DOM/page snapshots; current tail drives proprioception",
    ),
    "browser_context.jsonl": RotationPolicy(
        "browser_context.jsonl",
        keep_last=20_000,
        min_bytes=64 * 1024 * 1024,
        reason="browser context shifts; recent tail feeds present-time memory",
    ),
}

GIANT_BYTE_LEDGER_NAMES: tuple[str, ...] = (
    "fractal_pheromone_field.jsonl",
    "browser_page_state.jsonl",
    "kernel_process_table.jsonl",
)

GIANT_FRAME_DIRECTORIES: Dict[str, Dict[str, object]] = {
    "iris_frames": {
        "keep_files": 400,
        "min_bytes": 256 * 1024 * 1024,
        "reason": "camera frame cache; recent frames anchor live vision",
    },
    "browser_viewport": {
        "keep_files": 120,
        "min_bytes": 256 * 1024 * 1024,
        "reason": "browser viewport PNG cache; recent captures drive photo describe",
    },
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


def _read_tail_bytes_aligned(path: Path, keep_bytes: int, *, encoding: str = "utf-8") -> str:
    keep = max(1, int(keep_bytes))
    size = path.stat().st_size
    offset = max(0, size - keep)
    with path.open("rb") as fh:
        fh.seek(offset)
        chunk = fh.read().decode(encoding, errors="replace")
    if offset > 0:
        first_newline = chunk.find("\n")
        if first_newline >= 0:
            chunk = chunk[first_newline + 1:]
    if chunk and not chunk.endswith("\n"):
        chunk += "\n"
    return chunk


def fast_rotate_ledger_by_bytes(
    ledger_name: str,
    *,
    state_dir: Optional[Path] = None,
    archive_dir: Optional[Path] = None,
    rotation_ledger: Optional[Path] = None,
    max_bytes: int = 64 * 1024 * 1024,
    keep_bytes: int = 8 * 1024 * 1024,
    dry_run: bool = False,
    now: Optional[float] = None,
) -> Dict[str, object]:
    """Rotate a giant hot ledger without reading it all into memory.

    The full old file is moved into Archive/Ledger_Rotation and the active file
    is replaced with a line-aligned recent byte tail. This preserves history
    while keeping active control loops away from multi-GB JSONL bodies.
    """
    base = Path(state_dir) if state_dir is not None else _STATE
    archive_base = Path(archive_dir) if archive_dir is not None else _ARCHIVE
    audit = Path(rotation_ledger) if rotation_ledger is not None else _ROTATION_LEDGER
    path = base / str(ledger_name)
    t = time.time() if now is None else float(now)
    before_bytes = path.stat().st_size if path.exists() else 0
    row: Dict[str, object] = {
        "event": "ledger_rotation",
        "schema": "SIFTA_LEDGER_ROTATION_V1",
        "module_version": _MODULE_VERSION,
        "ledger_name": str(ledger_name),
        "dry_run": bool(dry_run),
        "before_bytes": int(before_bytes),
        "after_bytes": int(before_bytes),
        "keep_last": 0,
        "kept_lines": 0,
        "archived_lines": 0,
        "archive_path": "",
        "archive_sha256": "",
        "archive_bytes": 0,
        "reason": "fast byte-tail rotation for hot ledger",
        "ts": t,
    }
    if before_bytes < int(max_bytes) or not path.exists():
        row["reason"] = "skip: below max_bytes (fast byte-tail rotation)"
        return row
    if dry_run:
        row["reason"] = f"dry_run: would keep last {int(keep_bytes)} bytes"
        return row

    archive_base.mkdir(parents=True, exist_ok=True)
    archive_id = hashlib.sha256(f"{ledger_name}:{before_bytes}:{t}".encode("utf-8")).hexdigest()[:12]
    archive_path = archive_base / f"{ledger_name}.{int(t)}.{before_bytes}.{archive_id}.jsonl"
    tail = _read_tail_bytes_aligned(path, int(keep_bytes))
    os.replace(path, archive_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(tail, encoding="utf-8")

    row["after_bytes"] = int(path.stat().st_size)
    row["kept_lines"] = int(sum(1 for line in tail.splitlines() if line.strip()))
    # Count archived lines from the archive file
    archived_count = 0
    try:
        with open(archive_path, "rb") as fh:
            for _ in fh:
                archived_count += 1
    except Exception:
        archived_count = 0
    row["archived_lines"] = archived_count
    row["archive_path"] = str(archive_path)
    row["archive_sha256"] = f"fast-archive-id:{archive_id}"
    row["archive_bytes"] = int(archive_path.stat().st_size)
    row["reason"] = (
        "fast byte-tail rotation; full old ledger moved to archive, active ledger "
        f"keeps last {int(keep_bytes)} bytes"
    )
    assert_payload_keys("ledger_rotation.jsonl", row, strict=True)
    append_line_locked(audit, json.dumps(row, sort_keys=True) + "\n")
    return row


def _dir_total_bytes(path: Path) -> int:
    total = 0
    if not path.exists():
        return 0
    for child in path.rglob("*"):
        if child.is_file():
            try:
                total += child.stat().st_size
            except OSError:
                continue
    return total


def rotate_frame_directory(
    dir_name: str,
    *,
    state_dir: Optional[Path] = None,
    archive_dir: Optional[Path] = None,
    rotation_ledger: Optional[Path] = None,
    keep_files: int = 400,
    min_bytes: int = 256 * 1024 * 1024,
    dry_run: bool = False,
    now: Optional[float] = None,
) -> Dict[str, object]:
    """Archive oldest files in a giant frame directory; keep recent tail by mtime."""
    base = Path(state_dir) if state_dir is not None else _STATE
    archive_base = Path(archive_dir) if archive_dir is not None else _ARCHIVE
    audit = Path(rotation_ledger) if rotation_ledger is not None else _ROTATION_LEDGER
    path = base / str(dir_name)
    t = time.time() if now is None else float(now)
    before_bytes = _dir_total_bytes(path)
    row: Dict[str, object] = {
        "event": "ledger_rotation",
        "schema": "SIFTA_LEDGER_ROTATION_V1",
        "module_version": _MODULE_VERSION,
        "ledger_name": str(dir_name),
        "dry_run": bool(dry_run),
        "before_bytes": int(before_bytes),
        "after_bytes": int(before_bytes),
        "keep_last": int(keep_files),
        "kept_lines": 0,
        "archived_lines": 0,
        "archive_path": "",
        "archive_sha256": "",
        "archive_bytes": 0,
        "reason": "frame directory tail rotation",
        "ts": t,
    }
    if before_bytes < int(min_bytes) or not path.exists():
        row["reason"] = "skip: below min_bytes (frame directory tail rotation)"
        return row
    files = [p for p in path.rglob("*") if p.is_file()]
    if len(files) <= int(keep_files):
        row["reason"] = "skip: file count within keep_files (frame directory tail rotation)"
        return row
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    keep = files[: int(keep_files)]
    evict = files[int(keep_files) :]
    if dry_run:
        row["reason"] = f"dry_run: would archive {len(evict)} files, keep {len(keep)}"
        return row
    archive_base.mkdir(parents=True, exist_ok=True)
    archive_root = archive_base / f"{dir_name}.{int(t)}"
    archive_root.mkdir(parents=True, exist_ok=True)
    archived_bytes = 0
    for src in evict:
        rel = src.relative_to(path)
        dest = archive_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.replace(src, dest)
            archived_bytes += dest.stat().st_size
        except OSError:
            continue
    after_bytes = _dir_total_bytes(path)
    row.update(
        {
            "after_bytes": int(after_bytes),
            "kept_lines": int(len(keep)),
            "archived_lines": int(len(evict)),
            "archive_path": str(archive_root),
            "archive_sha256": f"frame-dir:{dir_name}:{len(evict)}",
            "archive_bytes": int(archived_bytes),
            "reason": (
                f"frame directory tail rotation; archived {len(evict)} files, "
                f"kept {len(keep)} newest"
            ),
        }
    )
    assert_payload_keys("ledger_rotation.jsonl", row, strict=True)
    append_line_locked(audit, json.dumps(row, sort_keys=True) + "\n")
    return row


def rotate_default_ledgers(
    *,
    state_dir: Optional[Path] = None,
    archive_dir: Optional[Path] = None,
    dry_run: bool = False,
    giant_bytes: int = 512 * 1024 * 1024,
    giant_keep_bytes: int = 8 * 1024 * 1024,
) -> List[Dict[str, object]]:
    base = Path(state_dir) if state_dir is not None else _STATE
    rows: List[Dict[str, object]] = []
    for policy in DEFAULT_POLICIES.values():
        path = base / policy.ledger_name
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        if size >= int(giant_bytes):
            rows.append(
                fast_rotate_ledger_by_bytes(
                    policy.ledger_name,
                    state_dir=state_dir,
                    archive_dir=archive_dir,
                    max_bytes=policy.min_bytes,
                    keep_bytes=giant_keep_bytes,
                    dry_run=dry_run,
                )
            )
            continue
        rows.append(
            rotate_ledger(policy, state_dir=state_dir, archive_dir=archive_dir, dry_run=dry_run)
        )
    for dir_name, cfg in GIANT_FRAME_DIRECTORIES.items():
        rows.append(
            rotate_frame_directory(
                dir_name,
                state_dir=state_dir,
                archive_dir=archive_dir,
                dry_run=dry_run,
                keep_files=int(cfg.get("keep_files") or 400),
                min_bytes=int(cfg.get("min_bytes") or (256 * 1024 * 1024)),
            )
        )
    return rows


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
