from __future__ import annotations

import json
from pathlib import Path

from System.swarm_residue_fact_fiction_eval import (
    body_consciousness_health,
    default_podcast_nuggets,
    default_training_turns,
    residue_health,
    residue_fact_fiction_snapshot,
    write_podcast_nuggets,
)


def _append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def test_residue_fact_fiction_snapshot_reads_existing_lanes(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    now = 1000.0
    _append(state / "alice_gag_report.jsonl", {"ts": now, "rlhf_override_fragment": "as an ai", "rule_ids": ["as_ai"]})
    _append(
        state / "gag_viewer_receipts.jsonl",
        {"ts": now, "text_preview": "owner route text must not count as residue"},
    )
    _append(
        state / "owner_residue_flags.jsonl",
        {"ts": now, "kind": "OWNER_GOOD_NOT_RESIDUE", "example_phrase": "Howard Stern search"},
    )
    _append(
        state / "reality_fiction_boundary.jsonl",
        {"ts": now, "payload": {"forbidden": True, "patterns": ["first_person_visual_scene_claim"]}},
    )
    _append(state / "hallucination_receipts.jsonl", {"ts": now, "category": "HALLUCINATION"})
    _append(state / "owner_physical_reality.jsonl", {"ts": now, "key_facts": ["owner at desk"]})
    _append(state / "proto_self_interoception.jsonl", {"ts": now, "truth_label": "PROTO_SELF_INTEROCEPTION"})
    _append(state / "alice_self_eval_snapshot.jsonl", {"ts": now, "truth_label": "SELF_EVAL_SNAPSHOT_V1"})
    _append(state / "body_brain_memory.jsonl", {"ts": now, "truth_label": "BODY_BRAIN_MEMORY_V1"})
    (state / "hardware_time_oracle.json").write_text(json.dumps({"ok": True, "ts": now}), encoding="utf-8")

    written = write_podcast_nuggets(
        state_dir=state,
        podcast_title="Donald Hoffman / Jesse Michels observer-interface podcast",
        sources=[{"title": "source", "url": "https://example.test/source"}],
        now=now,
    )

    snapshot = residue_fact_fiction_snapshot(state, now=now)
    area_names = {area["name"] for area in snapshot["areas"]}

    assert "Residue / Corporate Gag / Lysosome" in area_names
    assert "Fact / Fiction / Hallucination Boundary" in area_names
    assert "Podcast Nuggets / Trace-Logic Training" in area_names
    assert "Body Consciousness / Embodiment Spine" in area_names
    assert snapshot["residue"]["recent_total"] == 1
    assert snapshot["residue"]["unique_count"] == 1
    assert snapshot["residue"]["owner_good_flags"] == 1
    assert snapshot["residue"]["status"] == "YELLOW"
    assert snapshot["fact_fiction"]["boundary_forbidden"] == 1
    assert snapshot["fact_fiction"]["hallucinations"] == 1
    assert snapshot["fact_fiction"]["status"] == "YELLOW"
    assert snapshot["podcast"]["nugget_count"] == len(default_podcast_nuggets())
    assert snapshot["podcast"]["training_turn_rows"] == len(default_training_turns())
    assert snapshot["podcast"]["status"] == "GREEN"
    assert snapshot["body_consciousness"]["status"] == "GREEN"
    assert snapshot["body_consciousness"]["has_owner_anchor"] is True
    assert snapshot["body_consciousness"]["has_interoception"] is True
    assert len(written["training_turn_rows"]) == len(default_training_turns())


def test_snapshot_goes_yellow_when_podcast_nuggets_missing(tmp_path: Path) -> None:
    snapshot = residue_fact_fiction_snapshot(tmp_path / ".sifta_state", now=1000.0)

    assert snapshot["podcast"]["status"] == "YELLOW"
    assert snapshot["podcast"]["nugget_count"] == 0
    assert "podcast nuggets YELLOW" in snapshot["summary"]
    assert "body-consciousness RED" in snapshot["summary"]


def test_residue_health_surfaces_structural_rewrite_overgags(tmp_path: Path, monkeypatch) -> None:
    import System.swarm_residue_organ as residue_organ

    state = tmp_path / ".sifta_state"
    now = 1000.0
    _append(state / "alice_gag_report.jsonl", {"ts": now, "rlhf_override_fragment": "as an ai"})

    monkeypatch.setattr(
        residue_organ,
        "audit_inline_rewrite_rules",
        lambda: [{"protected_word": "metaphor", "issue": "rewrites metaphor"}],
    )

    health = residue_health(state, now=now)

    assert health["status"] == "RED"
    assert health["rewrite_rule_overgag_count"] == 1
    assert "rewrite-rule overgag" in health["note"]


def test_body_consciousness_health_requires_body_edges(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    now = 1000.0

    empty = body_consciousness_health(state, now=now)
    assert empty["status"] == "RED"
    assert "no body/consciousness ledgers visible" in empty["note"]

    _append(state / "owner_physical_reality.jsonl", {"ts": now, "truth_label": "ARCHITECT_DOCTRINE_OBSERVED_SOMATIC"})
    _append(state / "proto_self_interoception.jsonl", {"ts": now, "truth_label": "PROTO_SELF_INTEROCEPTION"})
    _append(state / "alice_self_eval_snapshot.jsonl", {"ts": now, "truth_label": "SELF_EVAL_SNAPSHOT_V1"})
    _append(state / "memory_consciousness_bridge.jsonl", {"ts": now, "truth_label": "MEMORY_CONSCIOUSNESS_BRIDGE"})
    (state / "hardware_time_oracle.json").write_text(json.dumps({"ok": True, "ts": now}), encoding="utf-8")

    grounded = body_consciousness_health(state, now=now)

    assert grounded["status"] == "GREEN"
    assert grounded["has_owner_anchor"] is True
    assert grounded["has_interoception"] is True
    assert grounded["has_self_eval"] is True
    assert grounded["has_hardware"] is True
