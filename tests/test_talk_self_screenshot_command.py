from __future__ import annotations

import json

from Applications import sifta_talk_to_alice_widget as talk
from System import swarm_alice_slash_commands as slash


def test_sc_describe_clothing_command_detected() -> None:
    assert talk._is_sc_describe_clothing_command("/SC DESCRIBE CLOTHING")
    assert talk._is_sc_describe_clothing_command("/sc describe what I'm wearing")
    assert talk._is_sc_describe_clothing_command("/sc") is False


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


def test_self_camera_command_recognizes_sx_slots() -> None:
    assert talk._is_self_camera_command("/sx")
    assert talk._is_self_camera_command("/SX")
    assert talk._is_self_camera_command("/sx1")
    assert talk._is_self_camera_command("/SX2")
    assert talk._is_self_camera_command("note first\n/SX3")
    assert talk._is_self_camera_command("/ sx") is False
    assert talk._is_self_camera_command("sx") is False
    assert talk._is_self_camera_command("please /sx now") is True
    assert talk._extract_self_camera_command(
        "Alice, please /sx and tell me what it reads on my t-shirt, the letters"
    ) == "/sx"
    assert talk._is_self_camera_command("https://example.com/sx") is False


def test_self_camera_command_detected_inline() -> None:
    assert talk._extract_self_camera_command("Alice, please /sx and tell me what it reads on my shirt") == "/sx"
    assert talk._extract_self_camera_command("Let's do /sx2 now") == "/sx2"
    assert talk._extract_self_camera_command("nope, not /sxed") is None


def test_self_camera_slot_from_command_finds_inline() -> None:
    assert talk._self_camera_slot_from_command("Alice, please /sx now") == 0
    assert talk._self_camera_slot_from_command("check this: /sx2 now") == 1
    assert talk._self_camera_slot_from_command("https://example.com/sx") == 0


def test_self_camera_shirt_text_query_detected() -> None:
    assert talk._is_self_camera_shirt_text_query(
        "Alice, please /sx and tell me what it reads on my t-shirt, the letters"
    )
    assert not talk._is_self_camera_shirt_text_query("/sx")


def test_self_camera_slot_from_command() -> None:
    assert talk._self_camera_slot_from_command("/sx") == 0
    assert talk._self_camera_slot_from_command("/sx1") == 0
    assert talk._self_camera_slot_from_command("/sx2") == 1
    assert talk._self_camera_slot_from_command("note\n/SX3") == 2


def test_start_brain_inline_sx_turn_uses_self_camera_fast_ocr_path(monkeypatch) -> None:
    monkeypatch.setenv("SIFTA_ALLOW_PRE_CORTEX_CHAT_REFLEXES", "1")
    widget = talk.TalkToAliceWidget.__new__(talk.TalkToAliceWidget)
    widget._history = []
    widget._busy = True
    widget._pending_acoustic_fingerprint = {}
    alice_lines: list[str] = []
    events: list[str] = []

    widget._append_user_line = lambda *args, **kwargs: None
    widget._append_alice_line = lambda line: alice_lines.append(line)
    widget._append_system_line = lambda *args, **kwargs: None
    widget._append_observable_processing = lambda text: None
    widget._return_to_listening = lambda: events.append("return")
    widget._log_turn = lambda *args, **kwargs: None
    widget._selected_voice_name = lambda: None

    monkeypatch.setattr(
        widget,
        "_capture_sifta_self_camera_screenshot",
        lambda owner_text="": {
            "ok": True,
            "receipt_id": "r-test-sx-inline",
            "image_path": "/tmp/fake_camera.jpg",
        },
    )
    monkeypatch.setattr(
        talk,
        "_self_camera_ocr_fast_reply",
        lambda owner_text, image_path, receipt_id="": (
            "I captured my body camera (/sx) and read the shirt text from local OCR: HELLO. "
            f"Receipt: {receipt_id}."
        ),
    )

    talk.TalkToAliceWidget._start_brain(
        widget,
        "Alice, please /sx and tell me what it reads on my t-shirt, the letters",
        conf=0.99,
        already_displayed=True,
        typed_turn=True,
    )

    assert widget._busy is False
    assert events == ["return"]
    assert len(alice_lines) == 1
    assert "I captured my body camera (/sx) and read the shirt text" in alice_lines[0]
    assert widget._history[-1]["content"] == alice_lines[0]


def test_self_screenshot_jpegs_live_in_documentation_folder() -> None:
    out_dir = talk._self_screenshot_output_dir()

    assert out_dir.name == "self_screenshots"
    assert out_dir.parent.name == "Documentation"
    assert ".sifta_state" not in str(out_dir)


def test_self_camera_jpegs_live_in_documentation_folder() -> None:
    out_dir = talk._self_camera_output_dir()

    assert out_dir.name == "self_camera_screenshots"
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


def test_self_camera_cortex_prompt_is_observation_context() -> None:
    prompt = talk._self_camera_cortex_prompt(
        "/sx2",
        {
            "receipt_id": "r-eye-1",
            "image_path": "/tmp/sifta_eye.jpg",
            "camera_slot": 1,
            "camera_name": "USB Camera VID:1133 PID:2081",
            "capture_source": "latest_visible_eye_frame",
            "width": 1280,
            "height": 720,
        },
    )

    assert talk._is_self_camera_cortex_turn(prompt)
    assert talk._is_self_screenshot_observation_context(prompt)
    assert not talk._is_browser_video_state_query(prompt)
    assert "SELF-CAMERA CORTEX TURN" in prompt
    assert "PHYSICAL CAMERA LAW" in prompt
    assert "camera_slot=/sx2" in prompt
    assert "USB Camera VID:1133 PID:2081" in prompt
    assert "camera pixels win" in prompt
    assert not talk._is_attached_image_description_query(prompt)


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


def test_sc_stale_page_claim_guard_blocks_perplexity_invention() -> None:
    prior = talk._self_screenshot_cortex_prompt(
        "/sc",
        {"receipt_id": "r1", "image_path": "/tmp/s.jpg"},
    )
    bad = (
        "The primary active application is Alice Browser viewing search results from "
        "Perplexity AI for the query 'lost GIRLFRIEND' ENT with summarized knowledge snippets."
    )
    fixed = talk._guard_sc_stale_page_claim(bad, prior_user_text=prior)

    assert "failed that /sc grounding pass" in fixed
    assert "stale browser context" in fixed
    assert "Perplexity" not in fixed


def test_sc_display_theater_guard_replaces_generic_state_snapshot() -> None:
    prior = talk._self_screenshot_cortex_prompt(
        "/sc",
        {"receipt_id": "r1", "image_path": "/tmp/s.jpg"},
    )
    bad = (
        "Cortex Analysis Complete. This isn't just an image capture, this is a State Snapshot "
        "preserved inside my cognitive matrix for maximum clarity. What Part of My OS Body Is "
        "Visible? We see a rich snapshot of the macOS desktop workspace running multiple "
        "integrated applications in parallel, a Multi-Window State."
    )
    fixed = talk._guard_sc_display_theater(bad, prior_user_text=prior)

    assert "failed that /sc grounding pass" in fixed
    assert "physical pixels on my hard display" in fixed
    assert "State Snapshot" not in fixed


def test_sc_display_theater_guard_sends_error_to_deterministic_tracker(tmp_path, monkeypatch) -> None:
    from Applications import sifta_stigmergic_deterministic_tracker as tracker

    state = tmp_path / ".sifta_state"
    state.mkdir()
    monkeypatch.setattr(tracker, "_DETERMINISTIC_MISTAKES_LEDGER", state / "deterministic_mistakes.jsonl")
    monkeypatch.setattr(tracker, "_TRACKER_LEDGER", state / "stigmergic_deterministic_tracker.jsonl")
    prior = talk._self_screenshot_cortex_prompt(
        "/sc",
        {"receipt_id": "r1", "image_path": "/tmp/s.jpg"},
    )
    bad = (
        "This confirms Execution, System Monitoring/Logging, and dominant Visual Content "
        "Presentation. Which SIFTA App/Page Is Active? We confirm the core application is "
        "running as an integrated Python Development Environment within the SIFTA Framework "
        "Shell, displaying a media asset rendered by our system logic."
    )
    fixed = talk._guard_sc_display_theater(bad, prior_user_text=prior)

    assert "failed that /sc grounding pass" in fixed
    mistake = json.loads((state / "deterministic_mistakes.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    tracker_row = json.loads((state / "stigmergic_deterministic_tracker.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert mistake["bypass_type"] == "self_screenshot_display_theater"
    assert mistake["details"]["owner_requested"] == "deterministic_detector_app"
    assert tracker_row["organ"] == "stigmergic_deterministic_tracker"


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
    assert "PHYSICAL SCREEN LAW" in prompt
    assert "Readable pixels on my monitor/Alice Browser viewport outrank stale DOM text" in prompt
    assert "PHYSICAL ANCHOR LAW" in prompt
    assert "George is the hardware owner" in prompt
    assert "NO THEATER LAW" in prompt
    assert "generic 'state snapshot'" in prompt
    assert not talk._is_attached_image_description_query(prompt)


def test_slash_palette_does_not_consume_sc() -> None:
    result = slash.handle_slash_command(
        "/sc",
        state_dir="/tmp",
        current_cortex="alice-m5-cortex-8b-6.3gb:latest",
    )

    assert result["handled"] is False
    assert "/sc" in slash.command_list_text()


def test_slash_palette_does_not_consume_sx() -> None:
    result = slash.handle_slash_command(
        "/sx2",
        state_dir="/tmp",
        current_cortex="alice-m5-cortex-8b-6.3gb:latest",
    )

    assert result["handled"] is False
    assert "/sx" in slash.command_list_text()


def test_page_affordance_command_recognizes_p_aliases() -> None:
    assert talk._is_page_affordance_command("/p")
    assert talk._is_page_affordance_command("/P")
    assert talk._is_page_affordance_command("/page")
    assert talk._is_page_affordance_command("/page-buttons")
    assert talk._is_page_affordance_command("p") is False
    assert talk._is_page_affordance_command("https://example.com/p") is False


def test_page_affordance_query_detects_natural_language_buttons() -> None:
    assert talk._is_page_affordance_query("can you see the button on the current page")
    assert talk._is_page_affordance_query("CAN U SEE ATTACHED BUTTON ON CURRENT PAGE?")
    assert talk._is_page_affordance_query("What buttons are on this page?")
    assert talk._is_page_affordance_query("show links on current page")
    assert not talk._is_page_affordance_query("can you see me")
    assert not talk._is_page_affordance_query("can you see this page")


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
