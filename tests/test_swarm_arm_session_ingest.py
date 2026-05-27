#!/usr/bin/env python3
"""Tests for swarm_arm_session_ingest — Round 50 / Task #103.

Arm-session ingestion into the memory card. Verifies:
  - empty/missing state dir → empty block
  - each ledger source produces a recognizable bullet
  - newest-first ordering
  - deduplication across overlapping ledgers
  - max_n cap honored
  - integration with swarm_memory_card.compose_memory_card +
    format_for_prompt — the new arm_session_block appears
  - real .sifta_state ledgers are READ-ONLY (delta=0)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from System import swarm_arm_session_ingest as ingest
from System import swarm_memory_card as card_mod


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def test_empty_state_dir_returns_empty_block(tmp_path):
    assert ingest.fetch_arm_session_block(tmp_path, now_ts=100.0) == ""


def test_arm_receipt_appears_in_block(tmp_path):
    _write_jsonl(tmp_path / "agent_arm_receipts.jsonl", [
        {"ts": 95.0, "receipt_id": "arm-aaa",
         "arm_id": "codex", "display_name": "Codex CLI",
         "actual_model": "gpt-5", "truth_label": "ARM_RUN_RECEIPT_V2",
         "summary": "Wrote module X"}
    ])
    block = ingest.fetch_arm_session_block(tmp_path, now_ts=100.0)
    assert "ARM SESSIONS" in block
    assert "codex" in block.lower()
    assert "Codex CLI" in block or "codex" in block.lower()
    assert "model=gpt-5" in block
    assert "truth=ARM_RUN_RECEIPT_V2" in block
    assert "Wrote module X" in block


def test_arm_briefing_appears_in_block(tmp_path):
    _write_jsonl(tmp_path / "alice_agent_arm_briefings.jsonl", [
        {"ts": 95.0, "arm_id": "claude",
         "model": "claude-opus-4-7",
         "briefing_id": "brf-001",
         "summary": "Refactor sensor module"}
    ])
    block = ingest.fetch_arm_session_block(tmp_path, now_ts=100.0)
    assert "[arm_briefing]" in block
    assert "claude" in block.lower()
    assert "Refactor sensor module" in block


def test_arm_async_evidence_with_status(tmp_path):
    _write_jsonl(tmp_path / "agent_arm_async_evidence.jsonl", [
        {"ts": 95.0, "arm_id": "grok", "model": "grok-4.3",
         "status": "COMPLETED", "job_id": "job-555",
         "note": "Tests passed"}
    ])
    block = ingest.fetch_arm_session_block(tmp_path, now_ts=100.0)
    assert "[arm_async_evidence]" in block
    assert "truth=COMPLETED" in block
    assert "Tests passed" in block


def test_grok_result_from_matrix_trace_appears(tmp_path):
    _write_jsonl(tmp_path / "matrix_terminal_process_trace.jsonl", [
        {"ts": 95.0, "event": "GROK_RESULT", "arm": "grok_pty",
         "model": "grok", "text": "All systems nominal."},
        # Non-result events should NOT appear.
        {"ts": 96.0, "event": "GROK_KEYSTROKE", "arm": "grok_pty",
         "text": "ls\n"},
    ])
    block = ingest.fetch_arm_session_block(tmp_path, now_ts=100.0)
    assert "[grok_result]" in block
    assert "All systems nominal." in block
    assert "GROK_KEYSTROKE" not in block
    assert "[grok_keystroke]" not in block


def test_old_events_excluded(tmp_path):
    _write_jsonl(tmp_path / "agent_arm_receipts.jsonl", [
        {"ts": 1.0, "receipt_id": "old", "arm_id": "codex",
         "summary": "ancient"},
        {"ts": 99.0, "receipt_id": "new", "arm_id": "codex",
         "summary": "recent"},
    ])
    block = ingest.fetch_arm_session_block(tmp_path, max_age_s=10.0, now_ts=100.0)
    assert "recent" in block
    assert "ancient" not in block


def test_events_newest_first(tmp_path):
    _write_jsonl(tmp_path / "agent_arm_receipts.jsonl", [
        {"ts": 90.0, "receipt_id": "earlier", "arm_id": "codex",
         "summary": "earlier_event"},
        {"ts": 99.0, "receipt_id": "later", "arm_id": "codex",
         "summary": "later_event"},
    ])
    block = ingest.fetch_arm_session_block(tmp_path, now_ts=100.0)
    later_idx = block.find("later_event")
    earlier_idx = block.find("earlier_event")
    assert later_idx >= 0 and earlier_idx >= 0
    assert later_idx < earlier_idx


def test_deduplication_across_ledgers(tmp_path):
    """Same (kind, arm, receipt_id, ts) across overlapping sources collapses to one."""
    common = {"ts": 95.0, "arm_id": "codex", "receipt_id": "dup-rid",
              "summary": "deduped"}
    _write_jsonl(tmp_path / "agent_arm_receipts.jsonl", [common])
    # Duplicate exact same row in a second source path doesn't actually
    # exist for arm_receipts (each source has its own extractor), but
    # writing twice in the SAME ledger should still dedupe via the dedup
    # key. Validate that.
    _write_jsonl(tmp_path / "agent_arm_receipts.jsonl", [common, common])
    block = ingest.fetch_arm_session_block(tmp_path, now_ts=100.0)
    # The substring "deduped" appears once, not twice.
    assert block.count("deduped") == 1


def test_max_n_cap(tmp_path):
    _write_jsonl(tmp_path / "agent_arm_receipts.jsonl", [
        {"ts": 90.0 + i, "receipt_id": f"r{i}", "arm_id": "codex",
         "summary": f"event_{i}"}
        for i in range(20)
    ])
    block = ingest.fetch_arm_session_block(tmp_path, max_n=4, now_ts=100.0)
    # Top 4 newest only
    assert "event_19" in block
    assert "event_18" in block
    assert "event_17" in block
    assert "event_16" in block
    assert "event_5" not in block
    assert "event_0" not in block


def test_malformed_rows_skipped(tmp_path):
    p = tmp_path / "agent_arm_receipts.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w") as fh:
        fh.write("not json\n")
        fh.write(json.dumps({"ts": 95.0, "receipt_id": "good", "arm_id": "codex",
                             "summary": "valid_row"}) + "\n")
        fh.write("{partial: \n")
    block = ingest.fetch_arm_session_block(tmp_path, now_ts=100.0)
    assert "valid_row" in block


# ─── Integration with swarm_memory_card ─────────────────────────────────────


def test_compose_memory_card_includes_arm_session_block(tmp_path):
    # Use real-time-ish timestamp so the 24h default window includes it.
    import time as _time
    now_ts = _time.time()
    _write_jsonl(tmp_path / "agent_arm_receipts.jsonl", [
        {"ts": now_ts - 60.0, "receipt_id": "arm-int", "arm_id": "codex",
         "actual_model": "gpt-5", "summary": "integration_proof"}
    ])
    card = card_mod.compose_memory_card(
        tmp_path,
        token_budget=2000,
        now=now_ts,
        user_text="what did codex do",
    )
    assert "arm_session_block" in card.__dataclass_fields__
    assert card.arm_session_block != ""
    assert "integration_proof" in card.arm_session_block


def test_format_for_prompt_renders_arm_section(tmp_path):
    import time as _time
    now_ts = _time.time()
    _write_jsonl(tmp_path / "agent_arm_receipts.jsonl", [
        {"ts": now_ts - 60.0, "receipt_id": "arm-fmt", "arm_id": "codex",
         "summary": "format_for_prompt_proof"}
    ])
    card = card_mod.compose_memory_card(tmp_path, now=now_ts)
    rendered = card_mod.format_for_prompt(card)
    assert "ARM SESSIONS" in rendered
    assert "format_for_prompt_proof" in rendered


def test_real_ledgers_untouched(tmp_path):
    """Hard invariant: arm-session ingest is READ-ONLY."""
    state = Path(".sifta_state")
    watch = [
        state / "agent_arm_receipts.jsonl",
        state / "alice_agent_arm_briefings.jsonl",
        state / "agent_arm_async_evidence.jsonl",
        state / "matrix_terminal_process_trace.jsonl",
        state / "work_receipts.jsonl",
    ]
    before = {str(p): (p.stat().st_size if p.exists() else 0) for p in watch}
    _ = ingest.fetch_arm_session_block(state, max_age_s=60.0)
    after = {str(p): (p.stat().st_size if p.exists() else 0) for p in watch}
    for k in before:
        assert before[k] == after[k], (
            f"arm-session ingest mutated {k}: {before[k]} -> {after[k]}"
        )
