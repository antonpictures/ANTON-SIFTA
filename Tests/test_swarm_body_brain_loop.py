#!/usr/bin/env python3
"""
tests/test_swarm_body_brain_loop.py
══════════════════════════════════════════════════════════════════════
Tests for the executable body-brain physiology loop.
"A living loop without tests is mythology."
"""

import os
import json
import math
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

os.environ["SIFTA_ALICE_ENABLE_CONSCIOUSNESS_LOOP"] = "1"

from System.swarm_body_brain_loop import SwarmPhysiology, _core_self_salience
from System.swarm_metabolic_homeostasis import MetabolicState
from System.swarm_reset_recovery_immunity import required_ledger_paths

@pytest.fixture
def clean_state(tmp_path):
    with patch("System.swarm_body_brain_loop._STATE_DIR", tmp_path):
        yield tmp_path


def _warm_reset_ledgers(root: Path) -> None:
    for name, path in required_ledger_paths(root).items():
        # Leave body_brain_memory.jsonl empty so tests can assert the current
        # tick's write count while still keeping Event 110 in READY phase
        # (6/7 warm ledgers meets the 0.85 threshold).
        if name == "body":
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"ts": 2_000_000_000.0}) + "\n", encoding="utf-8")

def test_body_brain_tick_normal_cycle(clean_state):
    _warm_reset_ledgers(clean_state)
    physiology = SwarmPhysiology(enable_george_prior=False)
    
    # Force a healthy metabolic state
    healthy_state = MetabolicState(usd_burn_24h=0.0, local_units_24h=0.0, stgm_balance=150.0)
    
    with patch("System.swarm_body_brain_loop.MetabolicHomeostat.sample_live", return_value=healthy_state):
        with patch("time.sleep") as mock_sleep:
            result = physiology.body_brain_tick()
            
            # Verify outputs
            assert "action" in result
            assert "value" in result
            assert "metabolic_mode" in result
            assert result["metabolic_mode"] == "GREEN_GROW"
            
            # Verify action execution (motor cortex sleep was called)
            mock_sleep.assert_called_once_with(0.1)
            
            # Verify memory was written
            memory_file = clean_state / "body_brain_memory.jsonl"
            assert memory_file.exists()
            lines = memory_file.read_text().strip().split("\n")
            assert len(lines) == 1
            row = json.loads(lines[0])
            assert row["event"] == "body_brain_tick"
            assert "action" in row
            assert "result" in row
            assert "td_value" in row
            assert row.get("drive_state")
            assert row.get("metabolic_mode")
            phen = clean_state / "visual_phenotype_uniforms.jsonl"
            assert phen.exists()
            prow = json.loads(phen.read_text().strip().splitlines()[-1])
            assert prow.get("u_stigmergic_drive") is not None
            assert prow.get("receipt_backed") is True
            assert row.get("tick_id")
            assert "u_chemotaxis_gradient" in prow
            assert row["drive_bias_applied"] is False
            assert row["truth_label"] == "NO_INTRINSIC_DRIVE_BIAS"
            assert "novelty_phase" in row
            assert row["novelty_phase"] in (
                "NO_MEMORY",
                "NOVEL",
                "FAMILIAR",
                "MIXED",
            )


def test_body_brain_tick_writes_prompt_visible_organ_heartbeats(clean_state):
    _warm_reset_ledgers(clean_state)
    physiology = SwarmPhysiology(enable_george_prior=False)
    healthy_state = MetabolicState(usd_burn_24h=0.0, local_units_24h=0.0, stgm_balance=150.0)

    with patch("System.swarm_body_brain_loop.MetabolicHomeostat.sample_live", return_value=healthy_state):
        with patch("time.sleep"):
            physiology.body_brain_tick()

    expected = {
        "motor_bus.jsonl": ("octopus", "coherence"),
        "cuttlefish_display.jsonl": ("cuttlefish", "contrast"),
        "electric_field.jsonl": ("electric", "phase"),
        "waggle_quorum.jsonl": ("honeybee", "angle"),
    }
    for ledger_name, (organ, top_level_key) in expected.items():
        ledger = clean_state / ledger_name
        assert ledger.exists()
        row = json.loads(ledger.read_text(encoding="utf-8").splitlines()[-1])
        assert row["schema"] == "ORGAN_EVENT_V1"
        assert row["source"] == "swarm_body_brain_loop:organ_heartbeat"
        assert row["organ"] == organ
        assert row["truth_label"] == "OPERATIONAL"
        assert row.get(top_level_key) is not None
        assert row["payload"]["tick_id"]
        assert row["payload"]["action_type"]
        assert row["payload"]["metabolic_mode"] == "GREEN_GROW"

    field = json.loads((clean_state / "organ_field_vector.jsonl").read_text().splitlines()[-1])
    assert (clean_state / "td_receipts.jsonl").exists()
    assert (clean_state / "dopamine_reward_ledger.jsonl").exists()
    assert (clean_state / "hippocampus" / "events.jsonl").exists()
    assert (clean_state / "reflex_arc_trace.jsonl").exists()
    assert (clean_state / "basal_ganglia_selections.jsonl").exists()
    assert field["schema"] == "ORGAN_EVENT_V1"
    assert field["organ"] == "unified_field"
    assert field["event_type"] == "high_dimensional_field_vector"
    assert field["dimension_count"] == len(field["field_vector"])
    assert field["dimension_count"] >= 29
    assert field["coupling_edge_count"] >= 8
    assert field["payload"]["tensor_shapes"]["cuttlefish_skin"] == [4, 4]
    assert field["payload"]["tensor_shapes"]["organ_health"] == [17]
    assert field["payload"]["tensor_shapes"]["field_memory"] == [field["dimension_count"]]
    assert field["payload"]["tensor_shapes"]["metabolic_context"] == [7]
    assert field["declared_organ_count"] == 17
    assert field["connected_organ_count"] == 17
    assert field["swimmer_count"] >= 45
    assert len(field["organ_nodes"]) == 17
    assert field["unknown_vector_count"] >= 1
    assert field["low_resolution_vector_count"] >= 1
    assert 0.0 <= field["field_completeness"] <= 1.0
    assert len(field["unknown_vectors"]) == field["unknown_vector_count"]
    assert all(
        {"organ", "reason", "source", "health", "resolution"} <= set(vector)
        for vector in field["unknown_vectors"]
    )
    assert {node["organ"] for node in field["organ_nodes"]} >= {
        "field",
        "td_learner",
        "dopamine",
        "sensor_gate",
        "bg_selector",
    }
    td = json.loads((clean_state / "td_receipts.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    dopamine = json.loads(
        (clean_state / "dopamine_reward_ledger.jsonl").read_text(encoding="utf-8").splitlines()[-1]
    )
    hippocampus = json.loads(
        (clean_state / "hippocampus" / "events.jsonl").read_text(encoding="utf-8").splitlines()[-1]
    )
    reflex = json.loads((clean_state / "reflex_arc_trace.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    bg = json.loads((clean_state / "basal_ganglia_selections.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert td["source"] == "swarm_body_brain_loop:cognitive_heartbeat"
    assert dopamine["source"] == "swarm_body_brain_loop:cognitive_heartbeat"
    assert hippocampus["event_type"] == "body_brain_tick"
    assert reflex["source"] == "swarm_body_brain_loop:reflex_monitor"
    assert reflex["fired"] is False
    assert bg["truth_label"] == "BASAL_GANGLIA_SELECTION"
    assert bg["source"] == "swarm_body_brain_loop:bg_selector_heartbeat"
    assert "truth_reward" in td
    assert "truth_reward" in dopamine
    assert field["payload"]["metabolic_cost"]["latency_ms"] >= 0.0
    assert field["payload"]["metabolic_cost"]["estimated_tokens"] >= 1
    assert 0.0 <= field["payload"]["cost_pressure"] <= 1.0
    assert field["payload"]["field_homeostasis_state"] in {
        "VIABLE",
        "REGULATE",
        "CONSERVE_REPAIR",
    }
    assert field["payload"]["field_control_action"]
    assert len(field["payload"]["field_memory_vector"]) == field["dimension_count"]
    assert 0.0 <= field["payload"]["field_memory_retention"] <= 1.0
    assert field["payload"]["motor_effector_policy"]["effector_gate"] == "LEDGER_ONLY"
    assert (clean_state / "field_homeostasis.jsonl").exists()
    assert (clean_state / "field_motor_effector.jsonl").exists()
    assert (clean_state / "motor_pulses.jsonl").exists()

    truth = json.loads(
        (clean_state / "truth_continuity_events.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[-1]
    )
    assert truth["schema"] == "TRUTH_CONTINUITY_EVENT_V1"
    assert truth["writer"] == "swarm_body_brain_loop:organ_heartbeat"
    assert truth["continuity_score"] == 1.0
    assert truth["drift_flags"] == []
    assert truth["tick_id"]
    assert "organ_field_vector.jsonl" in truth["evidence_refs"]


def test_organ_heartbeats_are_coupled_to_prior_organ_rows(clean_state):
    physiology = SwarmPhysiology(enable_george_prior=False)
    fixed_now = 100.0

    (clean_state / "electric_field.jsonl").write_text(
        json.dumps({"ts": fixed_now - 1, "payload": {"phase": math.pi / 2}}) + "\n",
        encoding="utf-8",
    )
    (clean_state / "waggle_quorum.jsonl").write_text(
        json.dumps({"ts": fixed_now - 1, "payload": {"vigor": 0.9}}) + "\n",
        encoding="utf-8",
    )
    (clean_state / "motor_bus.jsonl").write_text(
        json.dumps({"ts": fixed_now - 1, "payload": {"coherence": 0.8}}) + "\n",
        encoding="utf-8",
    )

    with patch("System.swarm_body_brain_loop._STATE_DIR", clean_state):
        with patch("System.swarm_body_brain_loop.time.time", return_value=fixed_now):
            with patch("System.swarm_pheromone_field._real_position", return_value=(0.0, 0.0, 0.0)):
                with patch("System.swarm_pheromone_field.sample_gradient", return_value=((1.0, 0.0), 0.2)):
                    physiology._write_organ_heartbeats(
                        action={"type": "explore", "target": "curiosity"},
                        value=0.5,
                        danger={"mode": "GREEN_GROW", "pressure": 0.0},
                        mem_row={"tick_id": "coupling-test"},
                        now_state={},
                    )

    electric = json.loads((clean_state / "electric_field.jsonl").read_text().splitlines()[-1])
    octopus = json.loads((clean_state / "motor_bus.jsonl").read_text().splitlines()[-1])
    honeybee = json.loads((clean_state / "waggle_quorum.jsonl").read_text().splitlines()[-1])
    cuttlefish = json.loads((clean_state / "cuttlefish_display.jsonl").read_text().splitlines()[-1])
    field = json.loads((clean_state / "organ_field_vector.jsonl").read_text().splitlines()[-1])

    base_angle = 0.1
    expected_td_error = 0.5
    expected_vigor = min(
        0.95,
        0.35 + 0.50 * 0.5 + 0.15 * 0.2 + 0.05 * 0.8 + min(0.3, abs(expected_td_error)),
    )
    expected_waggle = [
        round(math.cos(base_angle) * expected_vigor, 4),
        round(math.sin(base_angle) * expected_vigor, 4),
    ]
    motor_vigor = 0.75 * expected_vigor + 0.25 * 0.9
    expected_arms = []
    for i in range(8):
        arm_angle = i * (math.pi / 4.0)
        expected_arms.append(round(max(0.0, min(1.0, 0.5 + 0.3 * math.cos(arm_angle - base_angle) * motor_vigor)), 4))
    dipole_x = sum(a * math.cos(i * math.pi / 4) for i, a in enumerate(expected_arms))
    dipole_y = sum(a * math.sin(i * math.pi / 4) for i, a in enumerate(expected_arms))
    expected_phase = math.atan2(dipole_y, dipole_x) % (2 * math.pi)

    assert honeybee["vigor"] == round(expected_vigor, 4)
    assert honeybee["payload"]["dance_vector"] == expected_waggle
    assert honeybee["payload"]["prev_electric_phase"] == round(math.pi / 2, 6)
    assert honeybee["payload"]["prev_octopus_coherence"] == 0.8
    assert "electric_field.jsonl" in honeybee["payload"]["coupled_from"]

    assert electric["phase"] == round(expected_phase, 6)
    assert electric["payload"]["dipole_moments"] == [
        round(dipole_x, 4),
        round(dipole_y, 4),
        0.53,
    ]
    assert electric["payload"]["prev_octopus_coherence"] == 0.8
    assert electric["payload"]["coupled_from"] == ["motor_bus.jsonl"]

    assert octopus["payload"]["arm_activations"] == expected_arms
    assert octopus["payload"]["prev_honeybee_vigor"] == 0.9
    assert octopus["payload"]["coupled_from"] == ["waggle_quorum.jsonl"]

    assert cuttlefish["pattern"] == "alarm"
    assert len(cuttlefish["payload"]["skin_matrix"]) == 4
    assert len(cuttlefish["payload"]["skin_matrix"][0]) == 4
    assert cuttlefish["payload"]["prev_electric_phase"] == round(math.pi / 2, 6)
    assert cuttlefish["payload"]["prev_honeybee_vigor"] == 0.9
    assert "electric_field.jsonl" in cuttlefish["payload"]["coupled_from"]

    assert field["dimension_count"] == len(field["field_vector"])
    assert field["dimension_count"] == len(field["dimension_names"])
    assert field["coupling_edge_count"] == len(field["coupling_edges"])
    assert field["coupling_edge_count"] >= 30
    assert field["payload"]["declared_organ_count"] == 17
    assert field["payload"]["connected_organ_count"] == 17
    assert field["payload"]["swimmer_count"] >= 45
    assert len(field["payload"]["organ_health"]) == 17
    assert len(field["payload"]["swimmer_registry"]) == field["payload"]["swimmer_count"]
    assert field["payload"]["unknown_vector_count"] >= 1
    assert field["payload"]["low_resolution_vector_count"] >= 1
    assert 0.0 <= field["payload"]["field_completeness"] <= 1.0
    assert "metabolic_cost" in field["payload"]
    assert "field_homeostasis" in field["payload"]
    assert "field_decay" in field["payload"]
    assert "motor_effector_policy" in field["payload"]
    assert {
        "organ",
        "source",
        "source_strength",
        "resolution",
    } <= set(field["payload"]["organ_nodes"][0])
    assert any(edge["source"] == "td_learner" and edge["target"] == "honeybee" for edge in field["coupling_edges"])
    assert any(edge["source"] == "basal_ganglia" and edge["target"] == "octopus" for edge in field["coupling_edges"])
    assert field["payload"]["source_ledgers"][:4] == [
        "waggle_quorum.jsonl",
        "motor_bus.jsonl",
        "electric_field.jsonl",
        "cuttlefish_display.jsonl",
    ]


def test_body_brain_tick_critical_sleep_trigger(clean_state):
    _warm_reset_ledgers(clean_state)
    physiology = SwarmPhysiology(enable_george_prior=False)
    
    # Force a critical metabolic state (starving/high pressure)
    critical_state = MetabolicState(usd_burn_24h=12.0, local_units_24h=200.0, stgm_balance=0.0)
    
    with patch("System.swarm_body_brain_loop.MetabolicHomeostat.sample_live", return_value=critical_state):
        with patch("time.sleep") as mock_sleep:
            result = physiology.body_brain_tick()
            
            assert result["metabolic_mode"] in ("RED_CONSERVE", "CRITICAL_STARVATION")
            assert result["action"]["type"] == "rest"
            
            # Sleep should be called TWICE: once for motor execution (0.1) and once for enforced sleep (>0)
            assert mock_sleep.call_count == 2


def test_choose_action_applies_high_score_intrinsic_drive_bias(clean_state):
    physiology = SwarmPhysiology(enable_george_prior=False)
    receipt = {
        "topic": "biology",
        "goal": "Inspect dream skill crystallization.",
        "score": 0.168,
        "source": "test_harness",
    }

    action = physiology._choose_action(
        "curiosity",
        {"is_critical": False, "mode": "GREEN_GROW", "pressure": 0.0},
        intrinsic_receipt=receipt,
    )

    assert action["type"] == "explore"
    assert action["target"] == "curiosity"
    assert action["drive_bias_applied"] is True
    assert action["drive_bias_topic"] == "biology"
    assert action["drive_bias_goal"] == "Inspect dream skill crystallization."
    assert action["drive_bias_score"] == 0.168
    assert action["drive_bias_source"] == "test_harness"
    assert action["truth_label"] == "SIMULATED_INTRINSIC_DRIVE"


def test_choose_action_ignores_low_score_intrinsic_drive_bias(clean_state):
    physiology = SwarmPhysiology(enable_george_prior=False)
    receipt = {"topic": "biology", "goal": "Too weak.", "score": 0.01, "source": "test_harness"}

    action = physiology._choose_action(
        "curiosity",
        {"is_critical": False, "mode": "GREEN_GROW", "pressure": 0.0},
        intrinsic_receipt=receipt,
    )

    assert action["type"] == "explore"
    assert action["drive_bias_applied"] is False
    assert action["drive_bias_topic"] == ""
    assert action["truth_label"] == "NO_INTRINSIC_DRIVE_BIAS"


def test_body_brain_tick_writes_drive_bias_ledger_fields(clean_state):
    _warm_reset_ledgers(clean_state)
    physiology = SwarmPhysiology(enable_george_prior=False)
    healthy_state = MetabolicState(usd_burn_24h=0.0, local_units_24h=0.0, stgm_balance=150.0)
    receipt = {
        "topic": "identity",
        "goal": "Review the founding covenant.",
        "score": 0.2,
        "source": "test_harness",
    }

    with patch("System.swarm_body_brain_loop._GEORGE_PRIOR_AVAILABLE", True):
        with patch("System.swarm_body_brain_loop.get_current_drive", return_value=receipt):
            with patch("System.swarm_body_brain_loop.MetabolicHomeostat.sample_live", return_value=healthy_state):
                with patch("time.sleep"):
                    result = physiology.body_brain_tick()

    assert result["action"]["drive_bias_applied"] is True
    row = json.loads((clean_state / "body_brain_memory.jsonl").read_text().splitlines()[-1])
    assert row["drive_bias_applied"] is True
    assert row["drive_bias_topic"] == "identity"
    assert row["drive_bias_goal"] == "Review the founding covenant."
    assert row["drive_bias_score"] == 0.2
    assert row["drive_bias_source"] == "test_harness"
    assert row["truth_label"] == "SIMULATED_INTRINSIC_DRIVE"


def test_body_brain_tick_blocks_autonomy_when_reset_ledgers_are_cold(clean_state):
    physiology = SwarmPhysiology(enable_george_prior=False)
    healthy_state = MetabolicState(usd_burn_24h=0.0, local_units_24h=0.0, stgm_balance=150.0)

    with patch("System.swarm_body_brain_loop.MetabolicHomeostat.sample_live", return_value=healthy_state):
        with patch("time.sleep"):
            result = physiology.body_brain_tick()

    assert result["reset_recovery"]["autonomy_gate"] == "BLOCK"
    assert result["action"]["type"] == "repair"
    assert result["action"]["reason"] == "reset_recovery_immunity_block"
    row = json.loads((clean_state / "body_brain_memory.jsonl").read_text().splitlines()[-1])
    assert row["reset_recovery_gate"] == "BLOCK"


def test_body_brain_tick_wires_orienting_reflex(clean_state):
    _warm_reset_ledgers(clean_state)
    body = clean_state / "body_brain_memory.jsonl"
    body.write_text(
        "\n".join(json.dumps({"ts": 1.0 + i, "action": {"type": f"explore_{i}"}}) for i in range(10)) + "\n",
        encoding="utf-8",
    )
    (clean_state / "superior_colliculus.jsonl").write_text(
        json.dumps({"ts": 2.0, "integrated_salience": 0.9, "trace_id": "sc-1"}) + "\n",
        encoding="utf-8",
    )
    physiology = SwarmPhysiology(enable_george_prior=False)
    healthy_state = MetabolicState(usd_burn_24h=0.0, local_units_24h=0.0, stgm_balance=150.0)

    with patch("System.swarm_body_brain_loop.MetabolicHomeostat.sample_live", return_value=healthy_state):
        with patch("time.sleep"):
            result = physiology.body_brain_tick()

    orient = result["orienting_reflex"]
    assert orient["truth_label"] == "SIMULATED_ORIENTING_REFLEX"
    assert orient["orient_trigger"] is True
    assert orient["command"]["attention_gain"] > 1.0
    assert (clean_state / "orienting_reflex.jsonl").exists()
    row = json.loads((clean_state / "body_brain_memory.jsonl").read_text().splitlines()[-1])
    assert row["orient_trigger"] is True
    assert row["orienting_intensity"] == orient["orienting_intensity"]


def test_body_brain_tick_records_core_self_interaction_for_salient_causal_probe(clean_state):
    _warm_reset_ledgers(clean_state)
    physiology = SwarmPhysiology(enable_george_prior=False)
    healthy_state = MetabolicState(usd_burn_24h=0.0, local_units_24h=0.0, stgm_balance=150.0)

    probe_receipt = {
        "causal_effect_size": 0.25,
        "intervention": {"do": {"target": "exploration_bias", "dry_run": False}},
    }

    with patch("System.swarm_body_brain_loop.MetabolicHomeostat.sample_live", return_value=healthy_state):
        with patch(
            "System.swarm_active_causal_prober.propose_and_execute_runtime_intervention",
            return_value=probe_receipt,
        ):
            with patch("time.sleep"):
                physiology.body_brain_tick()

    identity_log = clean_state / "identity_continuity.jsonl"
    assert identity_log.exists()
    rows = [json.loads(line) for line in identity_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    core_rows = [row for row in rows if row.get("kind") == "CORE_SELF_INTERACTION"]
    assert core_rows
    assert core_rows[-1]["interaction_type"] == "CAUSAL_PROBE"
    assert core_rows[-1]["salience"] >= 0.6
    assert "exploration_bias" in core_rows[-1]["summary"]


def test_critical_danger_suppresses_drive_bias_even_with_receipt(clean_state):
    physiology = SwarmPhysiology(enable_george_prior=False)
    receipt = {
        "topic": "biology",
        "goal": "Should not override rest.",
        "score": 0.5,
        "source": "test_harness",
    }

    action = physiology._choose_action(
        "curiosity",
        {"is_critical": True, "mode": "CRITICAL_STARVATION", "pressure": 1.0},
        intrinsic_receipt=receipt,
    )

    assert action["type"] == "rest"
    assert action["drive_bias_applied"] is False
    assert action["drive_bias_topic"] == ""
    assert action["truth_label"] == "NO_INTRINSIC_DRIVE_BIAS"


def test_core_self_salience_filters_low_body_state_change():
    salience = _core_self_salience(
        action_confidence=0.2,
        causal_effect_size=0.01,
        uncertainty=0.1,
        valence=0.05,
        na_level=0.52,
        clamp_level="NONE",
    )
    assert salience < 0.6


def test_core_self_salience_records_causal_probe_effect():
    salience = _core_self_salience(
        action_confidence=0.2,
        causal_effect_size=0.25,
        uncertainty=0.2,
        valence=0.0,
        na_level=0.5,
        clamp_level="NONE",
    )
    assert salience >= 0.6


def test_core_self_salience_records_instability_clamp():
    salience = _core_self_salience(
        action_confidence=0.2,
        causal_effect_size=0.0,
        uncertainty=0.2,
        valence=0.0,
        na_level=0.5,
        clamp_level="EMERGENCY",
    )
    assert salience >= 0.6
