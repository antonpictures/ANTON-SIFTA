"""Proofs for the persistent 38-drive economy and its safety boundary."""
from __future__ import annotations

import json

from System.swarm_drive_economy import (
    DRIVE_NAMES,
    MAX_ACTION_BIAS,
    DriveEconomy,
)
from System.swarm_artificial_endocrinology import (
    ArtificialEndocrinology,
    interoceptive_summary,
)
from System.swarm_drive_valuation import form_goal, value_candidates


def test_registry_contains_exactly_all_38_first_class_pressures(tmp_path) -> None:
    economy = DriveEconomy(tmp_path)
    snapshot = economy.tick(now=100.0)

    assert len(DRIVE_NAMES) == 38
    assert len(set(DRIVE_NAMES)) == 38
    assert set(snapshot.pressures) == set(DRIVE_NAMES)
    assert set(snapshot.effective_pressures) == set(DRIVE_NAMES)
    assert snapshot.dominant in DRIVE_NAMES
    assert snapshot.action_policy == "bounded_bias_only_requires_existing_gate"

    state = json.loads((tmp_path / "drive_economy.json").read_text())
    assert set(state["pressures"]) == set(DRIVE_NAMES)
    assert set(state["last_satisfied"]) == set(DRIVE_NAMES)


def test_pressures_persist_accumulate_and_can_be_satiated(tmp_path) -> None:
    economy = DriveEconomy(tmp_path)
    first = economy.tick(now=100.0)
    later = economy.tick(now=3700.0)
    assert later.pressures["empowerment"] > first.pressures["empowerment"]

    satiated = economy.tick(
        now=3701.0,
        context={"satisfied_drives": ["empowerment"]},
    )
    assert satiated.pressures["empowerment"] < later.pressures["empowerment"]


def test_only_authentic_organ_pressure_signals_are_accepted(tmp_path) -> None:
    economy = DriveEconomy(tmp_path)
    valid = economy.sign_signal(
        organ="competence_critic",
        drive="competence",
        delta=0.4,
        evidence="skill error remains high",
        ts=200.0,
    )
    tampered = valid.as_dict()
    tampered["delta"] = 0.9

    snapshot = economy.tick(signals=[valid, tampered], now=200.0)
    assert snapshot.accepted_signals == 1
    assert snapshot.rejected_signals == 1
    assert snapshot.pressures["competence"] > 0.5

    logged = json.loads((tmp_path / "drive_pressure_signals.jsonl").read_text().splitlines()[-1])
    assert logged["signal_id"] == valid.signal_id
    assert logged["signature"] == valid.signature


def test_survival_pressure_inhibits_exploration_class_drives(tmp_path) -> None:
    economy = DriveEconomy(tmp_path)
    energy = economy.sign_signal(
        organ="metabolic_homeostat",
        drive="energy",
        delta=0.8,
        evidence="energy deficit",
        ts=300.0,
    )
    curiosity = economy.sign_signal(
        organ="novelty_map",
        drive="curiosity",
        delta=0.8,
        evidence="novel state",
        ts=300.0,
    )
    snapshot = economy.tick(signals=[energy, curiosity], now=300.0)

    assert snapshot.pressures["curiosity"] > 0.9
    assert snapshot.effective_pressures["curiosity"] < snapshot.pressures["curiosity"]
    assert snapshot.effective_pressures["energy"] == snapshot.pressures["energy"]


def test_projection_is_bounded_and_cannot_create_action_classes(tmp_path) -> None:
    economy = DriveEconomy(tmp_path)
    snapshot = economy.tick(
        context={
            "novelty": 1.0,
            "social_presence": 1.0,
            "care_need": 1.0,
            "goal_gap": 1.0,
        },
        now=400.0,
    )
    deltas = economy.action_score_deltas(snapshot)

    assert set(deltas) == {"SILENCE", "TOOL", "ENGAGE", "BOND"}
    assert all(abs(value) <= MAX_ACTION_BIAS for value in deltas.values())

    loops = [
        {"name": "repair_guard", "salience": 0.4},
        {"name": "curiosity_scan", "salience": 0.4},
    ]
    biased = economy.bias_named_loops(loops, snapshot)
    assert [row["name"] for row in biased] == [row["name"] for row in loops]
    assert len(biased) == len(loops)


def test_context_adapters_activate_previously_missing_pressures(tmp_path) -> None:
    economy = DriveEconomy(tmp_path)
    snapshot = economy.tick(
        context={
            "action_set_loss": 1.0,
            "reproductive_context": 1.0,
            "partner_context": 1.0,
        },
        now=500.0,
    )

    assert snapshot.pressures["empowerment"] > 0.3
    assert snapshot.pressures["reproduction"] > 0.05
    assert snapshot.pressures["partner_selection"] > 0.05
    assert snapshot.pressures["sexual_analogue"] > 0.03


def test_fast_energy_recovers_faster_than_slow_affiliation(tmp_path) -> None:
    economy = DriveEconomy(tmp_path)
    energy = economy.sign_signal(
        organ="test", drive="energy", delta=0.6, evidence="depleted", ts=100.0
    )
    affiliation = economy.sign_signal(
        organ="test", drive="affiliation", delta=0.6, evidence="isolated", ts=100.0
    )
    raised = economy.tick(signals=[energy, affiliation], now=100.0)
    recovered = economy.tick(now=3700.0)

    energy_drop = raised.pressures["energy"] - recovered.pressures["energy"]
    affiliation_drop = raised.pressures["affiliation"] - recovered.pressures["affiliation"]
    assert energy_drop > affiliation_drop * 10


def test_satisfaction_couples_drives_and_creates_refractory_period(tmp_path) -> None:
    economy = DriveEconomy(tmp_path)
    raised = economy.tick(context={"novelty": 1.0}, now=100.0)
    outcome = economy.record_outcome(
        action="safe_scan",
        observed_satisfaction={"exploration": 1.0},
        predicted_satisfaction={"exploration": 0.3},
        now=101.0,
    )
    after = outcome["snapshot"]

    assert after["pressures"]["exploration"] < raised.pressures["exploration"]
    assert after["pressures"]["curiosity"] < raised.pressures["curiosity"]
    assert after["effective_pressures"]["exploration"] < after["pressures"]["exploration"]
    assert outcome["prediction_error"]["exploration"] == 0.7
    assert outcome["learning_alpha"] == 0.2
    assert outcome["layer_policy"] == "consequence_updates_plasticity_not_authority"


def test_allostasis_and_anticipation_are_distinct_from_current_deficit(tmp_path) -> None:
    economy = DriveEconomy(tmp_path)
    baseline = economy.tick(now=100.0)
    for step in range(10):
        adapted = economy.tick(
            context={"allostatic_targets": {"energy": 0.6}},
            now=101.0 + step,
        )
    anticipated = economy.tick(
        context={"predicted_deficits": {"energy": 0.8}},
        now=120.0,
    )

    assert adapted.setpoints["energy"] > baseline.setpoints["energy"]
    assert anticipated.pressures["energy"] > adapted.pressures["energy"]


def test_repeated_arbitration_loss_accumulates_frustration_not_pressure(tmp_path) -> None:
    economy = DriveEconomy(tmp_path)
    initial = economy.tick(context={"novelty": 1.0}, now=100.0)
    raw_curiosity = initial.pressures["curiosity"]
    for _ in range(6):
        economy.record_arbitration(
            winner_drive="integrity",
            considered_drives=("integrity", "curiosity"),
            now=101.0,
        )
    after = economy.tick(now=101.0)

    assert after.frustration["curiosity"] > 0.3
    assert abs(after.pressures["curiosity"] - raw_curiosity) < 0.0001


def test_endocrine_and_interoception_do_not_specify_actions(tmp_path) -> None:
    economy = DriveEconomy(tmp_path)
    snapshot = economy.tick(
        context={"integrity_error": 1.0, "social_presence": 1.0},
        now=100.0,
    )
    endocrine = ArtificialEndocrinology(tmp_path).tick(
        snapshot,
        satisfaction_prediction_error=-0.5,
        now=101.0,
    )
    summary = interoceptive_summary(snapshot)
    goal = form_goal(snapshot)

    assert endocrine.cortisol > 0.15
    assert endocrine.action_policy == "modulation_only_no_action_semantics"
    assert "action" not in endocrine.as_dict()
    assert snapshot.dominant.replace("_", " ") in summary
    assert goal.policy == "proposal_only_requires_basal_ganglia_and_authority_gates"


def _history_valuations(root, learned_action: str):
    economy = DriveEconomy(root)
    economy.record_outcome(
        action=learned_action,
        observed_satisfaction={"curiosity": 1.0},
        now=100.0,
    )
    signal = economy.sign_signal(
        organ="novelty_map",
        drive="curiosity",
        delta=0.8,
        evidence="same external stimulus",
        ts=2000.0,
    )
    snapshot = economy.tick(signals=[signal], now=2000.0)
    endocrine = ArtificialEndocrinology(root).tick(snapshot, now=2000.0)
    return value_candidates(
        [
            {"name": "inspect", "base_value": 0.5, "cost": 0.1},
            {"name": "ask", "base_value": 0.5, "cost": 0.1},
        ],
        snapshot=snapshot,
        neuromodulation=endocrine,
        economy=economy,
    )


def test_same_stimulus_different_histories_produce_traceable_bounded_preferences(tmp_path) -> None:
    inspect_history = _history_valuations(tmp_path / "inspect_history", "inspect")
    ask_history = _history_valuations(tmp_path / "ask_history", "ask")

    assert inspect_history.values["inspect"] > inspect_history.values["ask"]
    assert ask_history.values["ask"] > ask_history.values["inspect"]
    assert inspect_history.expected_satisfaction["inspect"]["curiosity"] > 0.0
    assert ask_history.expected_satisfaction["ask"]["curiosity"] > 0.0
    assert inspect_history.policy == "values_existing_candidates_only"
