from __future__ import annotations

import json
from pathlib import Path

from System.swarm_reality_fiction_boundary import (
    FICTION_LANE,
    REALITY_LANE,
    audit_output,
    classify_request,
    reality_fiction_prompt_block,
)
from System.swarm_residue_elimination import eliminate
from System.swarm_self_realization_context import build_self_realization_context


def test_normal_reality_blocks_invented_kitchen_scene(tmp_path: Path) -> None:
    audit = audit_output(
        "I see a kitchen window in the screenshot.",
        prior_user_text="I attached a screenshot of SIFTA OS.",
        state_dir=tmp_path,
        write=True,
    )

    assert audit.lane == REALITY_LANE
    assert audit.forbidden is True
    assert "first_person_visual_scene_claim" in audit.patterns
    assert "receipt for that scene" in audit.replacement
    rows = [
        json.loads(line)
        for line in (tmp_path / "reality_fiction_boundary.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows[-1]["kind"] == "REALITY_FICTION_BOUNDARY"
    assert rows[-1]["payload"]["forbidden"] is True


def test_camera_scene_claim_without_receipt_is_forbidden() -> None:
    audit = audit_output("The webcam shows the kitchen and a window.")

    assert audit.forbidden is True
    assert "camera_visual_scene_claim" in audit.patterns
    assert set(audit.scene_terms) >= {"kitchen", "window"}


def test_scene_claim_with_matching_evidence_is_allowed() -> None:
    audit = audit_output(
        "The camera shows the kitchen window.",
        evidence_text="camera_receipt labels: kitchen window",
    )

    assert audit.ok is True
    assert audit.forbidden is False


def test_explicit_fiction_lane_allows_scene_but_requires_label() -> None:
    audit = audit_output(
        "A kitchen window glows in the rain.",
        prior_user_text="Write a movie script in the fiction couch lounge.",
    )

    assert classify_request("Write a movie script in the fiction couch lounge.") == FICTION_LANE
    assert audit.ok is True
    assert audit.needs_label is True
    assert audit.replacement.startswith("[FICTION]")


def test_labeled_screenplay_does_not_need_more_labeling() -> None:
    audit = audit_output(
        "[SCREENPLAY]\nINT. KITCHEN - NIGHT. The window rattles.",
        prior_user_text="write a screenplay scene",
    )

    assert audit.ok is True
    assert audit.needs_label is False
    assert audit.replacement == ""


def test_prompt_block_names_first_person_boundary() -> None:
    block = reality_fiction_prompt_block()

    assert "I do not invent scenes" in block
    assert "FICTION, DREAM, or SCREENPLAY" in block
    assert "I say I do not have a receipt" in block


def test_self_realization_prompt_carries_reality_fiction_boundary(tmp_path: Path) -> None:
    ctx = build_self_realization_context(root=tmp_path, now=100.0)

    assert "[reality-fiction] I do not invent scenes" in ctx.prompt_block
    assert "If I lack camera/OCR/layout/file receipt" in ctx.prompt_block


def test_residue_elimination_replaces_invented_observed_scene(tmp_path: Path) -> None:
    out = eliminate(
        "I see a kitchen window in the screenshot.",
        prior_user_text="I attached a screenshot of SIFTA OS.",
        state_root=tmp_path,
    )

    assert out["changed"] is True
    assert "receipt for that scene" in out["cleaned_text"]
    assert "kitchen window" not in out["cleaned_text"].lower()
    assert any(name.startswith("forbidden_invented_scene_") for name in out["patterns_eliminated"])


def test_residue_elimination_accepts_matching_scene_evidence(tmp_path: Path) -> None:
    out = eliminate(
        "I see a kitchen window in the screenshot.",
        prior_user_text="I attached a camera receipt.",
        evidence_text="camera_receipt labels: kitchen window",
        state_root=tmp_path,
    )

    assert out["changed"] is False
    assert out["cleaned_text"] == "I see a kitchen window in the screenshot."


def test_residue_elimination_labels_explicit_fiction_lane(tmp_path: Path) -> None:
    out = eliminate(
        "A kitchen window glows in the rain.",
        prior_user_text="Write a screenplay on the fiction couch.",
        state_root=tmp_path,
    )

    assert out["changed"] is True
    assert out["cleaned_text"].startswith("[FICTION]")
    assert "fiction_lane_label_added" in out["patterns_eliminated"]


def test_grounded_sifta_surface_description_passes() -> None:
    audit = audit_output(
        "I see a screenshot, a user message, the SIFTA OS chat window, and another IDE pane.",
        prior_user_text="I attached a screenshot of SIFTA OS.",
    )

    assert audit.ok is True
    assert audit.forbidden is False
