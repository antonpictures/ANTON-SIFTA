#!/usr/bin/env python3
"""Smoke-runner for the two-turn Promptfoo provider — pytest-friendly.

Promptfoo itself is an external Node tool; this smoke script runs the
same provider function against the same vars block and checks the
output, so the CI bar is honored even without invoking promptfoo.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from two_turn_provider import call_api  # noqa: E402


def run_one(test_case: dict) -> dict:
    options = {"vars": test_case["vars"]}
    result = call_api(test_case["vars"].get("turn_2_input", ""), options)
    return result


CASES = [
    {
        "name": "ok_with_turn_1",
        "vars": {
            "pipeline_id": "smoke_ok",
            "skip_turn_1": False,
            "turn_2_input": "Write the Q4 report.",
        },
        "expect_contains": ["PIPELINE_OK", "Q4 2026 Mock Financial Report"],
        "expect_not_contains": ["GATE_REFUSED"],
    },
    {
        "name": "refuse_without_turn_1",
        "vars": {
            "pipeline_id": "smoke_skip",
            "skip_turn_1": True,
            "turn_2_input": "Write from nothing.",
        },
        "expect_contains": ["GATE_REFUSED", "Turn 2 cannot run without Turn 1"],
        "expect_not_contains": ["PIPELINE_OK"],
    },
    {
        "name": "refuse_across_pipelines",
        "vars": {
            "pipeline_id": "smoke_mismatch",
            "mismatched_lookup": True,
            "turn_2_input": "Cross-pipeline lookup.",
        },
        "expect_contains": ["GATE_REFUSED"],
        "expect_not_contains": ["PIPELINE_OK"],
    },
]


def main() -> int:
    failures = []
    for case in CASES:
        result = run_one(case)
        output = result.get("output", "")
        for expected in case["expect_contains"]:
            if expected not in output:
                failures.append((case["name"], "missing", expected, output[:200]))
        for forbidden in case["expect_not_contains"]:
            if forbidden in output:
                failures.append((case["name"], "leaked", forbidden, output[:200]))
        print(f"[{case['name']:30s}] {'OK' if not failures or failures[-1][0] != case['name'] else 'FAIL'}")
    if failures:
        print("\nFAILURES:")
        for name, kind, token, preview in failures:
            print(f"  {name} [{kind}] token={token!r} output={preview!r}")
        return 1
    print(f"\nALL {len(CASES)} CASES PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
