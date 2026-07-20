"""r1376 — Alice/owner can edit anchor names and living-timeline concepts."""
from __future__ import annotations

from pathlib import Path

from System.swarm_stigmergic_shared_experience_anchors import (
    answer_anchor_edit_query,
    edit_shared_experience_anchor,
    list_anchor_snapshots,
    register_shared_experience_anchor,
    shared_experience_anchors_prompt_block,
)


def test_edit_anchor_rename_and_concept(tmp_path: Path) -> None:
    sd = tmp_path / ".sifta_state"
    register_shared_experience_anchor(
        "Vince",
        status="CANDIDATE",
        anchor_kind="ambiguous_person",
        state_dir=sd,
    )
    row = edit_shared_experience_anchor(
        "Vince",
        new_canonical_name="JD Vance",
        concept_label="The View news clip 2026-06-19",
        timeline_label="2026-06-19 evening with George",
        disambiguation="JD Vance, not bare Vince",
        editor="alice_in_app",
        state_dir=sd,
    )
    assert row["canonical_name"] == "JD Vance"
    assert row["previous_canonical_name"] == "Vince"
    assert row["concept_label"] == "The View news clip 2026-06-19"
    assert row["timeline_label"] == "2026-06-19 evening with George"
    snaps = {s.canonical_name: s for s in list_anchor_snapshots(state_dir=sd)}
    assert snaps["JD Vance"].concept_label.startswith("The View")
    assert snaps["JD Vance"].timeline_label.startswith("2026-06-19")


def test_talk_edit_reflex_rename(tmp_path: Path) -> None:
    sd = tmp_path / ".sifta_state"
    register_shared_experience_anchor("Vince", status="CANDIDATE", state_dir=sd)
    reply = answer_anchor_edit_query(
        "edit anchor Vince to JD Vance",
        editor="alice_talk",
        state_dir=sd,
    )
    assert "JD Vance" in reply
    assert "Anchor edit receipt" in reply
    snaps = {s.canonical_name: s for s in list_anchor_snapshots(state_dir=sd)}
    assert "JD Vance" in snaps


def test_prompt_block_includes_alice_self_model(tmp_path: Path) -> None:
    sd = tmp_path / ".sifta_state"
    register_shared_experience_anchor(
        "Joy Behar",
        status="CONFIRMED",
        anchor_kind="public_figure",
        concept_label="The View clip with George",
        timeline_label="2026-06-19 The View clip",
        state_dir=sd,
    )
    block = shared_experience_anchors_prompt_block(state_dir=sd)
    assert "ALICE SELF-MODEL" in block
    assert "living timeline" in block
    assert "concept:" in block
    assert "timeline:" in block


def test_talk_edit_reflex_sets_timeline(tmp_path: Path) -> None:
    sd = tmp_path / ".sifta_state"
    register_shared_experience_anchor("Joy Behar", status="CONFIRMED", state_dir=sd)
    reply = answer_anchor_edit_query(
        "set anchor Joy Behar timeline to 2026-06-19 The View clip",
        editor="alice_talk",
        state_dir=sd,
    )
    assert "Anchor timeline set" in reply
    snaps = {s.canonical_name: s for s in list_anchor_snapshots(state_dir=sd)}
    assert snaps["Joy Behar"].timeline_label == "2026-06-19 The View clip"


def test_talk_widget_wires_anchor_edit_reflex() -> None:
    src = Path("Applications/sifta_talk_to_alice_widget.py").read_text(encoding="utf-8")
    assert "answer_anchor_edit_query" in src
