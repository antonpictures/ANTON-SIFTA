from __future__ import annotations

import json
from pathlib import Path

from System.swarm_engram_feedback_loop import (
    ENGRAM_FEEDBACK_LEDGER,
    MEMORY_FITNESS_FILE,
    format_live_snapshot,
    live_memory_snapshot,
    process_owner_turn,
    prune_dead_engrams,
    summary_for_prompt,
)


def _write_active_engrams(state: Path, *rules: str) -> None:
    state.mkdir(parents=True, exist_ok=True)
    (state / "active_engrams.json").write_text(
        json.dumps({"engrams": list(rules)}),
        encoding="utf-8",
    )


def test_owner_feedback_reinforces_and_decays_matching_engram(tmp_path: Path) -> None:
    rule = "learning gap feedback memory changes behavior"
    _write_active_engrams(tmp_path, rule)

    positive = process_owner_turn(
        "yes good learning gap feedback memory",
        state_dir=tmp_path,
    )
    negative = process_owner_turn(
        "wrong bad learning gap feedback memory",
        state_dir=tmp_path,
    )

    fitness = json.loads((tmp_path / MEMORY_FITNESS_FILE).read_text(encoding="utf-8"))
    trace = next(iter(fitness["traces"].values()))

    assert positive["owner_signal"] == 1.0
    assert positive["actions"][0]["action"] == "reinforce"
    assert negative["owner_signal"] == -1.0
    assert negative["actions"][0]["action"] == "decay"
    assert trace["reinforcements"] == 1
    assert trace["decays"] == 1
    assert (tmp_path / ENGRAM_FEEDBACK_LEDGER).exists()


def test_prune_dead_engrams_removes_low_fitness_trace(tmp_path: Path) -> None:
    rule = "learning gap feedback memory changes behavior"
    _write_active_engrams(tmp_path, rule)

    process_owner_turn(
        "wrong bad learning gap feedback memory",
        state_dir=tmp_path,
        decay_amount=1.0,
    )
    result = prune_dead_engrams(state_dir=tmp_path, min_fitness=0.1)

    fitness = json.loads((tmp_path / MEMORY_FITNESS_FILE).read_text(encoding="utf-8"))
    assert result["pruned"] == 1
    assert fitness["traces"] == {}


def test_prune_preserves_unrelated_memory_fitness_overlay(tmp_path: Path) -> None:
    (tmp_path / MEMORY_FITNESS_FILE).write_text(
        json.dumps(
            {
                "traces": {
                    "other-organ": {
                        "fitness": 0.0,
                        "overlay": "memory_fitness_acmf_v1",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    result = prune_dead_engrams(state_dir=tmp_path, min_fitness=0.1)

    fitness = json.loads((tmp_path / MEMORY_FITNESS_FILE).read_text(encoding="utf-8"))
    assert result["pruned"] == 0
    assert "other-organ" in fitness["traces"]


def test_live_snapshot_and_formatter_show_receipts(tmp_path: Path) -> None:
    _write_active_engrams(tmp_path, "owner approval reinforces engram memory")
    process_owner_turn(
        "yes correct owner approval reinforces engram memory",
        state_dir=tmp_path,
    )

    snap = live_memory_snapshot(state_dir=tmp_path, limit=3)
    text = format_live_snapshot(snap)

    assert snap["truth_label"] == "ENGRAM_LIVE_MEMORY_SNAPSHOT"
    assert snap["trace_count"] == 1
    assert snap["recent_receipts"]
    assert "ENGRAM LIVE MEMORY SNAPSHOT" in text
    assert "owner approval reinforces" in text
    assert "Engram feedback:" in summary_for_prompt(state_dir=tmp_path)


def test_live_snapshot_filters_non_engram_fitness_rows(tmp_path: Path) -> None:
    (tmp_path / MEMORY_FITNESS_FILE).write_text(
        json.dumps({"traces": {"other-organ": {"fitness": 1.1}}}),
        encoding="utf-8",
    )

    snap = live_memory_snapshot(state_dir=tmp_path)

    assert snap["trace_count"] == 0
    assert snap["top_traces"] == []


def test_talk_owner_turn_wires_engram_feedback_to_log_turn() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "Applications"
        / "sifta_talk_to_alice_widget.py"
    ).read_text(encoding="utf-8", errors="replace")

    assert "from System.swarm_engram_feedback_loop import process_owner_turn" in source
    assert 'if role == "user":' in source
    assert '"actions_taken": len(_engram_fb.get("actions") or [])' in source
    assert '"receipt_ledger": "engram_feedback_receipts.jsonl"' in source
