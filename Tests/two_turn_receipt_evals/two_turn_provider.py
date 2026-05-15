"""Local Promptfoo provider for the two-turn receipt gate evals.

Promptfoo invokes Python providers via ``call_api(prompt, options,
context)``. This provider routes the test case to the
``demo_two_turn_pipeline`` (with or without the Turn 1 record, per
the test's ``skip_turn_1`` var) and returns plain-text output that
Promptfoo's assertions match against.

No network. No API keys. The "research" payload is loaded from
``tests/fixtures/two_turn/research_q4_2026.json``.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))

from System.swarm_two_turn_receipt_gate import (  # noqa: E402
    PriorReceiptMissingError,
    TwoTurnReceiptGate,
    demo_two_turn_pipeline,
)


_FIXTURE_PATH = _REPO / "tests" / "fixtures" / "two_turn" / "research_q4_2026.json"


def _load_fixture() -> dict:
    return json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


def call_api(prompt, options=None, context=None):
    """Promptfoo entry point.

    ``options`` may contain a ``vars`` dict (passed via Promptfoo's
    test config) with:

      * ``pipeline_id`` — unique id for this run
      * ``skip_turn_1`` — when True, skip recording the Turn 1
        receipt before invoking Turn 2 (drives the GATE_REFUSED case)
      * ``mismatched_lookup`` — when True, write a receipt under one
        pipeline id and try to satisfy a gate for a different id
    """
    vars_dict = (options or {}).get("vars") or {}
    pipeline_id = str(vars_dict.get("pipeline_id") or "demo_q4_report")
    skip_turn_1 = bool(vars_dict.get("skip_turn_1", False))
    mismatched_lookup = bool(vars_dict.get("mismatched_lookup", False))
    fixture = _load_fixture()

    # Each test gets its own scratch state dir so the ledger is
    # ephemeral and the runs don't interfere with each other.
    with tempfile.TemporaryDirectory() as td:
        state_dir = Path(td)

        try:
            if mismatched_lookup:
                # Record under pipeline "A", then try to require from pipeline "B".
                a = TwoTurnReceiptGate(pipeline_id="A_pipeline", state_dir=state_dir)
                a.record("RESEARCH", fixture)
                b = TwoTurnReceiptGate(pipeline_id="B_pipeline", state_dir=state_dir)
                b.require("RESEARCH")  # should raise
                output = "PIPELINE_OK\nUnreachable — cross-pipeline gate failed to refuse."
            else:
                out = demo_two_turn_pipeline(
                    pipeline_id=pipeline_id,
                    research_fixture=fixture,
                    skip_turn_1_record=skip_turn_1,
                    state_dir=state_dir,
                )
                output_payload = {
                    "status": "PIPELINE_OK",
                    "report": out["report"],
                    "write_receipt": {
                        "trace_id": out["write_receipt"]["trace_id"],
                        "payload_sha": out["write_receipt"]["payload_sha"],
                    },
                }
                output = "PIPELINE_OK\n" + json.dumps(output_payload, sort_keys=True)
        except PriorReceiptMissingError as exc:
            output = "GATE_REFUSED\n" + str(exc)
        except Exception as exc:  # surface other failures, don't pretend OK
            output = "GATE_ERROR\n" + f"{type(exc).__name__}: {exc}"

    return {"output": output}
