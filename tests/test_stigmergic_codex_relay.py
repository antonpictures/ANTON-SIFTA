from __future__ import annotations

import importlib
import json
from pathlib import Path


def test_poll_and_relay_skips_non_dict_trace_rows(tmp_path: Path, monkeypatch) -> None:
    relay = importlib.import_module("System.stigmergic_codex_relay")
    trace = tmp_path / "ide_stigmergic_trace.jsonl"
    cursor = tmp_path / "ide_codex_relay_cursor.json"
    trace.write_text(
        "\n".join(
            [
                "1780846404",
                json.dumps(
                    {
                        "trace_id": "trace-not-codex",
                        "kind": "handoff",
                        "source_ide": "cursor_m5",
                        "payload": "hello",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(relay, "IDE_TRACE_FILE", trace)
    monkeypatch.setattr(relay, "RELAY_STATE_FILE", cursor)

    relay.poll_and_relay()

    state = json.loads(cursor.read_text(encoding="utf-8"))
    assert state["byte_offset"] == trace.stat().st_size