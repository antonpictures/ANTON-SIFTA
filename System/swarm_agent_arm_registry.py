#!/usr/bin/env python3
"""Declarative registry for SIFTA governed agent arms.

This module is intentionally inert: it describes available arms and their
policy gates, but does not launch subprocesses. Runtime calls go through
``System.swarm_agent_arm_launcher`` so every attempt can be receipted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

try:
    from System.sifta_inference_defaults import CANONICAL_OLLAMA_FALLBACK
except Exception:
    CANONICAL_OLLAMA_FALLBACK = "alice-Q-m1-scout-2.3b-2.7gb:latest"


@dataclass(frozen=True)
class AgentArmSpec:
    arm_id: str
    display_name: str
    command: tuple[str, ...]
    model: str
    provider_base_url: str
    enabled: bool
    live_env_var: str
    default_toolsets: tuple[str, ...]
    max_turns: int
    capabilities: tuple[str, ...]
    notes: str

    def live_enabled(self, env: Mapping[str, str]) -> bool:
        return env.get(self.live_env_var) == "1"


HERMES_AGENT = AgentArmSpec(
    arm_id="hermes_agent",
    display_name="Hermes Agent",
    command=("hermes", "chat", "-Q"),
    model="alice-m5-cortex-8b-6.3gb:latest",
    provider_base_url="http://localhost:11434/v1",
    enabled=False,
    live_env_var="SIFTA_AGENT_ARMS_ENABLE",
    default_toolsets=("clarify",),
    max_turns=1,
    capabilities=("single_query_research", "evidence_output"),
    notes=(
        "Configured candidate arm only. Output is evidence, not Alice voice. "
        "Autonomous exposure requires SIFTA launcher receipts and Architect GO."
    ),
)

CODEX_AGENT = AgentArmSpec(
    arm_id="codex_agent",
    display_name="Codex CLI",
    command=(
        "codex",
        "exec",
        "--oss",
        "--local-provider",
        "ollama",
        "-m",
        "alice-m5-cortex-8b-6.3gb:latest",
        "--sandbox",
        "read-only",
        "--ephemeral",
        "--json",
    ),
    model="alice-m5-cortex-8b-6.3gb:latest",
    provider_base_url="ollama",
    enabled=False,
    live_env_var="SIFTA_AGENT_ARMS_ENABLE",
    default_toolsets=(),
    max_turns=1,
    capabilities=("single_query_code_review", "evidence_output", "read_only_workspace_reasoning"),
    notes=(
        "Configured read-only candidate arm. Runs codex exec with OSS/Ollama, "
        "read-only sandbox, ephemeral session, and SIFTA launcher receipts."
    ),
)

CORVID_SCOUT = AgentArmSpec(
    arm_id="corvid_scout",
    display_name="Corvid Scout",
    command=("internal:corvid_scout",),
    model=CANONICAL_OLLAMA_FALLBACK,
    provider_base_url="http://127.0.0.1:11434/api/chat",
    enabled=False,
    live_env_var="SIFTA_AGENT_ARMS_ENABLE",
    default_toolsets=("evidence", "summarize", "classify", "extract_intent"),
    max_turns=1,
    capabilities=(
        "fast_local_evidence",
        "bounded_summary",
        "intent_classification",
        "evidence_output",
    ),
    notes=(
        "Native SIFTA scout arm backed by SwarmCorvidApprentice. Runs inside "
        "the local Python/Ollama body and writes agent-arm receipts plus "
        "corvid_apprentice_trace rows."
    ),
)

_ARMS: dict[str, AgentArmSpec] = {
    HERMES_AGENT.arm_id: HERMES_AGENT,
    CODEX_AGENT.arm_id: CODEX_AGENT,
    CORVID_SCOUT.arm_id: CORVID_SCOUT,
}


def list_agent_arms() -> tuple[AgentArmSpec, ...]:
    return tuple(_ARMS.values())


def get_agent_arm(arm_id: str = "hermes_agent") -> AgentArmSpec:
    try:
        return _ARMS[arm_id]
    except KeyError as exc:
        raise ValueError(f"Unknown SIFTA agent arm: {arm_id}") from exc


def registry_summary() -> dict[str, dict[str, object]]:
    return {
        arm.arm_id: {
            "display_name": arm.display_name,
            "model": arm.model,
            "enabled": arm.enabled,
            "live_env_var": arm.live_env_var,
            "default_toolsets": list(arm.default_toolsets),
            "max_turns": arm.max_turns,
            "capabilities": list(arm.capabilities),
            "notes": arm.notes,
        }
        for arm in list_agent_arms()
    }
