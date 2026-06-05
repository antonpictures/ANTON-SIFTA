import json


def test_parallel_diagnostic_selects_non_stalled_arm_and_writes_receipts(tmp_path):
    from System.swarm_parallel_cortex_arm_diagnostics import (
        latest_parallel_diagnostic_block,
        schedule_parallel_diagnostic,
    )

    state = tmp_path / ".sifta_state"
    event = schedule_parallel_diagnostic(
        stalled_cortex="grok:grok-build",
        owner_text="THANK YOU ALICE, I LIKE IT",
        timeout_s=120,
        cause="grok_cli_timeout",
        recovery_receipt_id="abc123",
        state_dir=state,
    )

    assert event.truth_label == "ALICE_PARALLEL_CORTEX_ARM_DIAGNOSTICS_V1"
    assert event.diagnostic_arm != "grok_agent"
    assert event.diagnostic_arm in {
        "claude_agent",
        "codex_agent",
        "cline_agent",
        "qwen_agent",
    }
    assert "System/swarm_gemini_brain.py" in event.source_files
    assert "different" in event.habit_note.lower()

    rows = [
        json.loads(line)
        for line in (state / "parallel_cortex_arm_diagnostics.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert rows[-1]["diagnostic_arm"] == event.diagnostic_arm

    queue = [
        json.loads(line)
        for line in (state / "body_stabilization_queue.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert queue[-1]["source"] == "parallel_cortex_arm_diagnostics"
    assert queue[-1]["status"] == "queued"

    block = latest_parallel_diagnostic_block(state_dir=state)
    assert event.diagnostic_arm in block
    assert "grok:grok-build" in block

