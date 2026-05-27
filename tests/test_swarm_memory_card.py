"""Tests for System/swarm_memory_card.py — unified memory card composer."""
import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from System.swarm_memory_card import (
    TRUTH_LABEL,
    MemoryCard,
    compose_memory_card,
    format_for_prompt,
    _estimate_tokens,
    _truncate_to_budget,
)


@pytest.fixture
def tmp_ledgers(tmp_path):
    """Create a minimal .sifta_state-like directory for testing."""
    state = tmp_path / ".sifta_state"
    state.mkdir()
    return state


def test_empty_ledgers_returns_empty_card(tmp_ledgers):
    with patch("System.swarm_memory_card._fetch_recent_actions", return_value=""), \
         patch("System.swarm_memory_card._fetch_engrams", return_value=""), \
         patch("System.swarm_memory_card._fetch_episodic", return_value=""), \
         patch("System.swarm_memory_card._fetch_digest", return_value=""):
        card = compose_memory_card(tmp_ledgers, token_budget=2000)
    assert isinstance(card, MemoryCard)
    assert card.truth_label == TRUTH_LABEL
    assert card.estimated_tokens == 0
    assert card.recent_actions_block == ""
    assert card.episodic_block == ""
    assert card.engram_block == ""
    assert card.digest_block == ""


def test_format_for_prompt_empty_card():
    card = MemoryCard()
    assert format_for_prompt(card) == ""


def test_format_for_prompt_with_content():
    card = MemoryCard(
        recent_actions_block="ACTION: did something",
        engram_block="ENGRAM: remember this",
        episodic_block="",
        digest_block="",
        estimated_tokens=20,
    )
    result = format_for_prompt(card)
    assert "MEMORY CARD" in result
    assert TRUTH_LABEL in result
    assert "ACTION: did something" in result
    assert "ENGRAM: remember this" in result


def test_format_for_prompt_includes_digest_header():
    card = MemoryCard(digest_block="Some digest text")
    result = format_for_prompt(card)
    assert "ARCHITECT MEMORY DIGEST" in result
    assert "Some digest text" in result


def test_format_for_prompt_includes_restart_continuity_capsule():
    card = MemoryCard(continuity_capsule_block="RESTART CONTINUITY CAPSULE (ledger-grounded):\n- capsule_id=abc")
    result = format_for_prompt(card)
    assert "RESTART CONTINUITY CAPSULE" in result
    assert "capsule_id=abc" in result


def test_estimate_tokens():
    assert _estimate_tokens("") == 0
    assert _estimate_tokens("a") == 1
    assert _estimate_tokens("abcd") == 1
    assert _estimate_tokens("abcde") == 2
    assert _estimate_tokens("a" * 100) == 25


def test_truncate_to_budget():
    text = "line one\nline two\nline three\nline four"
    truncated = _truncate_to_budget(text, 3)
    assert _estimate_tokens(truncated) <= 3


def test_truncate_empty():
    assert _truncate_to_budget("", 100) == ""
    assert _truncate_to_budget("some text", 0) == ""


def test_submodule_failure_yields_empty_section_and_increments_errors(tmp_ledgers):
    with patch(
        "System.swarm_memory_card._fetch_recent_actions",
        side_effect=RuntimeError("boom"),
    ), patch(
        "System.swarm_memory_card._fetch_engrams",
        side_effect=RuntimeError("boom"),
    ), patch(
        "System.swarm_memory_card._fetch_episodic",
        side_effect=RuntimeError("boom"),
    ), patch(
        "System.swarm_memory_card._fetch_digest",
        side_effect=RuntimeError("boom"),
    ):
        card = compose_memory_card(tmp_ledgers, token_budget=2000)
    assert card.parse_errors == 4
    assert card.recent_actions_block == ""
    assert card.engram_block == ""
    assert card.episodic_block == ""
    assert card.digest_block == ""


def test_never_raises_on_any_input(tmp_ledgers):
    card = compose_memory_card(
        tmp_ledgers,
        token_budget=-1,
        now=-999,
        user_text="",
    )
    assert isinstance(card, MemoryCard)


def test_token_budget_respected(tmp_ledgers):
    big_text = "x" * 8000
    with patch(
        "System.swarm_memory_card._fetch_recent_actions", return_value=big_text
    ), patch(
        "System.swarm_memory_card._fetch_engrams", return_value=big_text
    ), patch(
        "System.swarm_memory_card._fetch_episodic", return_value=big_text
    ), patch(
        "System.swarm_memory_card._fetch_digest", return_value=big_text
    ):
        card = compose_memory_card(tmp_ledgers, token_budget=500)
    assert card.estimated_tokens <= 500


def test_sanitize_engrams_callback_applied(tmp_ledgers):
    def mock_sanitizer(text):
        return text.replace("BAD", "GOOD")

    with patch(
        "System.swarm_memory_card._fetch_engrams",
        return_value="BAD engram content",
    ):
        card = compose_memory_card(
            tmp_ledgers,
            token_budget=2000,
            sanitize_engrams=mock_sanitizer,
        )
    assert "BAD" not in card.engram_block
    assert "GOOD" in card.engram_block


def test_sanitize_engrams_failure_increments_errors(tmp_ledgers):
    def bad_sanitizer(text):
        raise ValueError("sanitizer broke")

    with patch(
        "System.swarm_memory_card._fetch_engrams",
        return_value="some engram",
    ):
        card = compose_memory_card(
            tmp_ledgers,
            token_budget=2000,
            sanitize_engrams=bad_sanitizer,
        )
    assert card.engram_block == ""
    assert card.parse_errors >= 1


def test_digest_from_artifact(tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    digest_dir = tmp_path / "Documents" / "architect_memory_digest"
    digest_dir.mkdir(parents=True)
    digest_file = digest_dir / "what_george_taught_alice_today.md"
    digest_file.write_text("# Digest\nLine 1\nLine 2\n")

    card = compose_memory_card(state, token_budget=2000, repo_root=tmp_path)
    assert "Digest" in card.digest_block or "Line 1" in card.digest_block


def test_leftover_redistribution(tmp_ledgers):
    with patch(
        "System.swarm_memory_card._fetch_recent_actions",
        return_value="short",
    ), patch(
        "System.swarm_memory_card._fetch_engrams",
        return_value="x" * 4000,
    ), patch(
        "System.swarm_memory_card._fetch_episodic",
        return_value="",
    ), patch(
        "System.swarm_memory_card._fetch_digest",
        return_value="",
    ):
        card = compose_memory_card(tmp_ledgers, token_budget=2000)
    engram_tokens = _estimate_tokens(card.engram_block)
    assert engram_tokens > int(2000 * 0.30)


def test_priority_order_recent_gets_leftover_first(tmp_ledgers):
    big = "word " * 2000
    with patch(
        "System.swarm_memory_card._fetch_recent_actions", return_value=big
    ), patch(
        "System.swarm_memory_card._fetch_engrams", return_value=""
    ), patch(
        "System.swarm_memory_card._fetch_episodic", return_value=""
    ), patch(
        "System.swarm_memory_card._fetch_digest", return_value=""
    ):
        card = compose_memory_card(tmp_ledgers, token_budget=2000)
    assert _estimate_tokens(card.recent_actions_block) > int(2000 * 0.40)
