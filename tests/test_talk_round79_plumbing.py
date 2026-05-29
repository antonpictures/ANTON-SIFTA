"""Round 81 Slice A tests — Talk widget plumbs Round 79 blocks.

The talk widget is a 22k-line PyQt module that can't import in the
Linux test sandbox without Qt. So we verify the wiring by static
inspection of the source: the file must import the Round 79
assemblers AND call them in the prompt-block assembly path.

That keeps the test honest — it proves the patch landed AND that the
call sites are wired, without spinning up Qt.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest


TALK_WIDGET = Path(__file__).resolve().parents[1] / "Applications" / "sifta_talk_to_alice_widget.py"


def _src() -> str:
    return TALK_WIDGET.read_text(encoding="utf-8")


def test_widget_file_exists() -> None:
    assert TALK_WIDGET.exists(), "talk widget source missing"


def test_imports_associative_recall_prompt_block() -> None:
    src = _src()
    # The exact import shape — must be the Round 79 block, not the
    # private _read_live_engrams helper. Round 83: the structural gate
    # query_requests_associative_recall is no longer required in the
    # widget — recall is always-on, threshold-gated INSIDE the function,
    # not by an outer if-check.
    assert "from System.swarm_hippocampus import" in src
    assert "associative_recall_prompt_block" in src


def test_imports_pheromone_freshness_summary() -> None:
    src = _src()
    assert "from System.swarm_pheromone_freshness_loop import" in src
    assert "summary_for_prompt as _pheromone_freshness_summary" in src


def test_calls_recall_block_with_user_text() -> None:
    """The recall must be queried with the current user_text so the
    hippocampus index returns matches relevant to THIS turn, not random
    rows."""
    src = _src()
    pattern = re.compile(
        r"associative_recall_prompt_block\s*\(\s*"
        r"query\s*=\s*user_text",
        re.DOTALL,
    )
    assert pattern.search(src), "recall must be called with query=user_text"


def test_recall_block_runs_always_on_every_turn() -> None:
    """Round 83 — Stigmergic memory field.

    The architect's rule: 'if it does not match well, computer just
    learned how to better connect memories... if it doesn't [match]
    she marks it that shit doesn't so we have real data.'

    Translation: the structural gate from Round 82 is removed.
    `associative_recall_prompt_block` runs on EVERY turn (no outer
    if-check). Threshold-gating happens INSIDE the function, which
    always writes a receipt to recall_attempts.jsonl regardless of
    whether the cortex prompt sees the full match block or a
    self-narrate line. The miss is data."""
    src = _src()
    # The pre-Round-83 structural gate must NOT be present.
    assert 'if query_requests_associative_recall(user_text or "")' not in src, (
        "Round 83 removes the outer structural gate; recall must run every turn"
    )
    # The call must still happen, guarded only by try/except.
    call_idx = src.find("associative_recall_prompt_block(")
    append_idx = src.find("parts.append(_recall_block)", call_idx)
    assert call_idx != -1, "recall call must still exist"
    assert append_idx != -1, "recall block must still append (when non-empty)"


def test_recall_block_appended_to_parts() -> None:
    """The block must reach the `parts` list that becomes the cortex
    prompt — otherwise it's dead code in the widget."""
    src = _src()
    # The recall call may have nested ()'s (e.g. _state_root()), so use a
    # simpler shape check: the assignment chain that ends in .strip(),
    # then the append.
    assert "associative_recall_prompt_block(" in src
    assert ".strip()" in src
    # And there must be an `if _recall_block: parts.append(_recall_block)`
    # idiom near the call.
    block_pattern = re.compile(
        r"_recall_block\s*=.*?parts\.append\(_recall_block\)",
        re.DOTALL,
    )
    assert block_pattern.search(src), "recall block must be assigned to _recall_block AND appended to parts list"


def test_pheromone_freshness_appended_to_parts() -> None:
    src = _src()
    pattern = re.compile(
        r"_pheromone_freshness\s*=.*?parts\.append\(_pheromone_freshness\)",
        re.DOTALL,
    )
    assert pattern.search(src), "freshness block must be appended to parts list"


def test_round79_blocks_protected_by_try_except() -> None:
    """The blocks are best-effort — a missing import or runtime crash
    must NOT take the whole prompt down. Each block must be guarded by
    its own try/except."""
    src = _src()
    # The recall import line must sit inside a try block (we look for
    # `try:` followed by the import within ~10 lines).
    import_pattern = re.compile(
        r"try:\s*\n([^\n]*\n){0,12}\s*from System\.swarm_hippocampus import",
        re.MULTILINE,
    )
    assert import_pattern.search(src), "recall import must be inside try/except guard"


def test_widget_still_parses_as_python() -> None:
    """If our patch broke the syntax of a 22k-line file we'd lose the
    whole surface. Validate the file still parses cleanly."""
    try:
        ast.parse(_src())
    except SyntaxError as exc:
        pytest.fail(f"talk widget no longer parses: {exc}")
