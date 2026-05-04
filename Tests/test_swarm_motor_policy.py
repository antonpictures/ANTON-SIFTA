"""Event 103 — motor policy from crystallized skills."""

import json
from pathlib import Path

from System import swarm_motor_policy as mp


def test_empty_skills_defaults_to_first_candidate(tmp_path: Path) -> None:
    chosen, bias = mp.select_action_type_from_skills(
        ("explore", "forage"),
        "observe",
        state_dir=tmp_path,
    )
    assert chosen == "explore"
    assert set(bias.keys()) == {"explore", "forage"}


def test_crystallized_forage_wins_when_mass_high(tmp_path: Path) -> None:
    db = {
        "PRIM_abc": {
            "pattern_signature": "body_brain:forage:physics|SIFTA_BODY",
            "success_rate": 1.0,
            "usage_count": 40,
            "stability": 1.0,
            "frozen": False,
            "quarantined": False,
        }
    }
    (tmp_path / "crystallized_skills.json").write_text(
        json.dumps(db, indent=2), encoding="utf-8"
    )
    chosen, bias = mp.select_action_type_from_skills(
        ("explore", "forage"),
        "observe",
        state_dir=tmp_path,
    )
    assert chosen == "forage"
    assert bias["forage"] > bias["explore"]


def test_jsonl_primitive_merges(tmp_path: Path) -> None:
    jpath = tmp_path / "skill_primitives.jsonl"
    jpath.write_text(
        json.dumps(
            {
                "action": "forage",
                "avg_reward": 0.95,
                "usage_count": 20.0,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    chosen, _bias = mp.select_action_type_from_skills(
        ("explore", "forage"),
        "x",
        state_dir=tmp_path,
    )
    assert chosen == "forage"


def test_write_motor_policy_row(tmp_path: Path) -> None:
    row = mp.write_motor_policy_row(
        selected_action="explore",
        bias={"explore": 0.9, "forage": 0.1},
        current_drive="learn",
        state_dir=tmp_path,
    )
    ledger = tmp_path / "motor_policy.jsonl"
    assert ledger.exists()
    assert row["truth_label"] == mp.TRUTH_LABEL


def test_novelty_explore_mass_tilts_empty_skill_band(tmp_path: Path) -> None:
    """Event 112 — CA1 bias: with only epsilon floors, extra explore mass wins."""
    low, _ = mp.select_action_type_from_skills(
        ("explore", "forage"),
        "observe",
        state_dir=tmp_path,
        novelty_explore_mass=0.0,
    )
    high, bias = mp.select_action_type_from_skills(
        ("explore", "forage"),
        "observe",
        state_dir=tmp_path,
        novelty_explore_mass=2.5,
    )
    assert low == "explore"
    assert high == "explore"
    assert bias["explore"] > bias["forage"]

    forage_pick, fb = mp.select_action_type_from_skills(
        ("explore", "forage"),
        "observe",
        state_dir=tmp_path,
        novelty_forage_mass=3.0,
    )
    assert forage_pick == "forage"
    assert fb["forage"] > fb["explore"]
