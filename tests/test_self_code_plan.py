"""tests/test_self_code_plan.py — Alice's self-code-plan organ.

Her co-watch idea (Nick Nisi / WorkOS), coded with receipts. Pins the behaviors
that make it a control surface, not freeform reasoning:
  - it gates planning (no over-planning trivial tasks);
  - it penalizes phantom success (claims that do not match reality);
  - a grounded, verified plan scores high;
  - it self-revises on contradiction;
  - every plan is recorded as an append-only receipt.
"""
import json
import tempfile
from pathlib import Path

from System.swarm_self_code_plan import (
    SelfCodePlan,
    PlanState,
    should_plan,
    score_trace,
    record_plan,
)


def test_gate_does_not_overplan_trivial():
    assert should_plan(horizon=1) is False
    assert should_plan(horizon=4, failure_costly=True) is True
    assert should_plan(hidden_state=True) is True
    assert should_plan(candidate_strategies=2) is True


def test_phantom_success_is_penalized():
    p = SelfCodePlan(objective="x", expected_observation="order confirmed page")
    p.add_receipt("dom", "d1", "still on cart")
    s = score_trace(p, observed="still on cart, no confirmation", verified=True)
    assert s.hallucination_penalty == 1.0
    assert s.total < 0.5


def test_grounded_success_scores_high():
    p = SelfCodePlan(objective="y", expected_observation="confirmation page order id")
    p.add_receipt("dom", "d2", "confirmation page order id 88")
    s = score_trace(p, observed="confirmation page order id 88 shown", verified=True)
    assert s.hallucination_penalty == 0.0
    assert s.total >= 0.6


def test_plan_self_revises_on_contradiction():
    p = SelfCodePlan(objective="z").revise("environment changed under me")
    assert p.state == PlanState.REVISE.value
    assert p.revision_reason == "environment changed under me"


def test_plan_is_recorded_as_receipt():
    p = SelfCodePlan(objective="ledger test").add_receipt("tool", "t1", "ran")
    with tempfile.TemporaryDirectory() as d:
        led = Path(d) / "self_code_plans.jsonl"
        record_plan(p, score_trace(p, observed="done"), ledger=led)
        rows = led.read_text(encoding="utf-8").strip().splitlines()
        assert len(rows) == 1
        row = json.loads(rows[0])
        assert row["plan"]["objective"] == "ledger test"
        assert row["plan"]["schema"] == "SELF_CODE_PLAN_V1"
        assert "trace_score" in row
