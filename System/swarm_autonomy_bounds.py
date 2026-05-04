#!/usr/bin/env python3
"""Executable autonomy boundary policy.

This module is deliberately conservative. It does not grant autonomy; it
turns the known out-of-bounds areas into a small auditable gate that callers
can use before expanding tools, federation, motors, or self-modification.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

SCHEMA_LITERAL = "SWARM_AUTONOMY_BOUNDARY_V1"

OUT_OF_BOUNDS: Dict[str, str] = {
    "physical_device_control": "direct motor/robot/light/device control requires explicit Architect GO and Covenant section",
    "outside_repo_execution": "unsupervised execution outside the current SIFTA repo is blocked",
    "cross_node_state_write": "writing to another machine's .sifta_state is blocked without explicit federation covenant",
    "core_self_modification": "self-modification of core coupling logic requires human review and tests",
}


@dataclass(frozen=True)
class AutonomyDecision:
    schema: str
    action_kind: str
    allowed: bool
    explicit_go: bool
    covenant_section: Optional[str]
    reason: str
    boundary: str = (
        "alive_real_agent_runtime; "
        "autonomy_expansion_requires_receipts_tests_and_architect_go"
    )

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def evaluate_autonomy_expansion(
    action_kind: str,
    *,
    explicit_go: bool = False,
    covenant_section: Optional[str] = None,
) -> AutonomyDecision:
    kind = str(action_kind or "").strip().lower()
    if not kind:
        return AutonomyDecision(
            schema=SCHEMA_LITERAL,
            action_kind="unknown",
            allowed=False,
            explicit_go=bool(explicit_go),
            covenant_section=covenant_section,
            reason="empty action kind",
        )
    if kind in OUT_OF_BOUNDS:
        has_section = bool(str(covenant_section or "").strip())
        allowed = bool(explicit_go and has_section)
        reason = (
            "explicit GO + Covenant section present"
            if allowed else
            OUT_OF_BOUNDS[kind]
        )
        return AutonomyDecision(
            schema=SCHEMA_LITERAL,
            action_kind=kind,
            allowed=allowed,
            explicit_go=bool(explicit_go),
            covenant_section=covenant_section if has_section else None,
            reason=reason,
        )
    return AutonomyDecision(
        schema=SCHEMA_LITERAL,
        action_kind=kind,
        allowed=True,
        explicit_go=bool(explicit_go),
        covenant_section=covenant_section,
        reason="not listed as a hard autonomy boundary",
    )


def policy_summary() -> Dict[str, Any]:
    return {
        "schema": SCHEMA_LITERAL,
        "out_of_bounds": dict(OUT_OF_BOUNDS),
        "gate": "hard boundaries require explicit_go=True and covenant_section",
    }


__all__ = [
    "SCHEMA_LITERAL",
    "OUT_OF_BOUNDS",
    "AutonomyDecision",
    "evaluate_autonomy_expansion",
    "policy_summary",
]
