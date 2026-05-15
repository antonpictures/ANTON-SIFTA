import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_steering_subsystem import (
    TRUTH_LABEL,
    steer_event,
    steering_prompt_block,
)


def test_time_query_routes_fast_reflex_when_low_risk():
    out = steer_event(
        "What time is it?",
        signals={"metabolic_pressure": 0.10, "novelty": 0.0, "risk": 0.0},
        write=False,
    )

    assert out.route == "FAST_REFLEX"
    assert out.importance_label == "UTILITY"
    assert out.should_write_memory is False
    assert out.should_verify_tools is False
    assert out.truth_label == TRUTH_LABEL


def test_doctrine_routes_deep_cortex_and_pulls_memory():
    out = steer_event(
        "From now on, steering goes before cortex.",
        signals={"novelty": 0.60, "memory_mass": 0.50},
        write=False,
    )

    assert out.route == "DEEP_CORTEX"
    assert out.importance_label == "DOCTRINE"
    assert out.should_pull_memory is True
    assert out.should_write_memory is True


def test_boundary_tool_truth_routes_verify_before_action():
    out = steer_event(
        "Do not send that message without a receipt.",
        signals={"tool_truth_risk": 0.90, "risk": 0.25},
        write=False,
    )

    assert out.route == "VERIFY_BEFORE_ACTION"
    assert out.importance_label == "BOUNDARY"
    assert out.should_verify_tools is True
    assert out.interrupt >= 0.85


def test_emergency_interrupt_overrides_metabolic_conserve():
    out = steer_event(
        "Help me now, I can't breathe.",
        signals={"metabolic_pressure": 0.95},
        write=False,
    )

    assert out.route == "EMERGENCY_INTERRUPT"
    assert out.importance_label == "EMERGENCY"
    assert out.budget_multiplier >= 0.50


def test_high_metabolic_pressure_defers_low_importance_work():
    out = steer_event(
        "Tell me a normal story about a meadow.",
        signals={"metabolic_pressure": 0.90, "novelty": 0.05, "risk": 0.0},
        write=False,
    )

    assert out.route == "CONSERVE_OR_DEFER"
    assert out.conserve == 0.90
    assert out.budget_multiplier <= 0.11


def test_sensor_salience_sets_probe_flag():
    out = steer_event(
        "What is happening in the room?",
        signals={"vision_salience": 0.80, "audio_salience": 0.20},
        write=False,
    )

    assert out.should_probe_sensors is True
    assert out.signals["sensor_salience"] == 0.80
    assert any(p.target == "probe_world" for p in out.predictions)


def test_high_novelty_routes_deep_cortex_even_if_text_is_plain():
    out = steer_event(
        "The cortex predicts the steering subsystem.",
        signals={"novelty": 0.72, "memory_mass": 0.40},
        write=False,
    )

    assert out.route == "DEEP_CORTEX"
    assert any(p.source == "novelty_risk" for p in out.predictions)


def test_reward_signal_sharpens_temperature():
    positive = steer_event("perfect, exactly", signals={"metabolic_pressure": 0.0}, write=False)
    negative = steer_event("wrong, try again", signals={"metabolic_pressure": 0.0}, write=False)

    assert positive.reward_delta > 0
    assert negative.reward_delta < 0
    assert positive.temperature_hint < negative.temperature_hint


def test_receipt_write_redacts_full_text_and_preserves_route(tmp_path):
    out = steer_event(
        "From now on use the steering subsystem for cortex routing.",
        signals={"novelty": 0.40},
        state_dir=tmp_path,
        write=True,
        now=123.0,
    )
    ledger = tmp_path / "steering_subsystem.jsonl"

    rows = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert len(rows) == 1
    assert rows[0]["schema"] == "SIFTA_STEERING_SUBSYSTEM_RECEIPT_V1"
    assert rows[0]["trace_id"] == out.trace_id
    assert rows[0]["route"] == "DEEP_CORTEX"
    assert rows[0]["input_sha12"]
    assert "truth_boundary" in rows[0]


def test_prompt_block_is_compact_and_actionable():
    out = steer_event(
        "Do not open Safari without a receipt.",
        signals={"tool_truth_risk": 0.75},
        write=False,
    )
    block = steering_prompt_block(out)

    assert "STEERING SUBSYSTEM" in block
    assert "route: VERIFY_BEFORE_ACTION" in block
    assert "verify_tools" in block
    assert TRUTH_LABEL in block


def test_decision_is_deterministic_for_same_inputs():
    kwargs = {
        "signals": {
            "metabolic_pressure": 0.20,
            "owner_pressure": 0.30,
            "novelty": 0.40,
            "risk": 0.10,
            "memory_mass": 0.50,
        },
        "write": False,
    }
    a = steer_event("Explain steering ecology.", **kwargs).to_dict()
    b = steer_event("Explain steering ecology.", **kwargs).to_dict()

    a.pop("trace_id")
    b.pop("trace_id")
    assert a == b
