from __future__ import annotations

import hashlib
import json

from System import swarm_file_organ as file_organ
from System import swarm_terminal_organ as terminal_organ
from System import swarm_web_organ as web_organ


def _seed_hashless_router_row(trace_path):
    row = {"event": "TOOL_CALL_PRE_FLIGHT", "tool": "read_file", "ts": 1.0}
    line = json.dumps(row)
    trace_path.write_text(line + "\n")
    return hashlib.sha256(line.encode()).hexdigest()[:16]


def _last_row(trace_path):
    rows = [json.loads(line) for line in trace_path.read_text().splitlines() if line.strip()]
    return rows[-1]


def test_file_organ_chains_after_hashless_router_row(tmp_path, monkeypatch):
    trace = tmp_path / "tool_router_trace.jsonl"
    expected_prev = _seed_hashless_router_row(trace)
    target = tmp_path / "demo.txt"
    target.write_text("hello")
    monkeypatch.setattr(file_organ, "_TRACE", trace)

    out = file_organ.read_file(str(target))

    assert out["receipt_hash"]
    row = _last_row(trace)
    assert row["type"] == "FILE_READ"
    assert row["prev_hash"] == expected_prev
    assert row["hash"] == out["receipt_hash"]


def test_terminal_organ_chains_after_hashless_router_row(tmp_path, monkeypatch):
    trace = tmp_path / "tool_router_trace.jsonl"
    expected_prev = _seed_hashless_router_row(trace)
    monkeypatch.setattr(terminal_organ, "_TRACE", trace)

    out = terminal_organ.run_terminal("echo hello")

    assert out["type"] == "TERMINAL_EXECUTION"
    row = _last_row(trace)
    assert row["prev_hash"] == expected_prev
    assert row["hash"] == out["hash"]


def test_web_organ_chains_after_hashless_router_row(tmp_path, monkeypatch):
    trace = tmp_path / "tool_router_trace.jsonl"
    expected_prev = _seed_hashless_router_row(trace)
    monkeypatch.setattr(web_organ, "_TRACE", trace)

    out = web_organ.search_web("sifta")

    assert out["receipt_hash"]
    row = _last_row(trace)
    assert row["type"] == "WEB_SEARCH"
    assert row["prev_hash"] == expected_prev
    assert row["hash"] == out["receipt_hash"]
