from __future__ import annotations

from Applications import sifta_talk_to_alice_widget as talk
from System import swarm_alice_slash_commands as slash


def test_self_screenshot_command_recognizes_sc_and_screenshot() -> None:
    assert talk._is_self_screenshot_command("/sc")
    assert talk._is_self_screenshot_command("/sc use history please")
    assert talk._is_self_screenshot_command("/screenshot")
    assert talk._is_self_screenshot_command("CAN U CHANGE PNG TO JPEG ? --\n/SC")
    assert talk._is_self_screenshot_command("---CAN U CHANGE PNG TO JPEG ? --\n/SC")
    assert talk._is_self_screenshot_command("note first\n/screenshot use history")
    assert talk._is_self_screenshot_command("/ screenshot") is False
    assert talk._is_self_screenshot_command("sc") is False
    assert talk._is_self_screenshot_command("please /sc now") is False
    assert talk._is_self_screenshot_command("https://example.com/sc") is False


def test_self_screenshot_jpegs_live_in_documentation_folder() -> None:
    out_dir = talk._self_screenshot_output_dir()

    assert out_dir.name == "self_screenshots"
    assert out_dir.parent.name == "Documentation"
    assert ".sifta_state" not in str(out_dir)


def test_self_screenshot_cortex_prompt_does_not_trigger_browser_video_state() -> None:
    prompt = talk._self_screenshot_cortex_prompt(
        "/sc",
        {
            "receipt_id": "r-self-1",
            "image_path": "/tmp/sifta_self.jpg",
            "window_title": "SIFTA Python GUI OS",
            "width": 1920,
            "height": 1080,
        },
    )

    assert talk._is_self_screenshot_cortex_turn(prompt)
    assert not talk._is_browser_video_state_query(prompt)


def test_sc_command_meaning_fiction_guard_rewrites_scroll_down_claim() -> None:
    prior = talk._self_screenshot_cortex_prompt(
        "/sc",
        {"receipt_id": "r1", "image_path": "/tmp/s.jpg"},
    )
    bad = (
        "I do know what /SC means! On TikTok, /SC is the universally accepted "
        "shorthand for Scroll Down."
    )
    fixed = talk._guard_sc_command_meaning_fiction(bad, prior_user_text=prior)

    assert "Self-Screenshot Cortex Turn" in fixed
    assert "scroll down" not in fixed.casefold() or "not tiktok" in fixed.casefold()


def test_self_screenshot_prompt_goes_to_cortex_not_direct_describe_bypass() -> None:
    prompt = talk._self_screenshot_cortex_prompt(
        "/sc",
        {
            "receipt_id": "r-self-1",
            "image_path": "/tmp/sifta_self.png",
            "window_title": "SIFTA Python GUI OS",
            "width": 1920,
            "height": 1080,
        },
    )

    assert "SELF-SCREENSHOT CORTEX TURN" in prompt
    assert "recent conversation history" in prompt
    assert "receipt_id=r-self-1" in prompt
    assert "SIFTA Python GUI OS" in prompt
    assert not talk._is_attached_image_description_query(prompt)


def test_slash_palette_does_not_consume_sc() -> None:
    result = slash.handle_slash_command(
        "/sc",
        state_dir="/tmp",
        current_cortex="alice-m5-cortex-8b-6.3gb:latest",
    )

    assert result["handled"] is False
    assert "/sc" in slash.command_list_text()


def test_page_affordance_command_recognizes_p_aliases() -> None:
    assert talk._is_page_affordance_command("/p")
    assert talk._is_page_affordance_command("/P")
    assert talk._is_page_affordance_command("/page")
    assert talk._is_page_affordance_command("/page-buttons")
    assert talk._is_page_affordance_command("p") is False
    assert talk._is_page_affordance_command("https://example.com/p") is False


def test_page_affordance_reply_formats_live_inventory_without_site_hardcode() -> None:
    reply = talk._format_page_affordance_reply(
        {
            "ok": True,
            "url": "https://example.test/current",
            "title": "Example Page",
            "count": 3,
            "elements": [
                {"label": "Search", "tag": "button"},
                {"label": "Open details", "tag": "a"},
                {"label": "Search", "tag": "button"},
            ],
        },
        receipt_id="r-page-1",
    )

    assert "Example Page" in reply
    assert "https://example.test/current" in reply
    assert "1. Search [button]" in reply
    assert "2. Open details [a]" in reply
    assert reply.count("Search") == 1
    assert "r-page-1" in reply
