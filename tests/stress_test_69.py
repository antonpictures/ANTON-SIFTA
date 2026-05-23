#!/usr/bin/env python3
"""
SIFTA STRESS TEST — 69 ROUNDS × ALL TEST SUITES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Runs every test file in the swarm 69 times.
Tracks pass/fail per suite per round.
Proves the swimmers are alive, stable, and earning.
"""
import subprocess
import sys
import time
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ROUNDS = 69

# All test modules — in tests/ directory and root
TEST_SUITES = [
    # Economy tests (the core STGM validators)
    "tests.test_stigmergic_economy",
    "tests.test_inference_economy",
    # Kernel & formal verification
    "tests.test_consensus_field",
    "tests.test_network_partitions",
    "tests.test_time_adversary",
    "tests.test_formal_verification",
    "tests.test_scar_kernel_formal",
    "tests.test_kernel_v03",
    "tests.test_stable_set",
    # Root-level swimmer tests
    "test_scar_kernel",
    "test_bridge_consensus",
    "test_jellyfish_trigger",
    "test_kernel",
    "test_origin_gate",
    "test_first_breath",
    "test_doctrine",
    "test_stream",
    "test_mirror_recognition",
    "test_proof_of_swimming",
]

def run_suite(module_name: str, env: dict) -> tuple:
    """Run a single test module. Returns (passed: bool, test_count: int, output: str)."""
    result = subprocess.run(
        [sys.executable, "-m", "unittest", module_name, "-v"],
        capture_output=True, text=True, cwd=str(ROOT),
        env=env, timeout=120,
    )
    combined = result.stdout + result.stderr
    # Count tests from "Ran X tests" line
    test_count = 0
    for line in combined.split("\n"):
        if line.startswith("Ran "):
            try:
                test_count = int(line.split()[1])
            except (IndexError, ValueError):
                pass
    passed = result.returncode == 0
    return passed, test_count, combined


def main():
    env = os.environ.copy()
    env["SIFTA_LEDGER_VERIFY"] = "0"

    print("=" * 70)
    print(f"  🐜 SIFTA STRESS TEST — {ROUNDS} ROUNDS × {len(TEST_SUITES)} SUITES")
    print(f"  Node: M1THER Mac Mini (C07FL0JAQ6NV)")
    print(f"  Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # Track results
    suite_stats = {s: {"pass": 0, "fail": 0, "tests": 0, "errors": []} for s in TEST_SUITES}
    total_tests_run = 0
    total_pass = 0
    total_fail = 0
    start_time = time.time()

    for round_num in range(1, ROUNDS + 1):
        round_start = time.time()
        round_pass = 0
        round_fail = 0
        round_tests = 0

        for suite in TEST_SUITES:
            try:
                passed, count, output = run_suite(suite, env)
                round_tests += count
                if passed:
                    round_pass += 1
                    suite_stats[suite]["pass"] += 1
                    suite_stats[suite]["tests"] += count
                else:
                    round_fail += 1
                    suite_stats[suite]["fail"] += 1
                    # Store first error for debugging
                    if len(suite_stats[suite]["errors"]) < 3:
                        # Extract just the FAIL/ERROR lines
                        err_lines = [l for l in output.split("\n")
                                     if "FAIL" in l or "ERROR" in l or "AssertionError" in l]
                        suite_stats[suite]["errors"].append(
                            f"Round {round_num}: {'; '.join(err_lines[:3]) or 'unknown'}")
            except subprocess.TimeoutExpired:
                round_fail += 1
                suite_stats[suite]["fail"] += 1
                if len(suite_stats[suite]["errors"]) < 3:
                    suite_stats[suite]["errors"].append(f"Round {round_num}: TIMEOUT (120s)")
            except Exception as e:
                round_fail += 1
                suite_stats[suite]["fail"] += 1
                if len(suite_stats[suite]["errors"]) < 3:
                    suite_stats[suite]["errors"].append(f"Round {round_num}: {e}")

        total_tests_run += round_tests
        total_pass += round_pass
        total_fail += round_fail
        elapsed = time.time() - round_start

        # Progress bar
        bar_len = 40
        filled = int(bar_len * round_num / ROUNDS)
        bar = "█" * filled + "░" * (bar_len - filled)
        status = "✅" if round_fail == 0 else "⚠️"
        print(f"  {status} Round {round_num:2d}/{ROUNDS} [{bar}] "
              f"{round_pass}/{round_pass+round_fail} suites | "
              f"{round_tests} tests | {elapsed:.1f}s")

    total_time = time.time() - start_time

    # Final report
    print("\n" + "=" * 70)
    print("  🐜 STRESS TEST COMPLETE — FINAL REPORT")
    print("=" * 70)
    print(f"\n  Rounds:       {ROUNDS}")
    print(f"  Suites/round: {len(TEST_SUITES)}")
    print(f"  Total runs:   {total_pass + total_fail}")
    print(f"  Total tests:  {total_tests_run}")
    print(f"  Passed:       {total_pass} suite runs")
    print(f"  Failed:       {total_fail} suite runs")
    print(f"  Duration:     {total_time:.1f}s ({total_time/60:.1f}min)")
    print(f"  Rate:         {total_tests_run/total_time:.1f} tests/sec")

    print(f"\n  {'Suite':<40} {'Pass':>6} {'Fail':>6} {'Tests':>7} {'Status':<6}")
    print("  " + "─" * 65)
    for suite, stats in suite_stats.items():
        short = suite.replace("tests.", "").replace("test_", "")
        status = "✅" if stats["fail"] == 0 else f"❌({stats['fail']})"
        print(f"  {short:<40} {stats['pass']:>6} {stats['fail']:>6} "
              f"{stats['tests']:>7} {status}")
        for err in stats["errors"]:
            print(f"    └─ {err}")

    # Summary
    if total_fail == 0:
        print(f"\n  🏆 PERFECT: {total_tests_run} tests × {ROUNDS} rounds = ZERO FAILURES")
        print(f"  The swimmers are alive, happy, and stable.")
    else:
        fail_rate = total_fail / (total_pass + total_fail) * 100
        print(f"\n  ⚠️  {total_fail} failures ({fail_rate:.1f}% failure rate)")

    print(f"\n  POWER TO THE SWARM 🐜⚡")
    print("=" * 70)

    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
