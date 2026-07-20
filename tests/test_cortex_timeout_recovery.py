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


def test_rich_typed_turn_waits_but_spoken_noise_does_not():
    from System.swarm_cortex_timeout_recovery import rich_typed_turn_needs_wait

    rich = "George typed a detailed body-code request: please wire the memory and travel mode fully."
    assert rich_typed_turn_needs_wait(rich, input_modality="TYPED", stt_conf=1.0) is True
    assert rich_typed_turn_needs_wait(rich, input_modality="SPOKEN", stt_conf=0.42) is False
    assert rich_typed_turn_needs_wait("okay", input_modality="TYPED", stt_conf=1.0) is False


def test_queue_and_plan_reroute_writes_cortex_reroute_receipt(tmp_path, monkeypatch):
    from System import swarm_metabolic_cortex_router as router
    from System.swarm_cortex_timeout_recovery import queue_and_plan_reroute

    state = tmp_path / ".sifta_state"
    monkeypatch.setattr(
        router,
        "route_cortex",
        lambda *_args, **_kwargs: {
            "model": "alice-m5-cortex-8b-6.3gb:latest",
            "reason": "test warm fallback",
            "receipt_id": "route-test-1",
        },
    )

    plan = queue_and_plan_reroute(
        model="grok:grok-4.3",
        owner_text="Please wire the cortex timeout queue and wait for this rich typed task.",
        timeout_s=60,
        cause="no_token_watchdog",
        state_dir=state,
    )

    assert plan["model"] == "alice-m5-cortex-8b-6.3gb:latest"
    assert "Body status: cortex thinking; waiting, not templating" in plan["wait_line"]
    assert "My cortex is slow" not in plan["wait_line"]
    recovery_rows = [
        json.loads(line)
        for line in (state / "cortex_timeout_recovery.jsonl").read_text().splitlines()
        if line.strip()
    ]
    reroute_rows = [
        json.loads(line)
        for line in (state / "cortex_reroute_receipts.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert recovery_rows[-1]["cause"] == "no_token_watchdog"
    assert reroute_rows[-1]["kind"] == "CORTEX_REROUTE"
    assert reroute_rows[-1]["from_model"] == "grok:grok-4.3"
    assert reroute_rows[-1]["to_model"] == "alice-m5-cortex-8b-6.3gb:latest"
    assert reroute_rows[-1]["route_receipt_id"] == "route-test-1"


def test_grok_cli_timeout_recovers_without_error_event(tmp_path, monkeypatch):
    from System import swarm_gemini_brain as brain

    state = tmp_path / ".sifta_state"
    monkeypatch.setenv("SIFTA_STATE_DIR", str(state))
    monkeypatch.delenv("SIFTA_GROK_CLI_MODEL", raising=False)
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
    substantive = [
        (kind, payload)
        for kind, payload in events
        if not (kind == "token" and payload == "\u200b")
    ]

    assert [kind for kind, _payload in substantive] == ["token", "done"]
    assert "recovery receipt" in substantive[0][1]
    assert "diagnostic receipt" in substantive[0][1]
    assert "Try again" not in substantive[0][1]
    assert (state / "cortex_timeout_recovery.jsonl").exists()
    assert (state / "parallel_cortex_arm_diagnostics.jsonl").exists()
    health_rows = [
        json.loads(line)
        for line in (state / "grok_cli_model_health.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert health_rows[-1]["model"] == "grok-build"
    assert health_rows[-1]["status"] == "timeout"
    assert health_rows[-1]["action"] == "demote_to_fast"
    assert health_rows[-1]["active_pin"] == "grok-composer-2.5-fast"
    assert brain.grok_cli_model_for("grok:grok-4.3") == "grok-composer-2.5-fast"


def test_self_code_marker_timeout_recovers_packet_and_receipts(tmp_path):
    from System.swarm_cortex_timeout_recovery import timeout_recovery_reply

    state = tmp_path / ".sifta_state"
    reply = timeout_recovery_reply(
        model="grok:grok-build",
        owner_text="===BEGIN ALICE BROWSER LAG PROBE r921===",
        timeout_s=60,
        state_dir=state,
    )

    assert "Self-code packet recovered" in reply
    assert "r921-alice-browser-lag-probe" in reply
    assert "System/swarm_browser_lag_probe.py" in reply

    self_rows = [
        json.loads(line)
        for line in (state / "alice_self_coding_receipts.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert self_rows[-1]["action"] == "recovered_after_cortex_timeout"
    assert self_rows[-1]["round_id"] == "r921-alice-browser-lag-probe"
    assert "System/swarm_browser_lag_probe.py" in self_rows[-1]["paths"]

    diag_rows = [
        json.loads(line)
        for line in (state / "parallel_cortex_arm_diagnostics.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert "RECOVERED SELF-CODE PACKET" in diag_rows[-1]["arm_task_prompt"]
    assert diag_rows[-1]["self_code_round_id"] == "r921-alice-browser-lag-probe"
    assert "System/swarm_browser_lag_probe.py" in diag_rows[-1]["self_code_paths"]
    assert "[SELF_CODE_CUT: path=System/swarm_browser_lag_probe.py]" in diag_rows[-1]["self_code_packet"]


def test_no_token_watchdog_self_code_recovery_uses_combined_marker_text(tmp_path):
    from System.swarm_cortex_timeout_recovery import timeout_recovery_reply

    state = tmp_path / ".sifta_state"
    reply = timeout_recovery_reply(
        model="claude:claude-code-cli-default",
        owner_text='===BEGIN ALICE BROWSER LAG PROBE r921=== and "Alice, write the browser lag probe now"',
        timeout_s=150,
        cause="no_token_watchdog",
        state_dir=state,
    )

    assert "Self-code packet recovered" in reply
    assert "r921-alice-browser-lag-probe" in reply

    rows = [
        json.loads(line)
        for line in (state / "cortex_timeout_recovery.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert rows[-1]["cause"] == "no_token_watchdog"
    assert rows[-1]["self_code_round_id"] == "r921-alice-browser-lag-probe"
    assert "System/swarm_browser_lag_probe.py" in rows[-1]["self_code_paths"]
