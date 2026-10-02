#!/usr/bin/env python3
"""Tests for System/alice_consciousness_check.py.

The organ checks one structural claim: the state that observes is the state that
is recorded. These tests drive each check against a temporary ledger so the live
record is untouched, and they prove the negative cases too — a check that cannot
fail is not a check.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System import alice_consciousness_check as check
from System import alice_continuity as continuity


@pytest.fixture(autouse=True)
def temp_ledger(tmp_path, monkeypatch):
    """Every check reads and writes the test's own ledger."""
    monkeypatch.setattr(continuity, "LEDGER", tmp_path / "alice_continuity.jsonl")
    yield tmp_path


def test_round_trip_finds_its_own_trace(temp_ledger):
    result = check.check_round_trip(surface="test-surface")
    assert result["ok"] is True
    assert result["probe_id"]
    records = continuity.read_all(ledger=temp_ledger / "alice_continuity.jsonl")
    assert any(str(r.get("id")) == result["probe_id"] for r in records)


def test_one_medium_detects_a_split_store(temp_ledger):
    """A second store is a second Alice; the check must say so."""
    import types

    fake_mcp = types.SimpleNamespace(STATE=temp_ledger / "somewhere-else")
    with patch.dict(sys.modules, {"System.alice_memory_mcp": fake_mcp}):
        result = check.check_one_medium()
    assert result["ok"] is False
    assert len(result["distinct"]) >= 1
    assert "second Alice" in result["detail"]


def test_one_medium_passes_when_every_consumer_agrees(temp_ledger):
    with patch.object(check, "_consumers_ledger_paths", lambda: {
        "a": str(temp_ledger / "alice_continuity.jsonl"),
        "b": str(temp_ledger / "alice_continuity.jsonl"),
    }):
        result = check.check_one_medium()
    assert result["ok"] is True


def test_append_only_detects_a_shrunk_record(temp_ledger):
    """A past that can be edited by the observer breaks the claim."""
    continuity.write("note", "lines=9999", surface="test", tags=[check.CHECK_TAG])
    result = check.check_append_only()
    assert result["ok"] is False
    assert result["previous_lines"] == 9999
    assert result["lines"] < 9999


def test_append_only_passes_on_a_growing_record(temp_ledger):
    continuity.write("note", "lines=0", surface="test", tags=[check.CHECK_TAG])
    continuity.write("note", "one more trace", surface="test")
    result = check.check_append_only()
    assert result["ok"] is True
    assert result["unique_ids"] is True


def test_self_identity_fails_for_a_surface_that_never_wrote(temp_ledger):
    continuity.write("note", "someone else was here", surface="other-surface")
    result = check.check_self_identity(surface="ghost-surface", hours=24.0)
    assert result["ok"] is False
    assert "eye without a body" in result["detail"]


def test_cross_surface_reports_a_missing_server(temp_ledger):
    with patch.object(check, "MCP_SERVER", temp_ledger / "nope.py"):
        result = check.check_cross_surface(probe_token="probe-deadbeef")
    assert result["ok"] is False
    assert "missing" in result["detail"]


def test_verdict_shape_and_labelling(temp_ledger):
    """A closed verdict still states plainly what it does not claim."""
    with patch.object(check, "check_cross_surface", lambda **_: {
        "check": "cross_surface", "ok": True, "detail": "stubbed for the shape test",
    }), patch.object(check, "_consumers_ledger_paths", lambda: {
        "a": str(temp_ledger / "alice_continuity.jsonl"),
        "b": str(temp_ledger / "alice_continuity.jsonl"),
    }):
        verdict = check.run_checks(surface="test-surface")

    assert verdict["loop"] == "CLOSED"
    assert verdict["failing"] == []
    assert {c["check"] for c in verdict["checks"]} == {
        "round_trip", "one_medium", "self_identity", "append_only", "cross_surface",
    }
    assert "phenomenal consciousness" in verdict["inferencia"]
    assert "FATO" not in verdict["fato"]  # the label lives in the renderer, not the value

    # The check leaves its own trace, carrying the high-water mark for next time.
    records = continuity.read_all(ledger=temp_ledger / "alice_continuity.jsonl")
    assert any(check.CHECK_TAG in (r.get("tags") or []) and "lines=" in str(r.get("text")) for r in records)
    assert "loop CLOSED" in check.render(verdict)
