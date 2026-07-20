#!/usr/bin/env python3
"""Tracked-repo corpus scan — LOC buckets, birth-time probe, scan receipt.

George r1343 / r1342-repo-scan-cursor-corpus workload:
  - ``git ls-files`` tracked corpus count
  - aggregate ``wc -l`` total
  - LOC split by language/format extension buckets
  - earliest tracked file by creation time (birth time, not mtime)

Truth label: REPO_CORPUS_SCAN_V1
Pure stdlib. Never raises from ``scan_tracked_corpus``.
"""
from __future__ import annotations

import json
import subprocess
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

TRUTH_LABEL = "REPO_CORPUS_SCAN_V1"
SCHEMA = "REPO_CORPUS_SCAN_V1"

_REPO = Path(__file__).resolve().parent.parent

# Extension → human bucket. First match wins; '' = no extension bucket.
_EXT_BUCKETS: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".json": "json",
    ".jsonl": "jsonl",
    ".md": "markdown",
    ".rst": "markdown",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "css",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".ini": "config",
    ".cfg": "config",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
    ".sql": "sql",
    ".tex": "latex",
    ".svg": "vector",
    ".png": "binary_image",
    ".jpg": "binary_image",
    ".jpeg": "binary_image",
    ".gif": "binary_image",
    ".webp": "binary_image",
    ".ico": "binary_image",
    ".pdf": "binary",
    ".zip": "binary",
    ".gz": "binary",
    ".woff": "binary",
    ".woff2": "binary",
    ".ttf": "binary",
    ".otf": "binary",
    ".mp3": "binary_audio",
    ".wav": "binary_audio",
    ".mp4": "binary_video",
    ".mov": "binary_video",
    ".ipynb": "notebook",
    ".csv": "tabular",
    ".tsv": "tabular",
    ".xml": "xml",
    ".plist": "plist",
    ".lock": "lockfile",
}


def _bucket_for_path(rel: str) -> str:
    suffixes = Path(rel).suffixes
    if not suffixes:
        return "no_extension"
    for ext in reversed(suffixes):
        key = ext.lower()
        if key in _EXT_BUCKETS:
            return _EXT_BUCKETS[key]
    return suffixes[-1].lstrip(".").lower() or "other"


def _git_tracked_files(repo: Path) -> list[str]:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(repo), "ls-files", "-z"],
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    parts = [p.decode("utf-8", errors="replace") for p in out.split(b"\0") if p]
    return parts


def _birth_time(path: Path) -> Optional[float]:
    try:
        st = path.stat()
    except OSError:
        return None
    birth = getattr(st, "st_birthtime", None)
    if birth is not None:
        return float(birth)
    return float(st.st_mtime)


def _count_lines(path: Path) -> int:
    try:
        with path.open("rb") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return 0


@dataclass
class ScanResult:
    tracked_file_count: int
    total_lines: int
    bucket_lines: dict[str, int]
    bucket_files: dict[str, int]
    earliest: dict[str, Any]
    scan_ts: float
    repo_root: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "truth_label": TRUTH_LABEL,
            "tracked_file_count": self.tracked_file_count,
            "total_lines": self.total_lines,
            "bucket_lines": dict(sorted(self.bucket_lines.items(), key=lambda kv: -kv[1])),
            "bucket_files": dict(sorted(self.bucket_files.items(), key=lambda kv: -kv[1])),
            "earliest_by_birth_time": self.earliest,
            "scan_ts": self.scan_ts,
            "repo_root": self.repo_root,
        }


def scan_tracked_corpus(*, repo: Optional[Path | str] = None) -> dict[str, Any]:
    """Scan git-tracked corpus; return JSON-serializable receipt dict."""
    root = Path(repo) if repo is not None else _REPO
    tracked = _git_tracked_files(root)
    bucket_lines: dict[str, int] = defaultdict(int)
    bucket_files: dict[str, int] = defaultdict(int)
    total_lines = 0
    earliest_path = ""
    earliest_birth: Optional[float] = None

    for rel in tracked:
        bucket = _bucket_for_path(rel)
        bucket_files[bucket] += 1
        path = root / rel
        if not path.is_file():
            continue
        lines = _count_lines(path)
        total_lines += lines
        bucket_lines[bucket] += lines
        birth = _birth_time(path)
        if birth is None:
            continue
        if earliest_birth is None or birth < earliest_birth:
            earliest_birth = birth
            earliest_path = rel

    earliest: dict[str, Any] = {}
    if earliest_path and earliest_birth is not None:
        earliest = {
            "path": earliest_path,
            "birth_epoch": earliest_birth,
            "birth_local": time.strftime(
                "%Y-%m-%d %H:%M:%S %Z",
                time.localtime(earliest_birth),
            ),
        }

    result = ScanResult(
        tracked_file_count=len(tracked),
        total_lines=total_lines,
        bucket_lines=dict(bucket_lines),
        bucket_files=dict(bucket_files),
        earliest=earliest,
        scan_ts=time.time(),
        repo_root=str(root),
    )
    return result.to_dict()


def format_scan_summary(report: dict[str, Any], *, top_buckets: int = 12) -> str:
    lines = [
        f"REPO CORPUS SCAN ({report.get('truth_label')}):",
        f"- tracked files: {report.get('tracked_file_count')}",
        f"- total lines (wc -l aggregate): {report.get('total_lines')}",
    ]
    earliest = report.get("earliest_by_birth_time") or {}
    if earliest:
        lines.append(
            f"- earliest by birth time: {earliest.get('path')} @ {earliest.get('birth_local')}"
        )
    lines.append("")
    lines.append("LOC by bucket (lines / files):")
    bucket_lines = report.get("bucket_lines") or {}
    bucket_files = report.get("bucket_files") or {}
    for bucket, line_count in list(bucket_lines.items())[:top_buckets]:
        files = bucket_files.get(bucket, 0)
        lines.append(f"  {bucket:16s}  {line_count:>10,d} lines  {files:>5,d} files")
    return "\n".join(lines)


def write_scan_receipt(
    report: dict[str, Any],
    *,
    state_dir: Optional[Path | str] = None,
) -> Path:
    import sys

    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
    from System.jsonl_file_lock import append_line_locked

    base = Path(state_dir) if state_dir is not None else (_REPO / ".sifta_state")
    if base.name != ".sifta_state":
        base = base / ".sifta_state"
    base.mkdir(parents=True, exist_ok=True)
    ledger = base / "repo_corpus_scan.jsonl"
    row = dict(report)
    row["event"] = "repo_corpus_scan"
    append_line_locked(ledger, json.dumps(row, sort_keys=True) + "\n")
    return ledger


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Scan git-tracked SIFTA corpus")
    ap.add_argument("--json", action="store_true", help="Emit JSON only")
    ap.add_argument("--write-receipt", action="store_true", help="Append to repo_corpus_scan.jsonl")
    ap.add_argument("--repo", default=str(_REPO))
    args = ap.parse_args()
    report = scan_tracked_corpus(repo=args.repo)
    if args.write_receipt:
        write_scan_receipt(report)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(format_scan_summary(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())