"""r1621-01 — false 'can't see screen' when IG post receipt is live."""
from __future__ import annotations

from System.swarm_browser_mouth_false_denial import (
    grounded_post_description_from_state,
    is_browser_limb_denial,
    repair_browser_false_denial,
)


def test_detects_glass_denial_phrase():
    assert is_browser_limb_denial(
        "I don't have direct access to your screen or live data, so I can't see the Instagram post"
    )
    assert not is_browser_limb_denial(
        "The post shows a person from the caption receipt on my browser."
    )


def test_grounded_from_state_uses_caption_not_deny():
    # Synthetic fixture only — no real people hardcoded into production code.
    state = {
        "url": "https://www.instagram.com/p/EXAMPLEPOST01/",
        "title": "Instagram",
        "image_alts": [
            "owneraccount's profile picture",
            "Studio set of the model @examplehandle — follow for more",
        ],
        "comments": [{"author": "commenter1", "text": "Nice"}],
    }
    text = grounded_post_description_from_state(state)
    assert "instagram.com/p/EXAMPLEPOST01" in text
    assert "@examplehandle" in text or "Studio set" in text
    assert "don't have" not in text.lower()


def test_repair_replaces_denial_when_url_live():
    denial = (
        "I don't have direct access to your screen or live data, so I can't see "
        "the Instagram post currently open on your device. Paste a screenshot."
    )
    state = {
        "url": "https://www.instagram.com/p/EXAMPLEPOST01/",
        "image_alts": [
            "Studio set of the model @examplehandle — follow for more",
        ],
    }
    out = repair_browser_false_denial(
        denial,
        owner_text="ok, describe the instagram post pld, the one on screen, what's in the photo?",
        state=state,
    )
    assert out["changed"] is True
    assert "examplehandle" in out["text"] or "Studio set" in out["text"]
    assert "instagram.com/p/" in out["text"]
    assert "don't have direct access" not in out["text"].lower()


def test_no_repair_without_browser_url():
    out = repair_browser_false_denial(
        "I don't have direct access to your screen",
        owner_text="describe the post",
        state={},
    )
    assert out["changed"] is False
