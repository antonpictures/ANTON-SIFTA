#!/usr/bin/env python3
"""Download ARKOMA NAO IK dataset (Mendeley DOI 10.17632/brg4dz8nbb.1) and refresh pytest fixture."""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.stigmerobotics_arkoma_ik import ARKOMA_COLUMNS, _DATASET_DIR, _DEFAULT_FIXTURE  # noqa: E402

DATASET_DOI = "10.17632/brg4dz8nbb.1"

PAIR_SPECS = (
    ("LTrain_x.csv", "LTrain_y.csv", "left", "train"),
    ("LVal_x.csv", "LVal_y.csv", "left", "val"),
    ("LTest_x.csv", "LTest_y.csv", "left", "test"),
    ("RTrain_x.csv", "RTrain_y.csv", "right", "train"),
    ("RVal_x.csv", "RVal_y.csv", "right", "val"),
    ("RTest_x.csv", "RTest_y.csv", "right", "test"),
)


def _download_dataset(dest: Path) -> None:
    try:
        from datahugger import get
    except ImportError as exc:
        raise SystemExit("datahugger required: pip install datahugger") from exc
    dest.mkdir(parents=True, exist_ok=True)
    get(DATASET_DOI, dest, unzip=True)


def _write_fixture_slice(src: Path, dest: Path, *, head_rows: int, stride: int) -> int:
    header = list(ARKOMA_COLUMNS)
    kept = 0
    with dest.open("w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        writer.writerow(header)
        for xname, yname, arm, split in PAIR_SPECS:
            xpath = src / xname
            ypath = src / yname
            if not xpath.exists() or not ypath.exists():
                continue
            with xpath.open(newline="", encoding="utf-8") as xf, ypath.open(newline="", encoding="utf-8") as yf:
                x_reader = csv.DictReader(xf)
                y_reader = csv.DictReader(yf)
                for idx, (xrow, yrow) in enumerate(zip(x_reader, y_reader)):
                    if idx < head_rows or idx % stride == 0:
                        writer.writerow(
                            [xrow[c] for c in header[:6]]
                            + [yrow[c] for c in header[6:11]]
                            + [arm, split]
                        )
                        kept += 1
    return kept


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--head-rows", type=int, default=40, help="Always keep first N rows per split file")
    parser.add_argument("--stride", type=int, default=200, help="Keep every Nth row after head block")
    parser.add_argument("--fixture-only", action="store_true", help="Rebuild fixture from cached CSV files")
    args = parser.parse_args()

    dataset_dir = _DATASET_DIR
    if not args.fixture_only or not any(dataset_dir.glob("*.csv")):
        print(f"Downloading {DATASET_DOI} …")
        _download_dataset(dataset_dir)
        print(f"Dataset dir: {dataset_dir}")

    kept = _write_fixture_slice(dataset_dir, _DEFAULT_FIXTURE, head_rows=args.head_rows, stride=args.stride)
    print(f"Fixture slice: {_DEFAULT_FIXTURE} ({kept} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())