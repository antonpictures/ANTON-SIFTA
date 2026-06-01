#!/usr/bin/env python3
"""Tests for associative name memory and single-focus app habit prompting."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System import swarm_associative_focus_field as aff


def test_extracts_explicit_name_list_without_hardcoding():
    names = aff.extract_name_handles(
        "names like grok, sam altman, claude, elon, to me these are memory handles"
    )

    assert names == ["grok", "sam altman", "claude", "elon"]


def test_records_name_association_rows_deduped(tmp_path):
    first = aff.remember_name_associations(
        "names like grok, sam altman, claude, elon",
        active_app="Alice Browser",
        state_dir=tmp_path,
        now=100.0,
    )
    second = aff.remember_name_associations(
        "names like grok, sam altman, claude, elon",
        active_app="Alice Browser",
        state_dir=tmp_path,
        now=101.0,
    )

    ledger = tmp_path / ".sifta_state" / aff.LEDGER_NAME
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert first["written"] == 4
    assert second["written"] == 0
    assert second["deduped"] == 4
    assert {row["name"] for row in rows} == {"grok", "sam altman", "claude", "elon"}
    assert all(row["active_app"] == "Alice Browser" for row in rows)


def test_associative_focus_prompt_names_single_stream_and_app_habits(tmp_path, monkeypatch):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    (state / "sifta_desktop_app_state.json").write_text(
        json.dumps({"active_app": "Ace", "open_apps": ["Ace"]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(aff, "STATE_DIR", state)

    block = aff.associative_focus_prompt(
        "names like Alice, Grok; teach Ace to read sentences",
        state_dir=tmp_path,
        write=False,
    )

    assert "ASSOCIATIVE FOCUS FIELD" in block
    assert "Name handles active now: Alice, Grok" in block
    assert "Current app organ: Ace" in block
    assert "one dominant stream of consciousness" in block
    assert "wordace_reading_coach" in block


def test_prompt_contract_includes_associative_focus_block(monkeypatch):
    from System.swarm_prompt_contract import tool_affordances_for_turn

    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_prompt_contract_includes_associative_focus_block")
    text = tool_affordances_for_turn("names like grok, claude are just associative handles")

    assert "ASSOCIATIVE FOCUS FIELD" in text
    assert "Name handles active now: grok, claude" in text


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
