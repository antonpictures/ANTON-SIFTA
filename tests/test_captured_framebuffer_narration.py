from __future__ import annotations

import json
from pathlib import Path

from System.swarm_recent_action_context import format_recent_action_working_memory


def _append_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def test_captured_framebuffer_is_synthesized_as_grok_result_receipt_line(tmp_path):
    _append_jsonl(
        tmp_path / "matrix_terminal_process_trace.jsonl",
        [
            {
                "ts": 1000.0,
                "action": "captured_framebuffer",
                "kind": "tool_result_capture",
                "source": "alice_global_chat_terminal",
                "payload": {
                    "captured_output_hash": "d78333cc335f5094",
                    "captured_output_chars": 407,
                    "pty_transcript_span": {"start_seq": 501, "end_seq": 700},
                },
                "text": "captured_framebuffer hash=d78333cc335f5094 captured 407 chars seq 501-700",
            }
        ],
    )

    block = format_recent_action_working_memory(
        state_dir=tmp_path,
        user_text="Alice, dispatch Grok for Round 20 and show receipt.",
        now=1010.0,
        max_events=5,
    )

    assert "GROK_RESULT receipt=d78333cc335f5094 captured=407chars seq=501-700" in block
    assert "FIRST sentence MUST be the latest GROK_RESULT receipt line verbatim" in block
