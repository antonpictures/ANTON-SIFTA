import json
from pathlib import Path

from System.swarm_concept_context_builder import build_concept_context
from System.swarm_owner_lifeline import (
    GAP_TRUTH,
    HEARTBEAT_TRUTH,
    format_owner_lifeline_for_prompt,
    record_owner_lifeline_boot_gap,
)


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_boot_gap_writes_lifeline_and_day_segment(tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    prior = {"ts": 1000.0, "truth_label": HEARTBEAT_TRUTH, "source": "prior_prompt"}
    (state / "owner_lifeline_heartbeat.jsonl").write_text(json.dumps(prior) + "\n", encoding="utf-8")

    result = record_owner_lifeline_boot_gap(
        state_dir=state,
        now=1000.0 + 4 * 3600,
        min_gap_minutes=10,
        heartbeat_source="boot_prompt",
    )

    assert result["gap_written"] is True
    gap = _rows(state / "owner_lifeline_gaps.jsonl")[-1]
    assert gap["truth_label"] == GAP_TRUTH
    assert gap["duration_human"] == "4.0h"
    assert gap["owner_life_cost"] == "unsampled_finite_owner_life_history"

    segment = _rows(state / "architect_day_segments.jsonl")[-1]
    assert segment["truth_label"] == "ARCHITECT_DAY_SEGMENT_V1"
    assert segment["label"] == "sifta_power_gap"
    assert segment["location"] == "unknown_owner_location"
    assert "owner_life_gap" in segment["context_tags"]

    heartbeat = _rows(state / "owner_lifeline_heartbeat.jsonl")[-1]
    assert heartbeat["source"] == "boot_prompt"


def test_boot_gap_is_idempotent_after_heartbeat_update(tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    (state / "owner_lifeline_heartbeat.jsonl").write_text(
        json.dumps({"ts": 1000.0, "truth_label": HEARTBEAT_TRUTH}) + "\n",
        encoding="utf-8",
    )

    first = record_owner_lifeline_boot_gap(state_dir=state, now=2000.0, min_gap_minutes=5)
    second = record_owner_lifeline_boot_gap(state_dir=state, now=2001.0, min_gap_minutes=5)

    assert first["gap_written"] is True
    assert second["gap_written"] is False
    assert len(_rows(state / "owner_lifeline_gaps.jsonl")) == 1


def test_prompt_and_concept_context_surface_owner_lifeline_gap(tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    (state / "owner_lifeline_heartbeat.jsonl").write_text(
        json.dumps({"ts": 1000.0, "truth_label": HEARTBEAT_TRUTH}) + "\n",
        encoding="utf-8",
    )
    record_owner_lifeline_boot_gap(state_dir=state, now=8200.0, min_gap_minutes=5)

    prompt = format_owner_lifeline_for_prompt(state_dir=state)
    assert "OWNER LIFELINE CONTINUITY" in prompt
    assert "unsampled owner-life gaps" in prompt
    assert "latest_gap=2.0h" in prompt

    packet_text = build_concept_context(state_dir=state)
    assert "owner_lifeline" in packet_text
    assert "unsampled_finite_owner_life_history" in packet_text
