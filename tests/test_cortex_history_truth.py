"""tests/test_cortex_history_truth.py — r985 model-truth from the ledger.

The incident (George 13:53): asked "i think u used alice-m5-cortex-8b …
what is the truth?" — Alice answered from chat narrative while her own
conversation ledger carried the real model per turn. /cortex history is
the deterministic lane: rows decide (§6), narrative does not.

Also proves the r985 mimo reconciliation: ONE tag everywhere.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from System.swarm_alice_slash_commands import (  # noqa: E402
    handle_slash_command,
    last_thinking_models,
)


def _seed_ledger(state: Path) -> None:
    state.mkdir(parents=True, exist_ok=True)
    rows = [
        # wrapped hash-chain shape (current writer)
        {"event_id": "a1", "ts": {"physical_pt": 1.0},
         "payload": {"ts": 1781211420.48, "role": "alice",
                     "model": "alice-m5-cortex-8b-6.3gb:latest",
                     "text": "Earlier thinking turn on the 8B."}},
        {"event_id": "a2", "ts": {"physical_pt": 2.0},
         "payload": {"ts": 1781211500.00, "role": "user", "text": "/cortex 9"}},
        # palette rows are not thinking turns — must be excluded
        {"event_id": "a3", "ts": {"physical_pt": 3.0},
         "payload": {"ts": 1781211501.00, "role": "alice",
                     "model": "slash_command_palette", "text": "Cortex switched: …"}},
        # legacy flat shape (old writer) — must still parse
        {"ts": 1781211600.00, "role": "alice",
         "model": "alice-gemma4-e2b-cortex-5.1b-4.4gb:latest",
         "text": "Bleep-boop! A delightful surge of computational satisfaction!"},
    ]
    with (state / "alice_conversation.jsonl").open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def test_last_thinking_models_reads_both_shapes_and_skips_palette(tmp_path):
    state = tmp_path / "state"
    _seed_ledger(state)
    turns = last_thinking_models(state, n=8)
    models = [t["model"] for t in turns]
    assert models == [
        "alice-m5-cortex-8b-6.3gb:latest",
        "alice-gemma4-e2b-cortex-5.1b-4.4gb:latest",
    ]
    assert "slash_command_palette" not in models
    assert turns[0]["text_head"].startswith("Earlier thinking turn")


def test_cortex_history_command_answers_from_rows(tmp_path):
    state = tmp_path / "state"
    _seed_ledger(state)
    res = handle_slash_command("/cortex history", state_dir=state,
                               current_cortex="alice-gemma4-e2b-cortex-5.1b-4.4gb:latest")
    reply = res["reply"]
    assert "Which brain actually thought" in reply
    assert "alice-m5-cortex-8b-6.3gb:latest" in reply
    assert "alice-gemma4-e2b-cortex-5.1b-4.4gb:latest" in reply
    assert "slash_command_palette" not in reply
    assert "Ledger rows decide" in reply


def test_cortex_history_empty_ledger_is_honest(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    res = handle_slash_command("/cortex history", state_dir=state, current_cortex="")
    assert "no receipted thinking turns" in res["reply"]


def test_model_command_compact_truth_from_ledger(tmp_path):
    state = tmp_path / "state"
    _seed_ledger(state)
    res = handle_slash_command(
        "/model",
        state_dir=state,
        current_cortex="alice-gemma4-e2b-cortex-5.1b-4.4gb:latest",
    )
    reply = res["reply"]
    assert res["handled"] is True
    assert "Model truth" in reply
    assert "alice-gemma4-e2b-cortex-5.1b-4.4gb:latest" in reply
    assert "Last receipted thinking brain: alice-gemma4-e2b-cortex-5.1b-4.4gb:latest" in reply
    assert "/cortex llm" in reply


def test_mimo_single_tag_everywhere():
    from System.sifta_inference_defaults import CANONICAL_CLOUD_MIMO
    from System.swarm_gemini_brain import _MIMO_DEFAULT_MENU

    assert CANONICAL_CLOUD_MIMO == "mimo:mimo-cli-default"
    assert _MIMO_DEFAULT_MENU == ("mimo:mimo-cli-default",)


def test_mimo_gate_sees_home_install_dirs(tmp_path, monkeypatch):
    from System import swarm_gemini_brain as brain

    monkeypatch.setattr(brain.shutil, "which", lambda name: None)
    fake_home = tmp_path / "home"
    bin_dir = fake_home / ".mimocode" / "bin"
    bin_dir.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(fake_home))
    # no binary yet → gate stays closed (no lie in the registry)
    assert brain._mimo_cli_installed() is False
    mimo = bin_dir / "mimo"
    mimo.write_text("#!/bin/sh\n")
    mimo.chmod(0o755)
    # binary present at the Dr Cursor OBSERVED path → gate opens
    assert brain._mimo_cli_installed() is True
