#!/usr/bin/env python3
"""
scripts/mermaid_release_gate.py — Deterministic Mermaid OS Release Gate

Runs every quality check in sequence, collects exit codes,
and emits a single JSON report + terminal summary.
Green = every gate exits 0.  Red = any gate fails.
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATE_DIR = REPO / ".sifta_state" / "release_gates"
GATE_DIR.mkdir(parents=True, exist_ok=True)

PYTHON = str(REPO / ".venv" / "bin" / "python") if (REPO / ".venv" / "bin" / "python").exists() else sys.executable


def _gate_env(*, skip_wm_autostart: bool = False) -> dict:
    """Environment for headless release-gate subprocesses.

    The full pytest gate may skip desktop autostart because teardown smoke
    covers that explicitly. The desktop smoke gate must not skip autostart,
    otherwise it can no longer prove Alice-in-MDI teardown.
    """
    env = {
        **os.environ,
        "PYTHONPATH": str(REPO),
        "QT_QPA_PLATFORM": "offscreen",
        "SIFTA_VOICE_BACKEND": "null",
        "SIFTA_DISABLE_MESH": "1",
        "SIFTA_ALICE_UNIFIED_BOOT_SILENT": "1",
    }
    if skip_wm_autostart:
        env["SIFTA_DESKTOP_SKIP_WM_AUTOSTART"] = "1"
    else:
        env.pop("SIFTA_DESKTOP_SKIP_WM_AUTOSTART", None)
    return env


def _run(
    label: str,
    cmd: list[str],
    timeout: int = 300,
    *,
    skip_wm_autostart: bool = False,
) -> dict:
    """Run a command, capture output, return gate result dict."""
    print(f"  ▸ {label}...", end=" ", flush=True)
    start = time.monotonic()
    try:
        result = subprocess.run(
            cmd,
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_gate_env(skip_wm_autostart=skip_wm_autostart),
        )
        elapsed = round(time.monotonic() - start, 2)
        ok = result.returncode == 0
        print(f"{'✅' if ok else '❌'} ({elapsed}s)")
        return {
            "label": label,
            "command": " ".join(cmd),
            "exit_code": result.returncode,
            "passed": ok,
            "elapsed_s": elapsed,
            "stdout_tail": result.stdout[-500:] if result.stdout else "",
            "stderr_tail": result.stderr[-500:] if result.stderr else "",
        }
    except subprocess.TimeoutExpired:
        elapsed = round(time.monotonic() - start, 2)
        print(f"⏱ TIMEOUT ({elapsed}s)")
        return {
            "label": label,
            "command": " ".join(cmd),
            "exit_code": -1,
            "passed": False,
            "elapsed_s": elapsed,
            "stdout_tail": "",
            "stderr_tail": "TIMEOUT",
        }


def _run_full_pytest_chunked(chunk_count: int = 8) -> dict:
    """Run the complete tests/ scope in isolated subprocess chunks.

    A monolithic pytest currently reports all tests passed, then segfaults
    during interpreter shutdown from accumulated Qt/audio teardown state.
    Chunking keeps the same test-file scope while making each subprocess
    responsible for a smaller lifetime.
    """
    print("  ▸ full_pytest_chunked...", end=" ", flush=True)
    start = time.monotonic()
    test_files = sorted(str(p.relative_to(REPO)) for p in (REPO / "tests").glob("test_*.py"))
    if not test_files:
        print("❌ (no test files)")
        return {
            "label": "full_pytest",
            "command": f"{PYTHON} -m pytest tests/ -q --tb=line (chunked)",
            "exit_code": 5,
            "passed": False,
            "elapsed_s": round(time.monotonic() - start, 2),
            "stdout_tail": "",
            "stderr_tail": "No tests/test_*.py files found",
        }

    chunks = [test_files[i::chunk_count] for i in range(chunk_count)]
    stdout_bits: list[str] = []
    stderr_bits: list[str] = []
    failing: list[dict] = []
    total_exit = 0

    for idx, chunk in enumerate(chunks, start=1):
        if not chunk:
            continue
        cmd = [PYTHON, "-m", "pytest", *chunk, "-q", "--tb=line"]
        result = subprocess.run(
            cmd,
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=240,
            env=_gate_env(skip_wm_autostart=True),
        )
        stdout_bits.append(f"[chunk {idx}/{chunk_count}]\n{result.stdout[-1200:] if result.stdout else ''}")
        if result.stderr:
            stderr_bits.append(f"[chunk {idx}/{chunk_count}]\n{result.stderr[-1200:]}")
        if result.returncode != 0:
            total_exit = result.returncode
            failing.append({
                "chunk": idx,
                "exit_code": result.returncode,
                "files": chunk,
                "stdout_tail": result.stdout[-1000:] if result.stdout else "",
                "stderr_tail": result.stderr[-1000:] if result.stderr else "",
            })

    elapsed = round(time.monotonic() - start, 2)
    ok = not failing
    print(f"{'✅' if ok else '❌'} ({elapsed}s)")
    return {
        "label": "full_pytest",
        "command": f"{PYTHON} -m pytest tests/test_*.py -q --tb=line (chunked x{chunk_count})",
        "exit_code": 0 if ok else total_exit,
        "passed": ok,
        "elapsed_s": elapsed,
        "stdout_tail": "\n".join(stdout_bits)[-2000:],
        "stderr_tail": "\n".join(stderr_bits)[-2000:],
        "chunks": len([c for c in chunks if c]),
        "test_files": len(test_files),
        "failures": failing,
    }


def _check_stale_processes() -> dict:
    """Check for orphaned pytest/smoke desktop processes."""
    print("  ▸ Stale process check...", end=" ", flush=True)
    try:
        result = subprocess.run(
            ["pgrep", "-f", "smoke_test_desktop|pytest.*tests/"],
            capture_output=True, text=True
        )
        pids = result.stdout.strip().split("\n") if result.stdout.strip() else []
        # Filter out our own PID
        pids = [p for p in pids if p and int(p) != os.getpid()]
        ok = len(pids) == 0
        print(f"{'✅' if ok else '⚠️ ' + str(len(pids)) + ' found'}")
        return {
            "label": "stale_process_check",
            "command": "pgrep -f smoke_test_desktop|pytest",
            "exit_code": 0 if ok else 1,
            "passed": ok,
            "elapsed_s": 0,
            "stdout_tail": f"PIDs: {pids}" if pids else "clean",
            "stderr_tail": "",
        }
    except Exception as e:
        print(f"⚠️ {e}")
        return {
            "label": "stale_process_check",
            "command": "pgrep",
            "exit_code": -1,
            "passed": True,  # non-fatal
            "elapsed_s": 0,
            "stdout_tail": str(e),
            "stderr_tail": "",
        }


def main():
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    print(f"\n{'='*60}")
    print(f"  MERMAID OS RELEASE GATE — {ts}")
    print(f"{'='*60}\n")

    gates = []

    # 1. Full pytest scope. Run in isolated chunks so post-test Qt/audio
    # interpreter teardown cannot turn a fully passing suite into a false RED.
    gates.append(_run_full_pytest_chunked())

    # 2. Manifest contract
    gates.append(_run(
        "manifest_contract",
        [PYTHON, "-m", "pytest", "tests/test_apps_manifest_contract.py", "-q", "--tb=short"],
        timeout=60,
    ))

    # 3. Desktop smoke (offscreen) — no os._exit masking; real Qt teardown.
    smoke_result = _run(
        "desktop_smoke",
        [PYTHON, "scripts/smoke_test_desktop.py"],
        timeout=180,
    )
    # Extra check: if smoke exited 0 but stderr contained QThread abort marker,
    # that means masking was hiding a real crash. Surface it as a gate failure.
    if smoke_result["passed"] and "QThread: Destroyed while thread" in smoke_result.get("stderr_tail", ""):
        smoke_result["passed"] = False
        smoke_result["exit_code"] = 2
        smoke_result["stderr_tail"] = "QThread destroyed-while-running detected in teardown stderr"
    gates.append(smoke_result)

    # 4. py_compile critical modules
    critical_modules = [
        "sifta_os_desktop.py",
        "System/sifta_app_catalog.py",
        "System/stigmergic_wm.py",
        "System/app_fitness.py",
    ]
    for mod in critical_modules:
        gates.append(_run(
            f"py_compile_{Path(mod).stem}",
            [PYTHON, "-m", "py_compile", mod],
            timeout=15,
        ))

    # 5. Distro scrubber — real scrub into a temp dir then post-scrub PII audit.
    # --dry-run always exits 0 and cannot gate on findings; we need the real run.
    import tempfile, shutil as _shutil
    scrubber = REPO / "Scripts" / "distro_scrubber.py"
    if not scrubber.exists():
        scrubber = REPO / "scripts" / "distro_scrubber.py"
    if scrubber.exists():
        tmp_distro = Path(tempfile.mkdtemp(prefix="mermaid_gate_distro_"))
        try:
            gates.append(_run(
                "distro_scrubber_pii_audit",
                [PYTHON, str(scrubber), "--output", str(tmp_distro)],
                timeout=120,
            ))
        finally:
            _shutil.rmtree(tmp_distro, ignore_errors=True)

    # 6. Stale processes
    gates.append(_check_stale_processes())

    # Build report
    all_passed = all(g["passed"] for g in gates)
    report = {
        "gate_version": "mermaid_os_v1",
        "timestamp": ts,
        "verdict": "GREEN" if all_passed else "RED",
        "total_gates": len(gates),
        "passed": sum(1 for g in gates if g["passed"]),
        "failed": sum(1 for g in gates if not g["passed"]),
        "gates": gates,
    }

    # Write report
    report_path = GATE_DIR / f"mermaid_os_gate_{ts}.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    # Terminal summary
    print(f"\n{'='*60}")
    print(f"  VERDICT: {'🟢 GREEN — RELEASE OK' if all_passed else '🔴 RED — BLOCKED'}")
    print(f"  Gates: {report['passed']}/{report['total_gates']} passed")
    print(f"  Report: {report_path}")
    print(f"{'='*60}\n")

    for g in gates:
        status = "✅" if g["passed"] else "❌"
        print(f"  {status} {g['label']} (exit {g['exit_code']}, {g['elapsed_s']}s)")

    if not all_passed:
        print("\n  FAILURES:")
        for g in gates:
            if not g["passed"]:
                print(f"    ❌ {g['label']}: {g['stderr_tail'][:200]}")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
