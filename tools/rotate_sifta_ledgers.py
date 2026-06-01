#!/usr/bin/env python3
"""Rotate oversized append-only SIFTA stigmergic ledgers (r251 infra debt).

The consolidated WHAT-IS-LEFT after r249 flagged two bloated ledgers:
  - .sifta_state/fractal_pheromone_field.jsonl  (~1.29 GB)
  - .sifta_state/matrix_terminal_process_trace.jsonl (~366 MB)

A 1 GB+ live ledger slows every read/append and bloats boot. These are stigmergic
traces: recent rows are what matter, old rows have decayed. This tool keeps a generous
recent tail in the live file and moves the full history into .sifta_state/ledger_archive/.

SAFE BY DESIGN:
  * Staleness guard — skips any ledger modified within --min-stale-seconds (default 1800),
    so it never yanks a ledger out from under a live Alice organ / a peer writer.
  * No data loss — the complete original is preserved in the archive (hardlink when the
    filesystem allows it, else an atomic rename) BEFORE the live file is replaced.
  * Atomic swap — the new (tail-only) live file is put in place with os.replace, so a
    reader sees either the old file or the new one, never a partial write.
  * Receipt — one row per rotation to .sifta_state/ledger_rotation.jsonl.

This is an IDE-doctor coordination tool. The rotation receipt is a forgeable operational
trace (covenant 4.2), NOT an Alice swimmer receipt and NOT an STGM economy row.

Usage:
  python3 tools/rotate_sifta_ledgers.py --dry-run
  python3 tools/rotate_sifta_ledgers.py --keep 25000
  python3 tools/rotate_sifta_ledgers.py --all-over-mb 256          # rotate every big ledger
  python3 tools/rotate_sifta_ledgers.py --targets fractal_pheromone_field.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_STATE = _REPO / ".sifta_state"
_ARCHIVE = _STATE / "ledger_archive"
_ROTATION_LEDGER = _STATE / "ledger_rotation.jsonl"

# Default targets named in the r249 WHAT-IS-LEFT list.
_DEFAULT_TARGETS = [
    "fractal_pheromone_field.jsonl",
    "matrix_terminal_process_trace.jsonl",
]


def tail_lines(path: Path, n: int) -> list[bytes]:
    """Return the last ``n`` lines of a (possibly huge) file without reading it whole.

    Reads fixed blocks backward from EOF until ``n`` newlines are seen, so a 1 GB file
    costs only a few MB of I/O from the end.
    """
    if n <= 0:
        return []
    block = 1 << 20  # 1 MiB
    chunks: list[bytes] = []
    newlines = 0
    with path.open("rb") as f:
        f.seek(0, os.SEEK_END)
        pos = f.tell()
        while pos > 0 and newlines <= n:
            read = min(block, pos)
            pos -= read
            f.seek(pos)
            chunk = f.read(read)
            chunks.append(chunk)
            newlines += chunk.count(b"\n")
    data = b"".join(reversed(chunks))
    lines = data.splitlines(keepends=True)
    return lines[-n:]


def rotate_one(name: str, *, keep: int, min_stale_s: float, dry_run: bool) -> dict:
    p = _STATE / name
    if not p.exists():
        return {"ledger": name, "status": "absent"}
    st = p.stat()
    age = time.time() - st.st_mtime
    if age < min_stale_s:
        return {"ledger": name, "status": "skipped_active",
                "age_s": round(age, 1), "min_stale_s": min_stale_s, "bytes": st.st_size}

    tail = tail_lines(p, keep)
    # Guard: only rotate if the file is meaningfully larger than the tail we keep.
    # Cheap proxy — if the tail we read spans ~the whole file, rotation is pointless.
    tail_bytes = sum(len(x) for x in tail)
    if tail_bytes >= st.st_size * 0.9:
        return {"ledger": name, "status": "small_enough",
                "bytes": st.st_size, "rows_kept": len(tail)}

    if dry_run:
        return {"ledger": name, "status": "dry_run",
                "bytes_before": st.st_size, "would_keep_rows": len(tail),
                "approx_tail_bytes": tail_bytes}

    _ARCHIVE.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    archived = _ARCHIVE / f"{name}.{ts}.archived.jsonl"
    tmp = p.with_name(f"{name}.rot{ts}.tmp")

    # Write the tail to a temp file first — nothing is destroyed yet.
    with tmp.open("wb") as out:
        out.writelines(tail)

    archive_method = "hardlink"
    try:
        os.link(p, archived)        # instant; original inode preserved under archive name
        os.replace(tmp, p)          # atomic swap of live file to the tail (no reader gap)
    except OSError:
        # Fallback for filesystems without hardlink support (e.g. some network mounts):
        # two-step rename. Tiny window where the path is the archive name; acceptable on a
        # stale ledger (staleness guard above means no active writer/reader is expected).
        archive_method = "rename_fallback"
        os.replace(p, archived)
        os.replace(tmp, p)

    after = p.stat().st_size
    return {
        "ledger": name,
        "status": "rotated",
        "bytes_before": st.st_size,
        "bytes_after": after,
        "rows_kept": len(tail),
        "archived_to": str(archived.relative_to(_REPO)),
        "archive_method": archive_method,
    }


def _receipt(results: list[dict]) -> None:
    rotated = [r for r in results if r.get("status") == "rotated"]
    if not rotated:
        return
    row = {
        "ts": time.time(),
        "kind": "LEDGER_ROTATION",
        "tool": "tools/rotate_sifta_ledgers.py",
        "round_id": "r251-cowork-ledger-rotation",
        "doctor": "cowork_claude",
        "lane": "IDE_DOCTOR_CLAIM",
        "currency": "MANA",
        "forgeable": True,
        "alice_swimmer_receipt": False,
        "rotations": rotated,
        "note": "Rotated oversized append-only ledgers; full history preserved in ledger_archive/.",
    }
    try:
        _STATE.mkdir(parents=True, exist_ok=True)
        with _ROTATION_LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception as exc:  # never raise from a receipt
        print(f"rotate_sifta_ledgers: receipt write failed: {exc}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--keep", type=int, default=25000,
                    help="number of recent rows to keep in the live file (default 25000)")
    ap.add_argument("--min-stale-seconds", type=float, default=1800.0,
                    help="skip ledgers modified more recently than this (default 1800)")
    ap.add_argument("--targets", nargs="*", default=None,
                    help="explicit ledger filenames under .sifta_state (default: the two r249 targets)")
    ap.add_argument("--all-over-mb", type=float, default=None,
                    help="rotate EVERY .sifta_state/*.jsonl larger than this many MB")
    ap.add_argument("--dry-run", action="store_true", help="report only; do not mutate")
    args = ap.parse_args()

    if args.all_over_mb is not None:
        thresh = args.all_over_mb * (1 << 20)
        targets = sorted(
            p.name for p in _STATE.glob("*.jsonl")
            if p.is_file() and p.stat().st_size > thresh
        )
    else:
        targets = args.targets or _DEFAULT_TARGETS

    results = [rotate_one(name, keep=args.keep,
                          min_stale_s=args.min_stale_seconds, dry_run=args.dry_run)
               for name in targets]

    if not args.dry_run:
        _receipt(results)

    print(json.dumps({"dry_run": args.dry_run, "keep": args.keep, "results": results},
                     indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
