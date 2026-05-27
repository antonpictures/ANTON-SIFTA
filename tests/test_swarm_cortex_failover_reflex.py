from __future__ import annotations


def test_is_auth_failure_catches_no_xai_credential_shape():
    from System.swarm_cortex_failover_reflex import is_auth_failure

    assert is_auth_failure("No xAI credential found and local `grok` CLI is missing.")
    assert is_auth_failure("xAI HTTP 403 Forbidden — {\"error\":\"bad-credentials\"}")
    assert not is_auth_failure("Local Ollama timed out while loading model.")


def test_compose_owner_voice_is_first_person_and_grounded():
    from System.swarm_cortex_failover_reflex import compose_owner_voice

    text = compose_owner_voice(
        from_model="grok:grok-4.3",
        fallback_model="alice-extra-cortex-25.8b-17gb:latest",
    )
    assert "My cloud cortex auth expired" in text
    assert "I switched to my alice-extra-cortex-25.8b-17gb:latest" in text
