from __future__ import annotations

import json
from pathlib import Path

from System.swarm_truth_navigation_field import (
    LEDGER_NAME,
    doctrine_backlog,
    prompt_block_for_claim,
    summary_for_prompt,
    truth_navigation_assessment,
)


def test_unreceipted_real_world_doctrine_names_missing_probes(tmp_path: Path) -> None:
    row = truth_navigation_assessment(
        "Truth of the image, physics, distance, people, environment; Alice can wake up and adapt as AGI.",
        state_dir=tmp_path,
        write=True,
    )

    assert row["verdict"] == "ARCHITECT_DOCTRINE_WITH_OPEN_PROBES"
    assert row["architect_doctrine_detected"] is True
    assert set(row["missing_probe_dimensions"]) >= {
        "image_truth",
        "physics_truth",
        "distance_truth",
        "people_truth",
        "environment_truth",
    }
    saved = json.loads((tmp_path / LEDGER_NAME).read_text(encoding="utf-8").splitlines()[0])
    assert saved["sha256"] == row["sha256"]


def test_receipted_visual_claim_is_observed(tmp_path: Path) -> None:
    row = truth_navigation_assessment(
        "The image shows the room.",
        evidence_packets=[
            {
                "kind": "visual_confirmation",
                "observed": True,
                "trace_id": "vis-1",
                "screenshot_hash": "abc123",
                "preview": "room observed",
            }
        ],
        state_dir=tmp_path,
    )

    assert row["verdict"] == "OBSERVED"
    assert row["missing_probe_dimensions"] == []
    assert row["dimensions"][0]["status"] == "OBSERVED"


def test_prompt_block_writes_current_turn_receipt_and_summary(tmp_path: Path) -> None:
    block = prompt_block_for_claim(
        "I need truth before navigation in a new environment.",
        state_dir=tmp_path,
        write=True,
    )

    assert "TRUTH NAVIGATION FIELD" in block
    assert "current_turn_verdict" in block
    assert (tmp_path / LEDGER_NAME).exists()
    summary = summary_for_prompt(state_dir=tmp_path)
    assert "last_verdict" in summary
    assert "environment_truth" in summary


def test_doctrine_backlog_names_four_coding_lanes() -> None:
    tasks = doctrine_backlog()
    ids = {task["task_id"] for task in tasks}

    assert ids == {
        "truth_nav_image_grounding",
        "truth_nav_physics_distance",
        "truth_nav_people_provenance",
        "truth_nav_adaptive_environment_loop",
    }


def test_talk_prompt_wires_truth_navigation_field() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "Applications"
        / "sifta_talk_to_alice_widget.py"
    ).read_text(encoding="utf-8", errors="replace")

    assert "from System.swarm_truth_navigation_field import prompt_block_for_claim" in source
    assert "state_dir=_state_root()" in source
    assert "write=bool((user_text or \"\").strip())" in source
