from System.swarm_tool_router import execute_tool_call, parse_tool_calls
from types import SimpleNamespace


def test_tool_router_exposes_organ_registry_lookup(monkeypatch) -> None:
    import System.swarm_tool_router as router

    monkeypatch.setattr(router, "_charge_tool_execution", lambda *args, **kwargs: {"receipt_hash": "test"})
    calls = parse_tool_calls(
        "[TOOL_CALL: organ_registry_lookup | query=schedule camera health | cost_justification=map query to receipt-backed organs]"
    )
    result = execute_tool_call(calls[0], owner_present=True, autonomous=True)

    assert result.executed is True
    assert result.status == "EXECUTED"
    assert "organ_registry_lookup" in result.feedback_for_alice
    assert "schedule_journal" in result.feedback_for_alice or "vision_lane" in result.feedback_for_alice


def test_tool_router_exposes_self_improvement_status(monkeypatch) -> None:
    import System.swarm_tool_router as router

    monkeypatch.setattr(router, "_charge_tool_execution", lambda *args, **kwargs: {"receipt_hash": "test"})
    calls = parse_tool_calls(
        "[TOOL_CALL: self_improvement_status | cost_justification=verify cortex promotion safety]"
    )
    result = execute_tool_call(calls[0], owner_present=True, autonomous=True)

    assert result.executed is True
    assert result.status == "EXECUTED"
    assert "self_improvement_status" in result.feedback_for_alice


def test_tool_router_exposes_consumer_surface_status(tmp_path, monkeypatch) -> None:
    import System.swarm_tool_router as router

    state = tmp_path / ".sifta_state"
    state.mkdir()
    monkeypatch.setattr(router, "_STATE", state)
    monkeypatch.setattr(router, "_charge_tool_execution", lambda *args, **kwargs: {"receipt_hash": "test"})

    calls = parse_tool_calls(
        "[TOOL_CALL: consumer_surface_status | page=tools | cost_justification=show normal human surface]"
    )
    result = execute_tool_call(calls[0], owner_present=True, autonomous=True)

    assert result.executed is True
    assert result.status == "EXECUTED"
    assert "consumer_surface_status" in result.feedback_for_alice
    assert (state / "consumer_surface_trace.jsonl").exists()


def test_tool_router_hermes_read_file_executor_passes_path(tmp_path, monkeypatch) -> None:
    import System.swarm_file_organ as file_organ
    import System.swarm_kernel_process_table as kernel_process_table
    import System.swarm_tool_router as router

    state = tmp_path / ".sifta_state"
    state.mkdir()
    target = tmp_path / "demo.txt"
    target.write_text("hello from sifta")
    trace = state / "tool_router_trace.jsonl"

    monkeypatch.setattr(router, "_STATE", state)
    monkeypatch.setattr(router, "_TRACE_LEDGER", trace)
    monkeypatch.setattr(file_organ, "_TRACE", trace)
    monkeypatch.setattr(kernel_process_table, "_GLOBAL_TABLE", None)
    monkeypatch.setattr(router, "_charge_tool_execution", lambda *args, **kwargs: {"receipt_hash": "test"})

    calls = parse_tool_calls(
        f"[TOOL_CALL: read_file | path={target} | cost_justification=prove pywebview read wiring]"
    )
    result = execute_tool_call(calls[0], owner_present=True, autonomous=False)

    assert result.executed is True
    assert result.status == "EXECUTED"
    assert result.result["ok"] is True
    assert result.result["content"] == "hello from sifta"
    assert result.result["receipt_hash"]


def test_tool_router_skill_status_executor(monkeypatch) -> None:
    import System.swarm_tool_router as router

    fake_lib = SimpleNamespace(
        build_skill_index=lambda: [{"name": "alpha"}],
        validate_skill_contracts=lambda: {"passed": True, "issues": []},
        _SKILL_RECEIPTS=None,
    )
    monkeypatch.setattr(router, "_skill_library", lambda: fake_lib)
    monkeypatch.setattr(router, "_charge_tool_execution", lambda *args, **kwargs: {"receipt_hash": "test"})
    monkeypatch.setattr(router, "_kernel_tool_preflight", lambda *args, **kwargs: (None, None))

    calls = parse_tool_calls(
        "[TOOL_CALL: skill_library_status | cost_justification=inspect skill lane]"
    )
    result = execute_tool_call(calls[0], owner_present=True, autonomous=False)

    assert result.executed is True
    assert result.status == "EXECUTED"
    assert result.result["skills_count"] == 1


def test_tool_router_capability_field_status_executor(monkeypatch) -> None:
    import System.swarm_tool_router as router

    fake_cap = SimpleNamespace(
        to_alice_dict=lambda: {
            "name": "morning_briefing",
            "description": "Read overnight ledgers and summarize",
            "can_execute": False,
            "can_teach_compose": True,
        }
    )
    fake_caps = SimpleNamespace(
        rank_capabilities=lambda query, limit=24: [(3.5, fake_cap)],
        build_capability_index=lambda: [fake_cap],
        capability_field_summary=lambda: {
            "total": 1,
            "tools": 0,
            "skills": 1,
            "hybrids": 0,
            "learned_from_trace": 0,
            "sample": ["morning_briefing"],
        },
    )
    monkeypatch.setattr(router, "_capability_registry", lambda: fake_caps)
    monkeypatch.setattr(router, "_charge_tool_execution", lambda *args, **kwargs: {"receipt_hash": "test"})
    monkeypatch.setattr(router, "_kernel_tool_preflight", lambda *args, **kwargs: (None, None))

    calls = parse_tool_calls(
        "[TOOL_CALL: capability_field_status | query=what skills can you use | cost_justification=inspect unified capabilities]"
    )
    result = execute_tool_call(calls[0], owner_present=True, autonomous=False)

    assert result.executed is True
    assert result.status == "EXECUTED"
    assert result.result["summary"]["skills"] == 1
    assert result.result["capabilities"][0]["name"] == "morning_briefing"
    assert "capability_field_status" in result.feedback_for_alice


def test_tool_router_architect_memory_digest_executor(monkeypatch) -> None:
    import System.swarm_tool_router as router

    fake_digest = SimpleNamespace(
        build_architect_memory_digest=lambda **kwargs: {
            "ok": True,
            "status": "ARCHITECT_MEMORY_DIGEST_READY",
            "markdown": "# What George Taught Alice Today\n\n- receipts",
            "alice_summary": "architect_memory_digest generated",
            "latest_path": "/tmp/what_george_taught_alice_today.md",
            "receipt_id": "architect_memory_digest_test",
            "kwargs": kwargs,
        }
    )
    monkeypatch.setattr(router, "_architect_memory_digest_module", lambda: fake_digest)
    monkeypatch.setattr(router, "_charge_tool_execution", lambda *args, **kwargs: {"receipt_hash": "test"})
    monkeypatch.setattr(router, "_kernel_tool_preflight", lambda *args, **kwargs: (None, None))
    monkeypatch.setattr(router, "_cerebellum_preflight", lambda *args, **kwargs: {"delay_s": 0.0})
    monkeypatch.setattr(router, "_cerebellum_update", lambda *args, **kwargs: {"ok": True})

    calls = parse_tool_calls(
        "[TOOL_CALL: architect_memory_digest | period=today | max_items=7 | cost_justification=George asked for memory digest]"
    )
    result = execute_tool_call(calls[0], owner_present=True, autonomous=False)

    assert result.executed is True
    assert result.status == "EXECUTED"
    assert result.result["status"] == "ARCHITECT_MEMORY_DIGEST_READY"
    assert result.result["kwargs"]["period"] == "today"
    assert result.result["kwargs"]["max_items"] == 7
    assert "architect_memory_digest generated" in result.feedback_for_alice


def test_tool_router_alice_self_vector_executor(monkeypatch) -> None:
    import System.swarm_tool_router as router

    fake_vector = SimpleNamespace(
        build_alice_self_vector=lambda **kwargs: {
            "ok": True,
            "status": "ALICE_SELF_VECTOR_READY",
            "truth_label": "OBSERVED_ALICE_SELF_VECTOR_V1",
            "memory_entropy": 0.3,
            "identity_continuity": 0.4,
            "alice_summary": "alice_self_vector generated",
            "artifact_path": "/tmp/alice_self_vector.json",
            "receipt_id": "alice_self_vector_test",
            "kwargs": kwargs,
        }
    )
    monkeypatch.setattr(router, "_alice_self_vector_module", lambda: fake_vector)
    monkeypatch.setattr(router, "_charge_tool_execution", lambda *args, **kwargs: {"receipt_hash": "test"})
    monkeypatch.setattr(router, "_kernel_tool_preflight", lambda *args, **kwargs: (None, None))
    monkeypatch.setattr(router, "_cerebellum_preflight", lambda *args, **kwargs: {"delay_s": 0.0})
    monkeypatch.setattr(router, "_cerebellum_update", lambda *args, **kwargs: {"ok": True})

    calls = parse_tool_calls(
        "[TOOL_CALL: alice_self_vector | window_hours=48 | max_items=9 | cost_justification=George asked what Alice knows now]"
    )
    result = execute_tool_call(calls[0], owner_present=True, autonomous=False)

    assert result.executed is True
    assert result.status == "EXECUTED"
    assert result.result["status"] == "ALICE_SELF_VECTOR_READY"
    assert result.result["kwargs"]["window_hours"] == 48.0
    assert result.result["kwargs"]["max_items"] == 9
    assert "alice_self_vector generated" in result.feedback_for_alice


def test_tool_router_skill_pull_executor(monkeypatch) -> None:
    import System.swarm_tool_router as router

    captured = {}

    def fake_pull(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return {"status": "INSTALLED", "skill_name": "reader", "ok": True}

    fake_lib = SimpleNamespace(pull_skill_from_url=fake_pull)
    monkeypatch.setattr(router, "_skill_library", lambda: fake_lib)
    monkeypatch.setattr(router, "_charge_tool_execution", lambda *args, **kwargs: {"receipt_hash": "test"})
    monkeypatch.setattr(router, "_kernel_tool_preflight", lambda *args, **kwargs: (None, None))
    monkeypatch.setattr(router, "_cerebellum_preflight", lambda *args, **kwargs: {"delay_s": 0.0})

    calls = parse_tool_calls(
        "[TOOL_CALL: skill_pull | url=https://example.com/SKILL.md | life_context=reading tutor | cost_justification=Alice needs a reading skill]"
    )
    result = execute_tool_call(calls[0], owner_present=True, autonomous=False)

    assert result.executed is True
    assert result.result["skill_name"] == "reader"
    assert captured["url"] == "https://example.com/SKILL.md"
    assert captured["kwargs"]["life_context"] == "reading tutor"


def test_tool_router_skill_extract_executor(monkeypatch) -> None:
    import System.swarm_tool_router as router

    captured = {}

    def fake_extract(**kwargs):
        captured.update(kwargs)
        return {"status": "INSTALLED", "skill_name": "trace_reader", "ok": True}

    fake_lib = SimpleNamespace(extract_skill_from_trace=fake_extract)
    monkeypatch.setattr(router, "_skill_library", lambda: fake_lib)
    monkeypatch.setattr(router, "_charge_tool_execution", lambda *args, **kwargs: {"receipt_hash": "test"})
    monkeypatch.setattr(router, "_kernel_tool_preflight", lambda *args, **kwargs: (None, None))
    monkeypatch.setattr(router, "_cerebellum_preflight", lambda *args, **kwargs: {"delay_s": 0.0})

    calls = parse_tool_calls(
        "[TOOL_CALL: skill_extract_from_trace | trace_id=abc123 | name=trace_reader | cost_justification=save the successful trace as a skill]"
    )
    result = execute_tool_call(calls[0], owner_present=True, autonomous=False)

    assert result.executed is True
    assert result.result["skill_name"] == "trace_reader"
    assert captured["trace_id"] == "abc123"
    assert captured["name"] == "trace_reader"


def test_tool_router_skill_autoproposal_scan_executor(monkeypatch) -> None:
    import System.swarm_tool_router as router

    captured = {}

    fake_auto = SimpleNamespace(
        scan_field_for_skill_needs=lambda **kwargs: captured.setdefault(
            "result",
            {
                "ok": True,
                "status": "PROPOSED",
                "proposal_count": 2,
                "action_count": 0,
                "receipt_id": "auto-1",
            },
        )
        or captured["result"]
    )

    def fake_scan(**kwargs):
        captured["kwargs"] = kwargs
        return {
            "ok": True,
            "status": "PROPOSED",
            "proposal_count": 2,
            "action_count": 0,
            "receipt_id": "auto-1",
        }

    fake_auto.scan_field_for_skill_needs = fake_scan
    monkeypatch.setattr(router, "_skill_autoproposal", lambda: fake_auto)
    monkeypatch.setattr(router, "_charge_tool_execution", lambda *args, **kwargs: {"receipt_hash": "test"})
    monkeypatch.setattr(router, "_kernel_tool_preflight", lambda *args, **kwargs: (None, None))
    monkeypatch.setattr(router, "_cerebellum_preflight", lambda *args, **kwargs: {"delay_s": 0.0})

    calls = parse_tool_calls(
        "[TOOL_CALL: skill_autoproposal_scan | allow_pull=false | min_repeat=4 | cost_justification=let the field propose missing skills]"
    )
    result = execute_tool_call(calls[0], owner_present=True, autonomous=False)

    assert result.executed is True
    assert result.result["proposal_count"] == 2
    assert captured["kwargs"]["allow_pull"] is False
    assert captured["kwargs"]["min_repeat"] == 4
