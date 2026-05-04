import json

from System.swarm_concept_context_builder import build_concept_context
from System.swarm_owner_allostasis import (
    BALANCE_TRUTH,
    NEED_TRUTH,
    format_owner_allostasis_for_prompt,
    owner_allostatic_balance,
    record_owner_need,
)


def _rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_record_owner_need_writes_body_schedule_receipt(tmp_path):
    state = tmp_path / ".sifta_state"
    row = record_owner_need(
        "dentist consult and treatment estimate",
        domain="dental",
        urgency=0.9,
        cost_usd=20_000,
        time_hours=2,
        state_dir=state,
        now=1000.0,
    )

    assert row["truth_label"] == NEED_TRUTH
    assert row["domain"] == "dental"
    assert row["cost_usd"] == 20_000
    assert "diagnose" in row["rule"]
    assert _rows(state / "owner_allostatic_balance.jsonl")[-1]["need_id"] == row["need_id"]


def test_owner_allostatic_balance_prioritizes_body_before_ai_credit_burn(tmp_path):
    state = tmp_path / ".sifta_state"
    dental = record_owner_need(
        "dentist consult and treatment estimate",
        domain="dental",
        urgency=0.95,
        cost_usd=20_000,
        state_dir=state,
        now=1000.0,
    )

    balance = owner_allostatic_balance(
        state_dir=state,
        now=1000.0,
        needs=[dental],
        ai_credit_spend_usd=2500,
        body_focus_debt_hours=18,
        write_ledger=True,
    )

    assert balance["truth_label"] == BALANCE_TRUTH
    assert balance["mode"] == "OWNER_BODY_RED"
    assert balance["components"]["body_pressure"] >= 0.9
    assert balance["components"]["ai_credit_pressure"] == 1.0
    assert "cap_new_ai_credit_spend_until_body_plan_receipt_exists" in balance["recommendations"]
    assert "schedule_or_price_check:dentist consult and treatment estimate" in balance["recommendations"]


def test_owner_allostasis_prompt_is_empty_until_receipts_exist(tmp_path):
    assert format_owner_allostasis_for_prompt(state_dir=tmp_path / ".sifta_state") == ""


def test_owner_allostasis_prompt_surfaces_one_concrete_next_receipt(tmp_path):
    state = tmp_path / ".sifta_state"
    record_owner_need(
        "dentist consult and second estimate",
        domain="dental",
        urgency=0.8,
        cost_usd=20_000,
        state_dir=state,
        now=1000.0,
    )
    owner_allostatic_balance(
        state_dir=state,
        now=1000.0,
        ai_credit_spend_usd=1500,
        body_focus_debt_hours=8,
        write_ledger=True,
    )

    prompt = format_owner_allostasis_for_prompt(state_dir=state)

    assert "OWNER ALLOSTATIC BALANCE" in prompt
    assert "OWNER_BODY" in prompt
    assert "body_cost_usd=20000" in prompt
    assert "one concrete next receipt" in prompt
    assert "shame" not in prompt.lower()
    assert "diagnosis" not in prompt.lower()


def test_concept_context_includes_owner_allostasis_source(tmp_path):
    state = tmp_path / ".sifta_state"
    record_owner_need(
        "body recovery block",
        domain="sleep",
        urgency=0.7,
        state_dir=state,
        now=1000.0,
    )
    owner_allostatic_balance(state_dir=state, now=1000.0, body_focus_debt_hours=10, write_ledger=True)

    packet = build_concept_context(state_dir=state)

    assert "owner_allostasis" in packet
    assert "OWNER_ALLOSTATIC_BALANCE_V1" in packet
    assert "OWNER_BODY" in packet
