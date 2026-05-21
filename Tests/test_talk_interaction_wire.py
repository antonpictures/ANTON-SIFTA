#!/usr/bin/env python3
"""Gates for wiring Interaction BORG into the Talk surface."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# Functional tests import only the pure PyQt6-free helper (headless everywhere).
from System.swarm_interaction_borg import deposit_talk_interaction_turn as _talk_deposit

# NOTE: widget import moved inside the single source-hygiene test (see below).
# This makes the entire test module collect and run on headless machines.


def _rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _line_count(path: Path) -> int:
    if not path.exists():
        return 0
    return len(path.read_text(encoding="utf-8", errors="replace").splitlines())


def test_high_band_turn_persists_with_interaction_mode_via_talk_helper(tmp_path):
    ok = _talk_deposit(
        "George, remember the launch is Tuesday at 3pm and tests must pass.",
        conf=0.92,
        app_context="talk_to_alice",
        state_dir=tmp_path,
    )

    rows = _rows(tmp_path / "memory_ledger.jsonl")
    assert ok is True
    assert len(rows) == 1
    assert rows[0]["interaction_mode"] == "DYAD_GEORGE_ALICE"


def test_low_band_phatic_is_skipped_via_talk_helper(tmp_path):
    ok = _talk_deposit(
        "ok",
        conf=0.95,
        app_context="talk_to_alice",
        state_dir=tmp_path,
    )

    assert ok is False
    assert not (tmp_path / "memory_ledger.jsonl").exists()


def test_fiction_cowatch_mode_and_label_via_talk_helper(tmp_path):
    ok = _talk_deposit(
        "In the movie the dragon attacks on Tuesday.",
        conf=0.88,
        app_context="fiction_cowatch",
        state_dir=tmp_path,
    )

    rows = _rows(tmp_path / "memory_ledger.jsonl")
    assert ok is True
    assert len(rows) == 1
    assert rows[0]["interaction_mode"] == "FICTION_COWATCH"
    assert rows[0]["epistemic_label"] == "FICTION"


def test_non_fatal_on_borg_failure(monkeypatch, tmp_path):
    def boom(*args, **kwargs):
        raise RuntimeError("simulated BORG failure")

    monkeypatch.setattr("System.swarm_interaction_borg.remember_interaction_turn", boom)

    ok = _talk_deposit(
        "This should not crash the Talk turn.",
        conf=0.9,
        app_context="talk_to_alice",
        state_dir=tmp_path,
    )

    assert ok is False
    assert not (tmp_path / "memory_ledger.jsonl").exists()


def test_widget_source_has_single_borg_wire_and_no_plain_memory_write():
    # Lazy import: the only test that touches the GUI module.
    # With this, the whole test file collects and runs on headless Linux/CI.
    talk_mod = pytest.importorskip(
        "Applications.sifta_talk_to_alice_widget",
        reason="PyQt6 GUI surface required for source-hygiene inspection only"
    )
    source = Path(talk_mod.__file__).read_text(encoding="utf-8")
    start = source.index("Interaction BORG wire")
    end = source.index("Event 77: automatic TD credit assignment", start)
    block = source[start:end]

    assert block.count("_interaction_borg_remember_turn_nonfatal(") == 1
    assert "StigmergicMemoryBus" not in block
    assert ".remember(" not in block


def test_real_ledgers_untouched_by_isolated_talk_helper(tmp_path):
    state = Path(".sifta_state")
    watch = [
        state / "memory_ledger.jsonl",
        state / "stgm_memory_rewards.jsonl",
        state / "memory_epistemology_audit.jsonl",
    ]
    before = {path: _line_count(path) for path in watch}

    _talk_deposit(
        "George, this isolated Talk helper probe must not touch live memory.",
        conf=0.95,
        app_context="talk_to_alice",
        state_dir=tmp_path,
    )
    _talk_deposit(
        "In the movie, the fictional dragon attacks Tuesday.",
        conf=0.95,
        app_context="fiction_cowatch",
        state_dir=tmp_path,
    )

    after = {path: _line_count(path) for path in watch}
    assert after == before
