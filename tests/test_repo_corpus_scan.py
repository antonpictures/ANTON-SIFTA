"""Repo corpus scan tool — tracked file count, LOC buckets, birth-time probe."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tools.repo_corpus_scan import (
    _bucket_for_path,
    format_scan_summary,
    scan_tracked_corpus,
    write_scan_receipt,
)


def test_bucket_for_path_python():
    assert _bucket_for_path("System/swarm_foo.py") == "python"
    assert _bucket_for_path("docs/readme.md") == "markdown"


def test_scan_tracked_corpus_on_repo():
    repo = Path(__file__).resolve().parents[1]
    report = scan_tracked_corpus(repo=repo)
    assert report["tracked_file_count"] > 100
    assert report["total_lines"] > 1000
    assert "python" in (report.get("bucket_lines") or {})
    assert report.get("earliest_by_birth_time", {}).get("path")


def test_format_scan_summary_includes_totals():
    report = {
        "truth_label": "REPO_CORPUS_SCAN_V1",
        "tracked_file_count": 10,
        "total_lines": 100,
        "bucket_lines": {"python": 80},
        "bucket_files": {"python": 5},
        "earliest_by_birth_time": {"path": "a.py", "birth_local": "2026-01-01"},
    }
    text = format_scan_summary(report)
    assert "tracked files: 10" in text
    assert "python" in text


def test_write_scan_receipt(tmp_path: Path):
    report = scan_tracked_corpus(repo=Path(__file__).resolve().parents[1])
    ledger = write_scan_receipt(report, state_dir=tmp_path)
    assert ledger.exists()
    row = json.loads(ledger.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert row["event"] == "repo_corpus_scan"
    assert row["tracked_file_count"] == report["tracked_file_count"]