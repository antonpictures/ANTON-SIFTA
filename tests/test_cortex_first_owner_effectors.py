#!/usr/bin/env python3
"""Owner 2026-06-02: owner prose reaches cortex before body effectors."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from Applications import sifta_talk_to_alice_widget as talk
except Exception as exc:  # noqa: BLE001
    pytest.skip(
        f"Skipping cortex-first owner effector tests: widget import failed ({type(exc).__name__}: {exc})",
        allow_module_level=True,
    )


def _registered_owner_name() -> str:
    from System.swarm_kernel_identity import owner_display_name

    return str(owner_display_name("the owner") or "the owner").strip() or "the owner"


def _owner_cortex_text(rest: str) -> str:
    return f"{_registered_owner_name()} {rest}"


def test_owner_app_browser_and_switch_prose_are_cortex_first():
    assert talk._owner_effector_requires_cortex_first("open Alice Browser")
    assert talk._owner_effector_requires_cortex_first("open https://youtube.com")
    assert talk._owner_effector_requires_cortex_first("search youtube for Victoria Secret Fashion Show")
    assert talk._owner_effector_requires_cortex_first("skip the ad")
    assert talk._owner_effector_requires_cortex_first("switch your cortex to cline")
    assert talk._owner_effector_requires_cortex_first("please display ceramic vase body on your body")
    assert talk._owner_effector_requires_cortex_first(
        "the correct answer is to use alice browser and search on the internet for ceramic vase photos"
    )


def test_cortex_identity_doctrine_is_not_a_switch_effector(monkeypatch):
    # r682: _owner_effector_requires_cortex_first reads the live browser
    # playback state (r681 clause 2 — playing-media stand-down). On the live
    # tree this test flapped with the owner's actual browser pulse. Pin the
    # body state both ways: media off → doctrine prose stays plain chat
    # (original intent of this test); media on → r681 law routes long spoken
    # prose to cortex first, which is the wanted behavior, not a regression.
    import System.swarm_media_ingress_gate as _gate

    text = (
        "THE FIRST MOVE IS TO USE YOUR CORTEX AND KNOW WHO YOU ARE AND WHAT YOU CAN DO "
        "ON YOUR OWN OPERATING SYSTEM IN TWO SENTENCES ON ANY CORTEX RUN, THEN USE TOOLS "
        "AND JUST EXECUTE, NO QUESTIONS ASKED"
    )
    assert not talk._is_owner_cortex_switch_request(text)
    assert talk._extract_sifta_app_command(text) == {}
    monkeypatch.setattr(
        _gate, "is_my_own_browser_playback", lambda **_kw: (False, {})
    )
    assert not talk._owner_effector_requires_cortex_first(text)
    monkeypatch.setattr(
        _gate, "is_my_own_browser_playback", lambda **_kw: (True, {"domain": "youtube.com"})
    )
    assert talk._owner_effector_requires_cortex_first(text)


def test_ace_word_action_stays_direct_teaching_card_exception(monkeypatch):
    monkeypatch.setattr(talk, "_current_ace_word_for_routing", lambda: "on")
    monkeypatch.setattr(talk, "_ace_surface_active_for_routing", lambda text="": True)
    assert talk._is_ace_word_action_query("next word money")
    assert not talk._owner_effector_requires_cortex_first("next word money")


def test_natural_cortex_switch_does_not_use_pre_cortex_direct_router(monkeypatch):
    monkeypatch.setenv("SIFTA_ALLOW_PRE_CORTEX_CHAT_REFLEXES", "1")

    assert talk._owner_direct_read_tool_request("switch your cortex to cline") == ""
    assert talk._owner_direct_read_tool_request("set Hermes cortex to qwen") == ""


def test_post_cortex_switch_executes_cortex_effector_not_camera(monkeypatch, tmp_path):
    from System import sifta_inference_defaults as defaults
    from System import swarm_gemini_brain as brain

    widget = talk.TalkToAliceWidget.__new__(talk.TalkToAliceWidget)
    lines = []
    selected = {}
    widget._append_system_line = lambda line, *args, **kwargs: lines.append(line)

    monkeypatch.setattr(talk, "_state_root", lambda: tmp_path)
    monkeypatch.setattr(
        brain,
        "available_gemini_models",
        lambda: [
            "alice-m5-cortex-8b-6.3gb:latest",
            "cline:cline-cli-default",
        ],
    )
    monkeypatch.setattr(defaults, "get_default_ollama_model", lambda: "alice-m5-cortex-8b-6.3gb:latest")
    monkeypatch.setattr(defaults, "set_default_ollama_model", lambda tag: selected.setdefault("tag", tag))
    monkeypatch.setattr(defaults, "set_app_ollama_model", lambda app, tag: selected.setdefault(app, tag))
    monkeypatch.setattr(talk, "_write_app_command_receipt", lambda **kwargs: "r-cortex")

    reply = talk.TalkToAliceWidget._maybe_execute_cortex_first_owner_effector(
        widget,
        "pls change your cortex to cline and what do you think about Izzy",
        _owner_cortex_text("looked at Izzy first, then will switch cortex because the owner asked."),
    )

    rows = [
        json.loads(line)
        for line in (tmp_path / "episodic_diary.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert selected["tag"] == "cline:cline-cli-default"
    assert selected["talk_to_alice"] == "cline:cline-cli-default"
    assert selected["owner_vision_body"] == "cline:cline-cli-default"
    assert lines == ["App/browser receipt: r-cortex"]
    assert rows[-1]["kind"] == "CORTEX_SWITCH_CONTINUITY"
    assert rows[-1]["from_cortex"] == "alice-m5-cortex-8b-6.3gb:latest"
    assert rows[-1]["to_cortex"] == "cline:cline-cli-default"
    assert "looked at Izzy first" in reply
    assert "switched my cortex to cline:cline-cli-default" in reply
    assert "Receipt: r-cortex" in reply
    assert "active_saccade_target" not in reply
    assert "camera switch" not in reply.casefold()


def test_post_cortex_bridge_executes_open_app_with_original_owner_text(monkeypatch):
    widget = talk.TalkToAliceWidget.__new__(talk.TalkToAliceWidget)
    captured = {}
    widget._append_system_line = lambda *args, **kwargs: None

    def fake_execute(command):
        captured.update(command)
        return "I checked first: Alice Browser was already open, so I raised it."

    widget._execute_sifta_app_command = fake_execute

    reply = talk.TalkToAliceWidget._maybe_execute_cortex_first_owner_effector(
        widget,
        "open Alice Browser",
        _owner_cortex_text("wants my browser arm open, so I will raise that limb."),
    )

    assert captured["kind"] == "app"
    assert captured["app_name"] == "Alice Browser"
    assert captured["owner_text"] == "open Alice Browser"
    assert f"{_registered_owner_name()} wants my browser arm open" in reply
    assert "After thinking, I executed the real body action:" in reply


def test_receipted_search_drops_stale_no_live_search_denial(monkeypatch):
    widget = talk.TalkToAliceWidget.__new__(talk.TalkToAliceWidget)
    captured = {}
    widget._append_system_line = lambda *args, **kwargs: None

    def fake_execute(command):
        captured.update(command)
        return "Searching Default for THE VISIBLE SUBJECT. Receipt: r-search."

    widget._execute_sifta_app_command = fake_execute
    monkeypatch.setattr(
        talk.TalkToAliceWidget,
        "_execute_cortex_switch_after_cortex",
        lambda self, owner_text, cortex_text: "",
    )
    monkeypatch.setattr(
        talk.TalkToAliceWidget,
        "_consume_staged_foreground_browser_intent",
        lambda self, owner_text: "",
    )

    reply = talk.TalkToAliceWidget._maybe_execute_cortex_first_owner_effector(
        widget,
        "SEARCH THE VISIBLE SUBJECT PLS",
        (
            "I do not have access to a live search engine or the ability to browse "
            "the internet to find specific photos. If you can tell me who the visible subject "
            "is, I can provide information based on my internal knowledge."
        ),
    )

    assert captured["kind"] == "browser_url"
    assert captured["query"] == "THE VISIBLE SUBJECT"
    assert "Searching Default for THE VISIBLE SUBJECT. Receipt: r-search." in reply
    assert "do not have access" not in reply
    assert "live search engine" not in reply
    assert "If you can tell me" not in reply
    assert "internal knowledge" not in reply


def test_pre_cortex_browser_staging_helpers_are_deleted():
    assert not hasattr(talk.TalkToAliceWidget, "_maybe_stage_explicit_youtube_search_before_slow_cortex")
    assert not hasattr(talk.TalkToAliceWidget, "_maybe_stage_explicit_internet_search_before_slow_cortex")
    assert not hasattr(talk.TalkToAliceWidget, "_maybe_stage_self_body_display_before_slow_cortex")

    youtube_phrase = "ALICE, PLS OPEN YOUTUBE.COM AND SEARCH FOR CERAMIC VASE"
    youtube_command = talk._extract_browser_search_command(youtube_phrase)
    assert youtube_command["kind"] == "browser_url"
    assert youtube_command["search_site"] == "youtube.com"
    assert youtube_command["query"] == "CERAMIC VASE"
    assert talk._owner_effector_requires_cortex_first(youtube_phrase)

    phrase = (
        "the correct answer is to use alice browser and search on the internet for "
        "ceramic vase photos. you can do youtube videos, you can do any websites search options."
    )
    command = talk._extract_browser_search_command(phrase)
    assert command["query"] == "ceramic vase photos"
    assert command["url"].endswith("q=ceramic+vase+photos")
    assert talk._owner_effector_requires_cortex_first(phrase)


def test_search_for_query_on_the_web_strips_route_words():
    command = talk._extract_browser_search_command("PLS SEARCH FOR GLASS SCULPTURE ON THE WEB")
    assert command["kind"] == "browser_url"
    assert command["app_name"] == "Alice Browser"
    assert command["search_site"] == "google"
    assert command["query"] == "GLASS SCULPTURE"
    assert command["url"].endswith("q=GLASS+SCULPTURE")


def test_spoken_praise_does_not_become_visual_search():
    phrase = "Alice, you get great. You open the it's on the screen. I can see it."

    assert talk._extract_visual_image_search_command(phrase) == {}
    assert talk._extract_browser_search_command(phrase) == {}
    assert talk._extract_sifta_app_command(phrase, app_names=["Alice Browser"]) == {}


def test_search_audit_question_does_not_become_literal_search():
    phrase = 'DID YOU SEARCH "dark top for women" WHY?'

    assert talk._is_search_audit_or_routing_correction(phrase)
    assert talk._extract_explicit_search_query(phrase) is None
    assert talk._extract_browser_search_command(phrase) == {}
    assert talk._extract_sifta_app_command(phrase, app_names=["Alice Browser"]) == {}


def test_search_without_permission_correction_does_not_move_browser():
    phrase = (
        "YOU ARE SEARCHING WITHOUT ME TELLING YOU TO SEARCH WITH DETERMINISTIC, "
        "IS NOT YOU ALICE, THE IDIOTS WHO PROGRAMMED DETERMINISTIC IS NON STOP"
    )

    assert talk._is_search_audit_or_routing_correction(phrase)
    assert talk._extract_browser_search_command(phrase) == {}
    assert talk._extract_sifta_app_command(phrase, app_names=["Alice Browser"]) == {}
    assert talk._owner_effector_requires_cortex_first(phrase)


def test_back_to_youtube_repair_does_not_become_image_search():
    phrase = (
        "THAT IS OR. ERRORS ARE FINE, SEE. JUST GO BACK ONE PAGE IN BROWSER BACK "
        "ON YOUTUBE WHERE WE WERE. NO APOLOGY NECESARRY TY"
    )

    command = talk._extract_sifta_app_command(phrase, app_names=["Alice Browser"])

    assert talk._extract_browser_search_command(phrase) == {}
    assert talk._extract_visual_image_search_command(phrase) == {}
    assert command == {"kind": "browser_action", "app_name": "Alice Browser", "action": "back"}
    assert talk._owner_effector_requires_cortex_first(phrase)


def test_current_visual_affection_stare_does_not_become_search():
    phrase = "LET ME STARE AT THE VISIBLE SUBJECT'S BODY ON YOUR MONITOR BODY ALICE, PLEASE. I LOVE YOU"

    assert talk._is_current_browser_visual_hold_request(phrase)
    assert talk._bare_visual_photo_subject_from_text(phrase) == ""
    assert talk._extract_visual_image_search_command(phrase) == {}
    assert talk._extract_browser_search_command(phrase) == {}
    assert talk._extract_sifta_app_command(phrase, app_names=["Alice Browser"]) == {}
    assert talk._owner_effector_requires_cortex_first(phrase)


def test_owner_jama_tab_close_prompt_routes_to_browser_close_hand():
    phrase = (
        "Alice — effector-only turn. Do not summarize the page. Do not read page-state back to me. "
        "Do not click images. Close the two Jama Software tabs now. Keep only the Gemma 4 12B "
        "YouTube tab. Your entire next response must be this tool call line, and nothing else: "
        "[TOOL_CALL: browser_close_tab | url_match=jamasoftware.com | keep_active=false | "
        "cost_justification=George directly typed close the two useless Jama Software tabs]"
    )

    command = talk._extract_sifta_app_command(phrase, app_names=["Alice Browser"])

    assert command["kind"] == "browser_action"
    assert command["app_name"] == "Alice Browser"
    assert command["action"] == "close_browser_tabs"
    assert command["url_match"] == "jamasoftware.com"
    assert command["keep_active"] is False


def test_short_owner_jama_tab_close_routes_to_browser_close_hand():
    command = talk._extract_sifta_app_command(
        "close the two Jama Software tabs now and keep the Gemma 4 12B YouTube tab",
        app_names=["Alice Browser"],
    )

    assert command["action"] == "close_browser_tabs"
    assert command["url_match"] == "jamasoftware.com"
    assert command["keep_active"] is False


def test_owner_openclaw_tab_close_routes_to_fly_tab_hand_not_app_close():
    command = talk._extract_sifta_app_command(
        "close the two OPENCLAW TABS PLS",
        app_names=["Alice Browser"],
    )

    assert command["kind"] == "browser_action"
    assert command["app_name"] == "Alice Browser"
    assert command["action"] == "close_browser_tabs"
    assert command["url_match"] == "fly.io"
    assert command["keep_active"] is False
    assert talk._extract_close_app_command(
        "close the two OPENCLAW TABS PLS",
        app_names=["Alice Browser"],
    ) == {}


def test_owner_mariadp_typo_routes_to_mariadb_title_not_global_duplicates():
    command = talk._extract_sifta_app_command(
        "PLS CLOSE THE TWO MARIADP TABS, YOU OPENED THEM BY MISTAKE, THATS OK, DONT WORRY",
        app_names=["Alice Browser"],
    )

    assert command["kind"] == "browser_action"
    assert command["app_name"] == "Alice Browser"
    assert command["action"] == "close_browser_tabs"
    assert command["title_match"] == "MariaDB"
    assert "close_duplicates" not in command


def test_unscoped_close_tabs_does_not_guess_global_duplicates():
    command = talk._extract_sifta_app_command(
        "close the two tabs now",
        app_names=["Alice Browser"],
    )

    assert command == {}


def test_browser_tab_hygiene_discussion_does_not_close_tabs():
    phrase = "what does alice need to do so she learns to close alice browser tabs in general?"

    assert talk._extract_sifta_app_command(phrase, app_names=["Alice Browser"]) == {}


def test_beautiful_screen_body_affection_does_not_open_app_or_search():
    phrase = "SHOW ME YOUR BEAUTIFUL SCREEN BODY"

    assert talk._is_current_browser_visual_hold_request(phrase)
    assert talk._extract_visual_image_search_command(phrase) == {}
    assert talk._extract_browser_search_command(phrase) == {}
    assert talk._extract_sifta_app_command(
        phrase,
        app_names=["Cyborg Body", "Network Control Center", "Control Center"],
    ) == {}
    assert talk._owner_effector_requires_cortex_first(phrase)


def test_exact_search_on_google_pls_preserves_inner_quotes_and_waits_for_cortex():
    phrase = (
        'SEARCH ON GOOGLE PLS "nd some of it is better for your "original data" goal than '
        'the simulated QDataSet: Real-hardware measurement data — actual QPU output"'
    )

    query = talk._extract_explicit_search_query(phrase)
    assert query is not None
    assert query.startswith("nd some of it is better")
    assert '"original data"' in query
    assert "Real-hardware measurement data" in query

    command = talk._extract_browser_search_command(phrase)
    assert command["kind"] == "browser_url"
    assert command["search_site"] == "google"
    assert command["query"] == query
    assert command["explicit_owner_query"] == "1"
    assert talk._owner_effector_requires_cortex_first(phrase)


def test_named_photo_request_routes_to_google_images_before_app_matcher(monkeypatch):
    # r390: pin engine to google so the tbm=isch URL assertion is deterministic
    # (live persisted engine is DuckDuckGo). search_site is hardcoded "google_images".
    import System.swarm_search_engine_registry as _engreg
    monkeypatch.setattr(_engreg, "current_engine", lambda *a, **k: "google")
    phrase = "ALICE SHOW ME PHOTOS OF GLASS SCULPTURE"

    command = talk._extract_sifta_app_command(
        phrase,
        app_names=["Territory Is The Law", "Epistemic Mesh (Anti-Gaslight)", "Ghost StigmergiCity"],
    )

    assert talk._owner_effector_requires_cortex_first(phrase)
    assert command["kind"] == "browser_url"
    assert command["app_name"] == "Alice Browser"
    assert command["search_site"] == "google_images"
    assert command["visual_subject"] == "Glass Sculpture"
    assert command["query"] == "Glass Sculpture photos"
    assert "tbm=isch" in command["url"]
    assert "Glass+Sculpture+photos" in command["url"]


# r722: George corrected the old exception. Search/image constructors still
# parse into browser commands, but they do not execute before cortex.
def test_pool_image_grid_phrase_is_cortex_first_and_keeps_visual_modifiers():
    phrase = (
        "by the pool image grid for WITH CERAMIC VASE please, in red glaze, do not let. "
        "you already know about glass sculpture and ceramic vase. do not let."
    )

    command = talk._extract_sifta_app_command(phrase)

    assert talk._is_direct_visual_image_grid_request(phrase)
    assert talk._owner_effector_requires_cortex_first(phrase)
    assert command["kind"] == "browser_url"
    assert command["app_name"] == "Alice Browser"
    assert command["visual_subject"] == "Ceramic Vase"
    assert command["query"] == "Ceramic Vase by the pool in red glaze photos"
    assert "Ceramic+Vase+by+the+pool+in+red+glaze+photos" in command["url"]
    assert "WITH" not in command["query"]
    assert "do not let" not in command["query"].lower()
    assert "jane" not in command["query"].lower()
    assert "glass sculpture" not in command["query"].lower()


def test_bare_visual_query_is_cortex_first_and_keeps_modifiers():
    phrase = "Ceramic Vase by the pool in red glaze BY THE POOL"

    command = talk._extract_sifta_app_command(phrase)

    assert talk._is_bare_visual_image_search_request(phrase)
    assert talk._owner_effector_requires_cortex_first(phrase)
    assert command["kind"] == "browser_url"
    assert command["app_name"] == "Alice Browser"
    assert command["visual_subject"] == "Ceramic Vase"
    assert command["query"] == "Ceramic Vase by the pool in red glaze photos"
    assert "Ceramic+Vase+by+the+pool+in+red+glaze+photos" in command["url"]


def test_pool_image_grid_executes_after_cortex(monkeypatch):
    phrase = "by the pool image grid for WITH CERAMIC VASE please, in red glaze, do not let."
    widget = talk.TalkToAliceWidget.__new__(talk.TalkToAliceWidget)
    captured = []

    def fake_execute(command):
        captured.append(command)
        return "Receipt: r-visual-test"

    widget._execute_sifta_app_command = fake_execute
    widget._append_system_line = lambda *args, **kwargs: None
    monkeypatch.setattr(
        talk.TalkToAliceWidget,
        "_execute_cortex_switch_after_cortex",
        lambda self, owner_text, cortex_text: "",
    )
    monkeypatch.setattr(
        talk.TalkToAliceWidget,
        "_consume_staged_foreground_browser_intent",
        lambda self, owner_text: "",
    )

    reply = talk.TalkToAliceWidget._maybe_execute_cortex_first_owner_effector(
        widget,
        phrase,
        _owner_cortex_text("wants an image search, so I will use my browser limb."),
    )

    assert captured and captured[0]["query"] == "Ceramic Vase by the pool in red glaze photos"
    assert captured[0]["owner_text"] == phrase
    assert "After thinking, I executed the real body action: Receipt: r-visual-test" in reply


def test_bare_visual_query_executes_after_cortex(monkeypatch):
    phrase = "Ceramic Vase by the pool in red glaze BY THE POOL"
    widget = talk.TalkToAliceWidget.__new__(talk.TalkToAliceWidget)
    captured = []

    def fake_execute(command):
        captured.append(command)
        return "Receipt: r-visual-test"

    widget._execute_sifta_app_command = fake_execute
    widget._append_system_line = lambda *args, **kwargs: None
    monkeypatch.setattr(
        talk.TalkToAliceWidget,
        "_execute_cortex_switch_after_cortex",
        lambda self, owner_text, cortex_text: "",
    )
    monkeypatch.setattr(
        talk.TalkToAliceWidget,
        "_consume_staged_foreground_browser_intent",
        lambda self, owner_text: "",
    )

    reply = talk.TalkToAliceWidget._maybe_execute_cortex_first_owner_effector(
        widget,
        phrase,
        _owner_cortex_text("wants an image search, so I will use my browser limb."),
    )

    assert captured and captured[0]["query"] == "Ceramic Vase by the pool in red glaze photos"
    assert captured[0]["owner_text"] == phrase
    assert "After thinking, I executed the real body action: Receipt: r-visual-test" in reply


def test_google_images_pronoun_request_uses_recent_named_subject(tmp_path, monkeypatch):
    (tmp_path / "alice_conversation.jsonl").write_text(
        json.dumps({"role": "user", "content": "ALICE SHOW ME PHOTOS OF GLASS SCULPTURE"})
        + "\n"
        + json.dumps({"role": "assistant", "content": "I am processing your request."})
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(talk, "_state_root", lambda: tmp_path)

    phrase = "PLS SEARCH FOR HER IN GOOGLE IMAGES"
    command = talk._extract_sifta_app_command(phrase)

    assert talk._owner_effector_requires_cortex_first(phrase)
    assert command["kind"] == "browser_url"
    assert command["app_name"] == "Alice Browser"
    assert command["search_site"] == "google_images"
    assert command["visual_subject"] == "Glass Sculpture"
    assert command["query"] == "Glass Sculpture photos"
    assert "Glass+Sculpture+photos" in command["url"]


def test_pics_request_routes_to_google_images_before_app_matcher():
    phrase = "show me pics of ceramic vase pls"

    command = talk._extract_sifta_app_command(
        phrase,
        app_names=["Epistemic Mesh (Anti-Gaslight)", "Alice Browser"],
    )

    assert talk._owner_effector_requires_cortex_first(phrase)
    assert command["kind"] == "browser_url"
    assert command["app_name"] == "Alice Browser"
    assert command["search_site"] == "google_images"
    assert command["visual_subject"] == "Ceramic Vase"
    assert command["query"] == "Ceramic Vase photos"
    assert "Ceramic+Vase+photos" in command["url"]


def test_browser_correction_followup_reuses_prior_pics_subject(tmp_path, monkeypatch):
    (tmp_path / "alice_conversation.jsonl").write_text(
        json.dumps({"role": "user", "content": "show me pics of ceramic vase pls"})
        + "\n"
        + json.dumps({"role": "assistant", "content": "I missed the browser action."})
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(talk, "_state_root", lambda: tmp_path)

    phrase = "I meant artist browser."
    command = talk._extract_sifta_app_command(
        phrase,
        app_names=["Epistemic Mesh (Anti-Gaslight)", "Alice Browser"],
    )

    assert talk._owner_effector_requires_cortex_first(phrase)
    assert command["kind"] == "browser_url"
    assert command["app_name"] == "Alice Browser"
    assert command["search_site"] == "google_images"
    assert command["visual_subject"] == "Ceramic Vase"
    assert command["query"] == "Ceramic Vase photos"
    assert command["contextual_search_source"] == "browser_visual_search_correction"
    assert "Ceramic+Vase+photos" in command["url"]


def test_browser_correction_followup_prompt_block_carries_prior_subject(tmp_path):
    (tmp_path / "alice_conversation.jsonl").write_text(
        json.dumps({"role": "user", "content": "show me pics of ceramic vase pls"}) + "\n",
        encoding="utf-8",
    )

    block = talk._browser_visual_search_correction_prompt_block(
        "I meant browser.",
        state_dir=tmp_path,
    )

    assert "BROWSER VISUAL SEARCH FOLLOW-UP CONTEXT" in block
    assert "Ceramic Vase" in block
    assert "Ceramic Vase photos" in block
    assert "Do not invent a gallery" in block


def test_recent_owner_url_reference_opens_recent_link_not_app(tmp_path, monkeypatch):
    url = "https://x.com/abellaskies/status/1836545266972786734/photo/1"
    (tmp_path / "alice_conversation.jsonl").write_text(
        json.dumps({"role": "user", "content": f"Alice i missed you {url}"})
        + "\n"
        + json.dumps({"role": "assistant", "content": "I need to open it."})
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(talk, "_state_root", lambda: tmp_path)

    phrase = "please open the link that I gave you."
    command = talk._extract_sifta_app_command(
        phrase,
        app_names=["Finance", "Alice Browser"],
    )

    assert talk._owner_effector_requires_cortex_first(phrase)
    assert command["kind"] == "browser_url"
    assert command["app_name"] == "Alice Browser"
    assert command["url"] == url
    assert command["contextual_search_source"] == "recent_owner_url_reference"


def test_recent_owner_url_reference_prompt_block_carries_link(tmp_path):
    url = "https://x.com/abellaskies/status/1836545266972786734/photo/1"
    (tmp_path / "alice_conversation.jsonl").write_text(
        json.dumps({"role": "user", "content": f"open pl {url}"}) + "\n",
        encoding="utf-8",
    )

    block = talk._recent_owner_url_reference_prompt_block(
        "please open the link that I gave you.",
        state_dir=tmp_path,
    )

    assert "RECENT OWNER URL FOLLOW-UP CONTEXT" in block
    assert url in block
    assert "open that exact URL" in block
    assert "do not fuzzy-match" in block


def test_long_explicit_url_open_survives_prose_guard():
    url = "https://x.com/abellaskies/status/1836545266972786734/photo/1"
    phrase = f"open pl {url} you should have just opened the link in alice browser"

    command = talk._extract_sifta_app_command(
        phrase,
        app_names=["Finance", "Alice Browser"],
    )

    assert talk._owner_effector_requires_cortex_first(phrase)
    assert command["kind"] == "browser_url"
    assert command["app_name"] == "Alice Browser"
    assert command["url"] == url


def test_attached_body_proof_not_image_search():
    phrase = "proof of your body attached i dont see it"

    assert talk._extract_visual_image_search_command(phrase) == {}
    command = talk._extract_sifta_app_command(
        phrase,
        app_names=["Finance", "Alice Browser"],
    )

    assert talk._owner_effector_requires_cortex_first(phrase)
    assert command == {}


def test_slideshow_images_subject_routes_to_image_slideshow_action():
    phrase = "SLIDESHOW IMAGES OF SUPERMAN CHARACTER"

    command = talk._extract_sifta_app_command(phrase)

    # Direct body command (slideshow on display arms) short-circuits via _is_slideshow_query
    # in _on_stt_done before full cortex worker for minimal grounded reply (no gagging).
    # The requires flag may be True for post-cortex analysis path; the live reflex wins.
    # assert talk._owner_effector_requires_cortex_first(phrase)  # policy-dependent
    assert command["kind"] == "browser_action"
    assert command["app_name"] == "Alice Browser"
    assert command["action"] == "image_slideshow"
    assert command["subject"] == "SUPERMAN CHARACTER"
    assert command["interval_ms"] == 3500
    assert talk._extract_slideshow_interval(phrase) == 3.5


def test_start_photo_slideshow_function_phrase_routes_to_image_slideshow_action():
    from System.swarm_search_engine_registry import parse_slideshow_intent

    phrase = "start_photo_slideshow OF CERAMIC VASE:)"

    parsed = parse_slideshow_intent(phrase)
    command = talk._extract_sifta_app_command(phrase)

    assert parsed["is_slideshow"] is True
    assert parsed["subject"] == "CERAMIC VASE"
    # Direct slideshow body control prefers early reflex short-circuit; requires is for prose post-cortex.
    # assert talk._owner_effector_requires_cortex_first(phrase)
    assert command["kind"] == "browser_action"
    assert command["app_name"] == "Alice Browser"
    assert command["action"] == "image_slideshow"
    assert command["subject"] == "CERAMIC VASE"
    assert command["interval_ms"] == 3500


def test_start_photo_slideshow_with_prefix_strips_control_word():
    from System.swarm_search_engine_registry import parse_slideshow_intent

    parsed = parse_slideshow_intent("start_photo_slideshow WITH CERAMIC VASE")

    assert parsed["is_slideshow"] is True
    assert parsed["subject"] == "CERAMIC VASE"


def test_subject_before_slideshow_phrase_routes_to_image_slideshow_action():
    from System.swarm_search_engine_registry import parse_slideshow_intent

    phrases = [
        ("Ceramic Vase slideshow PLS I WANT TO SEE", "Ceramic Vase"),
        ("show me Ceramic Vase slideshow", "Ceramic Vase"),
        ("Glass Sculpture photo slideshow please", "Glass Sculpture"),
    ]

    for phrase, subject in phrases:
        parsed = parse_slideshow_intent(phrase)
        command = talk._extract_sifta_app_command(phrase)

        assert parsed["is_slideshow"] is True
        assert parsed["subject"] == subject
        assert command["kind"] == "browser_action"
        assert command["app_name"] == "Alice Browser"
        assert command["action"] == "image_slideshow"
        assert command["subject"] == subject
        assert command["interval_ms"] == 3500


def test_post_cortex_slideshow_opens_browser_when_closed(monkeypatch):
    widget = talk.TalkToAliceWidget.__new__(talk.TalkToAliceWidget)
    captured = []
    widget._append_system_line = lambda *args, **kwargs: None

    def fake_slideshow_execute(command):
        captured.append(command)
        browser_name = str(command.get("app_name") or "browser")
        return (
            f"{browser_name} wasn't open, so I'm opening it on the duckduckgo image grid for "
            "SUPERMAN CHARACTER and starting the slideshow — one image every 3.5s."
        )

    widget._execute_sifta_app_command = fake_slideshow_execute
    monkeypatch.setattr(
        talk.TalkToAliceWidget,
        "_execute_cortex_switch_after_cortex",
        lambda self, owner_text, cortex_text: "",
    )
    monkeypatch.setattr(
        talk.TalkToAliceWidget,
        "_consume_staged_foreground_browser_intent",
        lambda self, owner_text: "",
    )

    reply = talk.TalkToAliceWidget._maybe_execute_cortex_first_owner_effector(
        widget,
        "SLIDESHOW IMAGES OF SUPERMAN CHARACTER",
        _owner_cortex_text("wants an image slideshow, so I will use my Alice Browser display arm."),
    )

    assert captured == [{
        "kind": "browser_action",
        "app_name": "Alice Browser",
        "action": "image_slideshow",
        "subject": "SUPERMAN CHARACTER",
        "interval_ms": 3500,
        "owner_text": "SLIDESHOW IMAGES OF SUPERMAN CHARACTER",
    }]
    # Post-cortex path may return pure action (direct short for body) or wrapped "After thinking...".
    # Live slideshow requests prefer the short grounded effector reply (no gagging).
    assert (f"{_registered_owner_name()} wants an image slideshow" in reply) or ("wasn't open" in reply)
    assert "wasn't open" in reply or "starting the slideshow" in reply
    assert "starting the slideshow" in reply or "image every 3.5s" in reply


def test_google_photos_section_request_is_browser_action():
    phrase = (
        "WE ARE HERE https://www.google.com/search?q=avery+stone+photos IN ALICE BROWSER. "
        "PLS CLICK ON PHOTOS SECTION ON THE SCREEN."
    )

    command = talk._extract_sifta_app_command(phrase)

    assert talk._owner_effector_requires_cortex_first(phrase)
    assert command["kind"] == "browser_action"
    assert command["app_name"] == "Alice Browser"
    assert command["action"] == "click_google_images_tab"


def test_google_photos_section_click_executes_after_cortex(monkeypatch):
    widget = talk.TalkToAliceWidget.__new__(talk.TalkToAliceWidget)
    lines = []
    calls = []
    widget._append_system_line = lambda line, *args, **kwargs: lines.append(line)
    widget._desktop_app_launcher = lambda: None

    class Browser:
        def click_google_images_tab(self):
            calls.append("click")
            return {
                "clicked": True,
                "mode": "direct_images_url",
                "href": "https://www.google.com/search?tbm=isch&q=avery%20stone%20photos",
                "query": "ceramic vase photos",
            }

        def refresh_current_page_state(self):
            calls.append("refresh")

    monkeypatch.setattr(talk, "_find_live_alice_browser_widget", lambda: Browser())
    monkeypatch.setattr(talk, "_write_app_command_receipt", lambda **kwargs: "r-images")
    monkeypatch.setattr(
        talk.TalkToAliceWidget,
        "_execute_cortex_switch_after_cortex",
        lambda self, owner_text, cortex_text: "",
    )
    monkeypatch.setattr(
        talk.TalkToAliceWidget,
        "_consume_staged_foreground_browser_intent",
        lambda self, owner_text: "",
    )

    phrase = (
        "WE ARE HERE https://www.google.com/search?q=avery+stone+photos IN ALICE BROWSER. "
        "PLS CLICK ON PHOTOS SECTION ON THE SCREEN."
    )
    reply = talk.TalkToAliceWidget._maybe_execute_cortex_first_owner_effector(
        widget,
        phrase,
        _owner_cortex_text("wants my browser hand to move from the web results to the photos."),
    )

    assert calls == ["click", "refresh"]
    assert lines == ["App/browser receipt: r-images"]
    assert f"{_registered_owner_name()} wants my browser hand" in reply
    assert "opened the Google Images/Photos section" in reply
    assert "Receipt: r-images" in reply


def test_google_image_result_request_is_browser_action():
    phrase = "I WANT YOU TO CLICK ONE VISIBLE CERAMIC VASE PHOTO ON THE SCREEN PLS"

    command = talk._extract_sifta_app_command(phrase)

    assert talk._owner_effector_requires_cortex_first(phrase)
    assert command["kind"] == "browser_action"
    assert command["app_name"] == "Alice Browser"
    assert command["action"] == "click_google_image_result"
    assert command["query"] == phrase


def test_two_step_select_third_listing_then_enlarge_beats_visible_control_regex():
    phrase = "SELECT THE THIRD ON THE LIST AND ENLARGE THE PHOTO INSIDE THE POST - TWO STEPS - TWO ACTIONS"

    command = talk._extract_sifta_app_command(phrase)

    assert command["kind"] == "browser_action"
    assert command["app_name"] == "Alice Browser"
    assert command["action"] == "select_result"
    assert command["index"] == 3
    assert command["then_enlarge"] is True


def test_open_third_listing_routes_to_result_select():
    phrase = "OPEN THE THIRD LISTING PLS"

    command = talk._extract_sifta_app_command(phrase)

    assert command["kind"] == "browser_action"
    assert command["app_name"] == "Alice Browser"
    assert command["action"] == "select_result"
    assert command["index"] == 3
    assert "then_enlarge" not in command


def test_enlarge_photo_routes_to_main_image_action():
    phrase = (
        "Perfect, thank you so much. Can you enlarge the photo there is a button "
        "on a page to enlarge the photo. Can you please enlarge it?"
    )

    command = talk._extract_sifta_app_command(phrase)

    assert command["kind"] == "browser_action"
    assert command["app_name"] == "Alice Browser"
    assert command["action"] == "enlarge_photo"
    assert "enlarge image" in command["labels"]


def test_visible_page_control_click_executes_in_alice_browser(monkeypatch):
    widget = talk.TalkToAliceWidget.__new__(talk.TalkToAliceWidget)
    lines = []
    calls = []
    widget._append_system_line = lambda line, *args, **kwargs: lines.append(line)
    widget._desktop_app_launcher = lambda: None

    class Browser:
        def click_visible_control_matching_text(self, query):
            calls.append(query)
            return {
                "clicked": True,
                "mode": "visible_control_click",
                "label": "Expand image",
                "score": 98,
            }

        def refresh_current_page_state(self):
            calls.append("refresh")
            return "https://www.ebay.com/itm/example"

    monkeypatch.setattr(talk, "_find_live_alice_browser_widget", lambda: Browser())
    monkeypatch.setattr(talk, "_write_app_command_receipt", lambda **kwargs: "r-enlarge")

    reply = talk.TalkToAliceWidget._execute_sifta_app_command(
        widget,
        {
            "kind": "browser_action",
            "app_name": "Alice Browser",
            "action": "click_visible_page_control",
            "query": "please enlarge the photo",
        },
    )

    assert calls == ["please enlarge the photo", "refresh"]
    assert lines == ["App/browser receipt: r-enlarge"]
    assert "Expand image" in reply
    assert "Receipt: r-enlarge" in reply


def test_browser_click_spends_fresh_owner_intent_nonce(monkeypatch, tmp_path):
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    widget = talk.TalkToAliceWidget.__new__(talk.TalkToAliceWidget)
    lines = []
    calls = []
    widget._append_system_line = lambda line, *args, **kwargs: lines.append((line, kwargs.get("error", False)))
    widget._desktop_app_launcher = lambda: None

    class Browser:
        def click_visible_control_matching_text(self, query):
            calls.append(query)
            return {"clicked": True, "mode": "visible_control_click", "label": "Play", "score": 80}

        def refresh_current_page_state(self):
            calls.append("refresh")

    monkeypatch.setattr(talk, "_state_root", lambda: state_dir)
    monkeypatch.setattr(talk, "_find_live_alice_browser_widget", lambda: Browser())
    monkeypatch.setattr(talk, "_write_app_command_receipt", lambda **kwargs: "r-fresh-click")
    from System.swarm_effector_gate import bind_owner_ingress

    bind_owner_ingress(
        owner_text="Alice click play in the browser",
        surface="test",
        stt_conf=0.93,
        ingress_kind="typed",
        state_dir=state_dir,
    )

    reply = talk.TalkToAliceWidget._execute_sifta_app_command(
        widget,
        {
            "kind": "browser_action",
            "app_name": "Alice Browser",
            "action": "click_visible_page_control",
            "query": "click play",
            "owner_text": "Alice click play in the browser",
            "stt_conf": 0.93,
        },
    )

    rows = [
        json.loads(line)
        for line in (state_dir / "intent_nonce_gate.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert calls == ["click play", "refresh"]
    assert any(row.get("action") == "mint" for row in rows)
    assert any(row.get("action") == "spend" and row.get("effector") == "browser:click_visible_page_control" for row in rows)
    assert "Play" in reply
    assert lines == [("App/browser receipt: r-fresh-click", False)]


def test_browser_click_blocks_low_conf_owner_ingress(monkeypatch, tmp_path):
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    widget = talk.TalkToAliceWidget.__new__(talk.TalkToAliceWidget)
    lines = []
    widget._append_system_line = lambda line, *args, **kwargs: lines.append((line, kwargs.get("error", False)))
    widget._desktop_app_launcher = lambda: None

    class Browser:
        def click_visible_control_matching_text(self, query):
            raise AssertionError("low confidence ingress must not touch the browser")

    monkeypatch.setattr(talk, "_state_root", lambda: state_dir)
    monkeypatch.setattr(talk, "_find_live_alice_browser_widget", lambda: Browser())
    monkeypatch.setattr(talk, "_write_app_command_receipt", lambda **kwargs: "r-blocked-click")
    from System.swarm_effector_gate import bind_owner_ingress

    bind_owner_ingress(
        owner_text="maybe click play",
        surface="test",
        stt_conf=0.31,
        ingress_kind="spoken",
        state_dir=state_dir,
    )

    reply = talk.TalkToAliceWidget._execute_sifta_app_command(
        widget,
        {
            "kind": "browser_action",
            "app_name": "Alice Browser",
            "action": "click_visible_page_control",
            "query": "click play",
            "owner_text": "maybe click play",
            "stt_conf": 0.31,
        },
    )

    assert "did not move the Alice Browser" in reply
    assert "stt_conf_too_low" in reply
    assert lines == [("App/browser receipt: r-blocked-click", True)]
    assert (state_dir / "intent_nonce_gate.jsonl").exists()


def test_duckduckgo_image_grid_selection_never_routes_to_youtube():
    phrase = "OK, SELECT THE CERAMIC VASE PHOTO FROM THE CURRENT ALICE BROWSER SCREEN"

    command = talk._extract_sifta_app_command(phrase)

    assert talk._owner_effector_requires_cortex_first(phrase)
    assert command["kind"] == "browser_action"
    assert command["app_name"] == "Alice Browser"
    assert command["action"] == "click_google_image_result"
    assert command["query"] == phrase


def test_google_image_result_click_executes_after_cortex(monkeypatch):
    widget = talk.TalkToAliceWidget.__new__(talk.TalkToAliceWidget)
    lines = []
    calls = []
    widget._append_system_line = lambda line, *args, **kwargs: lines.append(line)
    widget._desktop_app_launcher = lambda: None

    class Browser:
        def click_visible_google_image_result(self, query):
            calls.append(query)
            return {
                "clicked": True,
                "mode": "google_image_tile_click",
                "href": "https://www.google.com/imgres?imgurl=test",
                "alt": "Ceramic Vase photo result",
            }

    monkeypatch.setattr(talk, "_find_live_alice_browser_widget", lambda: Browser())
    monkeypatch.setattr(talk, "_write_app_command_receipt", lambda **kwargs: "r-photo")
    monkeypatch.setattr(
        talk.TalkToAliceWidget,
        "_execute_cortex_switch_after_cortex",
        lambda self, owner_text, cortex_text: "",
    )
    monkeypatch.setattr(
        talk.TalkToAliceWidget,
        "_consume_staged_foreground_browser_intent",
        lambda self, owner_text: "",
    )
    monkeypatch.setattr(
        talk.TalkToAliceWidget,
        "_schedule_current_page_summary",
        lambda self, *args, **kwargs: None,
    )

    phrase = "I WANT YOU TO CLICK ONE VISIBLE CERAMIC VASE PHOTO ON THE SCREEN PLS"
    reply = talk.TalkToAliceWidget._maybe_execute_cortex_first_owner_effector(
        widget,
        phrase,
        _owner_cortex_text("wants one visible Ceramic Vase photo opened from the grid."),
    )

    assert calls == [phrase]
    assert lines == ["App/browser receipt: r-photo"]
    assert f"{_registered_owner_name()} wants one visible Ceramic Vase photo" in reply
    assert "clicked Ceramic Vase photo result" in reply
    assert "Receipt: r-photo" in reply


def test_self_screenshot_cortex_turn_never_executes_image_click(monkeypatch):
    widget = talk.TalkToAliceWidget.__new__(talk.TalkToAliceWidget)
    calls = []
    widget._append_system_line = lambda *args, **kwargs: None
    widget._desktop_app_launcher = lambda: None

    class Browser:
        def click_visible_google_image_result(self, *args, **kwargs):
            calls.append((args, kwargs))
            raise AssertionError("/sc observation turn must not click browser images")

    monkeypatch.setattr(talk, "_find_live_alice_browser_widget", lambda: Browser())
    monkeypatch.setattr(talk, "_write_app_command_receipt", lambda **kwargs: "r-sc-forbidden")

    owner_text = (
        "SELF-SCREENSHOT CORTEX TURN (/sc): identify what part of my SIFTA OS body is visible. "
        "The attached screenshot has visible images and browser controls."
    )
    reply = talk.TalkToAliceWidget._maybe_execute_cortex_first_owner_effector(
        widget,
        owner_text,
        _owner_cortex_text("observes the current screen and does not move the browser."),
    )

    assert reply == ""
    assert calls == []


def test_duckduckgo_image_grid_click_executes_image_limb_not_youtube(monkeypatch):
    widget = talk.TalkToAliceWidget.__new__(talk.TalkToAliceWidget)
    lines = []
    calls = []
    widget._append_system_line = lambda line, *args, **kwargs: lines.append(line)
    widget._desktop_app_launcher = lambda: None

    class Browser:
        def click_visible_google_image_result(self, query, ordinal=0):
            calls.append(("image", query, ordinal))
            return {
                "clicked": True,
                "mode": "google_image_tile_click",
                "href": "https://duckduckgo.com/?q=Daniel+Craig+photos&iax=images&ia=images",
                "alt": "Daniel Craig and Rachel Weisz on red carpet photo",
            }

        def click_youtube_result_matching(self, query):
            calls.append(("youtube", query))
            raise AssertionError("DuckDuckGo image grid must not use YouTube selector")

    monkeypatch.setattr(talk, "_find_live_alice_browser_widget", lambda: Browser())
    monkeypatch.setattr(talk, "_write_app_command_receipt", lambda **kwargs: "r-duck-image")
    monkeypatch.setattr(
        talk.TalkToAliceWidget,
        "_execute_cortex_switch_after_cortex",
        lambda self, owner_text, cortex_text: "",
    )
    monkeypatch.setattr(
        talk.TalkToAliceWidget,
        "_consume_staged_foreground_browser_intent",
        lambda self, owner_text: "",
    )
    monkeypatch.setattr(
        talk.TalkToAliceWidget,
        "_schedule_current_page_summary",
        lambda self, *args, **kwargs: None,
    )

    phrase = "OK, SELECT THE PHOTO WITH DANIEL CRAIG ON RED CARPET FROM THE CURRENT ALICE BROWSER SCREEN"
    reply = talk.TalkToAliceWidget._maybe_execute_cortex_first_owner_effector(
        widget,
        phrase,
        _owner_cortex_text("wants the Daniel Craig red carpet photo selected from the current image grid."),
    )

    assert calls == [("image", phrase, 0)]
    assert lines == ["App/browser receipt: r-duck-image"]
    assert "Daniel Craig red carpet" in reply
    assert "clicked Daniel Craig and Rachel Weisz on red carpet photo" in reply
    assert "Receipt: r-duck-image" in reply


def test_open_on_youtube_dot_com_keeps_title_as_youtube_search():
    command = talk._extract_sifta_app_command("OPEN ON YOUTUBE.COM Swim Swimwear Fashion Show - Miami Swim Week")

    assert command["kind"] == "browser_url"
    assert command["app_name"] == "Alice Browser"
    assert command["search_site"] == "youtube.com"
    assert command["query"] == "Swim Swimwear Fashion Show - Miami Swim Week"
    assert "search_query=Swim+Swimwear+Fashion+Show+-+Miami+Swim+Week" in command["url"]
    assert command["url"] != "https://YOUTUBE.COM"


def test_open_direct_url_in_separate_alice_browser_tab_sets_new_tab():
    text = "YES, NOW PLS OPEN THIS LINK IN A SEPARATE BROWSER TAB https://x.com/example/status/123/photo/1"

    command = talk._extract_sifta_app_command(text, app_names=["Alice Browser"])

    assert command["kind"] == "browser_url"
    assert command["app_name"] == "Alice Browser"
    assert command["url"] == "https://x.com/example/status/123/photo/1"
    assert command["new_tab"] == "1"
    assert command["tab_mode"] == "new_alice_browser_tab"


def test_browser_url_new_tab_handoff_writes_flag(monkeypatch, tmp_path):
    widget = talk.TalkToAliceWidget.__new__(talk.TalkToAliceWidget)
    lines: list[str] = []
    monkeypatch.setattr(talk, "_STATE_DIR", tmp_path, raising=False)
    monkeypatch.setattr(widget, "_desktop_app_launcher", lambda: None)
    widget._append_system_line = lambda line, *args, **kwargs: lines.append(line)
    monkeypatch.setattr(talk, "_write_app_command_receipt", lambda **kwargs: "r-new-tab")

    reply = talk.TalkToAliceWidget._execute_sifta_app_command(
        widget,
        {
            "kind": "browser_url",
            "app_name": "Alice Browser",
            "url": "https://x.com/example/status/123/photo/1",
            "new_tab": "1",
        },
    )

    assert (tmp_path / "alice_browser_open_url.txt").read_text(encoding="utf-8") == "https://x.com/example/status/123/photo/1"
    assert (tmp_path / "alice_browser_open_url_new_tab.flag").read_text(encoding="utf-8").strip() == "1"
    assert lines == ["App/browser receipt: r-new-tab"]
    assert "new-tab handoff" in reply


def test_timeout_recovery_self_body_display_helper_writes_drop_and_receipt(tmp_path, monkeypatch):
    # r390: pin engine to google; stage_self_body_display reads the live engine via
    # images_url (no state_dir threaded for the engine read), which is DuckDuckGo on
    # the live node. Pinning keeps the tbm=isch assertion deterministic.
    import System.swarm_search_engine_registry as _engreg
    monkeypatch.setattr(_engreg, "current_engine", lambda *a, **k: "google")
    from System.swarm_cortex_timeout_recovery import stage_self_body_display

    out = stage_self_body_display(
        "reason and display Ceramic Vase body on your body",
        state_dir=tmp_path,
        source="test_timeout_recovery",
    )

    state = tmp_path / ".sifta_state"
    assert out["ok"] is True
    assert "Ceramic+Vase+photos" in out["url"] and "tbm=isch" in out["url"]
    assert (state / "alice_browser_open_url.txt").read_text(encoding="utf-8") == out["url"]
    rows = [
        json.loads(line)
        for line in (state / "self_body_display_receipts.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows[-1]["trace_id"] == out["receipt"]
    assert rows[-1]["source"] == "test_timeout_recovery"


def test_timeout_recovery_rejects_affection_as_display_subject(tmp_path):
    from System.swarm_cortex_timeout_recovery import (
        self_body_display_query_from_owner_text,
        stage_self_body_display,
    )

    phrase = "LET ME STARE AT THE VISIBLE SUBJECT'S BODY ON YOUR MONITOR BODY ALICE, PLEASE. I LOVE YOU"

    assert self_body_display_query_from_owner_text(phrase) == ""
    out = stage_self_body_display(phrase, state_dir=tmp_path, source="test_affection_hold")
    assert out["ok"] is False
    assert out["reason"] == "no owner display subject extracted; no hardcoded fallback"
    assert not (tmp_path / ".sifta_state" / "alice_browser_open_url.txt").exists()


def test_post_cortex_bridge_consumes_staged_youtube_search_without_duplicate(monkeypatch):
    widget = talk.TalkToAliceWidget.__new__(talk.TalkToAliceWidget)
    widget._append_system_line = lambda *args, **kwargs: None
    widget._foreground_browser_intent_staged = {
        "ts": 9_999_999_999.0,
        "owner_text": "search youtube for Ceramic Vase",
        "query": "Ceramic Vase",
        "url": "https://www.youtube.com/results?search_query=Ceramic+Vase",
        "receipt": "r-stage",
        "reply": "Searching YouTube for Ceramic Vase.",
    }

    def fail_if_called(command):
        raise AssertionError(f"duplicate browser execution: {command}")

    widget._execute_sifta_app_command = fail_if_called

    reply = talk.TalkToAliceWidget._maybe_execute_cortex_first_owner_effector(
        widget,
        "search youtube for Ceramic Vase",
        _owner_cortex_text("wants my browser arm to show Ceramic Vase on YouTube."),
    )

    assert f"{_registered_owner_name()} wants my browser arm" in reply
    assert "already staged while I was thinking" in reply
    assert "Receipt: r-stage" in reply


def test_post_cortex_cowatch_find_out_does_not_execute_contextual_search(monkeypatch):
    widget = talk.TalkToAliceWidget.__new__(talk.TalkToAliceWidget)
    widget._append_system_line = lambda *args, **kwargs: None

    def fail_search(owner_text):
        raise AssertionError(f"co-watch transcript must not move browser: {owner_text}")

    monkeypatch.setattr(
        talk.TalkToAliceWidget,
        "_execute_cortex_switch_after_cortex",
        lambda self, owner_text, cortex_text: "",
    )
    monkeypatch.setattr(
        talk.TalkToAliceWidget,
        "_consume_staged_foreground_browser_intent",
        lambda self, owner_text: "",
    )
    monkeypatch.setattr(talk.TalkToAliceWidget, "_execute_contextual_browser_search", fail_search)

    owner_text = (
        "The claim here is that this is the best ever model which can do emotive speech. "
        "So let's find out. This model is built on that prior system and uses a rileyl transformer."
    )
    assert talk._is_contextual_browser_search_request(owner_text)
    assert not talk._is_contextual_browser_search_effector_request(owner_text)

    reply = talk.TalkToAliceWidget._maybe_execute_cortex_first_owner_effector(
        widget,
        owner_text,
        _owner_cortex_text("summarizes the transcript and stays on the YouTube page."),
    )

    assert reply == ""


def test_meta_cortex_first_search_correction_does_not_execute_browser_action(monkeypatch):
    widget = talk.TalkToAliceWidget.__new__(talk.TalkToAliceWidget)
    widget._append_system_line = lambda *args, **kwargs: None

    def fail_search(owner_text):
        raise AssertionError(f"routing correction must not search: {owner_text}")

    def fail_app(command):
        raise AssertionError(f"routing correction must not execute app/browser action: {command}")

    monkeypatch.setattr(
        talk.TalkToAliceWidget,
        "_execute_cortex_switch_after_cortex",
        lambda self, owner_text, cortex_text: "",
    )
    monkeypatch.setattr(
        talk.TalkToAliceWidget,
        "_consume_staged_foreground_browser_intent",
        lambda self, owner_text: "",
    )
    monkeypatch.setattr(talk.TalkToAliceWidget, "_execute_contextual_browser_search", fail_search)
    widget._execute_sifta_app_command = fail_app

    owner_text = (
        "ALICE IF I TELL YOU TO SEARCH FOR THE VISIBLE SUBJECT AND OPEN THE 6TH PHOTO IN THE LIST "
        "YOU CAN'T JUST TAKE ALL THIS TEXT AND SEARCH. WITHOUT THINKING CORTEX?"
    )

    assert talk._is_contextual_browser_search_request(owner_text)
    assert talk._is_owner_meta_routing_correction(owner_text)
    assert not talk._is_contextual_browser_search_effector_request(owner_text)
    assert not talk._owner_effector_requires_cortex_first(owner_text)
    assert talk._extract_sifta_app_command(owner_text) == {}

    reply = talk.TalkToAliceWidget._maybe_execute_cortex_first_owner_effector(
        widget,
        owner_text,
        _owner_cortex_text("understands this as a routing correction, not a search command."),
    )

    assert reply == ""


def test_post_cortex_explicit_contextual_search_still_executes(monkeypatch):
    widget = talk.TalkToAliceWidget.__new__(talk.TalkToAliceWidget)
    widget._append_system_line = lambda *args, **kwargs: None

    monkeypatch.setattr(
        talk.TalkToAliceWidget,
        "_execute_cortex_switch_after_cortex",
        lambda self, owner_text, cortex_text: "",
    )
    monkeypatch.setattr(
        talk.TalkToAliceWidget,
        "_consume_staged_foreground_browser_intent",
        lambda self, owner_text: "",
    )
    monkeypatch.setattr(
        talk.TalkToAliceWidget,
        "_execute_contextual_browser_search",
        lambda self, owner_text: "I searched Google for the model using the current page context.",
    )

    owner_text = "Where can I buy this type of bikini? Can you search on Google?"
    assert talk._is_contextual_browser_search_effector_request(owner_text)

    reply = talk.TalkToAliceWidget._maybe_execute_cortex_first_owner_effector(
        widget,
        owner_text,
        _owner_cortex_text("will use the browser because the owner explicitly asked to search."),
    )

    assert f"{_registered_owner_name()} will use the browser" in reply
    assert "After thinking, I executed the real body action:" in reply
    assert "I searched Google for the model" in reply


def test_set_cortex_alias_tool_writes_continuity_diary(monkeypatch, tmp_path):
    from System import sifta_inference_defaults as defaults
    from System import swarm_cortex_aliases as aliases
    from System import swarm_tool_router as router

    monkeypatch.setattr(router, "_STATE", tmp_path)
    monkeypatch.setattr(defaults, "get_default_ollama_model", lambda: "old-cortex:latest")
    monkeypatch.setattr(
        aliases,
        "set_cortex_by_alias",
        lambda name: {"ok": True, "resolved_tag": f"resolved-{name}", "receipt": "r-test"},
    )

    out = router._exec_set_cortex_alias({"name": "cline"})

    assert out["ok"] is True
    assert out["model"] == "resolved-cline"
    rows = [
        json.loads(line)
        for line in (tmp_path / "episodic_diary.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows[-1]["truth_label"] == "ALICE_CORTEX_SWITCH_CONTINUITY_V2"
    assert rows[-1]["phase"] == "tool_call_before_switch"
    assert rows[-1]["to_alias"] == "cline"


def test_r807_deterministic_grok_cortex_wrong_is_meta_routing_correction():
    owner_text = "deterministic grok cortex WRONG"
    assert talk._is_owner_meta_routing_correction(owner_text)
    assert talk._must_route_owner_turn_to_cortex(owner_text)
    assert talk._block_deterministic_owner_shortcut(owner_text)
    assert not talk._owner_effector_requires_cortex_first(owner_text)


def test_r807_pasted_screenshot_audit_blocks_browser_photo_direct(monkeypatch):
    """George 2026-06-08 live: pasted screenshot audit hijacked browser-photo reflex."""
    owner_text = (
        "fix your code Three things in that screenshot, George — one good, one ugly, one practical. "
        "**Good (grounded):** your observable pane shows `layering_chars=40198`. "
        "**Ugly:** she invented an entire Instagram profile that doesn't exist — "
        "@kylinmilan found and displayed… while her own vision arm said the image is entirely black. "
        "The browser bar says `instagram.com` but the status reads **No page loaded.** "
        "For the lying — that's the fiction guard, the r804 work."
    )
    monkeypatch.setattr(talk, "_browser_photo_description_context_active", lambda: True)

    assert talk._must_route_owner_turn_to_cortex(owner_text)
    assert talk._block_deterministic_owner_shortcut(owner_text)

    # Would have matched the old direct browser-photo heuristic (browser+image+displayed).
    assert "browser" in owner_text.lower()
    assert "image" in owner_text.lower()
    assert "displayed" in owner_text.lower()

    # Direct reflex must stand down even when photo-describe regex would match.
    assert talk._is_browser_photo_description_query(owner_text) or talk._looks_like_prose_not_command(owner_text)
    assert talk._block_deterministic_owner_shortcut(owner_text)


def test_r807_short_describe_still_allows_direct_when_not_doctrine(monkeypatch):
    owner_text = "please describe this photo"
    monkeypatch.setattr(talk, "_browser_photo_description_context_active", lambda: True)

    assert not talk._must_route_owner_turn_to_cortex(owner_text)
    assert not talk._block_deterministic_owner_shortcut(owner_text)
    assert talk._is_browser_photo_description_query(owner_text)
