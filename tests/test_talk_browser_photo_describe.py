from __future__ import annotations

import json
import time

from Applications import sifta_talk_to_alice_widget as talk
from System import swarm_browser_page_state as page_state
from System import swarm_browser_photo_description as photo_desc


def _write_live_browser_url(state_dir, url: str) -> None:
    (state_dir / "browser_context.jsonl").write_text(
        json.dumps({"ts": time.time(), "url": url}) + "\n",
        encoding="utf-8",
    )


def test_browser_photo_description_query_matches_explicit_photo_language() -> None:
    assert talk._is_browser_photo_description_query("Alice, describe this photo")
    assert talk._is_browser_photo_description_query("what do you see in the current browser image?")
    assert talk._is_browser_photo_description_query("look at the picture on this post")
    assert talk._is_browser_photo_description_query("Can you describe her swimsuit?")
    assert talk._is_browser_photo_description_query("Please describe her body.")


def test_browser_photo_description_query_matches_visual_corrections() -> None:
    assert talk._is_browser_photo_description_query("Actually, this is bikini. You have to look again.")
    assert talk._is_browser_photo_description_query("Look again, this is a swimsuit.")
    assert talk._is_browser_photo_description_query("I wish you could see her body.")
    assert talk._is_browser_photo_description_query("please look again at her swimsuit")


def test_browser_photo_description_query_allows_bare_describe_for_active_browser() -> None:
    assert talk._is_browser_photo_description_query("describe")
    assert talk._is_browser_photo_description_query("please describe this")


def test_browser_photo_description_query_does_not_steal_general_planning() -> None:
    assert not talk._is_browser_photo_description_query("describe the plan for tomorrow")
    assert not talk._is_browser_photo_description_query("describe how the app router works")
    assert not talk._is_browser_photo_description_query("look again at the code patch")
    assert not talk._is_browser_photo_description_query("body schema architecture")


def test_browser_photo_open_query_routes_to_browser_not_app_launcher() -> None:
    phrase = (
        "pls open the photo currently positioned against the beach/ocean backdrop, "
        "and what is her primary feature?"
    )

    assert talk._is_browser_photo_open_query(phrase)
    assert talk._is_browser_page_cortex_description_query(phrase)
    assert talk._extract_sifta_app_command(phrase) == {}


def test_vision_arm_from_current_cortex_model() -> None:
    assert talk._vision_arm_from_cortex_model("cline:cline-cli-default") == "cline_agent"
    assert talk._vision_arm_from_cortex_model("claude:opus") == "claude_agent"
    assert talk._vision_arm_from_cortex_model("codex:gpt-5.3-codex") == "codex_agent"
    assert talk._vision_arm_from_cortex_model("grok:grok-4.3") == "grok_agent"
    assert talk._vision_arm_from_cortex_model("qwen:accounts/fireworks/models/kimi-k2p6") == "qwen_agent"


def test_browser_photo_context_active_from_focused_browser(monkeypatch) -> None:
    monkeypatch.setattr(talk, "_active_sifta_app_name_for_prompt", lambda: "Alice Browser")
    monkeypatch.setattr(talk, "_current_browser_page_snapshot", lambda max_age_s=900.0: {})
    monkeypatch.setattr(talk, "_find_live_alice_browser_widget", lambda: None)

    assert talk._browser_photo_description_context_active()


def test_browser_photo_context_active_from_fresh_snapshot(monkeypatch) -> None:
    monkeypatch.setattr(talk, "_active_sifta_app_name_for_prompt", lambda: "")
    monkeypatch.setattr(talk, "_current_browser_page_snapshot", lambda max_age_s=900.0: {"url": "https://example.com"})
    monkeypatch.setattr(talk, "_find_live_alice_browser_widget", lambda: None)

    assert talk._browser_photo_description_context_active()


def test_browser_photo_context_inactive_without_browser_or_snapshot(monkeypatch) -> None:
    monkeypatch.setattr(talk, "_active_sifta_app_name_for_prompt", lambda: "Ace")
    monkeypatch.setattr(talk, "_current_browser_page_snapshot", lambda max_age_s=900.0: {})
    monkeypatch.setattr(talk, "_find_live_alice_browser_widget", lambda: None)

    assert not talk._browser_photo_description_context_active()


def test_browser_photo_context_active_from_live_widget(monkeypatch) -> None:
    monkeypatch.setattr(talk, "_active_sifta_app_name_for_prompt", lambda: "Swarm App Store")
    monkeypatch.setattr(talk, "_current_browser_page_snapshot", lambda max_age_s=900.0: {})
    monkeypatch.setattr(talk, "_find_live_alice_browser_widget", lambda: object())

    assert talk._browser_photo_description_context_active()


def test_comments_summary_query_matches_explicit_and_followup() -> None:
    assert talk._is_comments_summary_query("Can you summarize the comments?")
    assert talk._is_comments_summary_query(
        "Yes please can you summarize them?",
        history=[
            {"role": "user", "content": "summarize the loaded comments"},
            {"role": "assistant", "content": "I will summarize only captured comments."},
        ],
    )
    assert not talk._is_comments_summary_query(
        "Yes please can you summarize them?",
        history=[{"role": "user", "content": "summarize the app plan"}],
    )


def test_describe_this_page_matches_browser_page_reflex() -> None:
    assert talk._is_webpage_summary_query("Please describe this page.")
    assert talk._is_webpage_summary_query("What page am I on?")
    assert talk._is_webpage_summary_query("What am I looking at right now?")


def test_loaded_in_alice_browser_can_you_tell_hits_live_page_reflex() -> None:
    assert talk._is_current_page_query("yes, i have youtube loaded in alice browser now, can you tell?")
    assert talk._is_current_page_query("Can you tell what is loaded in Alice Browser?")


def test_describe_instagram_page_uses_cortex_lane_not_raw_dom() -> None:
    assert talk._is_browser_page_cortex_description_query("Please describe this Instagram page.")
    assert talk._is_browser_page_cortex_description_query("describe this page")
    assert not talk._is_browser_page_cortex_description_query("What page am I on right now?")
    assert not talk._is_browser_page_cortex_description_query("Can you summarize the comments?")
    assert talk._is_browser_page_cortex_description_query("Can you describe her outfit?")


def test_current_page_summary_refreshes_live_manual_browser(monkeypatch, tmp_path) -> None:
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    url = "https://www.instagram.com/p/DX5OL9GGam/?img_index=1"

    class FakeBrowser:
        def refresh_current_page_state(self, wait_ms=0):
            (state_dir / "browser_context.jsonl").write_text(
                json.dumps({"url": url, "ts": time.time()}) + "\n",
                encoding="utf-8",
            )
            page_state.record_page_state(
                url,
                title="Instagram",
                text="mikaylademaiter i'm the reason love at first sight exists",
                headings=["mikaylademaiter"],
                images=[{"alt": "person in a red outfit", "src": "post.jpg"}],
                comments=[{"author": "fan_one", "text": "Wonderful"}],
                state_dir=state_dir,
            )
            return url

    class DummyTalk:
        def __init__(self):
            self.lines = []

        def _append_system_line(self, line, error=False):
            self.lines.append((line, error))

    monkeypatch.setattr(talk, "_state_root", lambda: state_dir)
    monkeypatch.setattr(talk, "_find_live_alice_browser_widget", lambda: FakeBrowser())

    dummy = DummyTalk()
    reply = talk.TalkToAliceWidget._execute_current_page_summary(dummy)

    assert url in reply
    assert "mikaylademaiter" in reply
    assert "Comment thread" in reply
    assert dummy.lines


def test_current_page_summary_states_live_url_when_dom_not_ready(monkeypatch, tmp_path) -> None:
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    url = "https://www.instagram.com/p/NEWPOST/"

    class FakeBrowser:
        def refresh_current_page_state(self, wait_ms=0):
            return url

    class DummyTalk:
        def _append_system_line(self, line, error=False):
            pass

    monkeypatch.setattr(talk, "_state_root", lambda: state_dir)
    monkeypatch.setattr(talk, "_find_live_alice_browser_widget", lambda: FakeBrowser())

    reply = talk.TalkToAliceWidget._execute_current_page_summary(DummyTalk())

    assert f"I am on {url}" in reply
    assert "browser widget" in reply


def test_browser_page_cortex_context_wraps_receipt_without_answer_dump(monkeypatch, tmp_path) -> None:
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    url = "https://www.instagram.com/p/DY35YqljJwT/?img_index=1"
    (state_dir / "browser_context.jsonl").write_text(
        json.dumps({"url": url, "ts": time.time()}) + "\n",
        encoding="utf-8",
    )
    page_state.record_page_state(
        url,
        title="Instagram",
        text="ramonna_olaru Ramona Nicoleta Olaru TV show Stay humble",
        headings=["ramonna_olaru", "@sitaraclothing.official"],
        images=[{"alt": "ramonna_olaru's profile picture", "src": "profile.jpg"}],
        comments=[{"author": "roxanavancea", "text": "Uuu hearts"}],
        state_dir=state_dir,
    )

    class DummyTalk:
        def __init__(self):
            self.lines = []

        def _append_system_line(self, line, error=False):
            self.lines.append((line, error))

    monkeypatch.setattr(talk, "_state_root", lambda: state_dir)
    monkeypatch.setattr(talk, "_refresh_live_alice_browser_page", lambda wait_ms=0: url)
    monkeypatch.setattr(talk, "_write_app_command_receipt", lambda **kwargs: "context-receipt")

    dummy = DummyTalk()
    block = talk.TalkToAliceWidget._browser_page_cortex_context_block(
        dummy,
        "Please describe this Instagram page.",
    )

    assert block.startswith("ALICE BROWSER PAGE CONTEXT FOR CORTEX")
    assert "do NOT print this raw block" in block
    assert "WHAT IS ON MY SCREEN" in block
    assert "Treat Instagram legal/footer/about links as page chrome" in block
    assert "ramonna_olaru" in block
    assert dummy.lines == [("Web page-context receipt: context-receipt", False)]


def test_browser_photo_context_does_not_treat_api_error_as_visual_evidence(monkeypatch, tmp_path) -> None:
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    url = "https://www.instagram.com/p/DZAktltGvMv/"
    page_state.record_page_state(
        url,
        title="Instagram",
        text="Hollywood Reporter Alexa Demie cover story teaser",
        headings=["hollywoodreporter"],
        state_dir=state_dir,
    )

    class FakeBrowser:
        def describe_current_photo(self, **kwargs):
            return {
                "status": "failed",
                "description": "API error 401: missing xAI key",
                "attempts": [{"arm": "grok_agent", "status": "EXEC_FAILED_COMMAND_FAILED"}],
            }

    class DummyTalk:
        def _append_system_line(self, line, error=False):
            pass

        def _current_brain_model(self, owner_text):
            return "grok:grok-4.3"

    monkeypatch.setattr(talk, "_state_root", lambda: state_dir)
    monkeypatch.setattr(talk, "_refresh_live_alice_browser_page", lambda wait_ms=0: url)
    monkeypatch.setattr(talk, "_find_live_alice_browser_widget", lambda: FakeBrowser())
    monkeypatch.setattr(talk, "_write_app_command_receipt", lambda **kwargs: "context-receipt")

    block = talk.TalkToAliceWidget._browser_page_cortex_context_block(
        DummyTalk(),
        "Can you describe her outfit and her body please?",
    )

    assert "VISION ROUTING NOTE" in block
    assert "VISUAL EVIDENCE —" not in block
    assert "API error 401" not in block
    assert "grok_agent:EXEC_FAILED_COMMAND_FAILED" in block


def test_page_state_surfaces_instagram_video_playback_error(tmp_path) -> None:
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    url = "https://www.instagram.com/reel/ERROR/"
    page_state.record_page_state(
        url,
        title="Instagram",
        text="coffin_couture Suggested for you Sorry, we're having trouble playing this video.",
        headings=["coffin_couture"],
        media_playback={
            "status": "error",
            "visible_error_text": "Sorry, we're having trouble playing this video.",
        },
        state_dir=state_dir,
    )

    latest = page_state.latest_page_state(state_dir=state_dir)
    err = page_state.media_playback_error_from_state(latest)
    block = page_state.page_state_block(state_dir=state_dir)

    assert err["kind"] == "instagram_video_playback_error"
    assert err["message"] == "Sorry, we're having trouble playing this video."
    assert "Media playback error visible on screen" in block
    assert "do not describe a photo/video frame" in block


def test_browser_page_cortex_context_prefers_playback_error_over_vision(monkeypatch, tmp_path) -> None:
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    url = "https://www.instagram.com/reel/ERROR/"
    _write_live_browser_url(state_dir, url)
    page_state.record_page_state(
        url,
        title="Instagram",
        text="Sorry, we're having trouble playing this video.",
        headings=["coffin_couture"],
        media_playback={
            "status": "error",
            "visible_error_text": "Sorry, we're having trouble playing this video.",
        },
        state_dir=state_dir,
    )

    class FakeBrowser:
        def describe_current_photo(self, **kwargs):
            raise AssertionError("vision should not run for a visible playback-error screen")

    class DummyTalk:
        def _append_system_line(self, line, error=False):
            pass

        def _current_brain_model(self, owner_text):
            return "grok:grok-4.3"

    monkeypatch.setattr(talk, "_state_root", lambda: state_dir)
    monkeypatch.setattr(talk, "_refresh_live_alice_browser_page", lambda wait_ms=0: url)
    monkeypatch.setattr(talk, "_find_live_alice_browser_widget", lambda: FakeBrowser())
    monkeypatch.setattr(talk, "_write_app_command_receipt", lambda **kwargs: "context-receipt")

    block = talk.TalkToAliceWidget._browser_page_cortex_context_block(
        DummyTalk(),
        "please describe the photo",
    )

    assert "SCREEN MEDIA ERROR RECEIPT" in block
    assert "Sorry, we're having trouble playing this video." in block
    assert "VISUAL EVIDENCE — what my vision arm actually saw" not in block


def test_browser_photo_context_uses_same_url_anchor_after_grok_403(monkeypatch, tmp_path) -> None:
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    url = "https://www.instagram.com/p/CbVbizsJzKi/"
    page_state.record_page_state(
        url,
        title="Instagram",
        text="kylinmilan Hiking shoes for models",
        headings=["kylinmilan"],
        state_dir=state_dir,
    )
    photo_desc.record_photo_description(
        url,
        description="A woman wears a colorful floral bikini top, green bikini bottoms, fuzzy green leg warmers, and heels.",
        arm="claude_agent",
        now=time.time() - 20,
        state_dir=state_dir,
    )

    class FakeBrowser:
        _current_url = url

        def describe_current_photo(self, **kwargs):
            return {
                "status": "grok_eye_failed",
                "description": "",
                "attempts": [{"arm": "grok_agent", "status": "oauth_bad_credentials"}],
            }

    class DummyTalk:
        def _append_system_line(self, line, error=False):
            pass

        def _current_brain_model(self, owner_text):
            return "grok:grok-4.3"

    monkeypatch.setattr(talk, "_state_root", lambda: state_dir)
    monkeypatch.setattr(talk, "_refresh_live_alice_browser_page", lambda wait_ms=0: url)
    monkeypatch.setattr(talk, "_find_live_alice_browser_widget", lambda: FakeBrowser())
    monkeypatch.setattr(talk, "_write_app_command_receipt", lambda **kwargs: "context-receipt")

    block = talk.TalkToAliceWidget._browser_page_cortex_context_block(
        DummyTalk(),
        "so BioHuman body example she is wearing bikini or shorts, can you describe photo scan again",
    )

    assert "ANCHORED VISUAL EVIDENCE" in block
    assert "fresh selected-eye scan failed" in block
    assert "grok_agent:oauth_bad_credentials" in block
    assert "green bikini bottoms" in block
    assert "VISUAL EVIDENCE — what my vision arm actually saw" not in block


def test_direct_photo_description_reports_visible_playback_error_without_eye(monkeypatch, tmp_path) -> None:
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    url = "https://www.instagram.com/reel/ERROR/"

    class FakeBrowser:
        _current_url = url

        def refresh_current_page_state(self):
            _write_live_browser_url(state_dir, url)
            page_state.record_page_state(
                url,
                title="Instagram",
                text="Sorry, we're having trouble playing this video.",
                media_playback={
                    "status": "error",
                    "visible_error_text": "Sorry, we're having trouble playing this video.",
                },
                state_dir=state_dir,
            )
            return url

        def describe_current_photo(self, **kwargs):
            raise AssertionError("vision should not run for a visible playback-error screen")

    class DummyTalk:
        def __init__(self):
            self.lines = []

        def _append_system_line(self, line, error=False):
            self.lines.append((line, error))

        def _current_brain_model(self, owner_text):
            return "grok:grok-4.3"

    monkeypatch.setattr(talk, "_state_root", lambda: state_dir)
    monkeypatch.setattr(talk, "_find_live_alice_browser_widget", lambda: FakeBrowser())
    monkeypatch.setattr(talk, "_write_app_command_receipt", lambda **kwargs: "photo-receipt")

    reply = talk.TalkToAliceWidget._execute_current_browser_photo_description(
        DummyTalk(),
        "Please describe the photo",
    )

    assert "Instagram video playback error" in reply
    assert "Sorry, we're having trouble playing this video." in reply
    assert "no usable video pixels" in reply


def test_visual_reply_self_check_corrects_stale_photo_answer(monkeypatch, tmp_path) -> None:
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    url = "https://www.instagram.com/reel/ERROR/"
    _write_live_browser_url(state_dir, url)
    page_state.record_page_state(
        url,
        title="Instagram",
        text="Sorry, we're having trouble playing this video.",
        media_playback={
            "status": "error",
            "visible_error_text": "Sorry, we're having trouble playing this video.",
        },
        state_dir=state_dir,
    )
    monkeypatch.setattr(talk, "_state_root", lambda: state_dir)

    corrected, meta = talk._browser_visual_reply_self_check(
        "She is wearing a black dress in the photo.",
        "please describe the photo",
    )

    assert meta["changed"] is True
    assert "Instagram video playback error" in corrected
    assert "Sorry, we're having trouble playing this video." in corrected
    assert "black dress" not in corrected


def test_visual_reply_self_check_leaves_non_visual_answer_alone(monkeypatch, tmp_path) -> None:
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    _write_live_browser_url(state_dir, "https://www.instagram.com/reel/ERROR/")
    page_state.record_page_state(
        "https://www.instagram.com/reel/ERROR/",
        title="Instagram",
        text="Sorry, we're having trouble playing this video.",
        media_playback={
            "status": "error",
            "visible_error_text": "Sorry, we're having trouble playing this video.",
        },
        state_dir=state_dir,
    )
    monkeypatch.setattr(talk, "_state_root", lambda: state_dir)

    reply, meta = talk._browser_visual_reply_self_check(
        "I can help with that after the page settles.",
        "what should we do next?",
    )

    assert meta["changed"] is False
    assert reply == "I can help with that after the page settles."


def test_visual_reply_self_check_ignores_stale_media_error_after_navigation(monkeypatch, tmp_path) -> None:
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    _write_live_browser_url(state_dir, "https://www.instagram.com/p/FRESH/")
    page_state.record_page_state(
        "https://www.instagram.com/reel/OLD_ERROR/",
        title="Instagram",
        text="Sorry, we're having trouble playing this video.",
        media_playback={
            "status": "error",
            "visible_error_text": "Sorry, we're having trouble playing this video.",
        },
        state_dir=state_dir,
    )
    monkeypatch.setattr(talk, "_state_root", lambda: state_dir)

    reply, meta = talk._browser_visual_reply_self_check(
        "The fresh photo shows a person in a black tuxedo.",
        "please describe the photo",
    )

    assert meta["changed"] is False
    assert meta["reason"] == "no_media_error_receipt"
    assert reply == "The fresh photo shows a person in a black tuxedo."


def test_ace_word_action_requires_focused_ace_surface_or_explicit_ace(monkeypatch) -> None:
    monkeypatch.setattr(talk, "_current_ace_word_for_routing", lambda: "money")
    monkeypatch.setattr(talk, "_active_sifta_app_name_for_prompt", lambda: "Alice Browser")

    assert not talk._is_ace_word_action_query("please print money")
    assert talk._is_ace_word_action_query("Ace please print money")

    monkeypatch.setattr(talk, "_active_sifta_app_name_for_prompt", lambda: "Ace")

    assert talk._is_ace_word_action_query("please print money")


def test_direct_photo_description_uses_same_url_anchor_after_grok_failure(monkeypatch, tmp_path) -> None:
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    url = "https://www.instagram.com/p/CbVbizsJzKi/"
    photo_desc.record_photo_description(
        url,
        description="A woman wears a colorful floral bikini top, green bikini bottoms, fuzzy green leg warmers, and heels.",
        arm="claude_agent",
        now=time.time() - 10,
        state_dir=state_dir,
    )

    class FakeBrowser:
        _current_url = url

        def refresh_current_page_state(self):
            return url

        def describe_current_photo(self, **kwargs):
            return {
                "status": "grok_eye_failed",
                "description": "",
                "arm": "grok_agent",
                "attempts": [{"arm": "grok_agent", "status": "oauth_bad_credentials"}],
            }

    class DummyTalk:
        def __init__(self):
            self.lines = []

        def _append_system_line(self, line, error=False):
            self.lines.append((line, error))

        def _current_brain_model(self, owner_text):
            return "grok:grok-4.3"

    monkeypatch.setattr(talk, "_state_root", lambda: state_dir)
    monkeypatch.setattr(talk, "_find_live_alice_browser_widget", lambda: FakeBrowser())
    monkeypatch.setattr(talk, "_write_app_command_receipt", lambda **kwargs: "photo-receipt")

    reply = talk.TalkToAliceWidget._execute_current_browser_photo_description(
        DummyTalk(),
        "bikini or shorts?",
    )

    assert "fresh Grok scan failed" in reply
    assert "green bikini bottoms" in reply
    assert "not calling that a new look" in reply


def test_direct_photo_description_reports_codex_failure_without_claude_fallback(monkeypatch, tmp_path) -> None:
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()

    class FakeBrowser:
        _current_url = "https://www.instagram.com/p/current/"

        def refresh_current_page_state(self):
            return self._current_url

        def describe_current_photo(self, **kwargs):
            return {
                "status": "codex_eye_failed",
                "description": "",
                "arm": "codex_agent",
                "error_summary": "codex returned no usable visual text",
                "attempts": [{"arm": "codex_agent", "status": "OK"}],
            }

    class DummyTalk:
        def __init__(self):
            self.lines = []

        def _append_system_line(self, line, error=False):
            self.lines.append((line, error))

        def _current_brain_model(self, owner_text):
            return "codex:gpt-5.5"

    monkeypatch.setattr(talk, "_state_root", lambda: state_dir)
    monkeypatch.setattr(talk, "_find_live_alice_browser_widget", lambda: FakeBrowser())
    monkeypatch.setattr(talk, "_write_app_command_receipt", lambda **kwargs: "photo-receipt")

    reply = talk.TalkToAliceWidget._execute_current_browser_photo_description(
        DummyTalk(),
        "please describe the photo",
    )

    assert "selected Codex eye" in reply
    assert "codex returned no usable visual text" in reply
    assert "did not switch to Claude" in reply


def test_next_photo_advances_and_scans_new_frame(monkeypatch) -> None:
    calls = []
    composed = {}

    class FakeLoop:
        def __init__(self, parent=None):
            pass

        def exec(self):
            calls.append(("settle",))

        def quit(self):
            pass

    class FakeBrowser:
        _current_url = "https://www.instagram.com/p/OLD/"

        def go_next_photo(self):
            calls.append(("next",))
            self._current_url = "https://www.instagram.com/p/NEW/"
            return "next"

        def refresh_current_page_state(self):
            calls.append(("refresh",))
            return self._current_url

        def describe_current_photo(self, **kwargs):
            calls.append(("describe", kwargs))
            return {
                "status": "described",
                "arm": kwargs.get("current_arm"),
                "description": "BioHuman wears a bright pink satin robe-style mini dress and holds a spoon and bowl indoors.",
            }

    class DummyTalk:
        def __init__(self):
            self.lines = []

        def _append_system_line(self, line, error=False):
            self.lines.append((line, error))

        def _current_brain_model(self, owner_text):
            return "claude:opus"

    monkeypatch.setattr(talk, "_find_live_alice_browser_widget", lambda: FakeBrowser())
    monkeypatch.setattr(talk, "_write_app_command_receipt", lambda **kwargs: "next-receipt")
    monkeypatch.setattr(talk, "QEventLoop", FakeLoop)
    monkeypatch.setattr(talk.QTimer, "singleShot", lambda ms, cb: None)
    monkeypatch.setattr(
        talk,
        "_visual_subject_identity_evidence",
        lambda owner_text, **kwargs: {
            "name": "BioHuman",
            "source": "owner_correction",
            "confidence": 0.98,
            "evidence": "owner correction",
        },
    )

    def fake_compose(owner_text, visual_description, **kwargs):
        composed.update({"owner_text": owner_text, "visual": visual_description, **kwargs})
        return "BioHuman is in a bright pink satin robe-style mini dress, holding a spoon and bowl indoors."

    monkeypatch.setattr(talk, "_compose_next_photo_reply_with_cortex", fake_compose)

    dummy = DummyTalk()
    reply = talk.TalkToAliceWidget._execute_next_browser_photo(dummy, "Next post please")

    assert [c[0] for c in calls] == ["next", "settle", "refresh", "describe"]
    assert calls[-1][1]["current_arm"] == "claude_agent"
    assert composed["identity"]["name"] == "BioHuman"
    assert "New visual anchor" not in reply
    assert reply.startswith("BioHuman is")
    assert "bright pink satin robe-style mini dress" in reply
    assert dummy.lines == [("Browser next-photo receipt: next-receipt", False)]


def test_next_photo_reports_codex_failure_without_claude_fallback(monkeypatch) -> None:
    calls = []

    class FakeLoop:
        def __init__(self, parent=None):
            pass

        def exec(self):
            calls.append(("settle",))

        def quit(self):
            pass

    class FakeBrowser:
        _current_url = "https://www.instagram.com/p/CODEX/"

        def go_next_photo(self):
            calls.append(("next",))
            return "next"

        def refresh_current_page_state(self):
            calls.append(("refresh",))
            return self._current_url

        def describe_current_photo(self, **kwargs):
            calls.append(("describe", kwargs))
            return {
                "status": "codex_eye_failed",
                "arm": "codex_agent",
                "description": "",
                "error_summary": "codex returned no usable visual text",
                "attempts": [{"arm": "codex_agent", "status": "OK"}],
            }

    class DummyTalk:
        def __init__(self):
            self.lines = []

        def _append_system_line(self, line, error=False):
            self.lines.append((line, error))

        def _current_brain_model(self, owner_text):
            return "codex:gpt-5.5"

    monkeypatch.setattr(talk, "_find_live_alice_browser_widget", lambda: FakeBrowser())
    monkeypatch.setattr(talk, "_write_app_command_receipt", lambda **kwargs: "next-receipt")
    monkeypatch.setattr(talk, "QEventLoop", FakeLoop)
    monkeypatch.setattr(talk.QTimer, "singleShot", lambda ms, cb: None)

    dummy = DummyTalk()
    reply = talk.TalkToAliceWidget._execute_next_browser_photo(dummy, "next slide pls")

    assert [c[0] for c in calls] == ["next", "settle", "refresh", "describe"]
    assert calls[-1][1]["current_arm"] == "codex_agent"
    assert "selected Codex eye" in reply
    assert "did not switch to Claude" in reply
    assert "will not reuse the previous photo" in reply


def test_selected_eye_failure_hides_raw_grok_oauth_json() -> None:
    raw = (
        '{"code":"The caller does not have permission to execute the specified operation",'
        '"error":"The OAuth2 access token could not be validated. '
        '[WKE=unauthenticated:bad-credentials]"}'
    )

    reply = talk._selected_eye_failure_reply("grok_eye_auth_refresh_required", "grok_agent", raw)

    assert "raw JSON" not in reply
    assert '{"code"' not in reply
    assert "OAuth credential could not be validated" in reply
    assert "did not switch to Claude" in reply


def test_visual_subject_identity_owner_correction_is_generic() -> None:
    leonardo = talk._visual_subject_identity_from_owner_text("her name is Leonardo, you can not read?")
    alex = talk._visual_subject_identity_from_owner_text("his name is Alex Morgan; use his name")

    assert leonardo["name"] == "Leonardo"
    assert leonardo["source"] == "owner_correction"
    assert alex["name"] == "Alex Morgan"


def test_next_photo_fallback_binds_verified_name_without_cortex() -> None:
    reply = talk._identity_bound_visual_fallback(
        "A young man poses outdoors, wearing a blue jacket.",
        {"name": "Alex", "source": "owner_correction", "confidence": 0.98},
    )

    assert reply.startswith("Next photo. Alex poses outdoors")
    assert "A young man" not in reply


def test_browser_photo_open_context_invokes_browser_selection_before_vision(monkeypatch, tmp_path) -> None:
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    url = "https://www.instagram.com/kylinmilan/"
    page_state.record_page_state(
        url,
        title="BioHuman Body (@kylinmilan) Instagram",
        text="BioHuman Body Music Artist Actress Runway Model",
        headings=["kylinmilan"],
        state_dir=state_dir,
    )
    calls = []

    class FakeBrowser:
        def open_visible_photo_matching_text(self, owner_text, **kwargs):
            calls.append(("open", owner_text, kwargs))
            return {
                "status": "opened",
                "href": "https://www.instagram.com/p/OCEAN/",
                "row": 3,
                "col": 4,
                "used_vision": True,
            }

        def describe_current_photo(self, **kwargs):
            calls.append(("describe", kwargs))
            return {
                "status": "described",
                "arm": "grok_agent",
                "description": "A woman poses on a beach in a bikini with ocean water behind her.",
            }

    class DummyTalk:
        def __init__(self):
            self.lines = []

        def _append_system_line(self, line, error=False):
            self.lines.append((line, error))

        def _current_brain_model(self, owner_text):
            return "grok:grok-4.3"

    monkeypatch.setattr(talk, "_state_root", lambda: state_dir)
    monkeypatch.setattr(talk, "_refresh_live_alice_browser_page", lambda wait_ms=0: url)
    monkeypatch.setattr(talk, "_find_live_alice_browser_widget", lambda: FakeBrowser())
    monkeypatch.setattr(talk, "_write_app_command_receipt", lambda **kwargs: "context-receipt")

    block = talk.TalkToAliceWidget._browser_page_cortex_context_block(
        DummyTalk(),
        "pls open the photo currently positioned against the beach/ocean backdrop, and what is her primary feature?",
    )

    assert calls[0][0] == "open"
    assert calls[1][0] == "describe"
    assert "BROWSER ACTION EVIDENCE" in block
    assert "VISUAL EVIDENCE" in block
    assert "row=3, col=4" in block


def test_contextual_visual_shopping_search_composes_query_then_opens_google(monkeypatch, tmp_path) -> None:
    opened = {}

    class DummyTalk:
        def __init__(self):
            self._history = [
                {
                    "role": "assistant",
                    "content": (
                        "Yeah. Beach one now. Pink and black checkered bikini, "
                        "arms raised overhead, ocean waves behind her."
                    ),
                }
            ]
            self.lines = []

        def _append_system_line(self, line, error=False):
            self.lines.append((line, error))

        def _current_brain_model(self, owner_text):
            return "grok:grok-4"

        def _execute_sifta_app_command(self, command):
            opened.update(command)
            return "Searching Google for pink black checkered bikini."

    monkeypatch.setattr(
        talk,
        "_latest_contextual_search_evidence",
        lambda **kwargs: "Latest browser photo vision: Pink and black checkered bikini on a beach.",
    )
    monkeypatch.setattr(
        talk,
        "_compose_contextual_search_query_with_cortex",
        lambda owner_text, evidence, model="": {
            "query": "pink black checkered bikini",
            "source": "cortex",
            "raw": '{"query":"pink black checkered bikini"}',
        },
    )
    monkeypatch.setattr(talk, "_write_app_command_receipt", lambda **kwargs: "search-receipt")

    phrase = "Where can I buy this type of bikini? Can you search on Google?"
    assert talk._is_contextual_browser_search_request(phrase)
    reply = talk.TalkToAliceWidget._execute_contextual_browser_search(DummyTalk(), phrase)

    assert "searched Google for pink black checkered bikini" in reply
    assert opened["kind"] == "browser_url"
    assert opened["query"] == "pink black checkered bikini"
    assert opened["url"].endswith("q=pink+black+checkered+bikini")


def test_contextual_visual_search_resolves_vague_wardrobe_piece(monkeypatch, tmp_path) -> None:
    opened = {}

    class DummyTalk:
        def __init__(self):
            self._history = []
            self.lines = []

        def _append_system_line(self, line, error=False):
            self.lines.append((line, error))

        def _current_brain_model(self, owner_text):
            return "grok:grok-4"

        def _execute_sifta_app_command(self, command):
            opened.update(command)
            return "Searching Google."

    evidence = (
        "Latest browser photo vision: BioHuman Body on desert rocks in a colorful floral bikini top, "
        "green bikini bottoms, fuzzy green leg warmers, and heels."
    )
    monkeypatch.setattr(talk, "_latest_contextual_search_evidence", lambda **kwargs: evidence)
    monkeypatch.setattr(
        talk,
        "_compose_contextual_search_query_with_cortex",
        lambda owner_text, evidence, model="": {"query": "", "source": "cortex_failed", "raw": ""},
    )
    monkeypatch.setattr(talk, "_write_app_command_receipt", lambda **kwargs: "search-receipt")

    phrase = "search for the green puffy leg wardrobe things"
    assert talk._is_contextual_browser_search_request(phrase)
    reply = talk.TalkToAliceWidget._execute_contextual_browser_search(DummyTalk(), phrase)

    assert "fuzzy/faux-fur leg warmers or boot covers" in reply
    assert opened["query"] == "green fuzzy faux fur leg warmers boot covers"
    assert opened["url"].endswith("q=green+fuzzy+faux+fur+leg+warmers+boot+covers")


def test_live_current_page_uses_human_spoken_line_and_clean_print(monkeypatch, tmp_path) -> None:
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    url = (
        "https://em-executive.berkeley.edu/"
        "professional-certificate-machine-learning-artificial-intelligence/"
        "?utm_source=Facebook&utm_medium=California&fbclid=tracking"
    )
    page_state.record_page_state(
        url,
        title="Professional Certificate in Machine Learning and Artificial Intelligence",
        text="Professional Certificate in Machine Learning and Artificial Intelligence from UC Berkeley.",
        headings=[
            "Professional Certificate in Machine Learning and Artificial Intelligence",
            "Get Your Brochure",
            "Program Overview: Professional Certificate in Machine Learning and Artificial Intelligence",
        ],
        state_dir=state_dir,
    )

    class FakeBrowser:
        def current_live_page(self):
            return {
                "url": url,
                "title": "Professional Certificate in Machine Learning and Artificial Intelligence | UC Berkeley ExecEd",
                "on_page": True,
            }

    class DummyTalk:
        def __init__(self):
            self.lines = []

        def _append_system_line(self, line, error=False):
            self.lines.append((line, error))

    monkeypatch.setattr(talk, "_state_root", lambda: state_dir)
    monkeypatch.setattr(talk, "_find_live_alice_browser_widget", lambda: FakeBrowser())
    monkeypatch.setattr(talk, "_write_app_command_receipt", lambda **kwargs: "receipt-test")

    dummy = DummyTalk()
    spoken, printed = talk.TalkToAliceWidget._execute_live_current_page(dummy)

    expected = (
        "Right now Alice Browser is on Professional Certificate in Machine Learning "
        "and Artificial Intelligence from UC Berkeley."
    )
    assert spoken == expected
    assert printed.startswith(expected)
    assert "utm_" not in printed
    assert "fbclid" not in printed
    assert "?" not in printed
    assert (
        "Address: em-executive.berkeley.edu/"
        "professional-certificate-machine-learning-artificial-intelligence."
    ) in printed
    assert "Visible headings: Get Your Brochure" in printed
    assert dummy.lines == [("Page receipt: receipt-test", False)]


def test_tts_budget_failure_is_not_rendered_as_error() -> None:
    class DummyTalk:
        def __init__(self):
            self._busy = True
            self.lines = []
            self.statuses = []
            self.returned = False

        def _append_system_line(self, line, error=False):
            self.lines.append((line, error))

        def set_status(self, status):
            self.statuses.append(status)

        def _return_to_listening(self):
            self.returned = True

    dummy = DummyTalk()
    talk.TalkToAliceWidget._on_tts_failed(
        dummy,
        "voice backend macsay returned no speech (voice ran past its budget for this tick)",
    )

    assert dummy._busy is False
    assert dummy.lines == [("(voice skipped: answer is printed above.)", False)]
    assert dummy.statuses == ["Answer printed; voice skipped."]
    assert dummy.returned is True
