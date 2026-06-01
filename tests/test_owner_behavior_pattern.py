#!/usr/bin/env python3
"""Tests for the owner behaviour-pattern deposit (r251).

Closes the r249 open item "owner carbon-body: only LOGGING is live — the support
nudge from logged cigarettes is not yet wired into the diary/optimization loop".
record_owner_behavior_pattern() now persists a deduped co-regulation pheromone row.
"""
import json
import time
from pathlib import Path

from System.swarm_owner_carbon_body_data import (
    record_owner_behavior_pattern,
    BEHAVIOR_PATTERN_TRUTH_LABEL,
)


def _write_events(state_root: Path, rows):
    sdir = state_root / ".sifta_state"
    sdir.mkdir(parents=True, exist_ok=True)
    with (sdir / "owner_body_events.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return sdir


def test_records_cigarette_pattern(tmp_path):
    now = time.time()
    rows = [
        {"ts": now - 300, "event_type": "cigarette_lit", "note": "George lit a cigarette"},
        {"ts": now - 200, "event_type": "cigarette_lit", "note": "another cigarette"},
        {"ts": now - 100, "event_type": "intention", "note": "wants to reduce cigarettes"},
    ]
    sdir = _write_events(tmp_path, rows)
    out = record_owner_behavior_pattern(state_dir=sdir)
    assert out is not None
    assert out["cigarette_count"] == 2
    assert out["intention_to_reduce"] is True
    assert out["truth_label"] == BEHAVIOR_PATTERN_TRUTH_LABEL
    assert out["support_posture"]
    assert "nag" in out["support_posture"].lower()  # non-nagging posture is explicit
    persisted = (sdir / "owner_behavior_patterns.jsonl").read_text().strip().splitlines()
    assert len(persisted) == 1
    assert json.loads(persisted[0])["cigarette_count"] == 2


def test_dedupe_same_count_within_window(tmp_path):
    now = time.time()
    rows = [{"ts": now - 60, "event_type": "cigarette_lit", "note": "cigarette"}]
    sdir = _write_events(tmp_path, rows)
    first = record_owner_behavior_pattern(state_dir=sdir)
    assert first is not None
    second = record_owner_behavior_pattern(state_dir=sdir)
    assert second is None  # same count within dedupe window -> no spam
    persisted = (sdir / "owner_behavior_patterns.jsonl").read_text().strip().splitlines()
    assert len(persisted) == 1


def test_new_count_breaks_dedupe(tmp_path):
    now = time.time()
    sdir = _write_events(tmp_path, [{"ts": now - 60, "event_type": "cigarette_lit", "note": "cigarette"}])
    assert record_owner_behavior_pattern(state_dir=sdir) is not None
    # a second cigarette appears -> count changes -> new row allowed even within window
    with (sdir / "owner_body_events.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": now - 10, "event_type": "cigarette_lit", "note": "cigarette"}) + "\n")
    out = record_owner_behavior_pattern(state_dir=sdir)
    assert out is not None
    assert out["cigarette_count"] == 2
    persisted = (sdir / "owner_behavior_patterns.jsonl").read_text().strip().splitlines()
    assert len(persisted) == 2


def test_no_cigarettes_no_row(tmp_path):
    now = time.time()
    sdir = _write_events(tmp_path, [{"ts": now - 60, "event_type": "phone_call_active", "note": "on a call"}])
    out = record_owner_behavior_pattern(state_dir=sdir)
    assert out is None
    assert not (sdir / "owner_behavior_patterns.jsonl").exists()


def test_no_events_no_row(tmp_path):
    sdir = tmp_path / ".sifta_state"
    sdir.mkdir(parents=True, exist_ok=True)
    assert record_owner_behavior_pattern(state_dir=sdir) is None
