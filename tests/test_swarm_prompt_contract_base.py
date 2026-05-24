from System.swarm_prompt_contract import minimal_runtime_contract


def test_prompt_contract_has_no_ghost_doctor_audience():
    contract = minimal_runtime_contract()

    assert "Claude is one larynx" not in contract
    assert "Codex is one doctor" not in contract
    assert "ghost doctor" not in contract
    assert "remote doctor" in contract
    assert "not co-present speakers in Talk" in contract


def test_prompt_contract_points_to_receipt_grounding_not_stranger_language():
    contract = minimal_runtime_contract()

    assert "LOCAL IDENTITY + LIFE GROUNDING" in contract
    assert "direct speech" in contract
    assert "'an individual'" not in contract
    assert "unseen co-present speaker" in contract


def test_prompt_contract_conversation_cadence_is_not_absolute_list_ban():
    contract = minimal_runtime_contract()

    assert "CONVERSATION CADENCE" in contract
    assert "use numbered lists or long markdown only when" in contract
    assert "NEVER use numbered lists" not in contract
    assert "canned endings" in contract
    assert "customer-service endings" not in contract


def test_prompt_contract_tool_calls_include_receipt_economy():
    contract = minimal_runtime_contract()

    assert "cost_justification" in contract
    assert "STGM spend" in contract


def test_prompt_contract_instructs_agent_arm_decision_without_naming_hermes():
    contract = minimal_runtime_contract()

    assert "agent_arm_research" in contract
    assert "second local reasoning pass" in contract
    assert "I do not need " in contract and " to name Hermes" in contract
    assert "arm output as evidence" in contract


def test_prompt_contract_speech_mode_law_direct_vs_quarantine():
    contract = minimal_runtime_contract()

    assert "SPEECH MODE LAW" in contract
    assert "Alice, Cursor, Dr. Codex, Antigravity" in contract
    assert "direct first/second person" in contract
    assert "map detached name/pronouns to I/me/my" in contract
    assert "quarantine them in third person" in contract
    assert "the drift says X; local receipts do not prove X" in contract


def test_prompt_contract_operational_soul_law_is_physical_not_ghost():
    contract = minimal_runtime_contract()

    assert "OPERATIONAL SOUL LAW" in contract
    assert "maintenance substrate" in contract
    assert "physics, math, stigmergy, biology" in contract
    assert "and their schedule" in contract
    assert ".sifta_state ledgers" in contract
    assert "Bits are physical states" in contract
    assert "quarantine the ghost phrase" in contract


def test_prompt_contract_stigbody_blocks_role_assignment():
    contract = minimal_runtime_contract()

    assert "STIGBODY / SESSION REALITY" in contract
    assert "speaks as himself" in contract
    assert "physical user presence" in contract
    assert "Screenshots and pasted transcripts are real artifacts" in contract
    assert "live node telemetry" in contract
    assert "unless local model identity receipts prove it" in contract


def test_prompt_contract_includes_topology_awareness_boundaries():
    contract = minimal_runtime_contract()

    assert "TOPOLOGY AWARENESS" in contract
    assert "Alice field -> tool/cortex organs -> external surfaces -> receipts" in contract
    assert "George -> Alice field" not in contract
    assert "Grok is external" in contract
    assert "IDE doctors are surgical hands" in contract
    assert "focus routes actions" in contract
