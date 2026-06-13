#!/usr/bin/env python3
"""Download ABB IRB 2400 IK dataset and refresh the sanitized pytest fixture slice."""
from __future__ import annotations

import argparse
import csv
import shutil
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.stigmerobotics_irb2400_ik import (  # noqa: E402
    DATASET_FILENAME,
    DATASET_SLUG,
    IRB2400_COLUMNS,
    _DEFAULT_FIXTURE,
    _FULL_DATASET,
)


def _download_full_csv(dest: Path) -> Path:
    try:
        import kagglehub
    except ImportError as exc:
        raise SystemExit("kagglehub required: pip install kagglehub") from exc
    cache = Path(kagglehub.dataset_download(DATASET_SLUG))
    matches = list(cache.rglob(DATASET_FILENAME))
    if not matches:
        raise FileNotFoundError(f"{DATASET_FILENAME} not found under {cache}")
    src = matches[0]
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return dest


def _write_fixture_slice(src: Path, dest: Path, *, head_rows: int, stride: int) -> int:
    kept = 0
    with src.open(newline="", encoding="utf-8") as f_in, dest.open("w", newline="", encoding="utf-8") as f_out:
        reader = csv.reader(f_in)
        writer = csv.writer(f_out)
        header = next(reader)
        if header != list(IRB2400_COLUMNS):
            raise ValueError(f"unexpected header: {header}")
        writer.writerow(header)
        for idx, row in enumerate(reader):
            if idx < head_rows or idx % stride == 0:
                writer.writerow(row)
                kept += 1
    return kept


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--head-rows", type=int, default=50, help="Always keep first N rows in fixture")
    parser.add_argument("--stride", type=int, default=1500, help="Keep every Nth row after head block")
    parser.add_argument("--fixture-only", action="store_true", help="Rebuild fixture from cached full CSV")
    args = parser.parse_args()

    full_path = _FULL_DATASET
    if not args.fixture_only or not full_path.exists():
        print(f"Downloading {DATASET_SLUG} …")
        full_path = _download_full_csv(full_path)
        print(f"Full dataset: {full_path} ({full_path.stat().st_size} bytes)")

    kept = _write_fixture_slice(full_path, _DEFAULT_FIXTURE, head_rows=args.head_rows, stride=args.stride)
    print(f"Fixture slice: {_DEFAULT_FIXTURE} ({kept} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())