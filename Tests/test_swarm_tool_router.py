from __future__ import annotations

import json

import pytest

from System import swarm_tool_router as router
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
