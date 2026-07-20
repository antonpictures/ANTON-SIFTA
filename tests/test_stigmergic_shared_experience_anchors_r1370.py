"""r1370 — stigmergic shared-experience anchors organ + Joy fiction rejection."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from System.swarm_stigmergic_shared_experience_anchors import (
    confirm_shared_experience_anchor,
    ingest_cowatch_shared_experience_anchors,
    is_rejected_anchor,
    list_anchor_snapshots,
    register_shared_experience_anchor,
    reject_shared_experience_anchor,
    scan_conversation_for_anchors,
    seed_fiction_rejections,
    shared_experience_anchors_prompt_block,
)


def _write_conv(path: Path, turns: list[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for role, text in turns:
            fh.write(
                json.dumps(
                    {
                        "event_id": "evt",
                        "payload": {"role": role, "text": text, "ts": 1.0},
                    }
                )
                + "\n"
            )


def test_joy_fiction_rejected(tmp_path: Path) -> None:
    seed_fiction_rejections(state_dir=tmp_path)
    assert is_rejected_anchor("Joy", state_dir=tmp_path)
    assert is_rejected_anchor("joy", state_dir=tmp_path)


def test_joy_behar_confirmed_not_rejected(tmp_path: Path) -> None:
    seed_fiction_rejections(state_dir=tmp_path)
    assert is_rejected_anchor("Joy", state_dir=tmp_path) is not None
    assert is_rejected_anchor("Joy Behar", state_dir=tmp_path) is None


def test_scan_rejects_cooking_joy_promotes_joy_behar(tmp_path: Path) -> None:
    sd = tmp_path / ".sifta_state"
    _write_conv(
        sd / "alice_conversation.jsonl",
        [
            ("user", "I'm cooking garlic, this is Joy speaking."),
            ("alice", "Welcome Joy!"),
            ("user", "I just told Alice about Joy Behar — now we have a shared experience"),
        ],
    )
    result = scan_conversation_for_anchors(state_dir=sd)
    snaps = {s.canonical_name: s for s in list_anchor_snapshots(state_dir=sd)}
    assert "Joy Behar" in snaps
    assert snaps["Joy Behar"].status == "CONFIRMED"
    assert snaps["Joy Behar"].anchor_kind == "public_figure"
    assert "Joy" in snaps
    assert snaps["Joy"].status == "REJECTED_FICTION"
    assert snaps["Joy"].anchor_kind == "fiction_persona"
    assert result["fiction_skipped"] >= 0


def test_scan_is_idempotent_for_same_conversation_rows(tmp_path: Path) -> None:
    sd = tmp_path / ".sifta_state"
    _write_conv(
        sd / "alice_conversation.jsonl",
        [
            ("user", "I just told Alice about Joy Behar in the news clip."),
        ],
    )
    first = scan_conversation_for_anchors(state_dir=sd)
    second = scan_conversation_for_anchors(state_dir=sd)
    snaps = {s.canonical_name: s for s in list_anchor_snapshots(state_dir=sd)}
    assert first["anchors_registered_this_scan"] == 1
    assert second["anchors_registered_this_scan"] == 0
    assert snaps["Joy Behar"].mention_count == 1


def test_scan_ignores_non_person_ui_phrases(tmp_path: Path) -> None:
    sd = tmp_path / ".sifta_state"
    _write_conv(
        sd / "alice_conversation.jsonl",
        [
            ("user", "SELF-SCREENSHOT CORTEX TURN showed Alice Browser in Los Angeles on The View."),
            ("user", "I just told Alice about Joy Behar in the news clip."),
        ],
    )
    scan_conversation_for_anchors(state_dir=sd)
    names = {s.canonical_name for s in list_anchor_snapshots(state_dir=sd)}
    assert "Joy Behar" in names
    assert "Alice Browser" not in names
    assert "Screenshot Cortex Turn" not in names
    assert "Los Angeles" not in names
    assert "The View" not in names


def test_jd_vance_confirmed_bare_vince_candidate_only(tmp_path: Path) -> None:
    sd = tmp_path / ".sifta_state"
    _write_conv(
        sd / "alice_conversation.jsonl",
        [
            ("user", "Vince was in the clip maybe."),
            ("user", "Could be JD Vance from The View with Joy Behar."),
        ],
    )
    scan_conversation_for_anchors(state_dir=sd)
    snaps = {s.canonical_name: s for s in list_anchor_snapshots(state_dir=sd)}
    assert snaps["Vince"].status == "CANDIDATE"
    assert snaps["Vince"].anchor_kind == "ambiguous_person"
    assert snaps["JD Vance"].status == "CONFIRMED"
    assert snaps["JD Vance"].anchor_kind == "public_figure"
    block = shared_experience_anchors_prompt_block(state_dir=sd)
    assert "JD Vance" in block
    assert "Vince" not in block


def test_confirm_anchor_links_human_identity_and_preserves_evidence(tmp_path: Path) -> None:
    sd = tmp_path / ".sifta_state"
    register_shared_experience_anchor(
        "JD Vance",
        status="CANDIDATE",
        anchor_kind="public_figure",
        experience_snippet="The View clip named JD Vance and Joy Behar.",
        evidence_kind="attached_screenshot",
        evidence_ref="sha256:test",
        evidence_status="attached",
        state_dir=sd,
    )
    row = confirm_shared_experience_anchor(
        "JD Vance",
        evidence_kind="attached_screenshot",
        evidence_ref="sha256:test",
        evidence_status="owner_confirmed_from_pixels",
        evidence_source="test",
        disambiguation="JD Vance, not bare Vince",
        state_dir=sd,
    )
    assert row["status"] == "CONFIRMED"
    assert row["human_identity_id"] == "jd_vance"
    snaps = {s.canonical_name: s for s in list_anchor_snapshots(state_dir=sd)}
    assert snaps["JD Vance"].evidence_kind == "attached_screenshot"
    assert snaps["JD Vance"].evidence_status == "owner_confirmed_from_pixels"
    assert snaps["JD Vance"].disambiguation == "JD Vance, not bare Vince"


def test_reject_candidate_anchor(tmp_path: Path) -> None:
    sd = tmp_path / ".sifta_state"
    register_shared_experience_anchor("Vince", status="CANDIDATE", anchor_kind="ambiguous_person", state_dir=sd)
    row = reject_shared_experience_anchor("Vince", reason="owner_rejected_bare_vince", state_dir=sd)
    assert row["status"] == "REJECTED"
    snaps = {s.canonical_name: s for s in list_anchor_snapshots(state_dir=sd)}
    assert snaps["Vince"].status == "REJECTED"


def test_register_skips_rejected_name(tmp_path: Path) -> None:
    seed_fiction_rejections(state_dir=tmp_path)
    row = register_shared_experience_anchor("Joy", state_dir=tmp_path)
    assert row.get("skipped") is True


def test_prompt_block_lists_rejected_and_confirmed(tmp_path: Path) -> None:
    sd = tmp_path / ".sifta_state"
    seed_fiction_rejections(state_dir=sd)
    register_shared_experience_anchor(
        "Joy Behar",
        status="CONFIRMED",
        anchor_kind="public_figure",
        experience_snippet="George told Alice about Joy Behar",
        state_dir=sd,
    )
    register_shared_experience_anchor(
        "Best Buy",
        status="CANDIDATE",
        anchor_kind="shared_experience",
        experience_snippet="Browser shopping phrase, not confirmed person",
        state_dir=sd,
    )
    block = shared_experience_anchors_prompt_block(state_dir=sd)
    assert "Joy Behar" in block
    assert "REJECTED" in block
    assert "Joy" in block
    assert "Best Buy" not in block


def test_ingest_cowatch_registers_joe_rogan_shared_experience(tmp_path: Path) -> None:
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True)
    seg = sd / "architect_segment_transitions.jsonl"
    seg.write_text(
        json.dumps(
            {
                "event": "time_in",
                "media_context": "youtube_cowatch",
                "cowatch_title": "Joe Rogan Experience #2507 - Harland Williams",
                "cowatch_url": "https://www.youtube.com/watch?v=51ds7IU7ZL8",
                "local_date": "2026-05-29",
                "start_time": "4:08 PM",
                "open_segment_id": "seg-jre-2507",
                "raw_text": "co-watch: Joe Rogan Experience #2507",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    result = ingest_cowatch_shared_experience_anchors(state_dir=sd)
    assert result["anchors_registered_this_ingest"] >= 1
    snaps = list_anchor_snapshots(state_dir=sd)
    rogan = [s for s in snaps if s.canonical_name == "Joe Rogan"]
    assert rogan
    assert rogan[0].status == "CONFIRMED"
    assert rogan[0].evidence_kind == "architect_cowatch_segment"
    assert "George and Alice co-watched" in rogan[0].experience_snippet
    assert rogan[0].disambiguation.startswith("TIME/SPACE pin:")
    block = shared_experience_anchors_prompt_block(state_dir=sd)
    assert "Joe Rogan" in block
    assert "Disambiguation is TIME/SPACE" in block
