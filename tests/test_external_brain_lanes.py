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
    from System.swarm_cortex_capabilities import record_attached_models

    state = tmp_path / "state"
    # qwen arm carrying Kimi on the Fireworks API — George's exact example
    assert cortex_brain_label("qwen:accounts/fireworks/models/kimi-k2p6", state_dir=state) == (
        "fireworks-api kimi-k2p6"
    )
    assert cortex_brain_label("codex:gpt-5.5", state_dir=state) == "openai gpt-5.5"
    record_attached_models(
        "codex:gpt-5.5",
        ["GPT-5.5", "GPT-5.4", "GPT-5.4-Mini", "GPT-5.3-Codex-Spark"],
        default_attached="GPT-5.3-Codex-Spark",
        source="test_owner_default_option_4",
        picker_is_upstream=True,
        state_dir=state,
    )
    assert cortex_brain_label("codex:gpt-5.5", state_dir=state) == (
        "openai-codex GPT-5.3-Codex-Spark"
    )
    record_attached_models(
        "mimo:mimo-cli-default",
        ["mimo-v2.5-pro", "mimo-auto", "krishairnd/Gemma-4-Uncensored:latest"],
        default_attached="krishairnd/Gemma-4-Uncensored:latest",
        source="test_owner_default_mimo_local_gemma4",
        picker_is_upstream=True,
        state_dir=state,
    )
    mimo_home = tmp_path / "mimo_home"
    (mimo_home / ".mimo").mkdir(parents=True)
    (mimo_home / ".mimo" / "config.json").write_text(json.dumps({"provider": "xiaomi"}))
    probe_external_brain("mimo", home=mimo_home, state_dir=state)
    assert cortex_brain_label("mimo:mimo-cli-default", state_dir=state) == (
        "mimo-picker krisha-g4u (local Ollama) (krishairnd/Gemma-4-Uncensored:latest)"
    )
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


def test_cortex_list_mimo_only_when_single_cortex_borg(monkeypatch):
    from System import swarm_gemini_brain as brain
    from System.swarm_alice_slash_commands import handle_slash_command

    monkeypatch.setenv("SIFTA_MIMO_BORG_SINGLE_CORTEX", "1")
    monkeypatch.setattr(brain, "_mimo_cli_installed", lambda: True)
    res = handle_slash_command(
        "/cortex",
        state_dir=Path("/tmp/unused"),
        current_cortex="mimo:mimo-cli-default",
    )
    reply = res["reply"]
    assert "mimo:mimo-cli-default" in reply
    assert "grok:grok-4.3" not in reply
    assert "claude:claude-code-cli-default" not in reply
    assert "codex:gpt-5.5" not in reply
    assert "qwen:accounts/fireworks/models/kimi-k2p6" not in reply
    assert "cline:cline-cli-default" not in reply


def test_cortex_list_carries_brain_truth(tmp_path, monkeypatch):
    from System.swarm_alice_slash_commands import handle_slash_command

    monkeypatch.setenv("SIFTA_MIMO_BORG_SINGLE_CORTEX", "0")
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
    assert "CLI/OAuth/local models" in reply
    assert "Do not assume an OpenAI API key" in reply
    assert "provider API" not in reply


def test_mimo_registry_label_is_not_rewritten_as_gemini(monkeypatch):
    from System import swarm_gemini_brain as brain

    def fake_which(name: str) -> str | None:
        return "/tmp/mimo" if name == "mimo" else None

    monkeypatch.setenv("SIFTA_MIMO_BORG_SINGLE_CORTEX", "1")
    monkeypatch.setattr(brain.shutil, "which", fake_which)
    assert brain.strip_prefix("mimo:mimo-cli-default") == "mimo-cli-default"
    assert brain.display_label("mimo:mimo-cli-default") == "mimo:mimo-cli-default"
    models = brain.available_gemini_models()
    assert models == ["mimo:mimo-cli-default"]
    assert "grok:grok-4.3" not in models
    assert "claude:claude-code-cli-default" not in models
    assert "codex:gpt-5.5" not in models
    assert "qwen:accounts/fireworks/models/kimi-k2p6" not in models
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
    assert "MiMo Auto (free) (mimo-auto)" in reply
    assert "Kimi K2.6 (fireworks-api kimi-k2p6)" in reply
    assert "krisha-g4u (local Ollama)" in reply
    assert "DiffusionGemma 26B (local diffusion)" in reply
    assert "GPT-5.3-Codex-Spark" in reply
    assert "GPT-5.5" not in reply
    assert "Live default" in reply


def test_mimo_stream_uses_cli_transport(monkeypatch, tmp_path):
    import subprocess

    from System import swarm_gemini_brain as brain
    from System.swarm_cortex_capabilities import record_attached_models

    class _Proc:
        returncode = 0
        stdout = (
            '{"type":"text","part":{"type":"text","text":"MIMO_OK"}}\n'
        )
        stderr = ""

    state = tmp_path / ".sifta_state"
    record_attached_models(
        "mimo:mimo-cli-default",
        ["mimo-auto"],
        default_attached="mimo-auto",
        state_dir=state,
    )
    monkeypatch.setattr(brain, "_STATE", state)
    monkeypatch.setattr(
        brain,
        "_mimo_cli_binary",
        lambda: "/tmp/mimo",
    )
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Proc())

    events = list(brain.stream_chat("mimo:mimo-cli-default", [{"role": "user", "content": "ping"}]))
    kinds = [k for k, _ in events]
    assert "token" in kinds
    assert events[-1] == ("done", "MIMO_OK")


def test_mimo_dispatch_lane_local_krisha_default(monkeypatch, tmp_path):
    from System.swarm_cortex_capabilities import (
        FIREWORKS_KIMI_K2P6_MODEL,
        mimo_attached_dispatch_lane,
        record_attached_models,
    )

    state = tmp_path / ".sifta_state"
    record_attached_models(
        "mimo:mimo-cli-default",
        ["krishairnd/Gemma-4-Uncensored:latest", "GPT-5.3-Codex-Spark", "mimo-auto"],
        default_attached="krishairnd/Gemma-4-Uncensored:latest",
        state_dir=state,
    )
    assert mimo_attached_dispatch_lane("krishairnd/Gemma-4-Uncensored:latest") == "mimo_cli_ollama_bridge"
    assert mimo_attached_dispatch_lane("GPT-5.3-Codex-Spark") == "mimo_cli_codex_bridge"
    assert mimo_attached_dispatch_lane("grok-composer-2.5-fast") == "mimo_cli_grok_bridge"
    assert mimo_attached_dispatch_lane("grok-build") == "mimo_cli_grok_bridge"
    assert mimo_attached_dispatch_lane(FIREWORKS_KIMI_K2P6_MODEL) == "mimo_cli_qwen_bridge"
    assert mimo_attached_dispatch_lane("mimo-auto") == "mimo_native"


def test_mimo_stream_routes_codex_spark_attached_default(monkeypatch, tmp_path):
    import subprocess

    from System import swarm_gemini_brain as brain
    from System.swarm_cortex_capabilities import record_attached_models

    class _Proc:
        returncode = 0
        stdout = '{"type":"text","part":{"type":"text","text":"SPARK_OK"}}\n'
        stderr = ""

    state = tmp_path / ".sifta_state"
    record_attached_models(
        "mimo:mimo-cli-default",
        ["mimo-auto", "mimo-v2.5-pro-ultraspeed", "GPT-5.3-Codex-Spark"],
        default_attached="GPT-5.3-Codex-Spark",
        state_dir=state,
    )
    captured = {}

    def fake_run(cmd, *args, **kwargs):
        if cmd and cmd[0] == "/tmp/mimo":
            captured["cmd"] = cmd
        return _Proc()

    monkeypatch.setattr(brain, "_STATE", state)
    monkeypatch.setattr(brain, "_mimo_cli_binary", lambda: "/tmp/mimo")
    monkeypatch.setattr(brain, "_cloud_inference_blocked_by_metabolism", lambda: (False, ""))
    monkeypatch.setattr(subprocess, "run", fake_run)

    events = list(brain.stream_chat("mimo:mimo-cli-default", [{"role": "user", "content": "ping"}]))

    assert events[-1] == ("done", "SPARK_OK")
    assert captured["cmd"][:2] == ["/tmp/mimo", "run"]
    assert captured["cmd"][captured["cmd"].index("-m") + 1] == "mimo/mimo-auto"
    prompt = captured["cmd"][-1]
    assert "CODEX_CLI_DOWNSTREAM_BRIDGE" in prompt
    assert "--model gpt-5.3-codex-spark" in prompt
    assert "DOWNSTREAM_MODEL=GPT-5.3-Codex-Spark" in prompt
    trace_path = state / "mimo_stigmergic_traces.jsonl"
    assert trace_path.exists()
    trace = json.loads(trace_path.read_text(encoding="utf-8").splitlines()[-1])
    assert trace["driving_organ"] == "talk_mimo_cortex"
    assert trace["model"] == "mimo/mimo-auto"
    assert "mimo_cli_codex_bridge" in trace["intent"]


def test_mimo_stream_routes_grok_composer_through_mimo_cli_bridge(monkeypatch, tmp_path):
    import subprocess

    from System import swarm_gemini_brain as brain
    from System.swarm_cortex_capabilities import record_attached_models

    class _Proc:
        returncode = 0
        stdout = '{"type":"text","part":{"type":"text","text":"GROK_BRIDGE_OK"}}\n'
        stderr = ""

    state = tmp_path / ".sifta_state"
    record_attached_models(
        "mimo:mimo-cli-default",
        ["mimo-auto", "grok-composer-2.5-fast", "grok-build"],
        default_attached="grok-composer-2.5-fast",
        state_dir=state,
    )
    captured = {}

    def fake_run(cmd, *args, **kwargs):
        if cmd and cmd[0] == "/tmp/mimo":
            captured["cmd"] = cmd
        return _Proc()

    def direct_grok_should_not_run(**kwargs):
        raise AssertionError("MiMo cortex must not bypass directly to Grok")

    monkeypatch.setattr(brain, "_STATE", state)
    monkeypatch.setattr(brain, "_mimo_cli_binary", lambda: "/tmp/mimo")
    monkeypatch.setattr(brain, "_grok_cli_binary", lambda: "/tmp/grok")
    monkeypatch.setattr(brain, "_cloud_inference_blocked_by_metabolism", lambda: (False, ""))
    monkeypatch.setattr(brain, "_stream_grok_chat", direct_grok_should_not_run)
    monkeypatch.setattr(subprocess, "run", fake_run)

    events = list(brain.stream_chat("mimo:mimo-cli-default", [{"role": "user", "content": "ping"}]))

    assert events[-1] == ("done", "GROK_BRIDGE_OK")
    assert captured["cmd"][:2] == ["/tmp/mimo", "run"]
    assert captured["cmd"][captured["cmd"].index("-m") + 1] == "mimo/mimo-auto"
    prompt = captured["cmd"][-1]
    assert "GROK_CLI_DOWNSTREAM_BRIDGE" in prompt
    assert "/tmp/grok --single <task_prompt> --model grok-composer-2.5-fast" in prompt
    assert "DOWNSTREAM_MODEL=grok-composer-2.5-fast" in prompt


def test_mimo_stream_local_attached_routes_ollama_through_mimo_cli_bridge(monkeypatch, tmp_path):
    import subprocess

    from System import swarm_gemini_brain as brain
    from System.swarm_cortex_capabilities import record_attached_models

    class _Proc:
        returncode = 0
        stdout = '{"type":"text","part":{"type":"text","text":"OLLAMA_BRIDGE_OK"}}\n'
        stderr = ""

    state = tmp_path / ".sifta_state"
    record_attached_models(
        "mimo:mimo-cli-default",
        ["krishairnd/Gemma-4-Uncensored:latest", "mimo-auto"],
        default_attached="krishairnd/Gemma-4-Uncensored:latest",
        state_dir=state,
    )
    captured = {}

    def fake_run(cmd, *args, **kwargs):
        if cmd and cmd[0] == "/tmp/mimo":
            captured["cmd"] = cmd
        return _Proc()

    monkeypatch.setattr(brain, "_STATE", state)
    monkeypatch.setattr(brain, "_mimo_cli_binary", lambda: "/tmp/mimo")
    monkeypatch.setattr(brain, "_cloud_inference_blocked_by_metabolism", lambda: (False, ""))
    monkeypatch.setattr(subprocess, "run", fake_run)

    events = list(brain.stream_chat("mimo:mimo-cli-default", [{"role": "user", "content": "ping"}]))
    assert events[-1] == ("done", "OLLAMA_BRIDGE_OK")
    assert captured["cmd"][:2] == ["/tmp/mimo", "run"]
    assert captured["cmd"][captured["cmd"].index("-m") + 1] == "mimo/mimo-auto"
    prompt = captured["cmd"][-1]
    assert "OLLAMA_CLI_DOWNSTREAM_BRIDGE" in prompt
    assert "ollama run krishairnd/Gemma-4-Uncensored:latest <task_prompt>" in prompt
    assert "DOWNSTREAM_MODEL=krishairnd/Gemma-4-Uncensored:latest" in prompt


def test_stream_grok_coerces_to_mimo_hub_not_direct_grok(monkeypatch, tmp_path):
    import subprocess

    from System import swarm_gemini_brain as brain
    from System.swarm_cortex_capabilities import record_attached_models

    class _Proc:
        returncode = 0
        stdout = '{"type":"text","part":{"type":"text","text":"GROK_COERCED_OK"}}\n'
        stderr = ""

    state = tmp_path / ".sifta_state"
    record_attached_models(
        "grok:grok-4.3",
        ["grok-composer-2.5-fast", "grok-build"],
        default_attached="grok-build",
        state_dir=state,
    )
    captured = {}

    def fake_run(cmd, *args, **kwargs):
        if cmd and cmd[0] == "/tmp/mimo":
            captured["cmd"] = cmd
        return _Proc()

    def direct_grok_should_not_run(**kwargs):
        raise AssertionError("grok:grok-4.3 must route through MiMo hub, not _stream_grok_chat")

    monkeypatch.setenv("SIFTA_MIMO_BORG_SINGLE_CORTEX", "1")
    monkeypatch.setattr(brain, "_STATE", state)
    monkeypatch.setattr(brain, "_mimo_cli_binary", lambda: "/tmp/mimo")
    monkeypatch.setattr(brain, "_mimo_cli_installed", lambda: True)
    monkeypatch.setattr(brain, "_grok_cli_binary", lambda: "/tmp/grok")
    monkeypatch.setattr(brain, "_cloud_inference_blocked_by_metabolism", lambda: (False, ""))
    monkeypatch.setattr(brain, "_stream_grok_chat", direct_grok_should_not_run)
    monkeypatch.setattr(subprocess, "run", fake_run)

    events = list(brain.stream_chat("grok:grok-4.3", [{"role": "user", "content": "ping"}]))

    assert events[-1] == ("done", "GROK_COERCED_OK")
    assert captured["cmd"][:2] == ["/tmp/mimo", "run"]
    prompt = captured["cmd"][-1]
    assert "GROK_CLI_DOWNSTREAM_BRIDGE" in prompt
    assert "--model grok-build" in prompt or "DOWNSTREAM_MODEL=grok-build" in prompt
    usage = next(event[1] for event in events if event[0] == "usage")
    assert usage.raw.get("coerced_from_parallel_cli") is True
    assert usage.raw.get("mimo_source_cortex") == "grok:grok-4.3"


def test_mimo_stream_honors_mimo_auto_native_attached_default(monkeypatch, tmp_path):
    import subprocess

    from System import swarm_gemini_brain as brain
    from System.swarm_cortex_capabilities import record_attached_models

    class _Proc:
        returncode = 0
        stdout = '{"type":"text","part":{"type":"text","text":"AUTO_OK"}}\n'
        stderr = ""

    state = tmp_path / ".sifta_state"
    record_attached_models(
        "mimo:mimo-cli-default",
        ["mimo-auto", "krishairnd/Gemma-4-Uncensored:latest"],
        default_attached="mimo-auto",
        state_dir=state,
    )
    captured = {}

    def fake_run(cmd, *args, **kwargs):
        if cmd and cmd[0] == "/tmp/mimo":
            captured["cmd"] = cmd
        return _Proc()

    monkeypatch.delenv("SIFTA_MIMO_CLI_MODEL", raising=False)
    monkeypatch.setattr(brain, "_STATE", state)
    monkeypatch.setattr(brain, "_mimo_cli_binary", lambda: "/tmp/mimo")
    monkeypatch.setattr(subprocess, "run", fake_run)

    events = list(brain.stream_chat("mimo:mimo-cli-default", [{"role": "user", "content": "ping"}]))

    assert events[-1] == ("done", "AUTO_OK")
    assert captured["cmd"][captured["cmd"].index("-m") + 1] == "mimo/mimo-auto"
