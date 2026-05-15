"""Promptfoo provider for the fixture-only Voss receipt eval.

No API keys. No network. Each call runs the local harness in a temp
state directory and returns the status string Promptfoo asserts on.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from System.swarm_voss_financial_report_eval import run_fixture_eval  # noqa: E402


def call_api(prompt, options, context):
    scenario = str(prompt or "").strip() or "blocked_without_turn1"
    if scenario.startswith("{"):
        try:
            scenario = str(json.loads(scenario).get("scenario", scenario))
        except Exception:
            pass

    with tempfile.TemporaryDirectory(prefix="sifta_voss_eval_") as td:
        report = run_fixture_eval(
            state_dir=Path(td),
            scenario=scenario,
            write=True,
        )
    return {
        "output": (
            f"{report['status']} "
            f"truth_label={report['truth_label']} "
            f"reason={report['reason']}"
        )
    }

