from __future__ import annotations

from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
TALK_APP = REPO / "Applications" / "sifta_talk_to_alice_widget.py"


def test_general_browse_receipt_is_wired_into_talk_browser_url_path() -> None:
    source = TALK_APP.read_text(encoding="utf-8")
    browser_url_idx = source.index('command.get("kind") == "browser_url"')
    block = source[browser_url_idx : source.index('if command.get("autoplay_youtube_query")', browser_url_idx)]

    required = [
        "is_general_browse_request",
        "general_browse_requested",
        "latest_page_state",
        "build_general_browse_receipt",
        "alice_browser_page_state",
        "verify_after_act",
        "General browse receipt:",
    ]
    for text in required:
        assert text in block
