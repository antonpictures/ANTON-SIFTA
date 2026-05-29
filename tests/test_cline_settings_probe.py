"""Tests for §2.I — Cline external-brain settings probe."""
from __future__ import annotations

import json
from pathlib import Path

from System import swarm_cline_settings_probe as probe


def test_probe_no_config_writes_no_config_row(tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    state = tmp_path / "state"
    row = probe.probe_cline_settings(home=fake_home, state_dir=state, now=100.0)
    assert row["lane"] == "cline"
    assert row["status"] == "no_config_found"
    assert row["model"] == ""
    assert row["config_path"] == ""
    assert row["ledger_write"] == "ok"
    ledger = state / "external_brain_settings.jsonl"
    assert ledger.exists()
    written = json.loads(ledger.read_text().strip().splitlines()[-1])
    assert written["status"] == "no_config_found"


def test_probe_finds_dot_cline_config_json(tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    (fake_home / ".cline").mkdir(parents=True)
    cfg = {
        "model": "GPT-5.4",
        "provider": "OpenAI",
        "reasoningLevel": "extra_high",
        "contextWindow": 922000,
    }
    (fake_home / ".cline" / "config.json").write_text(json.dumps(cfg))
    state = tmp_path / "state"
    row = probe.probe_cline_settings(home=fake_home, state_dir=state, now=200.0)
    assert row["status"] == "ok"
    assert row["model"] == "GPT-5.4"
    assert row["provider"] == "OpenAI"
    assert row["reasoning_level"] == "extra_high"
    assert row["context_window"] == "922000"


def test_probe_handles_nested_config(tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    (fake_home / ".config" / "cline").mkdir(parents=True)
    cfg = {
        "openai": {
            "model": "GPT-5.3 Codex Spark",
            "thinking_level": "medium",
        }
    }
    (fake_home / ".config" / "cline" / "config.json").write_text(json.dumps(cfg))
    state = tmp_path / "state"
    row = probe.probe_cline_settings(home=fake_home, state_dir=state)
    assert row["status"] == "ok"
    assert row["model"] == "GPT-5.3 Codex Spark"
    assert row["reasoning_level"] == "medium"


def test_probe_handles_malformed_config_safely(tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    (fake_home / ".cline").mkdir(parents=True)
    (fake_home / ".cline" / "config.json").write_text("{not json at all")
    state = tmp_path / "state"
    row = probe.probe_cline_settings(home=fake_home, state_dir=state)
    # malformed config falls through — row should still land safely
    assert row["status"] == "no_config_found"
    assert row["ledger_write"] == "ok"


def test_probe_always_appends_even_when_no_config(tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    state = tmp_path / "state"
    probe.probe_cline_settings(home=fake_home, state_dir=state, now=10.0)
    probe.probe_cline_settings(home=fake_home, state_dir=state, now=20.0)
    ledger = state / "external_brain_settings.jsonl"
    rows = [json.loads(line) for line in ledger.read_text().splitlines() if line.strip()]
    assert len(rows) == 2
    assert rows[0]["ts"] == 10.0
    assert rows[1]["ts"] == 20.0


def test_latest_block_returns_empty_when_no_ledger(tmp_path: Path) -> None:
    assert probe.latest_cline_brain_block(state_dir=tmp_path) == ""


def test_latest_block_formats_ok_row(tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    (fake_home / ".cline").mkdir(parents=True)
    (fake_home / ".cline" / "config.json").write_text(json.dumps({
        "model": "GPT-5.4",
        "reasoningLevel": "extra_high",
        "contextWindow": 922000,
    }))
    state = tmp_path / "state"
    probe.probe_cline_settings(home=fake_home, state_dir=state)
    block = probe.latest_cline_brain_block(state_dir=state)
    assert "CLINE EXTERNAL BRAIN" in block
    assert "GPT-5.4" in block
    assert "extra_high" in block
    assert "922000" in block


def test_latest_block_formats_status_when_no_config(tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    state = tmp_path / "state"
    probe.probe_cline_settings(home=fake_home, state_dir=state)
    block = probe.latest_cline_brain_block(state_dir=state)
    assert "CLINE EXTERNAL BRAIN" in block
    assert "no_config_found" in block
