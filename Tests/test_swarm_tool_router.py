from __future__ import annotations

import json

import pytest

from System import swarm_tool_router as router
from System import swarm_kernel_process_table as kernel_module
from System import whatsapp_bridge_autopilot as wa


class _FakeTimingUpdate:
    def __init__(self, action: str, ok: bool):
        self.action = action
        self.ok = ok

    def as_dict(self):
        return {
            "action": self.action,
            "ok": self.ok,
            "observed_latency": 0.01,
            "next_expected_latency": 1.0,
        }


class _FakeCerebellum:
    def __init__(self, delay_s: float = 0.0):
        self.delay_s = delay_s
        self.updates = []

    def should_delay(self, action: str, urgency: float):
        return self.delay_s

    def update(self, action: str, observed_latency: float, ok: bool, write_receipt: bool = True):
        self.updates.append(
            {
                "action": action,
                "observed_latency": observed_latency,
                "ok": ok,
                "write_receipt": write_receipt,
            }
        )
        return _FakeTimingUpdate(action, ok)


def _patch_cerebellum(monkeypatch, delay_s: float = 0.0) -> _FakeCerebellum:
    fake = _FakeCerebellum(delay_s=delay_s)
    monkeypatch.setattr(router, "_get_cerebellum_timing", lambda: fake)
    return fake


@pytest.fixture(autouse=True)
def _disable_real_tool_economy_charge(monkeypatch):
    monkeypatch.setattr(router, "_charge_tool_execution", lambda *_args, **_kwargs: None)


@pytest.fixture(autouse=True)
def _isolate_kernel_process_table(tmp_path, monkeypatch):
    state = tmp_path / ".sifta_state"
    state.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(router, "_STATE", state)
    monkeypatch.setattr(kernel_module, "_GLOBAL_TABLE", None)


def _send_call(extra: str = "") -> router.ParsedToolCall:
    parts = [
        "target=Carlton",
        "text=hello",
        "cost_justification=unit test proves router behavior",
    ]
    if extra:
        parts.append(extra)
    return router.parse_tool_calls(
        f"[TOOL_CALL: send_whatsapp | {' | '.join(parts)}]"
    )[0]


def _with_cost(tool_call: str) -> str:
    return tool_call[:-1] + " | cost_justification=unit test proves router behavior]"


def test_whatsapp_tool_call_without_owner_consent_records_silence(monkeypatch):
    seen = {}
    timing = _patch_cerebellum(monkeypatch)

    def fake_autonomous_send_whatsapp(**kwargs):
        seen.update(kwargs)
        return {
            "ok": False,
            "status": "SILENCE_NO_CONSENT",
            "result": "contact_or_owner_has_not_granted_autonomous_whatsapp_consent",
            "truth_note": "Autonomous boundary chose silence; no external WhatsApp action occurred.",
        }

    monkeypatch.setattr(wa, "autonomous_send_whatsapp", fake_autonomous_send_whatsapp)

    out = router.execute_tool_call(_send_call(), owner_present=True, autonomous=True)

    assert out.executed is False
    assert out.status == "EXEC_FAILED_SILENCE_NO_CONSENT"
    assert seen["consent"] is False
    assert "no external WhatsApp action occurred" in out.result["truth_note"]
    assert out.result["intent_provenance"]["intent_source"] == "model"
    assert out.result["intent_provenance"]["consent"] == "none"
    assert timing.updates[-1]["action"] == "send_whatsapp"
    assert timing.updates[-1]["ok"] is False


def test_whatsapp_tool_call_with_owner_consent_uses_owner_source(monkeypatch):
    seen = {}
    timing = _patch_cerebellum(monkeypatch)

    def fake_send_whatsapp(target, text, *, allow_group_send=False, source="", intent_provenance=None):
        seen.update(
            {
                "target": target,
                "text": text,
                "allow_group_send": allow_group_send,
                "source": source,
                "intent_provenance": intent_provenance,
            }
        )
        return {
            "ok": True,
            "status": "SENT",
            "source": source,
            "intent_provenance": intent_provenance,
            "truth_note": "External WhatsApp send is true only when ok=true and status=SENT.",
        }

    def fail_autonomous_send_whatsapp(**_kwargs):
        raise AssertionError("owner-consented send must not be labeled alice_autonomous")

    monkeypatch.setattr(wa, "send_whatsapp", fake_send_whatsapp)
    monkeypatch.setattr(wa, "autonomous_send_whatsapp", fail_autonomous_send_whatsapp)

    out = router.execute_tool_call(
        _send_call("owner_consent=true"),
        owner_present=True,
        autonomous=True,
    )

    assert out.executed is True
    assert out.result["status"] == "SENT"
    assert seen["source"] == "alice_tool_router_architect_consent"
    assert seen["intent_provenance"]["intent_source"] == "owner"
    assert seen["intent_provenance"]["consent"] == "explicit"
    assert out.result["cerebellum_timing"]["preflight"]["status"] == "CLEAR"
    assert out.result["cerebellum_timing"]["update"]["ok"] is True
    assert timing.updates[-1]["action"] == "send_whatsapp"


def test_tool_prompt_explains_owner_consent_boundary():
    prompt = router.tools_for_alice_prompt()

    assert "cost_justification" in prompt
    assert "owner_consent=true" in prompt
    assert "records a silence/refusal receipt" in prompt
    assert "ollama_inventory" in prompt
    assert "repo_git_snapshot" in prompt
    assert "stigmergic_bus_tail" in prompt
    assert "verification_contract" in prompt
    assert "agent_arm_research" in prompt
    assert "George does not need to name the arm" in prompt
    assert "codex_agent" in prompt
    assert "corvid_scout" in prompt
    assert "physical_effector_demo" in prompt


def test_missing_cost_justification_rejects_before_executor(monkeypatch):
    def fail_check_economy(_params):
        raise AssertionError("economy rejection must happen before executor")

    monkeypatch.setitem(router._EXECUTORS, "check_economy", fail_check_economy)

    call = router.parse_tool_calls("[TOOL_CALL: check_economy]")[0]
    out = router.execute_tool_call(call)

    assert out.executed is False
    assert out.status == "REJECTED_ECONOMY"
    assert "cost_justification" in out.feedback_for_alice


def test_successful_tool_execution_charges_economy(monkeypatch):
    charges = []

    monkeypatch.setitem(
        router._EXECUTORS,
        "check_economy",
        lambda _params: {"ok": True, "alice_summary": "economy ok"},
    )
    monkeypatch.setattr(
        router,
        "_charge_tool_execution",
        lambda call, spec, justification: charges.append((call.tool_name, spec.name, justification)),
    )

    call = router.parse_tool_calls(
        "[TOOL_CALL: check_economy | cost_justification=unit test needs a cheap economy read]"
    )[0]
    out = router.execute_tool_call(call)

    assert out.executed is True
    assert out.result["tool_economy"]["fee_stgm"] == router._TOOL_EXECUTION_COST_STGM
    assert charges == [("check_economy", "check_economy", "unit test needs a cheap economy read")]
    assert out.result["kernel_process_receipt_id"].startswith("receipt_")


def test_tool_router_writes_kernel_heartbeat_on_success(monkeypatch):
    monkeypatch.setitem(
        router._EXECUTORS,
        "check_economy",
        lambda _params: {"ok": True, "alice_summary": "economy ok"},
    )
    monkeypatch.setattr(
        router,
        "_cortex_generate_with_mtp",
        lambda *_args, **_kwargs: {
            "text": "draft",
            "tokens_per_sec": 14.0,
            "latency_ms": 71.0,
            "used_mtp": True,
            "verification_status": "VERIFIED_MTP",
        },
    )

    call = router.parse_tool_calls(
        "[TOOL_CALL: check_economy | cost_justification=unit test proves kernel heartbeat]"
    )[0]
    out = router.execute_tool_call(call)

    rows = [
        json.loads(line)
        for line in (router._STATE / "kernel_process_table.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert out.executed is True
    assert any(
        row["pid"] == router._KERNEL_TOOL_ROUTER_PID
        and row["action"] == "heartbeat"
        and row["current_job"] == "tool:check_economy:EXECUTED"
        and row["tokens_per_sec"] == 14.0
        and row["latency_ms"] == 71.0
        and row["used_mtp"] is True
        for row in rows
    )


def test_explicit_ghost_caller_rejected_before_effector(monkeypatch):
    _patch_cerebellum(monkeypatch)

    def fail_send_whatsapp(*_args, **_kwargs):
        raise AssertionError("ghost caller must not reach WhatsApp effector")

    monkeypatch.setattr(wa, "send_whatsapp", fail_send_whatsapp)

    out = router.execute_tool_call(
        _send_call("owner_consent=true"),
        owner_present=True,
        autonomous=True,
        caller_pid="ghost",
    )

    assert out.executed is False
    assert out.status == "REJECTED_KERNEL_REGISTRATION"
    assert "ghost pid" in out.feedback_for_alice


def test_ring3_registered_caller_cannot_execute_effector(monkeypatch):
    _patch_cerebellum(monkeypatch)
    table = kernel_module.get_kernel_process_table(state_root=router._STATE)
    table.sys_register(
        {
            "pid": "talk_ui",
            "organ_id": "Applications/sifta_talk_to_alice_widget.py",
            "ring": 3,
            "location": "sifta_desktop_body",
            "bodies_present": ["talk_ui"],
        }
    )

    def fail_send_whatsapp(*_args, **_kwargs):
        raise AssertionError("ring-3 UI must not reach WhatsApp effector")

    monkeypatch.setattr(wa, "send_whatsapp", fail_send_whatsapp)

    out = router.execute_tool_call(
        _send_call("owner_consent=true"),
        owner_present=True,
        autonomous=True,
        caller_pid="talk_ui",
    )

    assert out.executed is False
    assert out.status == "REJECTED_KERNEL_RING"
    assert "ring 3 cannot effector" in out.feedback_for_alice


def test_physical_effector_demo_runs_through_kernel_gate(monkeypatch):
    _patch_cerebellum(monkeypatch)
    call = router.parse_tool_calls(
        "[TOOL_CALL: physical_effector_demo | action=orient_eye_to_owner | estimated_cost=0.02 | expected_value=0.7 | cost_justification=investor demo shows STGM-gated physical behavior]"
    )[0]

    out = router.execute_tool_call(call, owner_present=True, autonomous=True)

    rows = [
        json.loads(line)
        for line in (router._STATE / "kernel_process_table.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    demo_rows = [
        json.loads(line)
        for line in (router._STATE / "physical_effector_demo.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert out.executed is True
    assert out.result["status"] == "SIMULATED_EXECUTED"
    assert out.result["kernel_effector_request"]["decision"] == "ALLOW"
    assert out.result["kernel_effector_request"]["estimated_cost_stgm"] == 0.02
    assert out.result["kernel_effector_request"]["receipt_id"].startswith("receipt_")
    assert demo_rows[-1]["action"] == "orient_eye_to_owner"
    assert demo_rows[-1]["simulated_only"] is True
    assert any(
        row["trace_id"] == out.result["kernel_effector_request"]["receipt_id"]
        and row["current_job"] == "effector_request:physical_effector_demo:ALLOW"
        for row in rows
    )


def test_scheduler_utility_gate_rejects_low_score_before_executor(monkeypatch):
    _patch_cerebellum(monkeypatch)
    table = kernel_module.get_kernel_process_table(state_root=router._STATE)
    table.sys_register(
        {
            "pid": "hot_arm",
            "organ_id": "System/hot_agent_arm.py",
            "ring": 2,
            "location": "sifta_desktop_body",
            "bodies_present": ["hot_arm"],
            "metadata": {"thermal_cost": "4.0"},
        }
    )

    def fail_check_economy(*_args, **_kwargs):
        raise AssertionError("low scheduler utility must not reach executor")

    monkeypatch.setitem(router._EXECUTORS, "check_economy", fail_check_economy)

    call = router.parse_tool_calls(_with_cost("[TOOL_CALL: check_economy]"))[0]
    out = router.execute_tool_call(call, caller_pid="hot_arm")

    assert out.executed is False
    assert out.status == "REJECTED_KERNEL_SCHEDULER"
    assert "score=" in out.feedback_for_alice
    assert out.result["kernel_process_receipt_id"].startswith("receipt_")
    rows = [
        json.loads(line)
        for line in (router._STATE / "kernel_process_table.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert any(
        row["trace_id"] == out.result["kernel_process_receipt_id"]
        and row["current_job"] == "tool_throttle:check_economy"
        for row in rows
    )


def test_cerebellum_delay_blocks_write_action_before_effector(monkeypatch):
    _patch_cerebellum(monkeypatch, delay_s=1.25)

    def fail_send_whatsapp(*_args, **_kwargs):
        raise AssertionError("delayed write action must not reach WhatsApp effector")

    monkeypatch.setattr(wa, "send_whatsapp", fail_send_whatsapp)

    out = router.execute_tool_call(
        _send_call("owner_consent=true"),
        owner_present=True,
        autonomous=True,
    )

    assert out.executed is False
    assert out.status == "EXEC_FAILED_DELAYED_CEREBELLUM"
    assert out.result["status"] == "DELAYED_CEREBELLUM"
    assert out.result["cerebellum_timing"]["delay_s"] == 1.25
    assert "No effector action occurred" in out.result["truth_note"]


def test_stigmergic_bus_tail_respects_line_cap(tmp_path, monkeypatch):
    st = tmp_path / ".sifta_state"
    st.mkdir(parents=True, exist_ok=True)
    trace = st / "ide_stigmergic_trace.jsonl"
    rows = [{"i": i} for i in range(10)]
    trace.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    monkeypatch.setattr(router, "_STATE", st)

    call = router.parse_tool_calls(_with_cost("[TOOL_CALL: stigmergic_bus_tail | lines=3]"))[0]
    out = router.execute_tool_call(call)
    assert out.executed
    assert '"i": 9' in out.feedback_for_alice


def test_ollama_inventory_missing_binary(monkeypatch):
    monkeypatch.setattr(router, "which", lambda _cmd: None)
    call = router.parse_tool_calls(_with_cost("[TOOL_CALL: ollama_inventory]"))[0]
    out = router.execute_tool_call(call)
    assert out.executed is False
    assert "not found" in out.feedback_for_alice.lower()


def test_repo_git_snapshot_on_tmp_repo(tmp_path, monkeypatch):
    import subprocess as sp

    monkeypatch.setattr(router, "_REPO", tmp_path)
    sp.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    sp.run(["git", "config", "user.email", "alice@test"], cwd=tmp_path, check=True)
    sp.run(["git", "config", "user.name", "Alice"], cwd=tmp_path, check=True)
    (tmp_path / "README.md").write_text("hello\n", encoding="utf-8")
    sp.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)
    sp.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)

    call = router.parse_tool_calls(_with_cost("[TOOL_CALL: repo_git_snapshot]"))[0]
    out = router.execute_tool_call(call)
    assert out.executed
    assert "git status" in out.feedback_for_alice.lower()


def test_verification_contract_tool_reads_latest_human_signal(tmp_path, monkeypatch):
    st = tmp_path / ".sifta_state"
    st.mkdir(parents=True, exist_ok=True)
    (st / "human_signals.jsonl").write_text(
        json.dumps(
            {
                "ts": 10,
                "kind": "MINE_INFERENCE",
                "signal": "VERIFICATION_CONTRACT",
                "policy": "automate_what_you_can_verify",
                "rules": {
                    "tool_router_changes": "Requires pytest execution before merge",
                    "new_surface": "Requires receipt-backed proof",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(router, "_STATE", st)

    call = router.parse_tool_calls(_with_cost("[TOOL_CALL: verification_contract]"))[0]
    out = router.execute_tool_call(call)

    assert out.executed
    assert out.result["contract"]["rules"]["new_surface"] == "Requires receipt-backed proof"
    assert "VERIFICATION CONTRACT" in out.feedback_for_alice
    assert "tool_router_changes" in out.feedback_for_alice


def test_agent_arm_research_is_alice_owned_evidence_tool(monkeypatch):
    from System import swarm_agent_arm_launcher as launcher

    def fake_ask_agent_arm(arm_id, prompt, **kwargs):
        assert arm_id == "hermes_agent"
        assert "compare agent frameworks" in prompt
        assert kwargs["evidence_mode"] is True
        return launcher.AgentArmResult(
            ok=True,
            receipt_id="arm-receipt-1",
            arm_id="hermes_agent",
            status="EVIDENCE_CAPTURED",
            mode="evidence",
            output="Hermes evidence: compare A/B/C.",
            artifact_path=".sifta_state/agent_arm_receipts.jsonl",
        )

    monkeypatch.setattr(launcher, "ask_agent_arm", fake_ask_agent_arm)
    call = router.parse_tool_calls(
        "[TOOL_CALL: agent_arm_research | prompt=compare agent frameworks | cost_justification=Alice needs a second local reasoning pass]"
    )[0]
    out = router.execute_tool_call(call, owner_present=True, autonomous=True)

    assert out.executed is True
    assert out.status == "EXECUTED"
    assert out.result["receipt_id"] == "arm-receipt-1"
    assert "agent_arm_research evidence captured" in out.feedback_for_alice
    assert "Hermes evidence" in out.feedback_for_alice


def test_agent_arm_research_can_target_codex_evidence_arm(monkeypatch):
    from System import swarm_agent_arm_launcher as launcher

    def fake_ask_agent_arm(arm_id, prompt, **kwargs):
        assert arm_id == "codex_agent"
        assert "review this patch" in prompt
        assert kwargs["evidence_mode"] is True
        assert kwargs["timeout_s"] == 150
        return launcher.AgentArmResult(
            ok=True,
            receipt_id="codex-receipt-1",
            arm_id="codex_agent",
            status="EVIDENCE_CAPTURED",
            mode="evidence",
            output="Codex evidence: patch risk is low.",
            artifact_path=".sifta_state/agent_arm_receipts.jsonl",
        )

    monkeypatch.setattr(launcher, "ask_agent_arm", fake_ask_agent_arm)
    call = router.parse_tool_calls(
        "[TOOL_CALL: agent_arm_research | arm=codex_agent | prompt=review this patch | cost_justification=Alice wants a code-focused second pass]"
    )[0]
    out = router.execute_tool_call(call, owner_present=True, autonomous=True)

    assert out.executed is True
    assert out.result["arm_id"] == "codex_agent"
    assert out.result["receipt_id"] == "codex-receipt-1"
    assert "Codex evidence" in out.feedback_for_alice


def test_agent_arm_research_can_target_corvid_scout(monkeypatch):
    from System import swarm_agent_arm_launcher as launcher

    def fake_ask_agent_arm(arm_id, prompt, **kwargs):
        assert arm_id == "corvid_scout"
        assert "classify this owner request" in prompt
        assert kwargs["evidence_mode"] is True
        return launcher.AgentArmResult(
            ok=True,
            receipt_id="corvid-receipt-1",
            arm_id="corvid_scout",
            status="EVIDENCE_CAPTURED",
            mode="evidence",
            output="Corvid evidence: command intent.",
            artifact_path=".sifta_state/agent_arm_receipts.jsonl",
        )

    monkeypatch.setattr(launcher, "ask_agent_arm", fake_ask_agent_arm)
    call = router.parse_tool_calls(
        "[TOOL_CALL: agent_arm_research | arm=corvid_scout | prompt=classify this owner request | cost_justification=Alice wants a fast local scout pass]"
    )[0]
    out = router.execute_tool_call(call, owner_present=True, autonomous=True)

    assert out.executed is True
    assert out.result["arm_id"] == "corvid_scout"
    assert out.result["receipt_id"] == "corvid-receipt-1"
    assert "Corvid evidence" in out.feedback_for_alice


def test_agent_arm_failure_feedback_does_not_claim_evidence(monkeypatch):
    from System import swarm_agent_arm_launcher as launcher

    def fake_ask_agent_arm(_arm_id, _prompt, **_kwargs):
        return launcher.AgentArmResult(
            ok=False,
            receipt_id="timeout-receipt-1",
            arm_id="hermes_agent",
            status="TIMEOUT",
            mode="evidence",
            output="",
            artifact_path=".sifta_state/agent_arm_receipts.jsonl",
        )

    monkeypatch.setattr(launcher, "ask_agent_arm", fake_ask_agent_arm)
    call = router.parse_tool_calls(
        "[TOOL_CALL: agent_arm_research | prompt=compare router paths | cost_justification=Alice wants an arm receipt]"
    )[0]
    out = router.execute_tool_call(call, owner_present=True, autonomous=True)

    assert out.executed is False
    assert out.status == "EXEC_FAILED_TIMEOUT"
    assert "returned no usable evidence" in out.feedback_for_alice
    assert "evidence captured" not in out.feedback_for_alice


def test_build_execution_receipt_reply_includes_proof_tokens():
    result = router.ToolResult(
        tool_name="send_whatsapp",
        params={"target": "Carlton"},
        executed=True,
        result={
            "ok": True,
            "status": "SENT",
            "receipt_id": "123e4567-e89b-12d3-a456-426614174000",
            "intent_provenance": {"trace_hash": "abcdef1234567890"},
        },
        status="EXECUTED",
        feedback_for_alice="ok",
    )
    reply = router.build_execution_receipt_reply([result])
    assert "EXECUTION RECEIPTS" in reply
    assert "executor=deterministic_tool_router" in reply
    assert "123e4567-e89b-12d3-a456-426614174000" in reply


def test_build_execution_receipt_reply_falls_back_to_trace_label():
    result = router.ToolResult(
        tool_name="check_economy",
        params={},
        executed=False,
        result={"ok": False, "error": "probe failed"},
        status="EXEC_FAILED_UNKNOWN",
        feedback_for_alice="failed",
    )
    reply = router.build_execution_receipt_reply([result])
    assert "tool=check_economy" in reply
    assert "proof=tool_router_trace" in reply
