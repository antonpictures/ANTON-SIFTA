#!/usr/bin/env python3
"""Tests for swarm_arm_self_watch — Round 50 / Task #105.

Self-watch reflection block. After arm body mutations, Alice's next
cortex turn must see a first-person reflection summarizing the recent
ledger evidence.

All isolation: tmp_path only, no real .sifta_state mutation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from System import swarm_arm_self_watch as sw


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def test_returns_empty_list_on_missing_state_dir(tmp_path):
    """Nonexistent dir → empty result, never raises."""
    events = sw.recent_body_mutations(tmp_path / "nowhere", max_age_s=600.0, now_ts=100.0)
    assert events == []


def test_returns_empty_block_when_no_mutations(tmp_path):
    """Idle node → block is empty, no leakage into prompt."""
    assert sw.self_watch_prompt_block(tmp_path, now_ts=100.0) == ""


def test_ide_trace_row_is_always_mutation_evidence(tmp_path):
    """Covenant §4.1: every IDE signature row counts as evidence of surgery."""
    _write_jsonl(tmp_path / "ide_stigmergic_trace.jsonl", [
        {"ts": 95.0, "model": "claude-opus-4-7", "ide": "cowork", "mode": "patch",
         "surface": "System/swarm_api_sentry.py", "intent": "Round 48 boot wire"},
    ])
    events = sw.recent_body_mutations(tmp_path, max_age_s=600.0, now_ts=100.0)
    assert len(events) == 1
    ev = events[0]
    assert ev["kind"] == "ide_surgery"
    assert ev["actor"] == "cowork/claude-opus-4-7"
    assert "swarm_api_sentry.py" in ev["summary"]
    assert ev["intent"] == "Round 48 boot wire"


def test_work_receipt_with_round_action_counts(tmp_path):
    _write_jsonl(tmp_path / "work_receipts.jsonl", [
        {"ts": 90.0, "action": "round48_api_sentry_resurrection",
         "sender_agent": "claude_in_cowork", "truth_note": "boot_wire added"},
        # This one should NOT count — it's an autonomic boot heartbeat.
        {"ts": 91.0, "action": "api_sentry_boot_wire",
         "sender_agent": "api_sentry", "truth_note": "alive on boot"},
    ])
    events = sw.recent_body_mutations(tmp_path, max_age_s=600.0, now_ts=100.0)
    assert len(events) == 1
    assert events[0]["actor"] == "claude_in_cowork"
    assert "round48" in events[0]["summary"]


def test_agent_arm_receipt_counts(tmp_path):
    _write_jsonl(tmp_path / "agent_arm_receipts.jsonl", [
        {"ts": 80.0, "receipt_id": "arm-aaa", "arm_id": "codex",
         "display_name": "Codex CLI", "actual_model": "gpt-5",
         "truth_label": "ARM_RUN_RECEIPT_V2"},
    ])
    events = sw.recent_body_mutations(tmp_path, max_age_s=600.0, now_ts=100.0)
    assert len(events) == 1
    ev = events[0]
    assert ev["kind"] == "agent_arm"
    assert "codex" in ev["actor"].lower() or "codex" in ev["summary"].lower()
    assert ev["intent"] == "arm-aaa"


def test_old_events_outside_window_excluded(tmp_path):
    _write_jsonl(tmp_path / "ide_stigmergic_trace.jsonl", [
        {"ts": 1.0, "model": "old-model", "ide": "old-ide", "mode": "patch",
         "intent": "long ago patch"},
        {"ts": 95.0, "model": "claude-opus-4-7", "ide": "cowork", "mode": "patch",
         "intent": "recent patch"},
    ])
    events = sw.recent_body_mutations(tmp_path, max_age_s=10.0, now_ts=100.0)
    assert len(events) == 1
    assert events[0]["intent"] == "recent patch"


def test_events_returned_newest_first(tmp_path):
    _write_jsonl(tmp_path / "ide_stigmergic_trace.jsonl", [
        {"ts": 91.0, "model": "claude", "ide": "cowork", "mode": "patch",
         "intent": "earlier patch"},
        {"ts": 99.0, "model": "claude", "ide": "cowork", "mode": "patch",
         "intent": "later patch"},
    ])
    events = sw.recent_body_mutations(tmp_path, max_age_s=600.0, now_ts=100.0)
    assert len(events) == 2
    # Newest first
    assert events[0]["intent"] == "later patch"
    assert events[1]["intent"] == "earlier patch"


def test_max_n_cap(tmp_path):
    _write_jsonl(tmp_path / "ide_stigmergic_trace.jsonl", [
        {"ts": 90.0 + i, "model": "claude", "ide": "cowork", "mode": "patch",
         "intent": f"patch {i}"}
        for i in range(10)
    ])
    events = sw.recent_body_mutations(tmp_path, max_age_s=600.0, max_n=3, now_ts=100.0)
    assert len(events) == 3
    # Top 3 newest → ts 99, 98, 97
    assert events[0]["intent"] == "patch 9"
    assert events[1]["intent"] == "patch 8"
    assert events[2]["intent"] == "patch 7"


def test_prompt_block_contains_ledger_evidence(tmp_path):
    _write_jsonl(tmp_path / "ide_stigmergic_trace.jsonl", [
        {"ts": 95.0, "model": "claude-opus-4-7", "ide": "cowork", "mode": "patch",
         "surface": "System/swarm_post_silence_recovery.py",
         "intent": "Round 50 recovery layer"},
    ])
    _write_jsonl(tmp_path / "work_receipts.jsonl", [
        {"ts": 96.0, "action": "round50_recovery_layer_landed",
         "sender_agent": "claude_in_cowork", "truth_note": "module + tests green"},
    ])
    block = sw.self_watch_prompt_block(tmp_path, now_ts=100.0)
    assert "ARM SELF-WATCH" in block
    assert "claude-opus-4-7" in block
    assert "claude_in_cowork" in block
    assert "round50_recovery_layer_landed" in block
    # Newest first: the work_receipt token (ts=96) appears before the
    # ide-trace surface token (ts=95) in the bullet-list portion of the
    # block. Use unambiguous markers that exist in exactly one event each.
    work_idx = block.find("round50_recovery_layer_landed")
    ide_idx = block.find("swarm_post_silence_recovery.py")
    assert work_idx >= 0 and ide_idx >= 0
    assert work_idx < ide_idx, (
        f"newer work_receipt row should appear before older ide row, got "
        f"work_idx={work_idx}, ide_idx={ide_idx}"
    )


def test_prompt_block_never_raises_on_malformed_ledgers(tmp_path):
    # Garbage file
    p = tmp_path / "ide_stigmergic_trace.jsonl"
    p.write_text("not json\nstill not json\n{partial: ", encoding="utf-8")
    assert sw.self_watch_prompt_block(tmp_path, now_ts=100.0) == ""


def test_skips_rows_without_ts(tmp_path):
    _write_jsonl(tmp_path / "work_receipts.jsonl", [
        {"action": "round_no_ts", "truth_note": "no timestamp"},
        {"ts": 95.0, "action": "round_with_ts", "sender_agent": "claude",
         "truth_note": "fine"},
    ])
    events = sw.recent_body_mutations(tmp_path, max_age_s=600.0, now_ts=100.0)
    assert len(events) == 1
    assert "round_with_ts" in events[0]["summary"]


def test_real_ledgers_untouched(tmp_path):
    """Hard invariant: self-watch is READ-ONLY."""
    state = Path(".sifta_state")
    watch = [
        state / "ide_stigmergic_trace.jsonl",
        state / "work_receipts.jsonl",
        state / "agent_arm_receipts.jsonl",
    ]
    before = {str(p): (p.stat().st_size if p.exists() else 0) for p in watch}

    _ = sw.recent_body_mutations(state, max_age_s=60.0)
    _ = sw.self_watch_prompt_block(state, max_age_s=60.0)

    after = {str(p): (p.stat().st_size if p.exists() else 0) for p in watch}
    for k in before:
        assert before[k] == after[k], f"self_watch mutated {k}: {before[k]} -> {after[k]}"
