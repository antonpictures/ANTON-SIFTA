from __future__ import annotations

import json
from uuid import UUID

from System import stigmergic_terminal_trace as trace


def _use_tmp_trace(monkeypatch, tmp_path):
    path = tmp_path / "stigmergic_terminal_trace.jsonl"
    monkeypatch.setattr(trace, "TRACE_PATH", path)
    return path


def _read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_append_returns_uuid_and_writes_row(monkeypatch, tmp_path):
    path = _use_tmp_trace(monkeypatch, tmp_path)

    row_id = trace.append_terminal_trace(
        "pty_visible",
        {"line": "Grok queued"},
        ide="pytest",
        model="test-model",
    )

    UUID(row_id)
    rows = _read_jsonl(path)
    assert len(rows) == 1
    assert rows[0]["id"] == row_id
    assert rows[0]["kind"] == "pty_visible"
    assert rows[0]["payload"] == {"line": "Grok queued"}
    assert rows[0]["ide"] == "pytest"
    assert rows[0]["model"] == "test-model"
    assert rows[0]["homeworld_serial"] == "GTH4921YP3"
    assert isinstance(rows[0]["ts"], float)


def test_append_is_truly_append_only(monkeypatch, tmp_path):
    path = _use_tmp_trace(monkeypatch, tmp_path)

    ids = [
        trace.append_terminal_trace(f"kind_{i}", {"i": i}, ide="pytest", model="test-model")
        for i in range(3)
    ]

    rows = _read_jsonl(path)
    assert [row["id"] for row in rows] == ids
    assert [row["payload"]["i"] for row in rows] == [0, 1, 2]
    assert len(path.read_text(encoding="utf-8").splitlines()) == 3


def test_tail_recent_rows_returns_in_chrono_order(monkeypatch, tmp_path):
    _use_tmp_trace(monkeypatch, tmp_path)
    for i in range(5):
        trace.append_terminal_trace("tick", {"i": i}, ide="pytest", model="test-model")

    rows = trace.tail_recent_rows(3)

    assert [row["payload"]["i"] for row in rows] == [2, 3, 4]


def test_find_by_kind_filters_correctly(monkeypatch, tmp_path):
    path = _use_tmp_trace(monkeypatch, tmp_path)
    trace.append_terminal_trace("X", {"i": 1}, ide="pytest", model="test-model")
    trace.append_terminal_trace("Y", {"i": 2}, ide="pytest", model="test-model")
    trace.append_terminal_trace("X", {"i": 3}, ide="pytest", model="test-model")
    rows = _read_jsonl(path)
    since_second_x = rows[-1]["ts"]

    assert [row["payload"]["i"] for row in trace.find_by_kind("X")] == [1, 3]
    assert [row["payload"]["i"] for row in trace.find_by_kind("Y")] == [2]
    assert [row["payload"]["i"] for row in trace.find_by_kind("X", since_ts=since_second_x)] == [3]


def test_empty_file_returns_empty_list(monkeypatch, tmp_path):
    _use_tmp_trace(monkeypatch, tmp_path)

    assert trace.tail_recent_rows() == []
    assert trace.find_by_kind("missing") == []


def test_payload_with_nested_dict_round_trips(monkeypatch, tmp_path):
    _use_tmp_trace(monkeypatch, tmp_path)
    payload = {
        "screen": {"rows": 24, "cols": 80},
        "events": ["queue", "trace", "receipt"],
        "ok": True,
    }

    trace.append_terminal_trace("nested", payload, ide="pytest", model="test-model")

    assert trace.tail_recent_rows(1)[0]["payload"] == payload
