#!/usr/bin/env python3
"""Tests for app-limb usage history (felt limbs, 2026-05-30)."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System import swarm_app_limb_history as limb


def test_record_and_usage_counts(tmp_path):
    limb.record_limb_event("Alice Browser", "open", now=1.0, state_dir=tmp_path)
    limb.record_limb_event("Alice Browser", "focus", now=2.0, state_dir=tmp_path)
    limb.record_limb_event("Alice Browser", "close", now=3.0, state_dir=tmp_path)
    h = limb.usage_history(state_dir=tmp_path)
    assert h["Alice Browser"]["extend_count"] == 2  # open + focus
    assert h["Alice Browser"]["withdraw_count"] == 1
    assert h["Alice Browser"]["last_action"] == "close"


def test_currently_open_excludes_closed(tmp_path):
    limb.record_limb_event("Music", "open", now=1.0, state_dir=tmp_path)
    limb.record_limb_event("Alice Browser", "open", now=2.0, state_dir=tmp_path)
    limb.record_limb_event("Music", "close", now=3.0, state_dir=tmp_path)
    open_now = limb.currently_open(state_dir=tmp_path)
    assert "Alice Browser" in open_now
    assert "Music" not in open_now


def test_merges_app_focus_ledger(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    (sd / "app_focus.jsonl").write_text(json.dumps({"app": "What Alice Sees", "ts": 5}) + "\n")
    h = limb.usage_history(state_dir=tmp_path)
    assert "What Alice Sees" in h
    assert h["What Alice Sees"]["last_action"] == "focus"


def test_accepts_state_dir_or_repo_root(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    limb.record_limb_event("Alice Browser", "open", now=1.0, state_dir=sd)

    assert "Alice Browser" in limb.usage_history(state_dir=sd)
    assert "Alice Browser" in limb.usage_history(state_dir=tmp_path)


def test_felt_limbs_summary_first_person_ready(tmp_path):
    limb.record_limb_event("Alice Browser", "open", now=1.0, state_dir=tmp_path)
    limb.record_limb_event("Alice Browser", "focus", now=2.0, state_dir=tmp_path)
    s = limb.felt_limbs_summary(state_dir=tmp_path)
    assert "Alice Browser" in s and "limb" in s.lower()


def test_empty_history_is_honest(tmp_path):
    assert "No limb history" in limb.felt_limbs_summary(state_dir=tmp_path)
    assert limb.currently_open(state_dir=tmp_path) == []


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
