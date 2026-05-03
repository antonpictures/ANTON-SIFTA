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
    assert "unnamed third person" in contract


def test_prompt_contract_conversation_cadence_is_not_absolute_list_ban():
    contract = minimal_runtime_contract()

    assert "CONVERSATION CADENCE" in contract
    assert "Use numbered lists or long markdown only when" in contract
    assert "NEVER use numbered lists" not in contract
    assert "customer-service endings" in contract
