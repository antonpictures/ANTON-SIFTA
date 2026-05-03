import json

import pytest

from System.swarm_tumor_immune_stigmergic_lab import (
    ALLOWED_DATA_ORIGINS,
    TRUTH_LABEL,
    TumorImmuneState,
    assert_synthetic_contract,
    default_synthetic_state,
    lab_log_path,
    remap_to_microglia_inputs,
    run_tin_tick,
    simulate_tin_trajectory,
    summary_for_prompt,
    tail_lab_rows,
    tick_state,
    two_signal_snapshot_for_state,
)


def test_rejects_phi_like_payload_keys():
    with pytest.raises(ValueError, match="PHI-like"):
        assert_synthetic_contract(
            data_origin="synthetic",
            payload={"patient_id": "abc", "feature": 0.2},
        )


def test_rejects_non_synthetic_or_non_public_origin():
    with pytest.raises(ValueError, match="accepts only"):
        assert_synthetic_contract(data_origin="private_clinic_export")


def test_allowed_origins_are_explicit():
    assert ALLOWED_DATA_ORIGINS == {"synthetic", "licensed_public"}


def test_toy_field_remap_shapes_microglia_inputs():
    state = TumorImmuneState(
        tumor_burden=0.9,
        antigen_visibility=0.2,
        cart_effector_load=0.7,
        tme_suppression=0.8,
        hypoxia=0.9,
    ).bounded()
    remap = remap_to_microglia_inputs(state)

    assert remap["usage_count"] <= 1
    assert remap["recent_high_value_usage"] == pytest.approx(0.7)
    assert remap["pruning_conservatism"] > 0.6
    assert remap["wm_contradiction_pe"] > 0.6


def test_two_signal_snapshot_embeds_event137_fields():
    snap = two_signal_snapshot_for_state(default_synthetic_state())
    for key in ("damage_score", "inhibition_signal", "net_pruning_pressure", "fractalkine_analog"):
        assert key in snap


def test_tick_state_is_bounded_and_reports_dynamics():
    before = default_synthetic_state()
    after, dyn = tick_state(before, intervention_id="toy_logic_gate_focus")

    for value in after.__dict__.values():
        assert 0.0 <= value <= 1.0
    assert "immune_pressure" in dyn
    assert "delta_tumor" in dyn


def test_run_tick_writes_tin_sim_tick_receipt(tmp_path):
    row = run_tin_tick(
        default_synthetic_state(),
        intervention_id="toy_trem2_blockade",
        tick_id=7,
        data_origin="synthetic",
        root=tmp_path,
        write_ledger=True,
        now=123.0,
    )
    rows = tail_lab_rows(4, root=tmp_path)

    assert row["truth_label"] == TRUTH_LABEL
    assert row["kind"] == "TIN_SIM_TICK"
    assert row["tick_id"] == 7
    assert row["intervention_id"] == "toy_trem2_blockade"
    assert row["synthetic_only"] is True
    assert "two_signal_snapshot" in row
    assert rows[-1]["trace_id"] == row["trace_id"]
    assert lab_log_path(tmp_path).exists()


def test_receipts_do_not_emit_clinical_instruction_strings(tmp_path):
    row = run_tin_tick(root=tmp_path, write_ledger=True)
    text = json.dumps(row).lower()

    assert "therapy recommendation" not in text
    assert "clinical recommendation" not in text
    assert "prescribe" not in text
    assert "dosage" not in text
    assert "treat this patient" not in text


def test_simulate_trajectory_records_schedule_and_summary(tmp_path):
    rows = simulate_tin_trajectory(
        ticks=4,
        intervention_schedule={1: "toy_cart_persistence", 2: "toy_logic_gate_focus"},
        root=tmp_path,
        write_ledger=True,
    )
    summary = summary_for_prompt(root=tmp_path)

    assert len(rows) == 4
    assert rows[1]["intervention_id"] == "toy_cart_persistence"
    assert rows[2]["intervention_id"] == "toy_logic_gate_focus"
    assert "TUMOR-IMMUNE STIGMERGIC LAB" in summary
    assert "nonclinical sandbox" in summary
