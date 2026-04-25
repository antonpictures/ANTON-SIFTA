#!/usr/bin/env python3
"""
Split physically joined JSON objects on one line in ide_stigmergic_trace.jsonl.

Historical writers sometimes appended `}{` without a newline between records,
which makes json.loads(line) raise "Extra data". This script rewrites the file
so each line is exactly one JSON object. Unrecoverable fragments go to a sidecar.

Uses System.ide_trace_defensive.split_physical_line_to_dicts (same recovery
rules as defensive readers).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.ide_trace_defensive import split_physical_line_to_dicts  # noqa: E402


def repair(trace: Path, *, dry_run: bool) -> dict:
    corrupt_sidecar = trace.parent / "ide_stigmergic_trace_corrupt_fragments.jsonl"
    lines = trace.read_text(encoding="utf-8", errors="replace").splitlines()
    out_lines: list[str] = []
    stats: dict = {"lines_in": 0, "lines_out": 0, "split_joined": 0, "corrupt": 0, "fixed_literal_nl": 0}

    for physical_line in lines:
        stats["lines_in"] += 1
        raw = physical_line
        if raw.endswith("\\n"):
            raw = raw[:-2]
            stats["fixed_literal_nl"] += 1
        if not raw.strip():
            continue

        objs = split_physical_line_to_dicts(raw)
        if len(objs) >= 2:
            stats["split_joined"] += 1
            for o in objs:
                out_lines.append(json.dumps(o, ensure_ascii=False))
                stats["lines_out"] += 1
            continue
        if len(objs) == 1:
            out_lines.append(json.dumps(objs[0], ensure_ascii=False))
            stats["lines_out"] += 1
            continue

        try:
            one = json.loads(raw.strip())
            out_lines.append(json.dumps(one, ensure_ascii=False))
            stats["lines_out"] += 1
        except json.JSONDecodeError:
            stats["corrupt"] += 1
            row = {
                "ts": time.time(),
                "kind": "CORRUPT_TRACE_FRAGMENT",
                "original_line_preview": raw[:800],
            }
            if not dry_run:
                corrupt_sidecar.parent.mkdir(parents=True, exist_ok=True)
                with corrupt_sidecar.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    if dry_run:
        return stats
    backup = trace.with_suffix(trace.suffix + f".bak.{int(time.time())}")
    shutil.copy2(trace, backup)
    trace.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    stats["backup_path"] = str(backup)
    return stats


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--trace",
        type=Path,
        default=_REPO / ".sifta_state" / "ide_stigmergic_trace.jsonl",
    )
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    st = repair(args.trace, dry_run=args.dry_run)
    print(json.dumps(st, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
