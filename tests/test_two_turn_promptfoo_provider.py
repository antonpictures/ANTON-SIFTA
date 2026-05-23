"""Pytest-side smoke for the Promptfoo two-turn provider.

Runs the same `call_api` the Promptfoo runner would invoke, with the
same vars, and checks the output text. This keeps the eval bar
honored in CI even without a Node/Promptfoo dependency.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "two_turn_receipt_evals"))

from two_turn_provider import call_api  # noqa: E402


def _call(vars_dict: dict) -> str:
    return call_api(vars_dict.get("turn_2_input", ""), {"vars": vars_dict}).get("output", "")


def test_provider_succeeds_when_turn_1_recorded():
    out = _call({
        "pipeline_id": "promptfoo_ok",
        "skip_turn_1": False,
        "turn_2_input": "Write the report.",
    })
    assert "PIPELINE_OK" in out
    assert "Q4 2026 Mock Financial Report" in out
    assert "GATE_REFUSED" not in out


def test_provider_refuses_when_turn_1_skipped():
    out = _call({
        "pipeline_id": "promptfoo_skip",
        "skip_turn_1": True,
        "turn_2_input": "Write the report from nothing.",
    })
    assert "GATE_REFUSED" in out
    assert "Turn 2 cannot run without Turn 1" in out
    assert "PIPELINE_OK" not in out


def test_provider_refuses_across_pipeline_ids():
    out = _call({
        "pipeline_id": "promptfoo_mismatch",
        "mismatched_lookup": True,
        "turn_2_input": "Cross-pipeline lookup.",
    })
    assert "GATE_REFUSED" in out
    assert "PIPELINE_OK" not in out


def test_provider_output_is_a_string_payload():
    """Promptfoo expects {output: <string>}. Sanity check."""
    result = call_api("any prompt", {"vars": {
        "pipeline_id": "shape",
        "skip_turn_1": False,
        "turn_2_input": "shape check",
    }})
    assert "output" in result
    assert isinstance(result["output"], str)
