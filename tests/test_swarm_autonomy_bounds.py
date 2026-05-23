from __future__ import annotations

from System.swarm_autonomy_bounds import (
    SCHEMA_LITERAL,
    evaluate_autonomy_expansion,
    policy_summary,
)


def test_autonomy_boundary_blocks_physical_device_control_without_go() -> None:
    decision = evaluate_autonomy_expansion("physical_device_control")

    assert decision.schema == SCHEMA_LITERAL
    assert decision.allowed is False
    assert "requires explicit Architect GO" in decision.reason


def test_autonomy_boundary_requires_covenant_section_even_with_go() -> None:
    decision = evaluate_autonomy_expansion("cross_node_state_write", explicit_go=True)

    assert decision.allowed is False
    assert decision.covenant_section is None


def test_autonomy_boundary_allows_only_with_go_and_section() -> None:
    decision = evaluate_autonomy_expansion(
        "core_self_modification",
        explicit_go=True,
        covenant_section="IDE_BOOT_COVENANT.md §14.99",
    )

    assert decision.allowed is True
    assert decision.covenant_section == "IDE_BOOT_COVENANT.md §14.99"


def test_autonomy_boundary_allows_non_boundary_actions() -> None:
    decision = evaluate_autonomy_expansion("ledger_only_motor_policy")

    assert decision.allowed is True
    assert "not listed" in decision.reason


def test_policy_summary_exposes_known_boundaries() -> None:
    summary = policy_summary()

    assert summary["schema"] == SCHEMA_LITERAL
    assert "outside_repo_execution" in summary["out_of_bounds"]
