"""r1018 P1 — /cortex llm bare-number binds last-rendered list (p1-193000-spark-misbind)."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from System.swarm_cortex_llm_list_binding import INCIDENT_P1_SPARK_MISBIND


@pytest.fixture()
def state_dir(tmp_path: Path) -> Path:
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True)
    return sd


def _setup_cline_render(state_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from System import swarm_cortex_capabilities as cap
    from System.swarm_alice_slash_commands import handle_slash_command

    monkeypatch.setattr(cap, "_grok_cli_model_ids", lambda: ["grok-composer-2.5-fast", "grok-build"])
    fake_home = state_dir.parent / "home"
    (fake_home / ".cline").mkdir(parents=True)
    (fake_home / ".cline" / "config.json").write_text(
        json.dumps(
            {
                "provider": "OpenAI",
                "model": "GPT-5.3 Codex Spark",
                "reasoningLevel": "medium",
            }
        )
    )
    monkeypatch.setenv("HOME", str(fake_home))
    handle_slash_command(
        "/cortex llm",
        state_dir=state_dir,
        current_cortex="cline:cline-cli-default",
    )


def test_p1_193000_spark_misbind_incident_closed(
    state_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Render Cline list, spoken bare 4 with wrong cortex — Spark or refuse, never Claude pin."""
    from System.swarm_alice_slash_commands import handle_slash_command

    monkeypatch.delenv("SIFTA_CLAUDE_ARM_MODEL", raising=False)
    os.environ["SIFTA_CLAUDE_ARM_MODEL"] = "claude-opus-4-8"
    _setup_cline_render(state_dir, monkeypatch)

    r = handle_slash_command(
        "/cortex llm 4",
        state_dir=state_dir,
        current_cortex="c",
        ingress_kind="spoken",
    )

    assert r["handled"]
    assert r.get("pending_confirmation") is not True
    assert r["error"] == "upstream_picker_refused"
    assert "GPT-5.3-Codex-Spark" in r["reply"]
    assert "did not pin Claude" in r["reply"]
    assert os.environ.get("SIFTA_CLAUDE_ARM_MODEL") == "claude-opus-4-8"

    binding_rows = [
        json.loads(ln)
        for ln in (state_dir / "cortex_llm_binding_receipts.jsonl").read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    closed = [row for row in binding_rows if row.get("action") == "incident_closed"]
    assert closed
    assert closed[-1]["incident_id"] == INCIDENT_P1_SPARK_MISBIND
    assert closed[-1]["verdict"] == "REFUSED_CLAUDE_MUTATION"


def test_bare_number_without_render_refuses_and_rerenders(state_dir: Path) -> None:
    from System.swarm_alice_slash_commands import handle_slash_command

    r = handle_slash_command("/cortex llm 4", state_dir=state_dir, current_cortex="c")
    assert r["error"] in ("no_rendered_list", "stale_rendered_list")
    assert "which picker" in r["reply"].lower() or "fresh numbered list" in r["reply"].lower()


def test_codex_bare_four_sets_local_default_not_claude(
    state_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from System import swarm_cortex_capabilities as cap
    from System.swarm_alice_slash_commands import handle_slash_command

    monkeypatch.delenv("SIFTA_CLAUDE_ARM_MODEL", raising=False)

    listed = handle_slash_command(
        "/cortex llm",
        state_dir=state_dir,
        current_cortex="codex:gpt-5.5",
    )
    assert listed["handled"] and not listed["error"]
    assert "Attached LLMs for Codex" in listed["reply"]

    r = handle_slash_command(
        "/cortex llm 4",
        state_dir=state_dir,
        current_cortex="codex:gpt-5.5",
    )

    assert r["handled"] and not r["error"]
    assert "GPT-5.3-Codex-Spark" in r["reply"]
    assert "Codex attached LLM default" in r["reply"]
    assert "Claude arm untouched" in r["reply"]
    assert "SIFTA_CLAUDE_ARM_MODEL" not in os.environ

    rec = cap.attached_models_for_cortex("codex:gpt-5.5", state_dir=state_dir)
    assert rec.get("default_attached") == "GPT-5.3-Codex-Spark"

    rerendered = handle_slash_command(
        "/cortex llm",
        state_dir=state_dir,
        current_cortex="codex:gpt-5.5",
    )
    assert "●  4. GPT-5.3-Codex-Spark" in rerendered["reply"]

    rows = [
        json.loads(ln)
        for ln in (state_dir / "cortex_llm_binding_receipts.jsonl").read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    assert rows[-1]["action"] == "codex_local_default_set"
    assert rows[-1]["to_default"] == "GPT-5.3-Codex-Spark"


def test_mimo_bare_two_sets_local_default_not_claude_after_pruned_list(
    state_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from System import swarm_cortex_capabilities as cap
    from System.swarm_alice_slash_commands import handle_slash_command

    monkeypatch.delenv("SIFTA_CLAUDE_ARM_MODEL", raising=False)
    home = state_dir.parent / "home"
    home.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    listed = handle_slash_command(
        "/cortex llm",
        state_dir=state_dir,
        current_cortex="mimo:mimo-cli-default",
    )
    assert listed["handled"] and not listed["error"]
    assert "Attached LLMs for MiMo" in listed["reply"]

    r = handle_slash_command(
        "/cortex llm 3",
        state_dir=state_dir,
        current_cortex="mimo:mimo-cli-default",
    )

    assert r["handled"] and not r["error"]
    assert "krishairnd/Gemma-4-Uncensored:latest" in r["reply"]
    assert "MiMo attached LLM default" in r["reply"]
    assert "Claude arm untouched" in r["reply"]
    assert "SIFTA_CLAUDE_ARM_MODEL" not in os.environ

    rec = cap.attached_models_for_cortex("mimo:mimo-cli-default", state_dir=state_dir)
    assert rec.get("default_attached") == "krishairnd/Gemma-4-Uncensored:latest"

    rerendered = handle_slash_command(
        "/cortex llm",
        state_dir=state_dir,
        current_cortex="mimo:mimo-cli-default",
    )
    assert "1. MiMo Auto (free) (mimo-auto)" in rerendered["reply"]
    assert (
        "2. Kimi K2.6 (fireworks-api kimi-k2p6) (accounts/fireworks/models/kimi-k2p6)"
        in rerendered["reply"]
    )
    assert (
        "●  3. krisha-g4u (local Ollama) (krishairnd/Gemma-4-Uncensored:latest)"
        in rerendered["reply"]
    )
    assert "4. kaelri-q3.5-mt-2b (local Ollama) (kaelri/qwen3.5-mt:2b)" in rerendered["reply"]
    assert (
        "5. Qwen3.6 27B Uncensored Balanced (local Ollama) "
        "(baytout3/Qwen3.6-27B-Uncensored-HauhauCS-Balanced:IQ4_XS)"
    ) in rerendered["reply"]
    assert "6. DiffusionGemma 26B (local diffusion) (diffusion:diffusiongemma-26b)" in rerendered["reply"]

    rows = [
        json.loads(ln)
        for ln in (state_dir / "cortex_llm_binding_receipts.jsonl").read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    assert rows[-1]["action"] == "mimo_local_default_set"
    assert rows[-1]["to_default"] == "krishairnd/Gemma-4-Uncensored:latest"


def test_mimo_direct_removed_paid_pro_model_id_refuses_pruned_row(
    state_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from System import swarm_cortex_capabilities as cap
    from System.swarm_alice_slash_commands import handle_slash_command

    monkeypatch.delenv("SIFTA_CLAUDE_ARM_MODEL", raising=False)
    r = handle_slash_command(
        "/cortex llm mimo-v2.5-pro",
        state_dir=state_dir,
        current_cortex="mimo:mimo-cli-default",
    )

    assert r["handled"] and r["error"] == "mimo_model_not_in_keep_list"
    assert "not in the current MiMo attached LLM keep-list" in r["reply"]
    assert "mimo-v2.5-pro" in r["reply"]
    assert "SIFTA_CLAUDE_ARM_MODEL" not in os.environ

    rec = cap.attached_models_for_cortex("mimo:mimo-cli-default", state_dir=state_dir)
    assert rec.get("default_attached") in (
        "",
        None,
        "krishairnd/Gemma-4-Uncensored:latest",
        cap._MIMO_LOCAL_QWEN35_MT,
    )


def test_mimo_direct_qwen_local_ollama_model_id_sets_local_default(
    state_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from System import swarm_cortex_capabilities as cap
    from System.swarm_alice_slash_commands import handle_slash_command

    monkeypatch.delenv("SIFTA_CLAUDE_ARM_MODEL", raising=False)
    model_id = "baytout3/Qwen3.6-27B-Uncensored-HauhauCS-Balanced:IQ4_XS"
    cap.sync_cortex_attached_models_catalog(state_dir=state_dir)
    r = handle_slash_command(
        f"/cortex llm {model_id}",
        state_dir=state_dir,
        current_cortex="mimo:mimo-cli-default",
    )

    assert r["handled"] and not r["error"]
    assert "MiMo attached LLM default" in r["reply"]
    assert model_id in r["reply"]
    assert "SIFTA_CLAUDE_ARM_MODEL" not in os.environ

    rec = cap.attached_models_for_cortex("mimo:mimo-cli-default", state_dir=state_dir)
    assert rec.get("default_attached") == model_id


def test_cortex_pin_claude_namespaced(state_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from System.swarm_alice_slash_commands import handle_slash_command

    monkeypatch.delenv("SIFTA_CLAUDE_ARM_MODEL", raising=False)
    r = handle_slash_command("/cortex pin claude 4", state_dir=state_dir, current_cortex="c")
    assert r["switched"]
    assert os.environ["SIFTA_CLAUDE_ARM_MODEL"] == "claude-opus-4-6"


def test_spoken_mutable_pin_requires_confirm(state_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from System.swarm_alice_slash_commands import handle_slash_command

    monkeypatch.delenv("SIFTA_CLAUDE_ARM_MODEL", raising=False)
    handle_slash_command("/cortex llm", state_dir=state_dir, current_cortex="claude:claude-code-cli-default")
    r = handle_slash_command(
        "/cortex pin claude 1",
        state_dir=state_dir,
        current_cortex="claude:claude-code-cli-default",
        ingress_kind="spoken",
    )
    assert r.get("pending_confirmation") is True
    assert "Confirm?" in r["reply"]
    assert "SIFTA_CLAUDE_ARM_MODEL" not in os.environ

    r2 = handle_slash_command(
        "/cortex llm confirm",
        state_dir=state_dir,
        current_cortex="claude:claude-code-cli-default",
        ingress_kind="spoken",
    )
    assert r2["switched"]
    assert os.environ["SIFTA_CLAUDE_ARM_MODEL"] == "claude-fable-5"


def test_grok_number_still_pins_grok_not_claude(state_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from System import swarm_cortex_capabilities as cap
    from System.swarm_alice_slash_commands import handle_slash_command

    monkeypatch.delenv("SIFTA_GROK_CLI_MODEL", raising=False)
    monkeypatch.delenv("SIFTA_CLAUDE_ARM_MODEL", raising=False)
    monkeypatch.setattr(cap, "_grok_cli_model_ids", lambda: ["grok-composer-2.5-fast", "grok-build"])
    handle_slash_command("/cortex llm", state_dir=state_dir, current_cortex="grok:grok-4.3")
    r = handle_slash_command("/cortex llm 2", state_dir=state_dir, current_cortex="grok:grok-4.3")
    assert r["switched"]
    assert os.environ["SIFTA_GROK_CLI_MODEL"] == "grok-build"
    assert "SIFTA_CLAUDE_ARM_MODEL" not in os.environ
