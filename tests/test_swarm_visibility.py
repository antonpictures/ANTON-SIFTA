"""
test_swarm_visibility.py
========================
Offline tests for swarm_visibility. Stages a fake .sifta_state/ and
asserts each read function returns the right shape.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


@pytest.fixture
def chdir_tmp(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".sifta_state").mkdir()
    yield tmp_path


@pytest.fixture
def fresh_vis(chdir_tmp):
    for mod in list(sys.modules):
        if mod.startswith("swarm_visibility"):
            del sys.modules[mod]
    import swarm_visibility  # noqa
    return swarm_visibility


def _drop(state: Path, fname: str, rows):
    with (state / fname).open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def test_organ_status_empty_tree(fresh_vis):
    out = fresh_vis.organ_status()
    assert isinstance(out, list)
    assert len(out) > 0
    for o in out:
        assert "organ" in o and "health" in o and "row_count" in o
        # No files staged → all red except owner_genesis special-case
        if o["organ"] != "owner_genesis":
            assert o["row_count"] == 0


def test_organ_status_with_data(fresh_vis, chdir_tmp):
    import time
    _drop(chdir_tmp / ".sifta_state", "terminal_organ.jsonl", [
        {"type": "TERMINAL_INTENT", "command": "ls", "ts": time.time(), "hash": "a" * 64},
        {"type": "TERMINAL_RESULT", "exit_code": 0, "ts": time.time(), "hash": "b" * 64},
    ])
    rows = {o["organ"]: o for o in fresh_vis.organ_status()}
    assert rows["terminal"]["exists"]
    assert rows["terminal"]["row_count"] == 2
    assert rows["terminal"]["health"] in ("green", "yellow")
    assert rows["terminal"]["head"]  # non-empty


def test_field_recent_and_swimmers(fresh_vis, chdir_tmp):
    import time
    now = time.time()
    _drop(chdir_tmp / ".sifta_state", "ide_stigmergic_trace.jsonl", [
        {"type": "LLM_REGISTRATION", "doctor": "Grok", "model": "grok-4.3",
         "trace_id": "t1", "ts": now - 100, "hash": "1" * 64},
        {"type": "LLM_REGISTRATION", "doctor": "Cursor", "model": "gpt-5.5",
         "trace_id": "t2", "ts": now - 50, "hash": "2" * 64},
        {"type": "TOOL_CALL_PRE_FLIGHT", "doctor": "Grok",
         "ts": now - 10, "hash": "3" * 64},
    ])
    field = fresh_vis.field_recent(10)
    assert len(field) == 3
    types_ = [f["type"] for f in field]
    assert "LLM_REGISTRATION" in types_

    swimmers = fresh_vis.active_swimmers()
    doctors = {s["doctor"] for s in swimmers}
    assert doctors == {"Grok", "Cursor"}


def test_stgm_flow_picks_current_balance(fresh_vis, chdir_tmp):
    import time
    _drop(chdir_tmp / ".sifta_state", "stgm_ledger.jsonl", [
        {"type": "STGM_DEBIT", "organ": "terminal", "amount": 0.01,
         "balance_after": 99.99, "reason": "cmd", "ts": time.time(),
         "hash": "a" * 64},
        {"type": "STGM_DEBIT", "organ": "file", "amount": 0.02,
         "balance_after": 99.97, "reason": "read", "ts": time.time(),
         "hash": "b" * 64},
    ])
    flow = fresh_vis.stgm_flow(10)
    assert flow["current_balance"] == 99.97
    assert len(flow["entries"]) == 2


def test_full_snapshot_shape(fresh_vis, chdir_tmp):
    snap = fresh_vis.full_snapshot()
    assert set(snap.keys()) >= {"organs", "field", "stgm", "swimmers", "snapshot_ts"}
    assert isinstance(snap["organs"], list)
    assert isinstance(snap["field"], list)
    assert isinstance(snap["stgm"], dict)
    assert isinstance(snap["swimmers"], list)
