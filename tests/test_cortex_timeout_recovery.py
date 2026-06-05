import json
import subprocess


def test_timeout_recovery_records_queue_and_reply(tmp_path):
    from System.swarm_cortex_timeout_recovery import timeout_recovery_reply

    state = tmp_path / ".sifta_state"
    reply = timeout_recovery_reply(
        model="grok:grok-build",
        owner_text="use your arms and code it",
        timeout_s=120,
        state_dir=state,
    )

    assert "timed out after 120s" in reply
    assert "recovery receipt" in reply
    assert "asking George to repeat" in reply
    assert "Try again" not in reply
    assert "switch cortex" not in reply

    rows = [
        json.loads(line)
        for line in (state / "cortex_timeout_recovery.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert rows[-1]["truth_label"] == "ALICE_CORTEX_TIMEOUT_RECOVERY_V1"
    assert rows[-1]["queue_status"] == "written"
    assert rows[-1]["diagnostic_status"] == "scheduled"
    assert rows[-1]["diagnostic_arm"]
    assert rows[-1]["diagnostic_receipt_id"]

    queue_rows = [
        json.loads(line)
        for line in (state / "body_stabilization_queue.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert any(row["source"] == "cortex_timeout_recovery" and row["status"] == "active" for row in queue_rows)

    diag_rows = [
        json.loads(line)
        for line in (state / "parallel_cortex_arm_diagnostics.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert diag_rows[-1]["recovery_receipt_id"] == rows[-1]["trace_id"]
    assert diag_rows[-1]["diagnostic_arm"] == rows[-1]["diagnostic_arm"]


def test_grok_cli_timeout_recovers_without_error_event(tmp_path, monkeypatch):
    from System import swarm_gemini_brain as brain

    state = tmp_path / ".sifta_state"
    monkeypatch.setenv("SIFTA_STATE_DIR", str(state))
    monkeypatch.setattr(brain, "_grok_cli_binary", lambda: "/fake/grok")

    def _timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="grok", timeout=120)

    monkeypatch.setattr(brain.subprocess, "run", _timeout)
    events = list(
        brain._stream_grok_chat_via_cli(
            model="grok:grok-4.3",
            messages=[{"role": "user", "content": "code the love modules"}],
            timeout_s=120,
        )
    )

    assert [kind for kind, _payload in events] == ["token", "done"]
    assert "recovery receipt" in events[0][1]
    assert "diagnostic receipt" in events[0][1]
    assert "Try again" not in events[0][1]
    assert (state / "cortex_timeout_recovery.jsonl").exists()
    assert (state / "parallel_cortex_arm_diagnostics.jsonl").exists()
