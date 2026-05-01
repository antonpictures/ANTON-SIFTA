import json
from pathlib import Path

import pytest

from System import ollama_file_weight_ledger as ledger


TAGS_PAYLOAD = {
    "models": [
        {
            "name": "gemma4:latest",
            "model": "gemma4:latest",
            "size": 9_600 * 1024 * 1024,
            "digest": "digest-gemma",
            "modified_at": "2026-04-30T12:00:00Z",
        },
        {
            "name": "qwen3.5:2b",
            "model": "qwen3.5:2b",
            "size": 2_700 * 1024 * 1024,
            "digest": "digest-qwen",
            "modified_at": "2026-04-30T13:00:00Z",
        },
    ]
}


def test_ollama_payload_becomes_one_file_weight_row_per_tag():
    rows = ledger.ollama_file_weight_rows_from_payload(
        TAGS_PAYLOAD,
        trace_id="trace-test",
        source_url="http://127.0.0.1:11434/api/tags",
        ts=123.0,
    )

    assert [row["tag"] for row in rows] == ["gemma4:latest", "qwen3.5:2b"]
    assert [row["file_weight_mb"] for row in rows] == [9600.0, 2700.0]
    assert all(row["schema"] == ledger.SCHEMA for row in rows)
    assert all(row["trace_id"] == "trace-test" for row in rows)
    assert all(row["read_only_probe"] is True for row in rows)
    assert all(row["no_global_mesh_scalar"] is True for row in rows)
    assert all(row["row_hash"] for row in rows)


def test_ollama_file_weight_append_writes_jsonl_rows(tmp_path: Path):
    rows = ledger.ollama_file_weight_rows_from_payload(TAGS_PAYLOAD, trace_id="trace-test", ts=123.0)
    target = tmp_path / "ollama_file_weight_ledger.jsonl"

    appended = ledger.append_ollama_file_weight_rows(rows, ledger_path=target)

    stored = [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines()]
    assert len(appended) == len(stored) == 2
    assert stored[0]["tag"] == "gemma4:latest"
    assert stored[1]["tag"] == "qwen3.5:2b"


def test_ollama_file_weight_probe_uses_tags_api_without_ollama_cli(monkeypatch, tmp_path: Path):
    calls = []

    def fake_fetch(source_url: str, timeout: float):
        calls.append((source_url, timeout))
        return TAGS_PAYLOAD

    monkeypatch.setattr(ledger, "fetch_ollama_tags", fake_fetch)

    rows = ledger.probe_and_append_ollama_file_weights(
        trace_id="trace-test",
        source_url="http://local.test/api/tags",
        ledger_path=tmp_path / "weights.jsonl",
        timeout=0.25,
    )

    assert calls == [("http://local.test/api/tags", 0.25)]
    assert [row["tag"] for row in rows] == ["gemma4:latest", "qwen3.5:2b"]


def test_ollama_file_weight_rejects_negative_sizes():
    with pytest.raises(ValueError, match="non-negative"):
        ledger.ollama_file_weight_rows_from_payload({"models": [{"name": "bad", "size": -1}]})
