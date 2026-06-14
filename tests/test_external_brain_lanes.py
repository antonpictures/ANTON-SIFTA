"""tests/test_external_brain_lanes.py — r984 external-brain family proof.

George 2026-06-11: "thinking with cline, i want to know what llm too …
then we add mimo to the cortex list … rename this just Qwen → now using
kimi API on fireworks." Three truths under test:
  1. the probe organ generalized to lanes (cline + mimo) without breaking
     the cline wrappers,
  2. cortex_brain_label tells the honest upstream brain for any tag,
  3. /cortex list and /cortex llm carry those truths.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from System.swarm_cline_settings_probe import (  # noqa: E402
    cortex_brain_label,
    latest_brain_block,
    latest_brain_row,
    probe_cline_settings,
    probe_external_brain,
)


def test_mimo_lane_no_config_is_recorded_not_invented(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    state = tmp_path / "state"
    row = probe_external_brain("mimo", home=home, state_dir=state)
    assert row["lane"] == "mimo"
    assert row["status"] == "no_config_found"
    assert row["ledger_write"] == "ok"
    assert cortex_brain_label("mimo:mimo-cli-default", state_dir=state) == "upstream picker (no_config_found)"
    on_disk = (state / "external_brain_settings.jsonl").read_text().strip().splitlines()
    assert json.loads(on_disk[-1])["lane"] == "mimo"


def test_mimo_lane_reads_config_and_block(tmp_path):
    home = tmp_path / "home"
    (home / ".mimo").mkdir(parents=True)
    (home / ".mimo" / "config.json").write_text(
        json.dumps({"provider": "openrouter", "model": "mimo-large", "reasoningLevel": "high"})
    )
    state = tmp_path / "state"
    row = probe_external_brain("mimo", home=home, state_dir=state)
    assert row["status"] == "ok"
    assert row["provider"] == "openrouter"
    assert row["model"] == "mimo-large"
    block = latest_brain_block("mimo", state_dir=state)
    assert block.startswith("MIMO EXTERNAL BRAIN:")
    assert "provider=openrouter" in block and "model=mimo-large" in block


def test_mimo_lane_reads_xiaomi_auth_without_openrouter_overclaim(tmp_path):
    home = tmp_path / "home"
    auth_dir = home / ".local" / "share" / "mimocode"
    auth_dir.mkdir(parents=True)
    (auth_dir / "auth.json").write_text(
        json.dumps(
            {
                "xiaomi": {
                    "type": "api",
                    "key": "redacted-test-key",
                    "metadata": {"base_url": "https://token-plan-sgp.xiaomimimo.com/v1"},
                }
            }
        )
    )
    state = tmp_path / "state"

    row = probe_external_brain("mimo", home=home, state_dir=state)

    assert row["status"] == "ok"
    assert row["provider"] == "xiaomi"
    assert row["model"] == ""
    assert row["base_url"] == "https://token-plan-sgp.xiaomimimo.com/v1"
    block = latest_brain_block("mimo", state_dir=state)
    assert "provider=xiaomi" in block
    assert "base_url=https://token-plan-sgp.xiaomimimo.com/v1" in block
    assert "openrouter" not in block.lower()


def test_cline_wrappers_still_speak_cline(tmp_path):
    home = tmp_path / "home"
    (home / ".cline").mkdir(parents=True)
    (home / ".cline" / "config.json").write_text(
        json.dumps({"provider": "openai-codex", "model": "gpt-5.4", "reasoningLevel": "xhigh"})
    )
    state = tmp_path / "state"
    row = probe_cline_settings(home=home, state_dir=state)
    assert row["lane"] == "cline" and row["status"] == "ok"
    assert latest_brain_row("cline", state_dir=state)["model"] == "gpt-5.4"
    # mimo rows never bleed into the cline read
    probe_external_brain("mimo", home=home, state_dir=state)
    assert latest_brain_row("cline", state_dir=state)["model"] == "gpt-5.4"


def test_cortex_brain_label_truths(tmp_path, monkeypatch):
    state = tmp_path / "state"
    # qwen arm carrying Kimi on the Fireworks API — George's exact example
    assert cortex_brain_label("qwen:accounts/fireworks/models/kimi-k2p6", state_dir=state) == (
        "fireworks-api kimi-k2p6"
    )
    assert cortex_brain_label("codex:gpt-5.5", state_dir=state) == "openai gpt-5.5"
    assert cortex_brain_label("grok:grok-4.3", state_dir=state) == "xai grok-4.3"
    monkeypatch.setenv("SIFTA_CLAUDE_ARM_MODEL", "claude-fable-5")
    assert cortex_brain_label("claude:claude-code-cli-default", state_dir=state) == (
        "anthropic claude-fable-5"
    )
    monkeypatch.delenv("SIFTA_CLAUDE_ARM_MODEL")
    assert "launcher-default" in cortex_brain_label("claude:claude-code-cli-default", state_dir=state)
    # local weights: the tag IS the model — no second name invented
    assert cortex_brain_label("alice-m5-cortex-8b-6.3gb:latest", state_dir=state) == ""
    assert cortex_brain_label("mlx-vlm:gemma-4-e2b-it", state_dir=state) == ""
    # cline with a probed row speaks the probe; without one it says so honestly
    assert "no probe row" in cortex_brain_label("cline:cline-cli-default", state_dir=state)
    home = tmp_path / "home"
    (home / ".cline").mkdir(parents=True)
    (home / ".cline" / "config.json").write_text(
        json.dumps({"provider": "openai-codex", "model": "gpt-5.4", "reasoningLevel": "xhigh"})
    )
    probe_external_brain("cline", home=home, state_dir=state)
    assert cortex_brain_label("cline:cline-cli-default", state_dir=state) == (
        "openai-codex gpt-5.4 xhigh"
    )


def test_cortex_list_carries_brain_truth(tmp_path):
    from System.swarm_alice_slash_commands import handle_slash_command

    state = tmp_path / "state"
    home = tmp_path / "home"
    (home / ".cline").mkdir(parents=True)
    (home / ".cline" / "config.json").write_text(
        json.dumps({"provider": "openai-codex", "model": "gpt-5.4"})
    )
    probe_external_brain("cline", home=home, state_dir=state)
    res = handle_slash_command(
        "/cortex",
        state_dir=state,
        current_cortex="cline:cline-cli-default",
        available=[
            "grok:grok-4.3",
            "cline:cline-cli-default",
            "qwen:accounts/fireworks/models/kimi-k2p6",
            "alice-m5-cortex-8b-6.3gb:latest",
        ],
    )
    reply = res["reply"]
    assert "← openai-codex gpt-5.4" in reply              # cline truth from probe
    assert "← fireworks-api kimi-k2p6" in reply            # the "just Qwen" lie corrected
    assert "← xai grok-4.3" in reply
    # the local tag carries no invented second name
    for line in reply.splitlines():
        if "alice-m5-cortex" in line:
            assert "←" not in line


def test_cortex_llm_mimo_branch(tmp_path, monkeypatch):
    from System.swarm_alice_slash_commands import handle_slash_command

    state = tmp_path / "state"
    home = tmp_path / "home"
    (home / ".mimo").mkdir(parents=True)
    (home / ".mimo" / "config.json").write_text(
        json.dumps({"provider": "fireworks", "model": "kimi-k2p6", "reasoningLevel": "high"})
    )
    monkeypatch.setenv("HOME", str(home))
    res = handle_slash_command(
        "/cortex llm",
        state_dir=state,
        current_cortex="mimo:mimo-cli-default",
    )
    reply = res["reply"]
    assert "Selected Talk cortex: mimo:mimo-cli-default" in reply
    assert "MIMO EXTERNAL BRAIN:" in reply
    assert "provider=fireworks" in reply and "model=kimi-k2p6" in reply
    assert "MiMo supports its own upstream provider/model picker" in reply


def test_mimo_registry_label_is_not_rewritten_as_gemini(monkeypatch):
    from System import swarm_gemini_brain as brain

    def fake_which(name: str) -> str | None:
        return "/tmp/mimo" if name == "mimo" else None

    monkeypatch.setattr(brain.shutil, "which", fake_which)
    assert brain.strip_prefix("mimo:mimo-cli-default") == "mimo-cli-default"
    assert brain.display_label("mimo:mimo-cli-default") == "mimo:mimo-cli-default"
    models = brain.available_gemini_models()
    assert "mimo:mimo-cli-default" in models
    assert "gemini:mimo:mimo-cli-default" not in models


def test_cortex_llm_includes_mimo_attached_models(tmp_path, monkeypatch):
    from System.swarm_alice_slash_commands import handle_slash_command

    state = tmp_path / "state"
    home = tmp_path / "home"
    (home / ".mimo").mkdir(parents=True)
    (home / ".mimo" / "config.json").write_text(
        '{"provider": "openrouter", "model": "kimi-k2p6", "reasoningLevel": "high"}'
    )
    monkeypatch.setenv("HOME", str(home))
    res = handle_slash_command(
        "/cortex llm",
        state_dir=state,
        current_cortex="mimo:mimo-cli-default",
    )
    reply = res["reply"]
    assert "Attached LLMs for MiMo" in reply
    assert "Claude-opus" in reply or "GPT-5.5" in reply  # fallback + label block present
    assert "Live default" in reply


def test_mimo_stream_uses_cli_transport(monkeypatch):
    import subprocess

    from System.swarm_gemini_brain import stream_chat

    class _Proc:
        returncode = 0
        stdout = (
            '{"type":"text","part":{"type":"text","text":"MIMO_OK"}}\n'
        )
        stderr = ""

    monkeypatch.setattr(
        "System.swarm_gemini_brain._mimo_cli_binary",
        lambda: "/tmp/mimo",
    )
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Proc())

    events = list(stream_chat("mimo:mimo-cli-default", [{"role": "user", "content": "ping"}]))
    kinds = [k for k, _ in events]
    assert "token" in kinds
    assert events[-1] == ("done", "MIMO_OK")
