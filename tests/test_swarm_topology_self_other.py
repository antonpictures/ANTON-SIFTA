from __future__ import annotations


def test_self_other_owner_identity_comes_from_kernel(monkeypatch) -> None:
    import System.swarm_kernel_identity as kernel_identity
    from System.swarm_topology_self_other import classify_kind

    monkeypatch.setattr(kernel_identity, "owner_name", lambda: "Layer One Owner")
    monkeypatch.setattr(kernel_identity, "owner_display_name", lambda default="": "Layer One Owner")

    assert classify_kind("Layer One Owner") == "owner_operator_environment"
    assert classify_kind("owner") == "owner_operator_environment"
    assert classify_kind("George") == "external_tool_cortex"


def test_preanswer_guard_forces_topology_answer(monkeypatch) -> None:
    import System.swarm_kernel_identity as kernel_identity
    from System.swarm_topology_self_other import preanswer_guard

    monkeypatch.setattr(kernel_identity, "owner_name", lambda: "Layer One Owner")
    monkeypatch.setattr(kernel_identity, "owner_display_name", lambda default="": "Layer One Owner")

    guard = preanswer_guard("Alice, who are you and who is Grok?")

    assert guard["attention"]["is_identity_question"] is True
    assert "force_answer" in guard
    assert "I am Alice" in guard["force_answer"]
    assert "grok is an external tool/cortex surface" in guard["force_answer"]
    assert "Layer One Owner = OWNER" in guard["mandatory_preamble"]
    assert "Claude Code" in guard["mandatory_preamble"]
    assert "George" not in guard["mandatory_preamble"]


def test_preanswer_guard_does_not_force_grok_action_requests(monkeypatch) -> None:
    import System.swarm_kernel_identity as kernel_identity
    from System.swarm_topology_self_other import preanswer_guard

    monkeypatch.setattr(kernel_identity, "owner_name", lambda: "Layer One Owner")
    monkeypatch.setattr(kernel_identity, "owner_display_name", lambda default="": "Layer One Owner")

    for text in (
        "ask grok how are your organs wired",
        "ask Claude Code to inspect SIFTA and report one renderer risk",
        "i used my voice, i meant grok, start grok cli now",
        "i want you to be able to ask grok and grok to print the answer here in global chat as proof",
    ):
        guard = preanswer_guard(text)

        assert guard.get("action_intent") is True
        assert "force_answer" not in guard


def test_preanswer_guard_does_not_force_identity_reflex_on_awareness_question(monkeypatch) -> None:
    import System.swarm_kernel_identity as kernel_identity
    from System.swarm_topology_self_other import preanswer_guard

    monkeypatch.setattr(kernel_identity, "owner_name", lambda: "Layer One Owner")
    monkeypatch.setattr(kernel_identity, "owner_display_name", lambda default="": "Layer One Owner")

    guard = preanswer_guard("are you aware of what just happened?")
    assert "force_answer" not in guard


def test_claude_code_is_external_tool_cortex() -> None:
    from System.swarm_topology_self_other import classify_kind, describe_entity, is_self

    assert classify_kind("Claude Code") == "external_tool_cortex"
    assert classify_kind("claude_code") == "external_tool_cortex"
    assert is_self("Claude Code") is False
    assert "external tool/cortex surface" in describe_entity("Claude Code")
