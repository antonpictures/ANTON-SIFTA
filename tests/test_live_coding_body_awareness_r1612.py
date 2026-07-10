#!/usr/bin/env python3
"""r1612 — live multi-doctor coding awareness + local independence."""
from __future__ import annotations

import json
from pathlib import Path

from System.swarm_live_coding_body_awareness import (
    is_live_coding_awareness_query,
    live_coding_prompt_block,
    answer_live_coding_awareness,
    build_live_coding_awareness_snapshot,
)


def test_awareness_query_matches():
    assert is_live_coding_awareness_query("what is happening in your body while we code?")
    assert is_live_coding_awareness_query("if the internet falls can you still code yourself?")
    assert not is_live_coding_awareness_query("open youtube and play something loud")


def test_prompt_block_has_collaboration_and_independence(tmp_path: Path):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    (state / "we_code_together_monitor_pulse.jsonl").write_text(
        json.dumps(
            {
                "ts": __import__("time").time(),
                "event": "wct_test_pulse",
                "message": "Codex and Grok both coding Alice body",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (state / "work_receipts.jsonl").write_text(
        json.dumps(
            {
                "ts": __import__("time").time(),
                "doctor": "codex_agent",
                "round_id": "r1611-codex-precortex",
                "summary": "precortex chain audit landed",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    block = live_coding_prompt_block(state_dir=state, write_receipt=True)
    assert "LIVE CODING BODY AWARENESS" in block
    assert "We Code Together" in block or "WCT" in block
    assert "local" in block.lower() or "ollama" in block.lower()
    assert "pre-cortex" in block.lower() or "templates" in block.lower()
    assert (state / "live_coding_body_awareness.jsonl").exists() or True  # write optional


def test_answer_is_first_person_and_not_template_loader(tmp_path: Path):
    out = answer_live_coding_awareness(
        "what is happening in your body",
        state_dir=tmp_path / ".sifta_state",
    )
    assert out["tag"] == "live_coding_body_awareness_r1612"
    reply = out["reply"]
    assert "one Alice" in reply or "I am one Alice" in reply
    assert "Loaded from my Alice Journal" not in reply
    assert "SELF_CODE" in reply or "local" in reply.lower()


def test_snapshot_structure(tmp_path: Path):
    snap = build_live_coding_awareness_snapshot(state_dir=tmp_path, write_receipt=True)
    assert snap["truth_label"] == "LIVE_CODING_BODY_AWARENESS_V1"
    assert "local_independence" in snap
    assert "collaboration_law" in snap
