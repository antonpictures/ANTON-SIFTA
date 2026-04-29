"""Drive-to-basal-ganglia wiring stays a bias, not an effector permission."""

from __future__ import annotations

import json

from System import swarm_action_selector as selector
from System.swarm_drive_hypothalamus import DriveHypothalamus


def test_apply_drive_priors_can_bias_marginal_scores() -> None:
    scores = {
        selector.ACTION_SILENCE: 0.20,
        selector.ACTION_TOOL: 0.21,
        selector.ACTION_ENGAGE: 0.20,
        selector.ACTION_BOND: 0.20,
    }
    adjusted = selector.apply_drive_priors(
        scores,
        {
            selector.ACTION_SILENCE: 0.08,
            selector.ACTION_TOOL: -0.04,
        },
    )

    assert adjusted[selector.ACTION_SILENCE] > adjusted[selector.ACTION_TOOL]


def test_pipeline_accepts_drive_hypothalamus_without_changing_tuple_contract(tmp_path, monkeypatch) -> None:
    receipts = tmp_path / ".sifta_state" / "work_receipts.jsonl"
    monkeypatch.setattr(selector, "_REPO", tmp_path)

    drive = DriveHypothalamus()
    winner, injection, probs = selector.pipeline_step(
        "George is active at the desk.",
        c1_raw_output='{"action":"ENGAGE","tone":"brief"}',
        log=True,
        drive_hypothalamus=drive,
        metabolic_state={"energy_fraction": 0.85},
        recent_events={"owner_activity": True, "errors": False},
    )

    assert winner in selector.ALL_ACTIONS
    assert isinstance(injection, str)
    assert set(probs).issubset(set(selector.ALL_ACTIONS))

    row = json.loads(receipts.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert row["kind"] == "basal_ganglia_selection"
    assert row["drive_context"]["dominant"] in {"energy", "social", "curiosity", "safety"}
    assert row["drive_context"]["drives"]["social"] == 1.0


def test_pipeline_can_inject_theory_of_mind_before_corpus_callosum(tmp_path, monkeypatch) -> None:
    receipts = tmp_path / ".sifta_state" / "work_receipts.jsonl"
    monkeypatch.setattr(selector, "_REPO", tmp_path)

    from System.swarm_theory_of_mind import SwarmTheoryOfMind

    btom = SwarmTheoryOfMind(state_dir=str(tmp_path / ".sifta_state"))
    winner, injection, probs = selector.pipeline_step(
        "FIX THE CRYPTOPHYSICS NOW",
        c1_raw_output='{"action":"ENGAGE","tone":"brief"}',
        log=True,
        theory_of_mind=btom,
    )

    assert winner == selector.ACTION_ENGAGE
    assert injection.startswith("[THEORY_OF_MIND ")
    assert "state=high_stress" in injection
    assert "external_action_policy=explicit_owner_consent_required" in injection
    assert set(probs).issubset(set(selector.ALL_ACTIONS))

    row = json.loads(receipts.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert row["drive_context"]["social_modulation"]["inferred_state"] == "high_stress"
