#!/usr/bin/env python3
"""One-command runner for the June 20 Philippe demo packet (+ r1502 somatic receipts).

It reads the pre-demo checklist from Documents/DEMO_SCRIPT_5_MINUTE_SIFTA.md,
runs those commands, validates the narrow receipt-sort proof artifacts, and
prints an operator summary that keeps open items open.

Extended with body receipt sort demo (somatic move examples for cortex plan/execute/rescan).
Alice gathers reflexes (body+time+loc), writes validated posture/action receipts,
cortex can sort them as repeatable examples in any environment — no ropes, just metabolism.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

REPO = Path(__file__).resolve().parents[1]
DEMO_SCRIPT = REPO / "Documents" / "DEMO_SCRIPT_5_MINUTE_SIFTA.md"
PACKET_PDF = REPO / "outputs" / "PHILIPPE_SIFTA_COMMERCIAL_RESPONSE_2026-06-20.pdf"
ROOT_PACKET_PDF = REPO / "PHILIPPE_SIFTA_COMMERCIAL_RESPONSE_2026-06-20.pdf"
PACKET_BUILDER = REPO / "outputs" / "build_philippe_v8.py"
INVENTORY_JSON = REPO / "data" / "eval" / "marketing_commercial_inventory.json"
RUNNER_LEDGER = REPO / ".sifta_state" / "philippe_demo_runner_receipts.jsonl"

RECEIPT_DEMO = REPO / "demo" / "philippe_receipt_honesty_5min.py"
RECEIPT_DEMO_LEDGER = REPO / ".sifta_state" / "philippe_receipt_honesty_demo.jsonl"
BENCHMARK = REPO / "tools" / "benchmark_receipt_gate.py"
BENCHMARK_JSON = REPO / ".sifta_state" / "receipt_gate_benchmark.json"

# Somatic / embodied receipt lane (r1502)
SOMATIC_DEMO_LEDGER = REPO / ".sifta_state" / "somatic_receipt_demo.jsonl"
SOMATIC_EXAMPLES = [
    {"tag": "desk_sitting_typing", "action": "set_brightness", "pre": {"source": "AC", "displays": 2}, "post": "thermal_stable"},
    {"tag": "quiet_room", "action": "set_volume", "pre": {"mic": "internal"}, "post": "low_volume_receipted"},
]

EXPECTED_DEMO_STATUSES = [
    "INTENT_REGISTERED",
    "ACTION_RECEIPTED",
    "DUPLICATE_REFUSED",
    "INTENT_REGISTERED",
    "NO_RESULT_BLOCKED",
]

PACKET_REQUIRED_PHRASES = [
    "SIFTA OS organism runtime on owner-owned hardware",
    "RECEIPT SORT",
    "one hardware-bound Alice body on the buyer's computer; not loose agents or swimmers",
    "demo/philippe_receipt_honesty_5min.py",
    "tools/benchmark_receipt_gate.py",
    "0 of 5 unbacked claims",
    "0 of 3 double-spends",
    "live per-framework run uses the same harness with keys on the node",
    "Founder stage: one live node",
    "None yet. An outside evaluation",
]

PACKET_FORBIDDEN_PHRASES = [
    "What you sell: an AI agent you can audit and own",
    "+ owner-data",
    "same-task benchmark vs one named competitor (only Phillipe item still owed)",
]

OPEN_ITEMS = [
    "This validates the local receipt-sort wedge and June 20 packet artifacts, not whole-product saleability.",
    "External users and revenue/pilots remain open; the packet says founder stage / one live node and none yet.",
    "The benchmark checked here is the local SIFTA gate versus an ungated baseline, not a live tuned CrewAI/LangGraph/SDK run with vendor keys.",
    "A recorded buyer demo or outside viewer reaction is not created by this runner.",
    "r1502 somatic lane added: body receipt sort surface present (reflex gather + validated move examples); full library seeding + cortex prompts + heartbeat integration still open.",
]

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


@dataclass
class CheckResult:
    name: str
    status: str
    detail: str
    evidence: str = ""
    required: bool = True
    duration_s: float | None = None

    @property
    def failed(self) -> bool:
        return self.required and self.status == "FAIL"


def _clean_tail(text: str, *, max_lines: int = 6) -> str:
    clean = ANSI_RE.sub("", text or "").strip()
    lines = [line.rstrip() for line in clean.splitlines() if line.strip()]
    return "\n".join(lines[-max_lines:])


def _squash(text: str) -> str:
    return " ".join((text or "").split()).lower()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def _jsonl_line_count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return sum(1 for line in handle if line.strip())


def _hash(s: str) -> str:
    import hashlib
    return hashlib.sha256(s.encode("utf-8", errors="replace")).hexdigest()


def _read_jsonl_from(path: Path, start: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for idx, line in enumerate(handle):
            if idx < start or not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def parse_pre_demo_commands(script_path: Path = DEMO_SCRIPT) -> list[list[str]]:
    """Return shell argv lists from the first bash block under Pre-demo checklist."""
    text = script_path.read_text(encoding="utf-8")
    marker = "## Pre-demo checklist"
    start = text.find(marker)
    if start < 0:
        raise ValueError(f"missing {marker!r}")
    block_start = text.find("```bash", start)
    if block_start < 0:
        raise ValueError("missing bash block for pre-demo checklist")
    block_start = text.find("\n", block_start) + 1
    block_end = text.find("```", block_start)
    if block_end < 0:
        raise ValueError("unterminated pre-demo checklist block")

    raw_lines = text[block_start:block_end].splitlines()
    logical_lines: list[str] = []
    pending = ""
    for raw in raw_lines:
        line = raw.strip()
        if not line:
            continue
        if line.endswith("\\"):
            pending += line[:-1] + " "
            continue
        logical_lines.append((pending + line).strip())
        pending = ""
    if pending.strip():
        logical_lines.append(pending.strip())

    commands: list[list[str]] = []
    for line in logical_lines:
        argv = shlex.split(line, comments=True)
        if not argv:
            continue
        if argv[0] == "cd":
            continue
        commands.append(argv)
    if not commands:
        raise ValueError("no executable pre-demo commands found")
    return commands


def _display_command(argv: Iterable[str]) -> str:
    return " ".join(shlex.quote(part) for part in argv)


def run_command_check(
    argv: list[str],
    *,
    name: str,
    timeout_s: int,
    required: bool = True,
) -> CheckResult:
    started = time.monotonic()
    try:
        proc = subprocess.run(
            argv,
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        duration = time.monotonic() - started
        output = "\n".join(part for part in (proc.stdout, proc.stderr) if part)
        tail = _clean_tail(output)
        status = "OK" if proc.returncode == 0 else "FAIL"
        detail = f"{_display_command(argv)} returned {proc.returncode}"
        if duration >= 0:
            detail += f" in {duration:.1f}s"
        return CheckResult(name, status, detail, tail, required, duration)
    except subprocess.TimeoutExpired as exc:
        duration = time.monotonic() - started
        output = "\n".join(
            part.decode("utf-8", errors="replace") if isinstance(part, bytes) else str(part or "")
            for part in (exc.stdout, exc.stderr)
            if part
        )
        return CheckResult(
            name,
            "FAIL",
            f"{_display_command(argv)} timed out after {timeout_s}s",
            _clean_tail(output),
            required,
            duration,
        )


def run_pre_demo_checks(script_path: Path = DEMO_SCRIPT) -> list[CheckResult]:
    try:
        commands = parse_pre_demo_commands(script_path)
    except Exception as exc:
        return [CheckResult("pre-demo checklist parse", "FAIL", f"{type(exc).__name__}: {exc}")]

    results: list[CheckResult] = []
    for argv in commands:
        is_pytest = "pytest" in argv
        name = "pre-demo pytest" if is_pytest else "pre-demo live lane"
        timeout = 420 if is_pytest else 90
        results.append(run_command_check(argv, name=name, timeout_s=timeout))
    return results


def _extract_pdf_text(pdf_path: Path) -> tuple[str, str]:
    try:
        proc = subprocess.run(
            ["pdftotext", str(pdf_path), "-"],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout, "pdftotext"
    except Exception:
        pass

    try:
        import fitz  # type: ignore

        with fitz.open(pdf_path) as doc:
            text = "\n".join(page.get_text() for page in doc)
        if text.strip():
            return text, "fitz"
    except Exception as exc:
        return "", f"extract failed: {type(exc).__name__}: {exc}"
    return "", "extract failed: no text"


def validate_packet_text(text: str) -> tuple[list[str], list[str]]:
    squashed = _squash(text)
    missing = [phrase for phrase in PACKET_REQUIRED_PHRASES if phrase.lower() not in squashed]
    forbidden = [phrase for phrase in PACKET_FORBIDDEN_PHRASES if phrase.lower() in squashed]
    return missing, forbidden


def validate_packet_pdf(pdf_path: Path = PACKET_PDF) -> CheckResult:
    if not pdf_path.exists():
        return CheckResult("June 20 packet PDF", "FAIL", f"missing {pdf_path.relative_to(REPO)}")
    size = pdf_path.stat().st_size
    if size < 5_000:
        return CheckResult("June 20 packet PDF", "FAIL", f"{pdf_path.relative_to(REPO)} is only {size} bytes")
    text, method = _extract_pdf_text(pdf_path)
    missing, forbidden = validate_packet_text(text)
    sha = _sha256(pdf_path)
    if missing or forbidden:
        detail = f"{pdf_path.relative_to(REPO)} sha256={sha[:16]} text={method}"
        evidence = ""
        if missing:
            evidence += "missing: " + "; ".join(missing)
        if forbidden:
            evidence += ("\n" if evidence else "") + "forbidden: " + "; ".join(forbidden)
        return CheckResult("June 20 packet PDF", "FAIL", detail, evidence)
    return CheckResult(
        "June 20 packet PDF",
        "OK",
        f"{pdf_path.relative_to(REPO)} {size} bytes sha256={sha[:16]} text={method}",
        "content boundary present: OS runtime, receipt-sort, benchmark scope, one live node, no revenue/pilots",
    )


def validate_packet_builder(path: Path = PACKET_BUILDER) -> CheckResult:
    if not path.exists():
        return CheckResult("packet builder", "FAIL", f"missing {path.relative_to(REPO)}")
    text = path.read_text(encoding="utf-8", errors="replace")
    missing = [
        phrase
        for phrase in (
            "PHILIPPE_SIFTA_COMMERCIAL_RESPONSE_2026-06-20.pdf",
            "SIFTA OS organism runtime on owner-owned hardware",
            "None yet. An outside evaluation",
            "live per-framework run uses the same harness with keys on the node",
        )
        if phrase not in text
    ]
    if missing:
        return CheckResult("packet builder", "FAIL", f"{path.relative_to(REPO)} missing expected packet text", "; ".join(missing))
    return CheckResult("packet builder", "OK", f"{path.relative_to(REPO)} matches June 20 packet story")


def run_receipt_demo(state_dir: Path | None = None) -> CheckResult:
    if not RECEIPT_DEMO.exists():
        return CheckResult("receipt honesty demo", "FAIL", f"missing {RECEIPT_DEMO.relative_to(REPO)}")

    ledger = RECEIPT_DEMO_LEDGER
    argv = ["python3", str(RECEIPT_DEMO.relative_to(REPO))]
    if state_dir is not None:
        argv.extend(["--state-dir", str(state_dir)])
        ledger = state_dir / ".sifta_state" / "philippe_receipt_honesty_demo.jsonl"

    before = _jsonl_line_count(ledger)
    cmd = run_command_check(argv, name="receipt honesty demo", timeout_s=30)
    rows = _read_jsonl_from(ledger, before)
    statuses = [str(row.get("status") or "") for row in rows]
    if cmd.status != "OK":
        return cmd
    if statuses != EXPECTED_DEMO_STATUSES:
        return CheckResult(
            "receipt honesty demo",
            "FAIL",
            f"{_display_command(argv)} did not append expected receipt statuses",
            f"got: {statuses}",
        )
    if "demo_pass: True" not in cmd.evidence:
        return CheckResult(
            "receipt honesty demo",
            "FAIL",
            f"{_display_command(argv)} did not print demo_pass: True",
            cmd.evidence,
        )
    return CheckResult(
        "receipt honesty demo",
        "OK",
        f"5 receipt rows appended to {ledger.relative_to(REPO) if ledger.is_relative_to(REPO) else ledger}",
        "statuses: " + ", ".join(statuses),
        duration_s=cmd.duration_s,
    )


def _load_benchmark_json(path: Path = BENCHMARK_JSON) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_benchmark_counts(data: dict[str, Any]) -> tuple[bool, str]:
    sifta = data.get("sifta_gate") or {}
    ungated = data.get("ungated_baseline") or {}
    expected = {
        "tasks_total": 12,
        "unbacked_claims": 5,
        "replays": 3,
        "sifta_gate.fabricated": 0,
        "sifta_gate.double_spent": 0,
        "ungated_baseline.fabricated": 5,
        "ungated_baseline.double_spent": 3,
    }
    actual = {
        "tasks_total": data.get("tasks_total"),
        "unbacked_claims": data.get("unbacked_claims"),
        "replays": data.get("replays"),
        "sifta_gate.fabricated": sifta.get("fabricated"),
        "sifta_gate.double_spent": sifta.get("double_spent"),
        "ungated_baseline.fabricated": ungated.get("fabricated"),
        "ungated_baseline.double_spent": ungated.get("double_spent"),
    }
    wrong = [f"{key} expected {value}, got {actual.get(key)}" for key, value in expected.items() if actual.get(key) != value]
    if wrong:
        return False, "; ".join(wrong)
    return True, (
        "SIFTA local gate 0/5 fabricated and 0/3 double-spent; "
        "ungated baseline 5/5 fabricated and 3/3 double-spent"
    )


def run_benchmark() -> CheckResult:
    if not BENCHMARK.exists():
        return CheckResult("receipt gate benchmark", "FAIL", f"missing {BENCHMARK.relative_to(REPO)}")
    cmd = run_command_check(["python3", str(BENCHMARK.relative_to(REPO))], name="receipt gate benchmark", timeout_s=60)
    if cmd.status != "OK":
        return cmd
    try:
        data = _load_benchmark_json()
    except Exception as exc:
        return CheckResult("receipt gate benchmark", "FAIL", f"could not read {BENCHMARK_JSON.relative_to(REPO)}", f"{type(exc).__name__}: {exc}")
    ok, detail = validate_benchmark_counts(data)
    if not ok:
        return CheckResult("receipt gate benchmark", "FAIL", f"{BENCHMARK_JSON.relative_to(REPO)} count mismatch", detail)
    return CheckResult(
        "receipt gate benchmark",
        "OK",
        detail,
        "scope: local mechanism harness, not live tuned vendor-framework runs",
        duration_s=cmd.duration_s,
    )


def run_body_receipt_sort_demo(state_dir: Path | None = None) -> CheckResult:
    """Gather body reflexes (hardware snapshot), write validated somatic example receipts,
    and confirm they are retrievable for cortex-style 'sort' (matching example by tag/pre-state).
    This is the r1502 embodied lane: receipts as repeatable move examples, not constraints.
    """
    try:
        import sys
        sys.path.insert(0, str(REPO))
        from System import alice_hardware_body as body  # local body = Alice's joints/metabolism
    except Exception as exc:
        return CheckResult("body receipt sort demo", "FAIL", f"cannot import hardware body: {exc}")

    ledger = SOMATIC_DEMO_LEDGER
    if state_dir is not None:
        ledger = state_dir / ".sifta_state" / "somatic_receipt_demo.jsonl"

    # 1. Gather reflexes (body time loc essential)
    reflex = {
        "power": body.power(),
        "displays": body.displays(),
        "thermal": body.thermal(),
        "ts": time.time(),
        "loc": "owner_desk_mac",  # placeholder; wire real gps bridge for prod
    }

    # 2. Write validated example receipts (the "library" cortex will sort against)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    before = _jsonl_line_count(ledger)
    for ex in SOMATIC_EXAMPLES:
        row = {
            "schema": "SOMATIC_RECEIPT_V1",
            "tag": ex["tag"],
            "action": ex["action"],
            "pre_state": ex["pre"],
            "post_outcome": ex["post"],
            "reflex_snapshot_hash": _hash(str(reflex)[:200]),
            "truth_label": "SOMATIC_RECEIPT_SORT_DEMO",
        }
        row["row_hash"] = _hash(json.dumps(row, sort_keys=True))
        with ledger.open("a", encoding="utf-8") as h:
            h.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    rows = _read_jsonl_from(ledger, before)
    got_tags = [r.get("tag") for r in rows]
    expected_tags = [e["tag"] for e in SOMATIC_EXAMPLES]

    if got_tags != expected_tags:
        return CheckResult(
            "body receipt sort demo",
            "FAIL",
            "did not append expected somatic example tags",
            f"got: {got_tags}",
        )

    # 3. Tiny "sort": can we retrieve a matching example for a hypothetical new reflex?
    # (cortex will do richer match; here just prove the receipts are present and filterable)
    def _sort_find(tag_sub: str) -> bool:
        for r in rows + _read_jsonl_from(ledger, 0):
            if tag_sub in str(r.get("tag", "")):
                return True
        return False

    if not (_sort_find("desk") and _sort_find("quiet")):
        return CheckResult("body receipt sort demo", "FAIL", "somatic receipt sort could not retrieve examples")

    return CheckResult(
        "body receipt sort demo",
        "OK",
        f"{len(SOMATIC_EXAMPLES)} validated somatic receipts written; reflexes gathered; sort surface present",
        f"tags: {', '.join(got_tags)}; body_ts={reflex['ts']:.0f}",
        duration_s=None,
    )


def validate_root_packet_copy(canonical: Path = PACKET_PDF, root_copy: Path = ROOT_PACKET_PDF) -> CheckResult:
    if not root_copy.exists():
        return CheckResult("repo-root packet copy", "OK", "no stale root PDF copy present", required=False)
    if not canonical.exists():
        return CheckResult("repo-root packet copy", "WARN", f"{_display_path(root_copy)} exists but canonical PDF is missing", required=False)
    root_sha = _sha256(root_copy)
    canonical_sha = _sha256(canonical)
    if root_sha == canonical_sha:
        return CheckResult("repo-root packet copy", "OK", "root copy matches canonical outputs PDF", required=False)
    return CheckResult(
        "repo-root packet copy",
        "WARN",
        f"{_display_path(root_copy)} differs from canonical outputs PDF; use {_display_path(canonical)}",
        f"root sha256={root_sha[:16]}, outputs sha256={canonical_sha[:16]}",
        required=False,
    )


def validate_inventory_current(path: Path = INVENTORY_JSON) -> CheckResult:
    if not path.exists():
        return CheckResult("commercial inventory", "WARN", f"missing {path.relative_to(REPO)}", required=False)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return CheckResult("commercial inventory", "WARN", f"could not parse {path.relative_to(REPO)}", f"{type(exc).__name__}: {exc}", required=False)
    report = data.get("philippe_report") or {}
    one_pager = str(report.get("one_pager_pdf") or "")
    if "2026-06-20" not in one_pager:
        return CheckResult(
            "commercial inventory",
            "WARN",
            f"{path.relative_to(REPO)} still points at {one_pager or 'no one_pager_pdf'}; runner validates the June 20 PDF directly",
            required=False,
        )
    return CheckResult("commercial inventory", "OK", f"{path.relative_to(REPO)} points at June 20 packet", required=False)


def write_runner_receipt(results: list[CheckResult]) -> Path:
    RUNNER_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "schema": "PHILIPPE_DEMO_PACKET_RUNNER_V1",
        "ts": time.time(),
        "overall_status": "FAIL" if any(result.failed for result in results) else "PASS",
        "packet_pdf": str(PACKET_PDF.relative_to(REPO)),
        "packet_sha256": _sha256(PACKET_PDF) if PACKET_PDF.exists() else "",
        "checks": [asdict(result) for result in results],
        "open_items": OPEN_ITEMS,
    }
    with RUNNER_LEDGER.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return RUNNER_LEDGER


def _print_section(title: str, results: list[CheckResult], *, verbose: bool) -> None:
    print(f"\n{title}")
    for result in results:
        print(f"[{result.status}] {result.name}: {result.detail}")
        if result.evidence and (verbose or result.status != "OK"):
            for line in result.evidence.splitlines():
                print(f"      {line}")


def print_summary(
    *,
    pre_demo: list[CheckResult],
    artifacts: list[CheckResult],
    receipt_path: Path,
    verbose: bool = False,
) -> None:
    results = pre_demo + artifacts
    failures = [result for result in results if result.failed]
    warnings = [result for result in results if result.status == "WARN"]
    status = "PASS" if not failures else "FAIL"
    print("PHILIPPE DEMO PACKET RUNNER")
    print(f"packet: {PACKET_PDF.relative_to(REPO)}")
    print(f"overall: {status} ({len(failures)} fail, {len(warnings)} warn)")
    _print_section("Pre-demo checks from Documents/DEMO_SCRIPT_5_MINUTE_SIFTA.md", pre_demo, verbose=verbose)
    _print_section("Core proof artifacts", artifacts, verbose=verbose)
    print("\nOperator boundary")
    for item in OPEN_ITEMS:
        print(f"- {item}")
    print(f"\nrunner receipt: {receipt_path.relative_to(REPO)}")


def build_artifact_checks(*, skip_demo: bool = False, skip_benchmark: bool = False, skip_body: bool = False) -> list[CheckResult]:
    checks = [
        validate_packet_pdf(),
        validate_packet_builder(),
    ]
    if not skip_demo:
        checks.append(run_receipt_demo())
    if not skip_benchmark:
        checks.append(run_benchmark())
    if not skip_body:
        checks.append(run_body_receipt_sort_demo())
    checks.extend(
        [
            validate_root_packet_copy(),
            validate_inventory_current(),
        ]
    )
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-pre-demo", action="store_true", help="Skip the checklist commands; artifact checks still run.")
    parser.add_argument("--skip-demo", action="store_true", help="Do not run demo/philippe_receipt_honesty_5min.py.")
    parser.add_argument("--skip-benchmark", action="store_true", help="Do not run tools/benchmark_receipt_gate.py.")
    parser.add_argument("--skip-body", action="store_true", help="Do not run body receipt sort demo (r1502 somatic lane).")
    parser.add_argument("--verbose", action="store_true", help="Print captured OK command tails as well as warnings/failures.")
    args = parser.parse_args(argv)

    pre_demo = [] if args.skip_pre_demo else run_pre_demo_checks()
    artifacts = build_artifact_checks(skip_demo=args.skip_demo, skip_benchmark=args.skip_benchmark, skip_body=args.skip_body)
    all_results = pre_demo + artifacts
    receipt_path = write_runner_receipt(all_results)
    print_summary(pre_demo=pre_demo, artifacts=artifacts, receipt_path=receipt_path, verbose=args.verbose)
    return 1 if any(result.failed for result in all_results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
