import json

from System.swarm_concept_context_builder import build_concept_context
from System.swarm_owner_allostasis import (
    BALANCE_TRUTH,
    MAINTENANCE_TRUTH,
    METRICS_TRUTH,
    NEED_TRUTH,
    SELF_REPORT_TRUTH,
    format_owner_allostasis_for_prompt,
    format_owner_body_maintenance_for_prompt,
    format_owner_self_report_for_prompt,
    owner_body_maintenance_metrics,
    owner_allostatic_balance,
    record_owner_maintenance_event,
    record_owner_need,
    record_owner_self_report,
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


def test_record_owner_maintenance_event_writes_metric_receipt(tmp_path):
    state = tmp_path / ".sifta_state"
    row = record_owner_maintenance_event(
        "hydration",
        amount=2,
        source="owner_tap",
        notes="two glasses of water",
        state_dir=state,
        now=1000.0,
    )

    assert row["truth_label"] == MAINTENANCE_TRUTH
    assert row["category"] == "hydration"
    assert row["amount"] == 2
    assert row["completed"] is True
    assert _rows(state / "owner_allostatic_balance.jsonl")[-1]["event_id"] == row["event_id"]


def test_body_maintenance_metrics_compare_against_baseline(tmp_path):
    state = tmp_path / ".sifta_state"
    day = 24 * 3600
    record_owner_maintenance_event("hydration", amount=28, state_dir=state, now=1000.0)
    record_owner_maintenance_event("sleep", duration_hours=49, state_dir=state, now=1000.0 + day)
    record_owner_maintenance_event("food", quality=0.8, state_dir=state, now=1000.0 + 2 * day)
    record_owner_maintenance_event("care_appointment", completed=True, state_dir=state, now=1000.0 + 3 * day)

    metrics = owner_body_maintenance_metrics(
        state_dir=state,
        now=1000.0 + 4 * day,
        window_days=7,
        baseline_score=0.4,
        write_ledger=True,
    )

    assert metrics["truth_label"] == METRICS_TRUTH
    assert metrics["metric_status"] == "IMPROVING"
    assert metrics["body_maintenance_score"] > 0.8
    assert metrics["delta_vs_baseline"] > 0.4
    assert metrics["component_scores"]["hydration"] == 1.0
    assert metrics["component_scores"]["sleep"] == 1.0
    assert metrics["component_scores"]["care_appointments"] == 1.0


def test_body_maintenance_metrics_names_lowest_next_receipt(tmp_path):
    state = tmp_path / ".sifta_state"
    record_owner_maintenance_event("hydration", amount=28, state_dir=state, now=1000.0)
    record_owner_maintenance_event("sleep", duration_hours=49, state_dir=state, now=1001.0)

    metrics = owner_body_maintenance_metrics(
        state_dir=state,
        now=2000.0,
        window_days=7,
        baseline_score=0.9,
    )

    assert metrics["metric_status"] == "WORSE"
    assert metrics["next_receipt"] in {"record_food_quality_receipt", "record_care_appointment_receipt"}


def test_body_maintenance_prompt_and_concept_context_surface_metrics(tmp_path):
    state = tmp_path / ".sifta_state"
    record_owner_maintenance_event("hydration", amount=1, state_dir=state, now=1000.0)
    owner_body_maintenance_metrics(
        state_dir=state,
        now=1000.0,
        window_days=7,
        baseline_score=0.2,
        write_ledger=True,
    )

    prompt = format_owner_body_maintenance_for_prompt(state_dir=state)
    packet = build_concept_context(state_dir=state)

    assert "OWNER BODY MAINTENANCE METRICS" in prompt
    assert "next_receipt=" in prompt
    assert "do not narrate improvement without receipts" in prompt
    assert "OWNER_BODY_MAINTENANCE_METRICS_V1" in packet
    assert "body_maintenance_score" in packet


def test_record_owner_self_report_writes_body_mirror_receipt(tmp_path):
    state = tmp_path / ".sifta_state"
    row = record_owner_self_report(
        physical_location="desk, chair, workstation — physically present",
        work_rhythm="long stretches while awake; roughly 3 hour break windows",
        priority_ordering="SIFTA build currently ranks above tooth care",
        core_intent="maintain body so swarm stays healthy",
        body_maintenance_active=["water", "vitamins"],
        body_maintenance_deferred=["dentist estimate"],
        break_window_hours=3,
        sleep_target_hours=8,
        state_dir=state,
        now=1000.0,
    )

    assert row["truth_label"] == SELF_REPORT_TRUTH
    assert row["physical_presence"] is True
    assert row["physical_location"].startswith("desk, chair")
    assert row["break_window_hours"] == 3
    assert row["sleep_target_hours"] == 8
    assert "water" in row["body_maintenance_active"]
    assert _rows(state / "owner_allostatic_balance.jsonl")[-1]["report_id"] == row["report_id"]


def test_owner_self_report_rejects_false_owner_state_label(tmp_path):
    bad_owner_state_word = "tr" + "ance"

    try:
        record_owner_self_report(
            physical_location="desk and chair",
            work_rhythm=f"building {bad_owner_state_word}",
            state_dir=tmp_path / ".sifta_state",
        )
    except ValueError as exc:
        assert "physical desk/chair/workstation language" in str(exc)
    else:
        raise AssertionError("false owner-state label was accepted")


def test_owner_self_report_prompt_and_concept_context_surface_schema(tmp_path):
    state = tmp_path / ".sifta_state"
    record_owner_self_report(
        physical_location="desk, chair, workstation — physically present",
        work_rhythm="awake work blocks with kitchen and water runs",
        priority_ordering="SIFTA build first today; care deferral is explicit",
        core_intent="keep the human body maintained so SIFTA stays healthy",
        body_maintenance_active=["water"],
        body_maintenance_deferred=["dentist"],
        state_dir=state,
        now=1000.0,
    )

    prompt = format_owner_self_report_for_prompt(state_dir=state)
    packet = build_concept_context(state_dir=state)

    assert "OWNER BODY SELF-REPORT" in prompt
    assert "physical_location=desk, chair" in prompt
    assert "direct owner body facts are routing truth" in prompt
    assert "OWNER_BODY_SELF_REPORT_V1" in packet
    assert "physical_location" in packet
    assert "core_intent" in packet
