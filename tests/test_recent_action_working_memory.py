from __future__ import annotations

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _append_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def test_recent_action_working_memory_summarizes_grok_receipts(tmp_path):
    from System.swarm_recent_action_context import format_recent_action_working_memory

    now = 1000.0
    _append_jsonl(
        tmp_path / "matrix_terminal_process_trace.jsonl",
        [
            {
                "ts": now - 8,
                "action": "grok_resume_ready_for_prompt",
                "kind": "screen_navigation",
                "source": "alice_global_chat_terminal",
                "payload": {"prompt_chars": 721, "source": "alice_global_chat_terminal"},
                "text": "grok resume verified past startup screens -> paste queued prompt",
            },
            {
                "ts": now - 4,
                "action": "GROK_RESULT",
                "kind": "tool_result_capture",
                "source": "alice_global_chat_terminal",
                "payload": {
                    "capture_id": "grok_result_cb007641e2a4",
                    "capture_status": "captured_framebuffer",
                    "captured_output_hash": "d633b24c97dd0c18e9015d18307801b5",
                    "source": "alice_global_chat_terminal",
                    "answer": "Grok framebuffer receipt rendered.",
                },
                "text": "GROK_RESULT captured_framebuffer grok_result_cb007641e2a4",
            },
        ],
    )

    block = format_recent_action_working_memory(
        state_dir=tmp_path,
        user_text="Alice did u execute?",
        now=now,
    )

    assert "RECENT ACTION WORKING MEMORY" in block
    assert "did you execute" in block
    assert "Grok was past startup screens; queued prompt sent" in block
    assert "grok_result_cb007641e2a4" in block
    assert "captured_framebuffer" in block
    assert "d633b24c97dd0c18" in block
    assert "generic greeting" in block


def test_recent_action_working_memory_summarizes_agent_arm_results(tmp_path):
    from System.swarm_recent_action_context import format_recent_action_working_memory

    _append_jsonl(
        tmp_path / "agent_arm_receipts.jsonl",
        [
            {
                "ts": 950.0,
                "truth_label": "AGENT_ARM_LAUNCH_RESULT",
                "arm_id": "codex_agent",
                "status": "EVIDENCE_CAPTURED",
                "ok": True,
                "receipt_id": "51c0dba7-bae0-4b85-95fd-a741c0e2c646",
                "duration_s": 566.853,
                "output_tail": "Built Stigmergic Ant Foraging Trail and verified manifest.",
            }
        ],
    )

    block = format_recent_action_working_memory(state_dir=tmp_path, now=1000.0)

    assert "agent arm codex_agent result" in block
    assert "EVIDENCE_CAPTURED" in block
    assert "51c0dba7-bae0-4b85-95fd-a741c0e2c646" in block
    assert "Built Stigmergic Ant Foraging Trail" in block


def test_current_system_prompt_injects_recent_action_working_memory(tmp_path, monkeypatch):
    from Applications import sifta_talk_to_alice_widget as talk

    _append_jsonl(
        tmp_path / "matrix_terminal_process_trace.jsonl",
        [
            {
                "ts": 1000.0,
                "action": "GROK_RESULT",
                "kind": "tool_result_capture",
                "source": "alice_global_chat_terminal",
                "payload": {
                    "capture_id": "grok_result_memory_test",
                    "capture_status": "captured_framebuffer",
                    "captured_output_hash": "abc123def456",
                    "source": "alice_global_chat_terminal",
                    "answer": "Memory test completed.",
                },
                "text": "GROK_RESULT captured_framebuffer grok_result_memory_test",
            }
        ],
    )
    monkeypatch.setattr(talk, "_STATE_DIR", tmp_path, raising=False)

    prompt = talk._current_system_prompt(user_active=True, user_text="Alice did you execute?")

    assert "RECENT ACTION WORKING MEMORY" in prompt
    assert "grok_result_memory_test" in prompt
    assert "Answer from these receipts first" in prompt
