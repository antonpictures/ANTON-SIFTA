#!/usr/bin/env python3
"""EVAL-6 coverage gate and dashboard row.

Uses Python's stdlib trace module when the third-party coverage package is not
installed. The reported percentage is measured from executed line counts, never
hardcoded.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
_DEFAULT_MODULE = _REPO / "System" / "swarm_eval_loop.py"
_DEFAULT_TESTS = [
    "tests/test_eval_loop.py",
    "tests/test_eval_loop_talk.py",
    "tests/test_eval_talk_labeling_helper.py",
    "tests/test_eval_loop_skill.py",
    "tests/test_eval_loop_judge.py",
    "tests/test_eval_loop_regression.py",
    "tests/test_eval_loop_all.py",
    "tests/test_eval_golden_integrity.py",
]
_DASHBOARD = _REPO / ".sifta_state" / "eval" / "company_dashboard.jsonl"
_ORGAN_COVERAGE = _REPO / ".sifta_state" / "eval" / "organ_coverage.jsonl"


def parse_trace_cover_text(text: str) -> Dict[str, Any]:
    executed = 0
    missing = 0
    for line in text.splitlines():
        if line.startswith(">>>>>>"):
            missing += 1
            continue
        prefix = line.split(":", 1)[0].strip() if ":" in line else ""
        if prefix.isdigit():
            executed += 1
    total = executed + missing
    percent = (executed / total * 100.0) if total else 0.0
    return {
        "executed_lines": executed,
        "missing_lines": missing,
        "total_lines": total,
        "percent": round(percent, 2),
    }


def _module_cover_name(module_path: Path) -> str:
    rel = module_path.resolve().relative_to(_REPO)
    return ".".join(rel.with_suffix("").parts) + ".cover"


def _tests_passed(stdout: str) -> int:
    match = re.search(r"(\d+)\s+passed", stdout)
    return int(match.group(1)) if match else 0


def run_coverage_gate(
    *,
    module_path: Path = _DEFAULT_MODULE,
    tests: Optional[List[str]] = None,
    threshold: float = 80.0,
) -> Dict[str, Any]:
    """Run pytest under stdlib trace and return a real line-coverage report."""
    if tests is None:
        tests = list(_DEFAULT_TESTS)
    module_path = module_path.resolve()
    with tempfile.TemporaryDirectory(prefix="sifta_eval_coverage_") as td:
        coverdir = Path(td)
        cmd = [
            sys.executable,
            "-m",
            "trace",
            "--count",
            "--missing",
            "--coverdir",
            str(coverdir),
            "--module",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            *tests,
        ]
        proc = subprocess.run(
            cmd,
            cwd=_REPO,
            capture_output=True,
            text=True,
            timeout=180,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        cover_name = _module_cover_name(module_path)
        cover_path = next(coverdir.rglob(cover_name), None)
        counts = parse_trace_cover_text(cover_path.read_text(encoding="utf-8") if cover_path else "")

    report = {
        "tool": "stdlib_trace",
        "module": str(module_path.relative_to(_REPO)),
        "tests": tests,
        "tests_passed": _tests_passed(proc.stdout),
        "pytest_returncode": proc.returncode,
        "threshold": float(threshold),
        "ok": proc.returncode == 0 and counts["percent"] >= threshold,
        "stdout_tail": "\n".join(proc.stdout.splitlines()[-5:]),
        "stderr_tail": "\n".join(proc.stderr.splitlines()[-5:]),
    }
    report.update(counts)
    return report


def _git_commit_count(repo: Path = _REPO) -> int:
    try:
        out = subprocess.check_output(["git", "rev-list", "--count", "HEAD"], cwd=repo, text=True)
        return int(out.strip())
    except Exception:
        return 0


def _stgm_burn(state_root: Path = _REPO / ".sifta_state") -> float:
    path = state_root / "stgm_memory_rewards.jsonl"
    burn = 0.0
    if not path.exists():
        return burn
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except Exception:
            continue
        amount = row.get("amount")
        if isinstance(amount, (int, float)) and amount < 0:
            burn += abs(float(amount))
    return round(burn, 6)


def _eval_pass_rate() -> float:
    from System import swarm_eval_loop as loop

    with tempfile.TemporaryDirectory(prefix="sifta_eval_dashboard_") as td:
        root = Path(td)
        reports = [
            loop.run_eval_pack(metrics_path=root / "memory.jsonl", receipts_path=root / "receipts.jsonl", write_receipt=False),
            loop.run_talk_eval(metrics_path=root / "talk.jsonl", receipts_path=root / "receipts.jsonl", write_receipt=False),
            loop.run_skill_eval(metrics_path=root / "skill.jsonl", receipts_path=root / "receipts.jsonl", write_receipt=False),
            loop.run_regression_eval(metrics_path=root / "regression.jsonl", receipts_path=root / "receipts.jsonl", write_receipt=False),
        ]
    total = sum(len(report.get("turns", [])) for report in reports)
    passed = sum(int(report.get("passed", 0)) for report in reports)
    return round(passed / total, 6) if total else 0.0


def build_dashboard_row(coverage_report: Dict[str, Any], *, repo: Path = _REPO) -> Dict[str, Any]:
    now = _dt.datetime.now(_dt.timezone.utc)
    iso = now.isocalendar()
    return {
        "ts": time.time(),
        "week": f"{iso.year}-W{iso.week:02d}",
        "commits": _git_commit_count(repo),
        "tests_passed": int(coverage_report.get("tests_passed", 0)),
        "eval_pass_rate": _eval_pass_rate(),
        "stgm_burn": _stgm_burn(repo / ".sifta_state"),
        "coverage_percent": float(coverage_report.get("percent", 0.0)),
        "coverage_ok": bool(coverage_report.get("ok", False)),
        "coverage_tool": coverage_report.get("tool", "unknown"),
    }


def append_dashboard_row(row: Dict[str, Any], path: Path = _DASHBOARD) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")


def run_organ_coverage_gate(
    *,
    state_dir: Path = _REPO / ".sifta_state",
    max_age_days: float = 7.0,
    out_path: Optional[Path] = _ORGAN_COVERAGE,
    write_receipt: bool = True,
) -> Dict[str, Any]:
    """Check canonical organs for ledger presence, freshness, and outcome evidence."""
    from System.swarm_canonical_organ_registry import build_registry, _read_jsonl_tail, _row_outcome

    now = time.time()
    max_age_s = float(max_age_days) * 86400.0
    snap = build_registry(state_dir=state_dir, include_dynamic=False)
    canonical = [o for o in snap.get("organs", []) if o.get("source_registry") == "CANONICAL_ORGANS"]
    run_id = f"organ-coverage-{int(now)}"
    rows: List[Dict[str, Any]] = []

    for organ in canonical:
        ledger_details: List[Dict[str, Any]] = []
        for ledger in organ.get("ledgers", []) or []:
            path = state_dir / str(ledger)
            exists = path.exists()
            age_s = None
            row_count = 0
            outcome_rows = 0
            if exists:
                try:
                    age_s = max(0.0, now - path.stat().st_mtime)
                except OSError:
                    age_s = None
                if path.suffix == ".jsonl":
                    tail = _read_jsonl_tail(path, limit=120)
                    row_count = len(tail)
                    outcome_rows = sum(1 for row in tail if _row_outcome(row)[0] is not None)
            ledger_details.append({
                "ledger": str(ledger),
                "exists": exists,
                "age_s": None if age_s is None else round(age_s, 3),
                "fresh": bool(age_s is not None and age_s <= max_age_s),
                "tail_rows": row_count,
                "outcome_rows": outcome_rows,
            })

        any_ledger = any(item["exists"] for item in ledger_details)
        any_fresh = any(item["fresh"] for item in ledger_details)
        any_outcome = any(item["outcome_rows"] > 0 for item in ledger_details)
        ok = any_ledger and any_fresh and any_outcome
        if not any_ledger:
            status = "NO_LEDGER"
        elif not any_fresh:
            status = "COLD"
        elif not any_outcome:
            status = "NO_OUTCOME_ROWS"
        else:
            status = "COVERED"
        row = {
            "ts": now,
            "run_id": run_id,
            "truth_label": "CANONICAL_ORGAN_COVERAGE_V1",
            "organ_id": organ.get("organ_id"),
            "display_name": organ.get("display_name"),
            "ok": ok,
            "status": status,
            "ledger_exists": any_ledger,
            "fresh_ledger": any_fresh,
            "outcome_bearing_row": any_outcome,
            "max_age_days": max_age_days,
            "ledgers": ledger_details,
        }
        rows.append(row)

    if write_receipt and out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("a", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, sort_keys=True) + "\n")

    status_counts: Dict[str, int] = {}
    for row in rows:
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
    holes = [row for row in rows if not row["ok"]]
    return {
        "run_id": run_id,
        "truth_label": "CANONICAL_ORGAN_COVERAGE_SUMMARY_V1",
        "ts": now,
        "ok": not holes,
        "canonical_organs": len(rows),
        "covered": len(rows) - len(holes),
        "holes": len(holes),
        "status_counts": status_counts,
        "hole_rank": [
            {
                "organ_id": row["organ_id"],
                "status": row["status"],
                "missing": [
                    key
                    for key, present in (
                        ("ledger_exists", row["ledger_exists"]),
                        ("fresh_ledger", row["fresh_ledger"]),
                        ("outcome_bearing_row", row["outcome_bearing_row"]),
                    )
                    if not present
                ],
            }
            for row in holes
        ],
        "out_path": str(out_path) if out_path is not None else None,
    }


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run EVAL-6 coverage gate and optional dashboard append.")
    parser.add_argument("tests", nargs="*", help="pytest files to run under trace")
    parser.add_argument("--module", default=str(_DEFAULT_MODULE), help="module file to measure")
    parser.add_argument("--threshold", type=float, default=80.0)
    parser.add_argument("--dashboard-path", default=str(_DASHBOARD))
    parser.add_argument("--append-dashboard", action="store_true")
    parser.add_argument("--organ-coverage", action="store_true", help="also run canonical-organ coverage gate")
    parser.add_argument("--organ-coverage-path", default=str(_ORGAN_COVERAGE))
    parser.add_argument("--max-age-days", type=float, default=7.0)
    args = parser.parse_args(list(argv) if argv is not None else None)

    report = run_coverage_gate(
        module_path=Path(args.module),
        tests=args.tests or None,
        threshold=args.threshold,
    )
    row = build_dashboard_row(report)
    payload = {"coverage": report, "dashboard_row": row}
    if args.append_dashboard:
        append_dashboard_row(row, Path(args.dashboard_path))
        payload["dashboard_path"] = str(Path(args.dashboard_path))
    if args.organ_coverage:
        payload["organ_coverage"] = run_organ_coverage_gate(
            max_age_days=args.max_age_days,
            out_path=Path(args.organ_coverage_path),
            write_receipt=True,
        )
    print(json.dumps(payload, sort_keys=True))
    organ_ok = payload.get("organ_coverage", {}).get("ok", True)
    return 0 if report["ok"] and organ_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
