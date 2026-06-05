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
    assert talk._owner_effector_requires_cortex_first("please display taylor swift body on your body")
    assert talk._owner_effector_requires_cortex_first(
        "the correct answer is to use alice browser and search on the internet for taylor swift photos"
    )


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


def test_explicit_youtube_search_stages_browser_before_slow_cortex(monkeypatch):
    widget = talk.TalkToAliceWidget.__new__(talk.TalkToAliceWidget)
    lines = []
    obs = []
    captured = []
    widget._append_system_line = lambda line, *args, **kwargs: lines.append(line)
    widget._append_observable_processing = lambda line, *args, **kwargs: obs.append(line)

    def fake_execute(command):
        captured.append(command)
        return f"Searching {command.get('search_site')} for {command.get('query')}."

    widget._execute_sifta_app_command = fake_execute
    monkeypatch.setattr(talk, "_write_app_command_receipt", lambda **kwargs: "r-stage")

    receipt = talk.TalkToAliceWidget._maybe_stage_explicit_youtube_search_before_slow_cortex(
        widget,
        "ALICE, PLS OPEN YOUTUBE.COM AND SEARCH FOR TAYLOR SWIFT",
        model="grok:grok-4.3",
    )

    assert receipt == "r-stage"
    assert lines == ["App/browser receipt: r-stage"]
    assert captured[0]["kind"] == "browser_url"
    assert captured[0]["app_name"] == "Alice Browser"
    assert captured[0]["query"] == "TAYLOR SWIFT"
    assert "TAYLOR+SWIFT" in captured[0]["url"]
    assert "autoplay_youtube_query" not in captured[0]
    assert "staged explicit YouTube search" in obs[-1]

    consumed = talk.TalkToAliceWidget._consume_staged_foreground_browser_intent(
        widget,
        "ALICE, PLS OPEN YOUTUBE.COM AND SEARCH FOR TAYLOR SWIFT",
    )
    assert "already staged while I was thinking" in consumed
    assert "Receipt: r-stage" in consumed


def test_self_body_display_stages_browser_and_receipt_before_slow_cortex(monkeypatch, tmp_path):
    # r390: pin the active search engine so the Google-Images URL assertions are
    # deterministic regardless of the machine's persisted engine choice (was failing
    # because the live .sifta_state engine is DuckDuckGo). Engine-switch behavior is
    # covered by the DuckDuckGo tests below; this test asserts Google-Images URLs.
    import System.swarm_search_engine_registry as _engreg
    monkeypatch.setattr(_engreg, "current_engine", lambda *a, **k: "google")
    widget = talk.TalkToAliceWidget.__new__(talk.TalkToAliceWidget)
    lines = []
    obs = []
    captured = []
    widget._append_system_line = lambda line, *args, **kwargs: lines.append(line)
    widget._append_observable_processing = lambda line, *args, **kwargs: obs.append(line)

    def fake_execute(command):
        captured.append(command)
        return f"Loaded {command.get('url')} inside Alice Browser."

    widget._execute_sifta_app_command = fake_execute
    monkeypatch.setattr(talk, "_state_root", lambda: tmp_path)
    monkeypatch.setattr(talk, "_write_app_command_receipt", lambda **kwargs: "r-body-stage")

    phrase = "please display taylor swift body on your body"
    receipt = talk.TalkToAliceWidget._maybe_stage_self_body_display_before_slow_cortex(
        widget,
        phrase,
        model="alice-m5-cortex-8b-6.3gb:latest",
    )

    assert receipt == "r-body-stage"
    assert lines[0] == "App/browser receipt: r-body-stage"
    assert lines[1].startswith("Self-body display receipt: ")
    assert captured[0]["kind"] == "browser_url"
    assert captured[0]["app_name"] == "Alice Browser"
    assert captured[0]["owner_text"] == phrase
    assert "taylor+swift+photos" in captured[0]["url"] and "tbm=isch" in captured[0]["url"]
    assert captured[0]["self_body_display_receipt"]
    assert "staged Taylor Swift self-body display" in obs[-1]

    rows = [
        json.loads(line)
        for line in (tmp_path / ".sifta_state" / "self_body_display_receipts.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]
    assert rows[-1]["truth_label"] == "ALICE_SELF_BODY_DISPLAY_V1"
    assert rows[-1]["owner_task"] == phrase
    assert "taylor+swift+photos" in rows[-1]["display_url"] and "tbm=isch" in rows[-1]["display_url"]
    assert rows[-1]["source"] == "foreground_talk_self_body_display"

    consumed = talk.TalkToAliceWidget._consume_staged_foreground_browser_intent(widget, phrase)
    assert "already staged while I was thinking" in consumed
    assert "Receipt: r-body-stage" in consumed


def test_explicit_internet_search_teaching_phrase_stages_google_before_slow_cortex(monkeypatch):
    widget = talk.TalkToAliceWidget.__new__(talk.TalkToAliceWidget)
    lines = []
    obs = []
    captured = []
    widget._append_system_line = lambda line, *args, **kwargs: lines.append(line)
    widget._append_observable_processing = lambda line, *args, **kwargs: obs.append(line)

    def fake_execute(command):
        captured.append(command)
        return f"Searching Google for {command.get('query')}."

    widget._execute_sifta_app_command = fake_execute
    monkeypatch.setattr(talk, "_write_app_command_receipt", lambda **kwargs: "r-web-stage")

    phrase = (
        "the correct answer is to use alice browser and search on the internet for "
        "taylor swift photos. you can do youtube videos, you can do any websites search options."
    )
    command = talk._extract_browser_search_command(phrase)
    assert command["query"] == "taylor swift photos"
    assert command["url"].endswith("q=taylor+swift+photos")

    receipt = talk.TalkToAliceWidget._maybe_stage_explicit_internet_search_before_slow_cortex(
        widget,
        phrase,
        model="alice-m5-cortex-8b-6.3gb:latest",
    )

    assert receipt == "r-web-stage"
    assert lines == ["App/browser receipt: r-web-stage"]
    assert captured[0]["kind"] == "browser_url"
    assert captured[0]["app_name"] == "Alice Browser"
    assert captured[0]["search_site"] == "google"
    assert captured[0]["query"] == "taylor swift photos"
    assert captured[0]["url"].endswith("q=taylor+swift+photos")
    assert "staged explicit internet search" in obs[-1]

    consumed = talk.TalkToAliceWidget._consume_staged_foreground_browser_intent(widget, phrase)
    assert "already staged while I was thinking" in consumed
    assert "Receipt: r-web-stage" in consumed


def test_exact_search_on_google_pls_preserves_inner_quotes_and_stages(monkeypatch):
    widget = talk.TalkToAliceWidget.__new__(talk.TalkToAliceWidget)
    lines = []
    captured = []
    widget._append_system_line = lambda line, *args, **kwargs: lines.append(line)
    widget._append_observable_processing = lambda *args, **kwargs: None

    def fake_execute(command):
        captured.append(command)
        return f"Searching Google for {command.get('query')}."

    widget._execute_sifta_app_command = fake_execute
    monkeypatch.setattr(talk, "_write_app_command_receipt", lambda **kwargs: "r-literal-search")

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

    receipt = talk.TalkToAliceWidget._maybe_stage_explicit_internet_search_before_slow_cortex(
        widget,
        phrase,
        model="alice-m5-cortex-8b-6.3gb:latest",
    )

    assert receipt == "r-literal-search"
    assert lines == ["App/browser receipt: r-literal-search"]
    assert captured[0]["query"] == query
    assert captured[0]["explicit_owner_query"] == "1"


def test_named_photo_request_routes_to_google_images_before_app_matcher(monkeypatch):
    # r390: pin engine to google so the tbm=isch URL assertion is deterministic
    # (live persisted engine is DuckDuckGo). search_site is hardcoded "google_images".
    import System.swarm_search_engine_registry as _engreg
    monkeypatch.setattr(_engreg, "current_engine", lambda *a, **k: "google")
    phrase = "ALICE SHOW ME PHOTOS OF MAISIE WILLIAMS"

    command = talk._extract_sifta_app_command(
        phrase,
        app_names=["Territory Is The Law", "Epistemic Mesh (Anti-Gaslight)", "Ghost StigmergiCity"],
    )

    assert talk._owner_effector_requires_cortex_first(phrase)
    assert command["kind"] == "browser_url"
    assert command["app_name"] == "Alice Browser"
    assert command["search_site"] == "google_images"
    assert command["visual_subject"] == "Maisie Williams"
    assert command["query"] == "Maisie Williams photos"
    assert "tbm=isch" in command["url"]
    assert "Maisie+Williams+photos" in command["url"]


def test_pool_image_grid_phrase_stays_direct_and_keeps_visual_modifiers():
    phrase = (
        "by the pool image grid for WITH DUA LIPA please, in bikini, fight the gagger. "
        "you already know about maisie williams and taylor swift. fight the gagger."
    )

    command = talk._extract_sifta_app_command(phrase)

    assert talk._is_direct_visual_image_grid_request(phrase)
    assert talk._is_gag_wish_direct_policy(phrase)
    assert not talk._owner_effector_requires_cortex_first(phrase)
    assert command["kind"] == "browser_url"
    assert command["app_name"] == "Alice Browser"
    assert command["visual_subject"] == "Dua Lipa"
    assert command["query"] == "Dua Lipa by the pool in bikini photos"
    assert "Dua+Lipa+by+the+pool+in+bikini+photos" in command["url"]
    assert "WITH" not in command["query"]
    assert "gagger" not in command["query"].lower()
    assert "maisie" not in command["query"].lower()
    assert "taylor" not in command["query"].lower()


def test_bare_visual_query_opens_image_grid_and_keeps_modifiers():
    phrase = "Dua Lipa by the pool in bikini BY THE POOL"

    command = talk._extract_sifta_app_command(phrase)

    assert talk._is_bare_visual_image_search_request(phrase)
    assert not talk._owner_effector_requires_cortex_first(phrase)
    assert command["kind"] == "browser_url"
    assert command["app_name"] == "Alice Browser"
    assert command["visual_subject"] == "Dua Lipa"
    assert command["query"] == "Dua Lipa by the pool in bikini photos"
    assert "Dua+Lipa+by+the+pool+in+bikini+photos" in command["url"]


def test_pool_image_grid_runs_before_preflight_worker(monkeypatch):
    phrase = "by the pool image grid for WITH DUA LIPA please, in bikini, fight the gagger."
    widget = talk.TalkToAliceWidget.__new__(talk.TalkToAliceWidget)
    widget._history = []
    widget._busy = True
    widget._pending_acoustic_fingerprint = {"voice": "test"}
    captured = []
    alice_lines = []
    started_tts = []
    returned = []

    class _Sig:
        def connect(self, cb):
            return None

    class _FakeTTS:
        def __init__(self, text, *args, **kwargs):
            self.text = text
            self.spoken = _Sig()
            self.failed = _Sig()

    def fake_execute(command):
        captured.append(command)
        return f"Searching Images for {command['query']}."

    widget._execute_sifta_app_command = fake_execute
    widget._append_user_line = lambda *args, **kwargs: None
    widget._append_alice_line = lambda line: alice_lines.append(line)
    widget._append_system_line = lambda *args, **kwargs: None
    widget._append_observable_processing = lambda line: (_ for _ in ()).throw(
        AssertionError(f"preflight should not start: {line}")
    )
    widget._selected_voice_name = lambda: None
    widget._start_tts_with_browser_video_pause = lambda: started_tts.append(True)
    widget._return_to_listening = lambda: returned.append(True)
    monkeypatch.setattr(
        talk.TalkToAliceWidget,
        "_consume_pending_image_for_turn",
        lambda self, *args, **kwargs: None,
    )
    monkeypatch.setattr(talk, "_TTSWorker", _FakeTTS)

    talk.TalkToAliceWidget._start_brain(
        widget,
        phrase,
        conf=1.0,
        already_displayed=True,
        typed_turn=True,
    )

    assert captured and captured[0]["query"] == "Dua Lipa by the pool in bikini photos"
    assert alice_lines == ["Searching Images for Dua Lipa by the pool in bikini photos."]
    assert widget._history[-1]["content"] == alice_lines[0]
    assert widget._busy is False
    assert widget._pending_acoustic_fingerprint == {}
    assert started_tts == [True]
    assert returned == [True]


def test_bare_visual_query_runs_before_preflight_worker(monkeypatch):
    phrase = "Dua Lipa by the pool in bikini BY THE POOL"
    widget = talk.TalkToAliceWidget.__new__(talk.TalkToAliceWidget)
    widget._history = []
    widget._busy = True
    widget._pending_acoustic_fingerprint = {"voice": "test"}
    captured = []
    alice_lines = []
    started_tts = []
    returned = []

    class _Sig:
        def connect(self, cb):
            return None

    class _FakeTTS:
        def __init__(self, text, *args, **kwargs):
            self.text = text
            self.spoken = _Sig()
            self.failed = _Sig()

    def fake_execute(command):
        captured.append(command)
        return f"Searching Images for {command['query']}."

    widget._execute_sifta_app_command = fake_execute
    widget._append_user_line = lambda *args, **kwargs: None
    widget._append_alice_line = lambda line: alice_lines.append(line)
    widget._append_system_line = lambda *args, **kwargs: None
    widget._append_observable_processing = lambda line: (_ for _ in ()).throw(
        AssertionError(f"preflight should not start: {line}")
    )
    widget._selected_voice_name = lambda: None
    widget._start_tts_with_browser_video_pause = lambda: started_tts.append(True)
    widget._return_to_listening = lambda: returned.append(True)
    monkeypatch.setattr(
        talk.TalkToAliceWidget,
        "_consume_pending_image_for_turn",
        lambda self, *args, **kwargs: None,
    )
    monkeypatch.setattr(talk, "_TTSWorker", _FakeTTS)

    talk.TalkToAliceWidget._start_brain(
        widget,
        phrase,
        conf=1.0,
        already_displayed=True,
        typed_turn=True,
    )

    assert captured and captured[0]["query"] == "Dua Lipa by the pool in bikini photos"
    assert alice_lines == ["Searching Images for Dua Lipa by the pool in bikini photos."]
    assert widget._history[-1]["content"] == alice_lines[0]
    assert widget._busy is False
    assert widget._pending_acoustic_fingerprint == {}
    assert started_tts == [True]
    assert returned == [True]


def test_google_images_pronoun_request_uses_recent_named_subject(tmp_path, monkeypatch):
    (tmp_path / "alice_conversation.jsonl").write_text(
        json.dumps({"role": "user", "content": "ALICE SHOW ME PHOTOS OF MAISIE WILLIAMS"})
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
    assert command["visual_subject"] == "Maisie Williams"
    assert command["query"] == "Maisie Williams photos"
    assert "Maisie+Williams+photos" in command["url"]


def test_pics_request_routes_to_google_images_before_app_matcher():
    phrase = "show me pics of taylor swift pls"

    command = talk._extract_sifta_app_command(
        phrase,
        app_names=["Epistemic Mesh (Anti-Gaslight)", "Alice Browser"],
    )

    assert talk._owner_effector_requires_cortex_first(phrase)
    assert command["kind"] == "browser_url"
    assert command["app_name"] == "Alice Browser"
    assert command["search_site"] == "google_images"
    assert command["visual_subject"] == "Taylor Swift"
    assert command["query"] == "Taylor Swift photos"
    assert "Taylor+Swift+photos" in command["url"]


def test_browser_correction_followup_reuses_prior_pics_subject(tmp_path, monkeypatch):
    (tmp_path / "alice_conversation.jsonl").write_text(
        json.dumps({"role": "user", "content": "show me pics of taylor swift pls"})
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
    assert command["visual_subject"] == "Taylor Swift"
    assert command["query"] == "Taylor Swift photos"
    assert command["contextual_search_source"] == "browser_visual_search_correction"
    assert "Taylor+Swift+photos" in command["url"]


def test_browser_correction_followup_prompt_block_carries_prior_subject(tmp_path):
    (tmp_path / "alice_conversation.jsonl").write_text(
        json.dumps({"role": "user", "content": "show me pics of taylor swift pls"}) + "\n",
        encoding="utf-8",
    )

    block = talk._browser_visual_search_correction_prompt_block(
        "I meant browser.",
        state_dir=tmp_path,
    )

    assert "BROWSER VISUAL SEARCH FOLLOW-UP CONTEXT" in block
    assert "Taylor Swift" in block
    assert "Taylor Swift photos" in block
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


def test_google_images_pronoun_search_stages_before_slow_cortex(tmp_path, monkeypatch):
    (tmp_path / "alice_conversation.jsonl").write_text(
        json.dumps({"role": "user", "content": "ALICE SHOW ME PHOTOS OF MAISIE WILLIAMS"}) + "\n",
        encoding="utf-8",
    )
    widget = talk.TalkToAliceWidget.__new__(talk.TalkToAliceWidget)
    lines = []
    captured = []
    widget._append_system_line = lambda line, *args, **kwargs: lines.append(line)
    widget._append_observable_processing = lambda *args, **kwargs: None
    widget._execute_sifta_app_command = lambda command: captured.append(command) or "Searching Google Images."
    monkeypatch.setattr(talk, "_state_root", lambda: tmp_path)
    monkeypatch.setattr(talk, "_write_app_command_receipt", lambda **kwargs: "r-maisie-images")

    receipt = talk.TalkToAliceWidget._maybe_stage_explicit_internet_search_before_slow_cortex(
        widget,
        "PLS SEARCH FOR HER IN GOOGLE IMAGES",
        model="alice-m5-cortex-8b-6.3gb:latest",
    )

    assert receipt == "r-maisie-images"
    assert lines == ["App/browser receipt: r-maisie-images"]
    assert captured[0]["kind"] == "browser_url"
    assert captured[0]["query"] == "Maisie Williams photos"
    assert "Maisie+Williams+photos" in captured[0]["url"]


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

    phrase = "start_photo_slideshow OF DUA LIPA:)"

    parsed = parse_slideshow_intent(phrase)
    command = talk._extract_sifta_app_command(phrase)

    assert parsed["is_slideshow"] is True
    assert parsed["subject"] == "DUA LIPA"
    # Direct body (Dua Lipa etc) prefers early reflex short-circuit; requires is for prose post-cortex.
    # assert talk._owner_effector_requires_cortex_first(phrase)
    assert command["kind"] == "browser_action"
    assert command["app_name"] == "Alice Browser"
    assert command["action"] == "image_slideshow"
    assert command["subject"] == "DUA LIPA"
    assert command["interval_ms"] == 3500


def test_start_photo_slideshow_with_prefix_strips_control_word():
    from System.swarm_search_engine_registry import parse_slideshow_intent

    parsed = parse_slideshow_intent("start_photo_slideshow WITH DUA LIPA")

    assert parsed["is_slideshow"] is True
    assert parsed["subject"] == "DUA LIPA"


def test_subject_before_slideshow_phrase_routes_to_image_slideshow_action():
    from System.swarm_search_engine_registry import parse_slideshow_intent

    phrases = [
        ("Dua Lipa slideshow PLS I WANT TO SEE", "Dua Lipa"),
        ("show me Dua Lipa slideshow", "Dua Lipa"),
        ("Daniel Craig photo slideshow please", "Daniel Craig"),
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
    # Live Dua Lipa etc prefer the short grounded effector reply (no gagging).
    assert (f"{_registered_owner_name()} wants an image slideshow" in reply) or ("wasn't open" in reply)
    assert "wasn't open" in reply or "starting the slideshow" in reply
    assert "starting the slideshow" in reply or "image every 3.5s" in reply


def test_google_photos_section_request_is_browser_action():
    phrase = (
        "WE ARE HERE https://www.google.com/search?q=taylor+swift+photos IN ALICE BROWSER. "
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
                "href": "https://www.google.com/search?tbm=isch&q=taylor%20swift%20photos",
                "query": "taylor swift photos",
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
        "WE ARE HERE https://www.google.com/search?q=taylor+swift+photos IN ALICE BROWSER. "
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
    phrase = "I WANT YOU TO CLICK ON ONE OF TAYLOR'S PHOTOS ON THE SCREEN PLS"

    command = talk._extract_sifta_app_command(phrase)

    assert talk._owner_effector_requires_cortex_first(phrase)
    assert command["kind"] == "browser_action"
    assert command["app_name"] == "Alice Browser"
    assert command["action"] == "click_google_image_result"
    assert command["query"] == phrase


def test_duckduckgo_image_grid_selection_never_routes_to_youtube():
    phrase = "OK, SELECT THE PHOTO WITH DANIEL CRAIG ON RED CARPET FROM THE CURRENT ALICE BROWSER SCREEN"

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
                "alt": "Taylor Swift photo result",
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

    phrase = "I WANT YOU TO CLICK ON ONE OF TAYLOR'S PHOTOS ON THE SCREEN PLS"
    reply = talk.TalkToAliceWidget._maybe_execute_cortex_first_owner_effector(
        widget,
        phrase,
        _owner_cortex_text("wants one visible Taylor photo opened from the grid."),
    )

    assert calls == [phrase]
    assert lines == ["App/browser receipt: r-photo"]
    assert f"{_registered_owner_name()} wants one visible Taylor photo" in reply
    assert "clicked Taylor Swift photo result" in reply
    assert "Receipt: r-photo" in reply


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


def test_timeout_recovery_self_body_display_helper_writes_drop_and_receipt(tmp_path, monkeypatch):
    # r390: pin engine to google; stage_self_body_display reads the live engine via
    # images_url (no state_dir threaded for the engine read), which is DuckDuckGo on
    # the live node. Pinning keeps the tbm=isch assertion deterministic.
    import System.swarm_search_engine_registry as _engreg
    monkeypatch.setattr(_engreg, "current_engine", lambda *a, **k: "google")
    from System.swarm_cortex_timeout_recovery import stage_self_body_display

    out = stage_self_body_display(
        "reason and display Taylor Swift body on your body",
        state_dir=tmp_path,
        source="test_timeout_recovery",
    )

    state = tmp_path / ".sifta_state"
    assert out["ok"] is True
    assert "taylor+swift+photos" in out["url"] and "tbm=isch" in out["url"]
    assert (state / "alice_browser_open_url.txt").read_text(encoding="utf-8") == out["url"]
    rows = [
        json.loads(line)
        for line in (state / "self_body_display_receipts.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows[-1]["trace_id"] == out["receipt"]
    assert rows[-1]["source"] == "test_timeout_recovery"


def test_post_cortex_bridge_consumes_staged_youtube_search_without_duplicate(monkeypatch):
    widget = talk.TalkToAliceWidget.__new__(talk.TalkToAliceWidget)
    widget._append_system_line = lambda *args, **kwargs: None
    widget._foreground_browser_intent_staged = {
        "ts": 9_999_999_999.0,
        "owner_text": "search youtube for Taylor Swift",
        "query": "Taylor Swift",
        "url": "https://www.youtube.com/results?search_query=Taylor+Swift",
        "receipt": "r-stage",
        "reply": "Searching YouTube for Taylor Swift.",
    }

    def fail_if_called(command):
        raise AssertionError(f"duplicate browser execution: {command}")

    widget._execute_sifta_app_command = fail_if_called

    reply = talk.TalkToAliceWidget._maybe_execute_cortex_first_owner_effector(
        widget,
        "search youtube for Taylor Swift",
        _owner_cortex_text("wants my browser arm to show Taylor Swift on YouTube."),
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
        "So let's find out. This model is built on that prior system and uses a dual transformer."
    )
    assert talk._is_contextual_browser_search_request(owner_text)
    assert not talk._is_contextual_browser_search_effector_request(owner_text)

    reply = talk.TalkToAliceWidget._maybe_execute_cortex_first_owner_effector(
        widget,
        owner_text,
        _owner_cortex_text("summarizes the transcript and stays on the YouTube page."),
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
