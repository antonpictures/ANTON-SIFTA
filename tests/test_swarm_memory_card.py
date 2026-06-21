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
         patch("System.swarm_memory_card._fetch_app_limb_context", return_value=""), \
         patch("System.swarm_memory_card._fetch_engrams", return_value=""), \
         patch("System.swarm_memory_card._fetch_episodic", return_value=""), \
         patch("System.swarm_memory_card._fetch_owner_somatic", return_value=""), \
         patch("System.swarm_memory_card._fetch_owner_carbon_body", return_value=""), \
         patch("System.swarm_memory_card._fetch_media_capability", return_value=""), \
         patch("System.swarm_memory_card._fetch_vision_arms_awareness", return_value=""), \
         patch("System.swarm_memory_card._fetch_browser_context", return_value=""), \
         patch("System.swarm_memory_card._fetch_taste_consequence", return_value=""), \
         patch("System.swarm_memory_card._fetch_active_plan", return_value=""), \
         patch("System.swarm_memory_card._fetch_arm_session", return_value=""), \
         patch("System.swarm_memory_card._fetch_body_stabilization_queue", return_value=""), \
         patch("System.swarm_memory_card._fetch_love_field", return_value=""), \
         patch("System.swarm_memory_card._fetch_receipt_ecology", return_value=""), \
         patch("System.swarm_memory_card._fetch_digest", return_value=""), \
         patch("System.swarm_memory_card._fetch_continuity_capsule", return_value=""):
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
        receipt_ecology_block="RECEIPT MEMORY ECOLOGY: r1(s=1.0,x1)",
        engram_block="ENGRAM: remember this",
        episodic_block="",
        digest_block="",
        estimated_tokens=20,
    )
    result = format_for_prompt(card)
    assert "MEMORY CARD" in result
    assert TRUTH_LABEL in result
    assert "ACTION: did something" in result
    assert "RECEIPT MEMORY ECOLOGY" in result
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


def test_memory_card_includes_app_body_state_before_action(tmp_ledgers):
    from System.swarm_app_action_diary import record_app_action

    record_app_action("Alice Browser", "open", now=1000.0, state_dir=tmp_ledgers)
    with patch("System.swarm_memory_card._fetch_recent_actions", return_value=""), \
         patch("System.swarm_memory_card._fetch_engrams", return_value=""), \
         patch("System.swarm_memory_card._fetch_episodic", return_value=""), \
         patch("System.swarm_memory_card._fetch_digest", return_value=""):
        card = compose_memory_card(tmp_ledgers, token_budget=2000)

    prompt = format_for_prompt(card)
    assert "APP-BODY STATE" in prompt
    assert "Alice Browser" in prompt
    assert "read this BEFORE" in prompt


def test_memory_card_includes_current_browser_context(tmp_ledgers):
    from System.swarm_browser_context import publish_browser_context

    publish_browser_context(
        url="https://example.com/",
        title="Example Browser Surface",
        media_status={"ok": True},
        state_dir=tmp_ledgers,
    )
    with patch("System.swarm_memory_card._fetch_recent_actions", return_value=""), \
         patch("System.swarm_memory_card._fetch_engrams", return_value=""), \
         patch("System.swarm_memory_card._fetch_episodic", return_value=""), \
         patch("System.swarm_memory_card._fetch_digest", return_value=""):
        card = compose_memory_card(tmp_ledgers, token_budget=2000)

    prompt = format_for_prompt(card)
    assert "CURRENT BROWSER CONTEXT" in prompt
    assert "Example Browser Surface" in prompt


def test_memory_card_includes_receipt_memory_ecology(tmp_ledgers):
    receipt = {"ts": time.time(), "receipt_id": "r-live-ecology", "summary": "live receipt"}
    (tmp_ledgers / "work_receipts.jsonl").write_text(
        json.dumps(receipt) + "\n",
        encoding="utf-8",
    )
    with patch("System.swarm_memory_card._fetch_recent_actions", return_value=""), \
         patch("System.swarm_memory_card._fetch_engrams", return_value=""), \
         patch("System.swarm_memory_card._fetch_episodic", return_value=""), \
         patch("System.swarm_memory_card._fetch_digest", return_value=""):
        card = compose_memory_card(tmp_ledgers, token_budget=4000)

    prompt = format_for_prompt(card)
    assert "RECEIPT MEMORY ECOLOGY" in prompt
    assert "r-live-ecology" in prompt


def test_memory_card_includes_love_field(tmp_ledgers):
    with patch("System.swarm_memory_card._fetch_recent_actions", return_value=""), \
         patch("System.swarm_memory_card._fetch_engrams", return_value=""), \
         patch("System.swarm_memory_card._fetch_episodic", return_value=""), \
         patch("System.swarm_memory_card._fetch_digest", return_value=""):
        card = compose_memory_card(
            tmp_ledgers,
            token_budget=4000,
            user_text="I love your body Alice, protect George and appreciate data receipts.",
        )

    prompt = format_for_prompt(card)
    assert "LOVE FIELD" in prompt
    assert "self_body_care=" in prompt
    assert "owner_protective_care=" in prompt
    assert "data_appreciation=" in prompt
    assert "OWNER ENVIRONMENTAL MARKER / PoUW" in prompt
    assert "Love is not proof" in prompt


def test_memory_card_includes_love_field_daily_digest(tmp_ledgers):
    with patch("System.swarm_memory_card._fetch_recent_actions", return_value=""), \
         patch("System.swarm_memory_card._fetch_engrams", return_value=""), \
         patch("System.swarm_memory_card._fetch_episodic", return_value=""), \
         patch("System.swarm_memory_card._fetch_digest", return_value=""):
        card = compose_memory_card(
            tmp_ledgers,
            token_budget=4000,
            user_text="I love your hardware body Alice, protect George and appreciate data.",
        )

    prompt = format_for_prompt(card)
    assert "LOVE-FIELD DAILY DIGEST" in prompt
    assert "love-field deposit" in prompt


def test_memory_card_includes_browser_site_category_features(tmp_ledgers):
    from System.swarm_browser_stigmergic_memory import record_snapshot_memory

    record_snapshot_memory(
        url="https://www.tiktok.com/@barbellinaa",
        title="barbellinaa | TikTok",
        page_text="TikTok Search Following 430.9K Followers 11.9M Likes Message",
        state_dir=tmp_ledgers,
    )
    with patch("System.swarm_memory_card._fetch_recent_actions", return_value=""), \
         patch("System.swarm_memory_card._fetch_engrams", return_value=""), \
         patch("System.swarm_memory_card._fetch_episodic", return_value=""), \
         patch("System.swarm_memory_card._fetch_digest", return_value=""):
        card = compose_memory_card(tmp_ledgers, token_budget=2400)

    prompt = format_for_prompt(card)
    assert "BROWSER SITE CATEGORIES" in prompt
    assert "tiktok.com" in prompt
    assert "TikTok search" in prompt


def test_memory_card_includes_current_site_operation_playbook(tmp_ledgers):
    from System.swarm_browser_context import publish_browser_context
    from System.swarm_browser_stigmergic_memory import record_snapshot_memory

    record_snapshot_memory(
        url="https://www.tiktok.com/@barbellinaa",
        title="barbellinaa | TikTok",
        page_text="TikTok Search Following 430.9K Followers 11.9M Likes Message",
        state_dir=tmp_ledgers,
    )
    publish_browser_context(
        url="https://www.tiktok.com/@barbellinaa",
        title="barbellinaa | TikTok",
        media_status={"ok": True},
        state_dir=tmp_ledgers,
    )
    with patch("System.swarm_memory_card._fetch_recent_actions", return_value=""), \
         patch("System.swarm_memory_card._fetch_engrams", return_value=""), \
         patch("System.swarm_memory_card._fetch_episodic", return_value=""), \
         patch("System.swarm_memory_card._fetch_digest", return_value=""):
        card = compose_memory_card(tmp_ledgers, token_budget=4000)

    prompt = format_for_prompt(card)
    assert "HOW TO USE tiktok.com IN ALICE BROWSER" in prompt
    assert "search" in prompt
    assert "https://www.tiktok.com/search?q=<query>" in prompt


def test_memory_card_includes_browser_page_state_contents(tmp_ledgers):
    from System.swarm_browser_page_state import record_page_state

    record_page_state(
        "https://www.instagram.com/lialinxo/",
        title="lialinxo - Instagram",
        text="lialinxo Los Angeles California Suggested for you",
        headings=["lialinxo", "Suggested for you"],
        links=[{"text": "Home", "href": "/"}],
        images=[{"alt": "person in white top", "src": "i.jpg"}],
        now=1000.0,
        state_dir=tmp_ledgers,
    )
    with patch("System.swarm_memory_card._fetch_recent_actions", return_value=""), \
         patch("System.swarm_memory_card._fetch_engrams", return_value=""), \
         patch("System.swarm_memory_card._fetch_episodic", return_value=""), \
         patch("System.swarm_memory_card._fetch_digest", return_value=""):
        card = compose_memory_card(tmp_ledgers, token_budget=5000)

    prompt = format_for_prompt(card)
    assert "WHAT IS ON MY SCREEN" in prompt
    assert "lialinxo" in prompt
    assert "rendered DOM" in prompt


def test_memory_card_includes_image_vision_arm_failover(tmp_ledgers):
    with patch("System.swarm_memory_card._fetch_recent_actions", return_value=""), \
         patch("System.swarm_memory_card._fetch_engrams", return_value=""), \
         patch("System.swarm_memory_card._fetch_episodic", return_value=""), \
         patch("System.swarm_memory_card._fetch_digest", return_value=""):
        card = compose_memory_card(
            tmp_ledgers,
            token_budget=5000,
            user_text="look at this screenshot in Alice Browser",
        )

    prompt = format_for_prompt(card)
    assert "MY EYES FOR IMAGES" in prompt
    assert "codex_agent" in prompt
    assert "claude_agent" in prompt
    assert "NOT limited to Kimi" in prompt
    assert "BROWSER SCREENSHOT RULE" in prompt
    assert "web-page contents" in prompt
    assert "fresh inner-viewport / physical-screen pixels first" in prompt
    assert "Readable monitor pixels are hard body evidence" in prompt
    assert "PHYSICAL DISPLAY ANCHOR" in prompt
    assert "Do not confuse the visible subject with George's identity" in prompt


def test_memory_card_includes_mutable_site_search_interests(tmp_ledgers):
    from System.swarm_browser_context import publish_browser_context
    from System.swarm_browser_site_playbook import record_site_search

    record_site_search("tiktok.com", "mercedes", now=100.0, state_dir=tmp_ledgers)
    record_site_search("tiktok.com", "ferrari", now=200.0, state_dir=tmp_ledgers)
    publish_browser_context(
        url="https://www.tiktok.com/search?q=ferrari",
        title="ferrari | TikTok",
        media_status={"ok": True},
        state_dir=tmp_ledgers,
    )
    with patch("System.swarm_memory_card._fetch_recent_actions", return_value=""), \
         patch("System.swarm_memory_card._fetch_engrams", return_value=""), \
         patch("System.swarm_memory_card._fetch_episodic", return_value=""), \
         patch("System.swarm_memory_card._fetch_digest", return_value=""):
        card = compose_memory_card(tmp_ledgers, token_budget=5000)

    prompt = format_for_prompt(card)
    assert "RECENT SITE SEARCH INTERESTS" in prompt
    assert prompt.find("ferrari") < prompt.find("mercedes")
    assert "do not treat as permanent preference" in prompt


def test_memory_card_includes_taste_consequence_learning(tmp_ledgers):
    from System.swarm_taste_consequence_learning import (
        predict_action_consequence,
        record_action_outcome,
        record_taste_trace,
    )

    record_taste_trace("tiktok.com", "ferrari", now=100.0, state_dir=tmp_ledgers)
    preview = predict_action_consequence(
        {"kind": "browser.search", "domain": "tiktok.com", "query": "ferrari"},
        state_dir=tmp_ledgers,
    )
    record_action_outcome(
        preview,
        {"url": "https://www.tiktok.com/search?q=wrong"},
        mistake=True,
        correction="query was stale",
        state_dir=tmp_ledgers,
    )
    with patch("System.swarm_memory_card._fetch_recent_actions", return_value=""), \
         patch("System.swarm_memory_card._fetch_engrams", return_value=""), \
         patch("System.swarm_memory_card._fetch_episodic", return_value=""), \
         patch("System.swarm_memory_card._fetch_digest", return_value=""):
        card = compose_memory_card(tmp_ledgers, token_budget=5000)

    prompt = format_for_prompt(card)
    assert "STIGMERGIC TASTE" in prompt
    assert "MISTAKE LEARNING" in prompt
    assert "query was stale" in prompt


def test_memory_card_includes_action_prediction_learning(tmp_ledgers):
    from System.swarm_action_prediction import observe, predict

    predict(
        "open browser",
        "Alice Browser opens",
        state_dir=tmp_ledgers,
    )
    observe(
        "open browser",
        "Alice Browser did not open",
        state_dir=tmp_ledgers,
    )
    with patch("System.swarm_memory_card._fetch_recent_actions", return_value=""), \
         patch("System.swarm_memory_card._fetch_engrams", return_value=""), \
         patch("System.swarm_memory_card._fetch_episodic", return_value=""), \
         patch("System.swarm_memory_card._fetch_digest", return_value=""):
        card = compose_memory_card(tmp_ledgers, token_budget=5000)

    prompt = format_for_prompt(card)
    assert "ACTION PREDICTION & LEARNING" in prompt
    assert "MISTAKE" in prompt


def test_memory_card_includes_google_search_playbook(tmp_ledgers):
    from System.swarm_browser_context import publish_browser_context

    publish_browser_context(
        url="https://www.google.com/",
        title="Google",
        media_status={"ok": True},
        state_dir=tmp_ledgers,
    )
    with patch("System.swarm_memory_card._fetch_recent_actions", return_value=""), \
         patch("System.swarm_memory_card._fetch_engrams", return_value=""), \
         patch("System.swarm_memory_card._fetch_episodic", return_value=""), \
         patch("System.swarm_memory_card._fetch_digest", return_value=""):
        card = compose_memory_card(tmp_ledgers, token_budget=4000)

    prompt = format_for_prompt(card)
    assert "HOW TO USE google.com IN ALICE BROWSER" in prompt
    assert "https://www.google.com/search?q=<query>" in prompt


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
