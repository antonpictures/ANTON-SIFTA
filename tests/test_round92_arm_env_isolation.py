"""Round 92 tests — provider env isolation between arms.

The bug Codex flagged before its credit cap: ``qwen_fireworks_child_env``
used ``setdefault("OPENAI_API_KEY", key)`` which is a no-op if the parent
process already has ``OPENAI_API_KEY`` set from Codex OAuth, Cline's
ChatGPT-account session, or any earlier OpenAI-compatible call. The Qwen
subprocess would then dispatch to Fireworks with the *wrong* key and
either 401 silently or route to the wrong account.

This file proves the fix:
  - When the parent env has a stale OPENAI_API_KEY, the Qwen child env
    OVERWRITES it with the Fireworks key (not setdefault).
  - When OPENAI_API_BASE / OPENAI_BASE_URL are set in the parent env,
    they're stripped from the Qwen child env so `--openai-base-url`
    on the command line is authoritative.
  - Cline child env strips FIREWORKS_API_KEY so it doesn't leak into a
    different provider.
  - If the parent's OPENAI_API_KEY is literally the Fireworks key
    (because Qwen ran earlier in this process), Cline's child env
    drops it so Cline reads its own credentials.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from System import swarm_fireworks_qwen_config as fw
from System import swarm_agent_arm_launcher as launcher


# ─── Qwen env injection: bug Codex flagged ─────────────────────────────────


def test_qwen_env_overwrites_stale_openai_key(tmp_path: Path):
    """The exact bug: parent has stale OPENAI_API_KEY from another
    provider; Qwen MUST get the Fireworks key, not the stale one."""
    state = tmp_path / ".sifta_state"
    state.mkdir(parents=True, exist_ok=True)
    secrets = state / "secrets"
    secrets.mkdir()
    (secrets / "fireworks_api_key").write_text("fw_FIREWORKS_KEY_xxx\n", encoding="utf-8")

    base_env = {"OPENAI_API_KEY": "sk-STALE_CODEX_OAUTH_TOKEN", "PATH": "/usr/bin"}
    env = fw.qwen_fireworks_child_env(base_env, state_dir=state)

    # The fix: Fireworks key wins, stale Codex/OpenAI token is overwritten.
    assert env["OPENAI_API_KEY"] == "fw_FIREWORKS_KEY_xxx"
    assert env["FIREWORKS_API_KEY"] == "fw_FIREWORKS_KEY_xxx"
    assert env["OPENAI_API_KEY"] != "sk-STALE_CODEX_OAUTH_TOKEN"


def test_qwen_env_strips_stale_base_url(tmp_path: Path):
    """If the parent set OPENAI_API_BASE for another provider (e.g. a
    Together or local OpenAI proxy), Qwen's --openai-base-url on the
    command line must be the only authoritative endpoint."""
    state = tmp_path / ".sifta_state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "secrets").mkdir()
    (state / "secrets" / "fireworks_api_key").write_text("fw_key\n", encoding="utf-8")

    base_env = {
        "OPENAI_API_BASE": "https://other-provider.example.com/v1",
        "OPENAI_BASE_URL": "https://yet-another.example.com/v1",
        "OPENAI_API_TYPE": "azure",
    }
    env = fw.qwen_fireworks_child_env(base_env, state_dir=state)
    assert "OPENAI_API_BASE" not in env
    assert "OPENAI_BASE_URL" not in env
    assert "OPENAI_API_TYPE" not in env


def test_qwen_env_with_no_stale_key_still_sets_correctly(tmp_path: Path):
    """Sanity: when the parent doesn't have an OPENAI_API_KEY, the
    Fireworks key still lands (not just the no-op case)."""
    state = tmp_path / ".sifta_state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "secrets").mkdir()
    (state / "secrets" / "fireworks_api_key").write_text("fw_clean_key\n", encoding="utf-8")

    env = fw.qwen_fireworks_child_env({"PATH": "/usr/bin"}, state_dir=state)
    assert env["OPENAI_API_KEY"] == "fw_clean_key"
    assert env["FIREWORKS_API_KEY"] == "fw_clean_key"


def test_qwen_env_with_no_fireworks_key_does_not_overwrite(tmp_path: Path):
    """If there's no Fireworks key on disk, don't clobber whatever the
    parent has — let Qwen fail honestly rather than corrupt a working
    env. (This is the only place setdefault-shape behaviour is correct.)"""
    state = tmp_path / ".sifta_state"
    state.mkdir(parents=True, exist_ok=True)
    # No secrets file created.

    base_env = {"OPENAI_API_KEY": "sk-some-other-provider"}
    env = fw.qwen_fireworks_child_env(base_env, state_dir=state)
    # Without a Fireworks key, the function doesn't touch OPENAI_API_KEY.
    assert env["OPENAI_API_KEY"] == "sk-some-other-provider"


# ─── Cline env isolation ───────────────────────────────────────────────────


def test_cline_env_strips_fireworks_key(tmp_path: Path, monkeypatch):
    """Cline reads its own auth (cline auth). The Fireworks key MUST NOT
    leak into Cline's child env."""
    monkeypatch.setattr(launcher, "_STATE", tmp_path / ".sifta_state")
    secrets = tmp_path / ".sifta_state" / "secrets"
    secrets.mkdir(parents=True)
    (secrets / "fireworks_api_key").write_text("fw_qwen_only\n", encoding="utf-8")

    monkeypatch.setenv("FIREWORKS_API_KEY", "fw_qwen_only")
    monkeypatch.setenv("OPENAI_API_KEY", "fw_qwen_only")  # bleed-through case
    monkeypatch.setenv("QWEN_CODE_SUPPRESS_YOLO_WARNING", "1")

    env = launcher._agent_arm_child_env(["cline", "--json", "test"])

    # Fireworks-specific keys must be gone from Cline's env
    assert "FIREWORKS_API_KEY" not in env
    assert "QWEN_CODE_SUPPRESS_YOLO_WARNING" not in env
    # OPENAI_API_KEY that matched the Fireworks key must be removed so
    # Cline reads its own credentials.
    assert env.get("OPENAI_API_KEY") != "fw_qwen_only"


def test_cline_env_keeps_unrelated_openai_key(tmp_path: Path, monkeypatch):
    """If OPENAI_API_KEY in the parent is NOT the Fireworks key (e.g. a
    real OpenAI org token the user wants Cline to use), keep it."""
    monkeypatch.setattr(launcher, "_STATE", tmp_path / ".sifta_state")
    secrets = tmp_path / ".sifta_state" / "secrets"
    secrets.mkdir(parents=True)
    (secrets / "fireworks_api_key").write_text("fw_qwen_only\n", encoding="utf-8")

    monkeypatch.setenv("OPENAI_API_KEY", "sk-USER_OWN_OPENAI_TOKEN")
    monkeypatch.delenv("FIREWORKS_API_KEY", raising=False)
    monkeypatch.delenv("QWEN_CODE_SUPPRESS_YOLO_WARNING", raising=False)

    env = launcher._agent_arm_child_env(["cline", "--json", "test"])

    # The user's own OpenAI token survives — it's not the Fireworks key.
    assert env["OPENAI_API_KEY"] == "sk-USER_OWN_OPENAI_TOKEN"


# ─── Non-qwen, non-cline arms get raw env (no shaping) ─────────────────────


def test_codex_arm_env_unchanged(monkeypatch):
    """Codex arm relies on its own OAuth flow — _agent_arm_child_env
    should return the parent env untouched for codex/claude/grok/hermes."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-codex-oauth")
    env = launcher._agent_arm_child_env(["codex", "exec", "--full-auto", "prompt"])
    assert env.get("OPENAI_API_KEY") == "sk-codex-oauth"


# ─── Secret never leaks into command argv ─────────────────────────────────


def test_qwen_command_does_not_carry_secret(tmp_path: Path):
    """Defense-in-depth: even if env injection has a bug, the secret must
    never appear in the argv (subprocess receipts would log it)."""
    cmd = fw.qwen_fireworks_command("hello", model=fw.FIREWORKS_KIMI_K2P6_MODEL)
    joined = "\n".join(cmd)
    assert "fw_" not in joined  # any Fireworks key starts with fw_
    assert "sk-" not in joined  # any OpenAI-style key starts with sk-
    assert "Bearer" not in joined
    # The model id IS in the command — that's expected.
    assert fw.FIREWORKS_KIMI_K2P6_MODEL in joined
