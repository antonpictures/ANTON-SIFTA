"""Round 86 tests — Qwen arm (fifth agent arm) registration and wiring.

Verifies that qwen_agent:
  - is registered in swarm_agent_arm_registry._ARMS with the right
    display name, Fireworks model id, and Fireworks AI base URL
  - is in the CORE_ARM_IDS / _ARM_IDS enumerations in flex diagnostic
    and arm-skills catalog
  - has a command builder branch in swarm_agent_arm_launcher that
    produces an explicit Fireworks OpenAI-compatible headless command
  - the covenant boot prefix is applied before the prompt (same as
    grok/claude/codex)
  - the tool router recognises qwen / qwen_agent / qwen_code / kimi
    aliases and resolves them all to qwen_agent
  - the registered-arms doctrine line includes qwen_agent
  - the streaming runner whitelist includes qwen_agent
  - the per-arm timeout table gives qwen_agent builder-class time
    (900s default, 1200s ceiling)
"""
from __future__ import annotations

from pathlib import Path

import pytest

from System import swarm_agent_arm_decision
from System import swarm_agent_arm_launcher
from System import swarm_agent_arm_registry as reg
from System import swarm_arm_flex_diagnostic
from System import swarm_arm_skills_catalog
from System import swarm_tool_router


# ─── Registry ──────────────────────────────────────────────────────────────


def test_qwen_agent_is_registered():
    """Round 97 update: default model is now gpt-oss-20b (cheap drafter).
    Kimi K2.6 is still callable but no longer the registry default."""
    arm = reg.get_agent_arm("qwen_agent")
    assert arm.arm_id == "qwen_agent"
    assert arm.enabled is True
    # The default model is now the gpt-oss-20b drafter — a Round 97 cost
    # decision. Kimi K2.6 stays available via FIREWORKS_KIMI_K2P6_MODEL.
    assert arm.model == "accounts/fireworks/models/gpt-oss-20b"
    assert arm.provider_base_url == "https://api.fireworks.ai/inference/v1"
    assert "Qwen Code" in arm.display_name
    # Display name still references the cortex behind the arm; either the
    # drafter (gpt-oss-20b) name or kimi for back-compat is acceptable.
    assert (
        "gpt-oss-20b" in arm.display_name
        or "kimi" in arm.display_name.lower()
    )


def test_qwen_agent_in_arms_dict():
    arm_ids = {a.arm_id for a in reg.list_agent_arms()}
    assert "qwen_agent" in arm_ids
    # All five external arms + corvid_scout present
    assert {"hermes_agent", "codex_agent", "grok_agent", "claude_agent", "qwen_agent", "corvid_scout"} <= arm_ids


def test_qwen_agent_in_flex_diagnostic():
    assert "qwen_agent" in swarm_arm_flex_diagnostic.CORE_ARM_IDS


def test_qwen_agent_in_skills_catalog_enumeration():
    assert "qwen_agent" in swarm_arm_skills_catalog._ARM_IDS


# ─── Command builder ───────────────────────────────────────────────────────


def test_build_command_for_qwen_agent_uses_headless_print():
    arm = reg.get_agent_arm("qwen_agent")
    cmd = swarm_agent_arm_launcher._build_command(arm, "test prompt body")
    assert cmd[0] == "qwen"
    assert "--bare" in cmd
    assert "--auth-type" in cmd
    assert cmd[cmd.index("--auth-type") + 1] == "openai"
    assert "--openai-base-url" in cmd
    assert cmd[cmd.index("--openai-base-url") + 1] == "https://api.fireworks.ai/inference/v1"
    assert "--model" in cmd
    # Round 97 default: gpt-oss-20b (cheap drafter). Kimi K2.6 is still
    # callable but no longer the default model id in the qwen command.
    assert cmd[cmd.index("--model") + 1] == "accounts/fireworks/models/gpt-oss-20b"
    assert "--approval-mode" in cmd
    assert cmd[cmd.index("--approval-mode") + 1] == "yolo"
    assert "-p" in cmd
    # Covenant boot prefix MUST be applied (same standing order as
    # grok/claude/codex per launcher line 479).
    prompt_arg = cmd[cmd.index("-p") + 1]
    assert "test prompt body" in prompt_arg
    # The covenant prefix carries the SIFTA boot ritual text; we don't
    # snapshot its exact bytes here, only that the prompt has been
    # PREFIXED (it starts with non-user text).
    assert not prompt_arg.startswith("test prompt body"), (
        "qwen_agent prompt must be prefixed with covenant boot text "
        "before the user prompt — same standing order as grok/claude/codex"
    )


def test_build_command_qwen_handles_empty_prompt():
    arm = reg.get_agent_arm("qwen_agent")
    cmd = swarm_agent_arm_launcher._build_command(arm, "")
    assert cmd[0] == "qwen"
    assert "-p" in cmd
    assert len(cmd[cmd.index("-p") + 1]) > 0  # covenant prefix non-empty


def test_qwen_command_does_not_embed_fireworks_secret(monkeypatch, tmp_path):
    secret_dir = tmp_path / "secrets"
    secret_dir.mkdir()
    (secret_dir / "fireworks_api_key").write_text("fw_SECRET_SHOULD_NOT_APPEAR\n", encoding="utf-8")
    monkeypatch.setattr(swarm_agent_arm_launcher, "_STATE", tmp_path)
    arm = reg.get_agent_arm("qwen_agent")
    cmd = swarm_agent_arm_launcher._build_command(arm, "secret test")
    assert "fw_SECRET_SHOULD_NOT_APPEAR" not in "\n".join(cmd)
    env = swarm_agent_arm_launcher._agent_arm_child_env(cmd)
    assert env["OPENAI_API_KEY"] == "fw_SECRET_SHOULD_NOT_APPEAR"
    assert env["FIREWORKS_API_KEY"] == "fw_SECRET_SHOULD_NOT_APPEAR"


# ─── Tool router aliasing ──────────────────────────────────────────────────


def test_tool_router_aliases_resolve_to_qwen_agent():
    # We can't import the alias dict directly (it's a local variable in
    # _exec_agent_arm_research), so we inspect the source for the
    # alias entries we just added.
    src = Path("System/swarm_tool_router.py").read_text(encoding="utf-8")
    for alias in ('"qwen": "qwen_agent"', '"qwen_agent": "qwen_agent"',
                  '"qwen_code": "qwen_agent"', '"kimi": "qwen_agent"'):
        assert alias in src, f"missing tool-router alias: {alias}"


def test_tool_router_doctrine_line_lists_qwen_agent():
    src = Path("System/swarm_tool_router.py").read_text(encoding="utf-8")
    assert "qwen_agent" in src
    # The exact doctrine line must include qwen_agent so Alice's
    # cortex sees the arm in her registered-arms summary.
    assert (
        "hermes_agent, codex_agent, corvid_scout, grok_agent, claude_agent, qwen_agent"
        in src
    )


# ─── Streaming runner + timeouts ───────────────────────────────────────────


def test_qwen_agent_in_streaming_runner_whitelist():
    src = Path("System/swarm_agent_arm_launcher.py").read_text(encoding="utf-8")
    # The streaming runner whitelist line MUST include qwen_agent so
    # the live PTY+stream path applies (same as grok/claude/codex).
    assert (
        '"hermes_agent", "grok_agent", "claude_agent", "codex_agent", "qwen_agent"'
        in src
    )


def test_qwen_agent_gets_builder_class_timeouts():
    """qwen builds code like claude/codex; it must get 900s default and
    1200s ceiling, not the 420/300 grok-class numbers."""
    src = Path("System/swarm_tool_router.py").read_text(encoding="utf-8")
    assert '"qwen_agent": "900"' in src
    # Ceiling set must include qwen_agent (alongside claude/codex/hermes; the
    # set may also include other builder-class arms added in later rounds).
    assert "qwen_agent" in src
    # Locate the builder-class ceiling set and verify the four core builders
    # are all present.
    import re as _re
    m = _re.search(r'arm in \{([^}]+)\}', src)
    assert m is not None, "could not locate the builder-class ceiling set"
    members = m.group(1)
    for required in ("claude_agent", "codex_agent", "hermes_agent", "qwen_agent"):
        assert required in members, f"{required} missing from ceiling set"


# ─── Decision-layer timeout ─────────────────────────────────────────────────


def test_qwen_agent_in_decision_timeout_table():
    src = Path("System/swarm_agent_arm_decision.py").read_text(encoding="utf-8")
    # Round 100 (2026-05-28): bumped from 150s to 300s for builder arms.
    assert '"qwen_agent": 300' in src


# ─── No regressions: every other arm still wired ───────────────────────────


def test_existing_arms_untouched():
    for arm_id in ("hermes_agent", "codex_agent", "grok_agent", "claude_agent", "corvid_scout"):
        arm = reg.get_agent_arm(arm_id)
        assert arm.enabled is True or arm_id == "corvid_scout", (
            f"{arm_id} should remain enabled after Round 86 surgery"
        )
        # corvid_scout was enabled per George's "arms are ALWAYS enabled"
        # standing order; confirm it stayed enabled too
        if arm_id == "corvid_scout":
            assert arm.enabled is True
