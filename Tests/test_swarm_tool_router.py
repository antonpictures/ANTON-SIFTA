from __future__ import annotations

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


def _send_call(extra: str = "") -> router.ParsedToolCall:
    suffix = f" | {extra}" if extra else ""
    return router.parse_tool_calls(
        f"[TOOL_CALL: send_whatsapp | target=Carlton | text=hello{suffix}]"
    )[0]


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

    assert "owner_consent=true" in prompt
    assert "records a silence/refusal receipt" in prompt


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
