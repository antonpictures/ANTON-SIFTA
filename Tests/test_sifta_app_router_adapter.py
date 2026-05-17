from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from System import sifta_app


@dataclass
class _FakeParsedToolCall:
    tool_name: str
    params: dict
    raw_match: str


@dataclass
class _FakeToolResult:
    tool_name: str
    params: dict
    executed: bool
    result: dict
    status: str
    feedback_for_alice: str


def _install_fake_router(monkeypatch, registry=None):
    calls = []

    def execute_tool_call(call, *, owner_present=False, autonomous=True, caller_pid=None):
        calls.append(
            {
                "call": call,
                "owner_present": owner_present,
                "autonomous": autonomous,
                "caller_pid": caller_pid,
            }
        )
        return _FakeToolResult(
            tool_name=call.tool_name,
            params=call.params,
            executed=True,
            result={"ok": True, "echo": call.params},
            status="EXECUTED",
            feedback_for_alice=f"executed {call.tool_name}",
        )

    fake_router = SimpleNamespace(
        TOOL_REGISTRY=registry
        or {
            "read_file": SimpleNamespace(
                name="read_file",
                description="Read file",
                required_params=("path",),
                optional_params=(),
            ),
            "run_terminal": SimpleNamespace(
                name="run_terminal",
                description="Run terminal command",
                required_params=("command",),
                optional_params=("cwd",),
            ),
        },
        ParsedToolCall=_FakeParsedToolCall,
        execute_tool_call=execute_tool_call,
    )
    monkeypatch.setattr(sifta_app, "router", fake_router)
    monkeypatch.setattr(sifta_app, "_IMPORT_ERROR", None)
    monkeypatch.setattr(sifta_app, "_stgm_balance", lambda: None)
    monkeypatch.setattr(sifta_app, "_router_trace_head", lambda: "tracehead")
    monkeypatch.setattr(sifta_app, "_ensure_sifta_app_kernel_pid", lambda _name: None)
    return calls, fake_router


def test_status_uses_tool_registry_count(monkeypatch):
    _install_fake_router(monkeypatch)

    status = sifta_app._status()

    assert status["tools_count"] == 2
    assert status["router_head"] == "tracehead"


def test_api_list_tools_uses_tool_registry(monkeypatch):
    _install_fake_router(monkeypatch)

    assert sifta_app.API().list_tools() == ["read_file", "run_terminal"]


def test_api_call_tool_uses_execute_tool_call_with_cost(monkeypatch):
    calls, _fake_router = _install_fake_router(monkeypatch)

    out = sifta_app.API().call_tool("read_file", {"path": "README.md"})

    assert out["executed"] is True
    assert out["ok"] is True
    assert calls[0]["call"].tool_name == "read_file"
    assert calls[0]["call"].params["path"] == "README.md"
    assert calls[0]["call"].params["cost_justification"]
    assert calls[0]["owner_present"] is True
    assert calls[0]["autonomous"] is False
    assert calls[0]["caller_pid"] == "sifta_app"


def test_chat_routes_read_and_run_through_adapter(monkeypatch):
    calls, _fake_router = _install_fake_router(monkeypatch)
    monkeypatch.setattr(
        sifta_app,
        "_brain_tool_route",
        lambda _text: (_ for _ in ()).throw(AssertionError("keyword path used LLM")),
    )

    read_out = sifta_app._chat("read README.md")
    run_out = sifta_app._chat("run echo hello")

    assert read_out["tool_name"] == "read_file"
    assert run_out["tool_name"] == "run_terminal"
    assert [entry["call"].tool_name for entry in calls] == ["read_file", "run_terminal"]
    assert calls[0]["call"].params["path"] == "README.md"
    assert calls[1]["call"].params["command"] == "echo hello"


def test_unknown_tool_returns_stable_error(monkeypatch):
    calls, _fake_router = _install_fake_router(monkeypatch)

    out = sifta_app.API().call_tool("missing_tool", {})

    assert out == {"error": "unknown_tool", "name": "missing_tool"}
    assert calls == []


def test_tool_specs_fallback_from_registry(monkeypatch):
    _install_fake_router(monkeypatch)

    specs = sifta_app.API().tool_specs()


def test_chat_llm_path_parses_tool_call_and_sets_chat_llm_justification(monkeypatch):
    calls = []

    def fake_execute(name, args, reason):
        calls.append({"name": name, "args": args, "reason": reason})
        return {"tool_name": name, "executed": True, "result": {"ok": True}}

    monkeypatch.setattr(sifta_app, "_execute_router_tool", fake_execute)

    monkeypatch.setattr(
        sifta_app,
        "_brain_tool_route",
        lambda _text: {
            "provider": "test",
            "model": "fake",
            "error": None,
            "text": "I'll list it.\n[TOOL_CALL: list_dir | path=.]",
        },
    )

    out = sifta_app._chat("what files are in the current dir?")

    assert len(calls) == 1
    assert calls[0]["name"] == "list_dir"
    assert calls[0]["args"].get("path") == "."
    assert calls[0]["args"].get("cost_justification") == "chat_llm"
    assert calls[0]["reason"] == "chat_llm"
    assert out["type"] == "chat_llm_tool_calls"
    assert out["provider"] == "test"


def test_chat_llm_plain_reply_is_json_safe(monkeypatch):
    _install_fake_router(monkeypatch)
    monkeypatch.setattr(
        sifta_app,
        "_brain_tool_route",
        lambda _text: {
            "provider": "test",
            "model": "fake",
            "error": None,
            "text": "This does not need a tool.",
        },
    )

    out = sifta_app._chat("say a calm sentence")

    assert out == {
        "type": "chat_llm_reply",
        "alice": "This does not need a tool.",
        "provider": "test",
        "model": "fake",
        "tool_results": [],
    }


def test_skill_api_status_pull_and_extract(monkeypatch):
    calls = []

    class FakeSkillLib:
        _SKILL_RECEIPTS = None

        @staticmethod
        def build_skill_index():
            return [{"name": "alpha", "description": "Use when alpha.", "procedure_file": "alpha/SKILL.md"}]

        @staticmethod
        def validate_skill_contracts():
            return {"passed": True, "issues": []}

        @staticmethod
        def pull_skill_from_url(url, **kwargs):
            calls.append(("url", url, kwargs))
            return {"status": "INSTALLED", "skill_name": "remote_alpha", "ok": True}

        @staticmethod
        def pull_skill_from_marketplace(marketplace, **kwargs):
            calls.append(("market", marketplace, kwargs))
            return {"status": "INSTALLED", "skill_name": "market_alpha", "ok": True}

        @staticmethod
        def extract_skill_from_trace(**kwargs):
            calls.append(("extract", kwargs))
            return {"status": "INSTALLED", "skill_name": "trace_alpha", "ok": True}

    monkeypatch.setattr(sifta_app, "_skill_library_module", lambda: FakeSkillLib)

    status = sifta_app.API().skill_status()
    pulled = sifta_app.API().pull_skill("https://example.com/SKILL.md", "alpha context")
    market = sifta_app.API().pull_skill("", "alpha context", "market.json", "alpha")
    extracted = sifta_app.API().extract_skill_from_trace("tool_router_trace.jsonl", "abc", "trace_alpha")

    assert status["skills_count"] == 1
    assert pulled["skill_name"] == "remote_alpha"
    assert market["skill_name"] == "market_alpha"
    assert extracted["skill_name"] == "trace_alpha"
    assert calls[0][0] == "url"
    assert calls[1][0] == "market"
    assert calls[2][0] == "extract"


def test_skill_api_autoproposal_scan(monkeypatch):
    import System.sifta_app as sifta_app

    captured = {}

    class FakeAuto:
        @staticmethod
        def scan_field_for_skill_needs(**kwargs):
            captured["kwargs"] = kwargs
            return {
                "ok": True,
                "status": "PROPOSED",
                "proposal_count": 1,
                "action_count": 0,
                "receipt_id": "auto-1",
            }

        @staticmethod
        def latest_proposals(limit=8):
            captured["limit"] = limit
            return [{"proposal_type": "EXTRACT_TRACE_SKILL", "title": "Repeat read"}]

    monkeypatch.setattr(sifta_app, "_skill_autoproposal_module", lambda: FakeAuto)

    scan = sifta_app.API().scan_field_for_skills("market.json", False, 4)
    proposals = sifta_app.API().skill_autoproposals(3)

    assert scan["proposal_count"] == 1
    assert captured["kwargs"]["marketplace"] == "market.json"
    assert captured["kwargs"]["min_repeat"] == 4
    assert proposals[0]["proposal_type"] == "EXTRACT_TRACE_SKILL"
    assert captured["limit"] == 3
