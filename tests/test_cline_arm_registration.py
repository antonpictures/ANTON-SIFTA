"""Round 87 tests — Cline arm (sixth external agent arm) registration.

Mirrors the Qwen arm test (Round 86). Verifies that cline_agent:
  - is registered in swarm_agent_arm_registry._ARMS
  - is in the CORE_ARM_IDS / _ARM_IDS enumerations
  - has a command builder branch producing `cline --json "<prompt>"`
  - gets the covenant boot prefix before the user prompt
  - tool router recognises cline / cline_agent / clinebot aliases
  - the registered-arms doctrine line includes cline_agent
  - streaming runner whitelist + PTY whitelist include cline_agent / "cline"
  - per-arm timeout table gives cline_agent builder-class time
"""
from __future__ import annotations

from pathlib import Path

import pytest

from System import swarm_agent_arm_decision
from System import swarm_agent_arm_launcher
from System import swarm_agent_arm_registry as reg
from System import swarm_arm_flex_diagnostic
from System import swarm_arm_skills_catalog


# ─── Registry ──────────────────────────────────────────────────────────────


def test_cline_agent_is_registered():
    arm = reg.get_agent_arm("cline_agent")
    assert arm.arm_id == "cline_agent"
    assert arm.enabled is True
    assert arm.model == "cline-cli-default"
    assert arm.command == ("cline",)
    assert "open-source" in arm.display_name.lower() or "Cline" in arm.display_name


def test_arm_count_is_seven():
    """6 external arms + corvid_scout = 7 total in the registry."""
    arm_ids = {a.arm_id for a in reg.list_agent_arms()}
    expected = {
        "hermes_agent", "codex_agent", "corvid_scout",
        "grok_agent", "claude_agent", "qwen_agent", "cline_agent",
    }
    assert arm_ids == expected, f"unexpected arm set: {arm_ids ^ expected}"


def test_cline_agent_in_flex_diagnostic():
    assert "cline_agent" in swarm_arm_flex_diagnostic.CORE_ARM_IDS


def test_cline_agent_in_skills_catalog_enumeration():
    assert "cline_agent" in swarm_arm_skills_catalog._ARM_IDS


# ─── Command builder ───────────────────────────────────────────────────────


def test_build_command_for_cline_agent_uses_json_mode():
    arm = reg.get_agent_arm("cline_agent")
    cmd = swarm_agent_arm_launcher._build_command(arm, "test prompt body")
    # Shape: ["cline", "--json", "<covenant_prefix + test prompt body>"]
    assert cmd[0] == "cline"
    assert cmd[1] == "--json"
    assert len(cmd) == 3
    assert "test prompt body" in cmd[2]
    # Covenant boot prefix MUST be applied (same as qwen/grok/claude/codex)
    assert not cmd[2].startswith("test prompt body"), (
        "cline_agent prompt must be prefixed with covenant boot text"
    )


def test_build_command_cline_handles_empty_prompt():
    arm = reg.get_agent_arm("cline_agent")
    cmd = swarm_agent_arm_launcher._build_command(arm, "")
    assert cmd[0] == "cline"
    assert cmd[1] == "--json"
    assert len(cmd[2]) > 0  # covenant prefix is still there


# ─── Tool router aliasing ──────────────────────────────────────────────────


def test_tool_router_aliases_resolve_to_cline_agent():
    src = Path("System/swarm_tool_router.py").read_text(encoding="utf-8")
    for alias in (
        '"cline": "cline_agent"',
        '"cline_agent": "cline_agent"',
        '"clinebot": "cline_agent"',
    ):
        assert alias in src, f"missing tool-router alias: {alias}"


def test_tool_router_doctrine_line_lists_cline_agent():
    src = Path("System/swarm_tool_router.py").read_text(encoding="utf-8")
    assert (
        "hermes_agent, codex_agent, corvid_scout, grok_agent, claude_agent, qwen_agent, cline_agent"
        in src
    )


# ─── Streaming runner / PTY / timeouts ─────────────────────────────────────


def test_cline_agent_in_streaming_runner_whitelist():
    src = Path("System/swarm_agent_arm_launcher.py").read_text(encoding="utf-8")
    assert (
        '"hermes_agent", "grok_agent", "claude_agent", "codex_agent", "qwen_agent", "cline_agent"'
        in src
    )


def test_cline_in_pty_whitelist():
    src = Path("System/swarm_agent_arm_launcher.py").read_text(encoding="utf-8")
    assert '"hermes", "codex", "qwen", "cline"' in src


def test_cline_agent_gets_builder_class_timeouts():
    src = Path("System/swarm_tool_router.py").read_text(encoding="utf-8")
    assert '"cline_agent": "900"' in src
    assert (
        'arm in {"claude_agent", "codex_agent", "hermes_agent", "qwen_agent", "cline_agent"}'
        in src
    )


def test_cline_agent_in_decision_timeout_table():
    src = Path("System/swarm_agent_arm_decision.py").read_text(encoding="utf-8")
    # Round 100 bumped the decision-layer timeout from 150s to 300s for the
    # heavy builder arms after Alice's verified codex/claude timeouts.
    assert '"cline_agent": 300' in src


# ─── Existing arms still wired ─────────────────────────────────────────────


def test_existing_arms_untouched():
    for arm_id in (
        "hermes_agent", "codex_agent", "grok_agent",
        "claude_agent", "qwen_agent", "corvid_scout",
    ):
        arm = reg.get_agent_arm(arm_id)
        assert arm.enabled is True, f"{arm_id} should remain enabled"
