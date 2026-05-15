#!/usr/bin/env python3
"""swarm_visual_stigmergy_rotator.py — rotate the 2.4GB visual ledger.

Architect 2026-05-13 22:30 PT: chat widget sluggish during investor
demo. Diagnostic showed `.sifta_state/visual_stigmergy.jsonl` had
grown to 2.4 GB / 572,104 rows and was still being appended to,
saturating disk I/O and inflating any consumer that scanned the
unified-field history.

This rotator does ONE specific thing:
  1. Snapshot current visual_stigmergy.jsonl byte size + sha256
  2. gzip-archive it to .sifta_trash/visual_stigmergy_<UTC>.jsonl.gz
  3. Replace the live file with the TAIL — last N rows preserved so
     any consumer expecting recent history still finds it
  4. Write a signed receipt to .sifta_state/work_receipts.jsonl

Defaults: keep last 10,000 rows (~few MB), archive everything older.

Not destructive — the gzip lives in .sifta_trash/ until you delete it
yourself. The architect's restart of the talk widget is recommended
AFTER this runs.

Truth class: OPERATIONAL — disk rotation is a measurable event.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import sys
import time
import uuid
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_TRASH = _REPO / ".sifta_trash"

TARGET_LEDGER = "visual_stigmergy.jsonl"
TRUTH_LABEL = "VISUAL_STIGMERGY_ROTATION_V1"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _tail_rows_streaming(path: Path, last_n: int, out: Path) -> int:
    """Copy the last N lines of `path` into `out`. Streaming, low memory.

    We use a 2-pass strategy: pass 1 counts total lines. Pass 2 copies
    rows after `(total - last_n)`. For a 572k-row file this takes a
    few seconds and uses constant memory.
    """
    total = 0
    with path.open("rb") as f:
        for _ in f:
            total += 1
    skip = max(0, total - last_n)
    written = 0
    with path.open("rb") as src, out.open("wb") as dst:
        for i, line in enumerate(src):
            if i < skip:
                continue
            dst.write(line)
            written += 1
    return written


def rotate(
    *,
    state_root: str | Path | None = None,
    trash_root: str | Path | None = None,
    target_ledger: str = TARGET_LEDGER,
    keep_last_n: int = 10_000,
    dry_run: bool = False,
) -> dict[str, Any]:
    state = Path(state_root) if state_root else _STATE
    trash = Path(trash_root) if trash_root else _TRASH
    target = state / target_ledger
    if not target.exists():
        return {
            "ok": False,
            "truth_label": TRUTH_LABEL,
            "reason": f"target ledger not found: {target}",
        }
    original_size = target.stat().st_size
    if original_size < 50 * 1024 * 1024:
        # Don't bother rotating small files
        return {
            "ok": True,
            "truth_label": TRUTH_LABEL,
            "skipped": True,
            "reason": (
                f"file is only {original_size} bytes — under 50 MB threshold, "
                f"no rotation needed."
            ),
            "ledger": str(target),
        }
    # Pre-rotation sha256 (best-effort; expensive for 2.4 GB but worth it)
    print(f"[rotator] computing sha256 of {target} ({original_size:,} bytes)…", flush=True)
    pre_sha = _sha256_file(target)
    print(f"[rotator] pre-rotation sha256: {pre_sha}", flush=True)
    trash.mkdir(parents=True, exist_ok=True)
    archive_name = (
        f"{target.stem}_{time.strftime('%Y%m%d_%H%M%S', time.gmtime())}.jsonl.gz"
    )
    archive_path = trash / archive_name
    if dry_run:
        return {
            "ok": True,
            "truth_label": TRUTH_LABEL,
            "dry_run": True,
            "would_archive_to": str(archive_path),
            "original_size_bytes": original_size,
            "would_keep_last_n": keep_last_n,
            "pre_sha256": pre_sha,
        }
    # Archive: stream-gzip the original to .sifta_trash/
    print(f"[rotator] gzipping → {archive_path}…", flush=True)
    with target.open("rb") as src, gzip.open(archive_path, "wb", compresslevel=6) as dst:
        shutil.copyfileobj(src, dst, length=1 << 16)
    archive_size = archive_path.stat().st_size
    print(
        f"[rotator] archive written: {archive_size:,} bytes "
        f"(compression {original_size / max(archive_size, 1):.1f}×)",
        flush=True,
    )
    # Build the tail (last N rows) into a temp file alongside the target.
    tmp_path = state / f".{target_ledger}.rotating"
    print(f"[rotator] extracting last {keep_last_n} rows → {tmp_path}…", flush=True)
    n_written = _tail_rows_streaming(target, keep_last_n, tmp_path)
    # Atomic swap: rename tmp over the original.
    tmp_path.replace(target)
    post_size = target.stat().st_size
    post_sha = _sha256_file(target)
    print(
        f"[rotator] rotation complete. {post_size:,} bytes remaining, "
        f"{n_written:,} rows preserved.",
        flush=True,
    )
    # Write a signed receipt to work_receipts.jsonl
    payload = {
        "truth_label": TRUTH_LABEL,
        "ledger": str(target.relative_to(_REPO)),
        "archive": str(archive_path.relative_to(_REPO)),
        "original_size_bytes": original_size,
        "archive_size_bytes": archive_size,
        "compression_ratio": round(original_size / max(archive_size, 1), 2),
        "post_size_bytes": post_size,
        "rows_preserved": n_written,
        "pre_sha256": pre_sha,
        "post_sha256": post_sha,
        "bytes_freed": original_size - post_size,
    }
    receipt_row = {
        "receipt_id": uuid.uuid4().hex[:16],
        "agent_id": "ROTATOR_COWORK",
        "work_type": "LEDGER_ROTATION",
        "description": (
            f"Rotated {target.name}: archived {original_size/1e9:.2f} GB → "
            f"{archive_size/1e6:.1f} MB gzip; kept last {n_written} rows; "
            f"freed {(original_size - post_size)/1e9:.2f} GB"
        ),
        "timestamp": time.time(),
        "work_value": 0.30,
        "territory": "disk_hygiene",
        "output_hash": hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode()
        ).hexdigest()[:12],
        "payload": payload,
    }
    with (state / "work_receipts.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(receipt_row, sort_keys=True) + "\n")
    return {
        "ok": True,
        "truth_label": TRUTH_LABEL,
        **payload,
        "receipt_id": receipt_row["receipt_id"],
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--keep", type=int, default=10_000,
                   help="number of most-recent rows to preserve (default 10000)")
    p.add_argument("--dry-run", action="store_true",
                   help="report what would happen without writing anything")
    args = p.parse_args()
    out = rotate(keep_last_n=args.keep, dry_run=args.dry_run)
    print()
    print(json.dumps(out, indent=2, default=str))
    sys.exit(0 if out.get("ok") else 1)
