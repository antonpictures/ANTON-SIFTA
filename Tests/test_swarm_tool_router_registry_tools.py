from System.swarm_tool_router import execute_tool_call, parse_tool_calls


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
