from __future__ import annotations

import json
import time

from Applications import sifta_talk_to_alice_widget as talk
from System import swarm_browser_page_state as page_state


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


def test_describe_instagram_page_uses_cortex_lane_not_raw_dom() -> None:
    assert talk._is_browser_page_cortex_description_query("Please describe this Instagram page.")
    assert talk._is_browser_page_cortex_description_query("describe this page")
    assert not talk._is_browser_page_cortex_description_query("What page am I on right now?")
    assert not talk._is_browser_page_cortex_description_query("Can you summarize the comments?")
    assert not talk._is_browser_page_cortex_description_query("Can you describe her outfit?")


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
    assert "Do not print this raw block" in block
    assert "WHAT IS ON MY SCREEN" in block
    assert "Treat Instagram legal/footer/about links as page chrome" in block
    assert "ramonna_olaru" in block
    assert dummy.lines == [("Web page-context receipt: context-receipt", False)]


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
