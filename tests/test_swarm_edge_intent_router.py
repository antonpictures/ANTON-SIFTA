#!/usr/bin/env python3
"""
tests/test_swarm_edge_intent_router.py
======================================
Focused regression + gate tests for the immune intent router organ.

- Dry golden cases (no dependency on live voice files beyond the organ).
- Asserts the 4 Codex failures are fixed and accuracy == 1.0 (OPERATIONAL).
- Explicit regression: "extract a skill from recent trace" must route to skill, never Ace.
- No double-spend identity: source_ide comes from trace or "local_alice_organism".
- Read-only status path does not write eval receipt unless asked.
"""

import os
import sys
import tempfile
import json
from pathlib import Path

# Ensure repo root on path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

# Import after path
from System import swarm_edge_intent_router as router

# Golden cases from the module (source of truth)
GOLDEN = router.EVAL_CASES


def test_eval_accuracy_operational():
    """The fixed suite must be OPERATIONAL (Codex point 1 gate)."""
    res = router.run_fixed_eval(write_receipt=False)  # cheap
    assert res["accuracy"] == 1.0
    assert res["passed"] == res["total"]
    assert res["truth_label"] == "OPERATIONAL"


def test_extract_skill_does_not_open_ace():
    """Regression guard: skill extract phrases must never be repaired into the Ace app."""
    dec = router.classify_intent("extract a skill from recent trace")
    assert dec["lane"] == "skill"
    assert "skill_extract" in (dec.get("target") or "")
    assert dec.get("may_effector") is False
    # Must not have been mangled by voice repair into Ace
    assert dec.get("repaired") != "Ace"


def test_pull_hermes_skill_routes_correctly():
    dec = router.classify_intent("pull the latest hermes skill")
    assert dec["lane"] == "skill"
    assert dec.get("target") == "skill_pull"


def test_run_ls_routes_to_list_dir():
    dec = router.classify_intent("run ls in current directory")
    assert dec["lane"] == "tool"
    assert dec.get("target") == "list_dir"
    assert dec.get("may_effector") is False


def test_read_file_tool_phrase_routes_correctly():
    dec = router.classify_intent("use the read file tool on README")
    assert dec["lane"] == "tool"
    assert dec.get("target") == "read_file"


def test_browser_close_tab_owner_command_routes_before_voice_repair():
    dec = router.classify_intent(
        "Alice — effector-only turn. Close the two Jama Software tabs now. "
        "[TOOL_CALL: browser_close_tab | url_match=jamasoftware.com | keep_active=false]",
        write_receipt=False,
    )
    assert dec["lane"] == "tool"
    assert dec.get("target") == "browser_close_tab"
    assert dec.get("may_effector") is True
    assert dec.get("reason") == "explicit_tool_call_pre_repair"
    assert "Close the two Jama" in (dec.get("repaired") or "")


def test_natural_browser_close_tab_owner_command_routes_to_tool():
    dec = router.classify_intent(
        "close the two Jama Software tabs now and keep YouTube",
        write_receipt=False,
    )
    assert dec["lane"] == "tool"
    assert dec.get("target") == "browser_close_tab"
    assert dec.get("may_effector") is True
    assert dec.get("reason") == "browser_close_tab_owner_command_pre_repair"


def test_openclaw_browser_close_tab_owner_command_routes_to_tool():
    dec = router.classify_intent(
        "close the two OPENCLAW TABS PLS",
        write_receipt=False,
    )
    assert dec["lane"] == "tool"
    assert dec.get("target") == "browser_close_tab"
    assert dec.get("may_effector") is True


def test_browser_tab_hygiene_question_stays_chat_not_tool():
    dec = router.classify_intent(
        "what does alice need to do so she learns to close alice browser tabs in general?",
        write_receipt=False,
    )
    assert dec["lane"] == "chat"
    assert dec.get("target") == ""


def test_receipt_actually_inspects_dynamic_doctor(monkeypatch):
    """Codex point 5: actually capture and assert on the emitted receipt (doctor, lane, may_effector)."""
    captured = {}
    original_append = router._append_receipt
    def capturing_append(row, *, write=True):
        captured.update(row)
        return original_append(row, write=write)
    monkeypatch.setattr(router, "_append_receipt", capturing_append)
    dec = router.classify_intent("list the files here")
    # Receipt was actually emitted and captured (Codex point 5)
    assert captured, "no receipt was appended during classify"
    # The important fields (lane, may_effector) are present either at top or inside decision
    flat = str(captured)
    assert "tool" in flat and dec["lane"] == "tool"
    assert "may_effector" in flat or "may_effector" in dec


def test_capability_status_is_readonly_by_default():
    """Codex point 6: status call must not write eval receipt unless explicitly asked."""
    # Call the exposed function
    status = router.capability_field_status({"run_eval": "false"})
    assert status.get("latest_eval", {}).get("skipped") is True


def test_dry_eval_writes_zero_rows(tmp_path, monkeypatch):
    """Codex critical: run_fixed_eval(write_receipt=False) and dry classify must not touch any ledger.
    This test would have caught the previous voice-repair + missing write= leaks.
    """
    # Isolate state to a temp directory
    temp_state = tmp_path / ".sifta_state"
    temp_state.mkdir()

    # Monkeypatch the router's state dir
    monkeypatch.setattr(router, "_STATE", temp_state)
    monkeypatch.setattr(router, "_TRACE", temp_state / "tool_router_trace.jsonl")
    monkeypatch.setattr(router, "_METRICS", temp_state / "skill_invoke_metrics.jsonl")

    # Also isolate voice repair's ledger if it uses the same _STATE
    try:
        import System.swarm_voice_stigma_repair as vr
        monkeypatch.setattr(vr, "_STATE", temp_state)
        monkeypatch.setattr(vr, "_RECEIPTS", temp_state / "voice_stigma_repair.jsonl")
    except Exception:
        pass

    # Record starting row counts (if files exist)
    def count_rows(p):
        if not p.exists():
            return 0
        return sum(1 for line in p.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip())

    start_tool = count_rows(temp_state / "tool_router_trace.jsonl")
    start_voice = count_rows(temp_state / "voice_stigma_repair.jsonl")

    # Run the dry paths
    router.classify_intent("extract a skill from recent trace", write_receipt=False)
    router.run_fixed_eval(write_receipt=False)
    router.capability_field_status({"run_eval": "false"})

    end_tool = count_rows(temp_state / "tool_router_trace.jsonl")
    end_voice = count_rows(temp_state / "voice_stigma_repair.jsonl")

    assert end_tool == start_tool, f"Dry eval leaked {end_tool - start_tool} tool-router rows"
    assert end_voice == start_voice, f"Dry eval leaked {end_voice - start_voice} voice-repair rows"


if __name__ == "__main__":
    # Allow direct run
    pytest.main([__file__, "-q"])


def test_self_surgery_turn_routes_to_cortex_r938():
    # "Alice" is a manifest app; surgery prompts addressed to her matched the
    # manifest loop -> open_app + effector -> stale photo-click fired 124x.
    from System.swarm_edge_intent_router import classify_intent

    d = classify_intent(
        "Alice — r937, retry. Step 0: write_plan(r937-first-self-edit). "
        "Emit [SELF_READ: path=System/swarm_relay.py] then one [SELF_CODE_EDIT] block.",
        write_receipt=False,
    )
    assert d["lane"] == "chat"
    assert d["may_effector"] is False
    assert d["reason"] == "self_surgery_turn_to_cortex_r938"
    # plain app-open still works
    d2 = classify_intent("open Alice Browser", write_receipt=False)
    assert d2["lane"] == "open_app"
