"""Data-first grounding guards for Talk to Alice.

After de-scripting, the widget should still expose multimodal grounding data
while avoiding hardcoded behavior lawbooks.
"""

import importlib.util
import json
import time
from pathlib import Path


def _load_widget_module():
    here = Path(__file__).resolve().parent.parent
    path = here / "Applications" / "sifta_talk_to_alice_widget.py"
    spec = importlib.util.spec_from_file_location("ttw_grounding", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_system_prompt_contains_runtime_constraints_and_not_lawbook():
    mod = _load_widget_module()
    prompt = mod._current_system_prompt(user_active=True)
    assert "RUNTIME CONSTRAINTS:" in prompt
    assert "FALSE REFUSAL QUARANTINE:" in prompt
    assert "BODY / LOCATION / CONTINUITY / MEDIA-SOURCE TRUTH:" in prompt
    assert "CONVERSATIONAL DISCIPLINE" not in prompt
    assert "Lefty" not in prompt
    assert "Bishapi" not in prompt


def test_system_prompt_vendor_firewall_and_capability_bar():
    mod = _load_widget_module()
    prompt = mod._current_system_prompt(user_active=True)
    assert "ACTIVE_BRAIN_MODEL=" in prompt
    assert "IDENTITY FIREWALL:" in prompt
    assert "SESSION FRAMING:" in prompt
    assert "CAPABILITY BAR" not in prompt
    assert "NOT_CERTIFIED" not in prompt
    assert "strictly bounded, receipt-backed silicon organism" not in prompt.casefold()
    assert "advanced agentic system" not in prompt.casefold()
    assert "strong internal consistency mechanisms" not in prompt.casefold()


def test_system_prompt_architect_stigbody_not_fiction():
    mod = _load_widget_module()
    prompt = mod._current_system_prompt(user_active=True)
    assert "ARCHITECT / STIGBODY (REALITY ANCHOR):" in prompt
    assert "primary_operator" in prompt
    assert "stigbody" in prompt.casefold()


def test_system_prompt_still_contains_multimodal_identity_data():
    mod = _load_widget_module()
    prompt = mod._current_system_prompt(user_active=True)
    assert "COMPOSITE IDENTITY (live, multi-organ):" in prompt
    assert "- self:" in prompt
    assert "- body:" in prompt or "- endocrine:" in prompt or "- sensory:" in prompt


def test_system_prompt_includes_alice_self_organ_receipts():
    mod = _load_widget_module()
    prompt = mod._current_system_prompt(user_active=True)
    assert "ALICE SELF ORGAN (receipt-backed OS awareness):" in prompt
    assert "python_body_files_seen:" in prompt
    assert "app_organs_seen:" in prompt
    assert "running_sifta_python_processes_seen:" in prompt
    assert "somatic_sensors:" in prompt
    assert "biography:" in prompt
    assert "continuity:" in prompt
    assert "social_field:" in prompt
    assert "thermodynamic_risk:" in prompt
    assert "answer self/OS-awareness questions from this organ" in prompt


def test_system_prompt_keeps_architect_and_whatsapp_identity_separate():
    mod = _load_widget_module()
    prompt = mod._current_system_prompt(user_active=True)

    from System.swarm_kernel_identity import owner_name
    actual_owner = owner_name()

    assert f"{actual_owner} is the Architect" in prompt
    assert "SIFTA organism" in prompt and "running on this machine" in prompt
    assert f"I am not {actual_owner}" in prompt
    assert "never invent nicknames" in prompt
    assert "quoted or observed WhatsApp" in prompt or "WhatsApp names belong to" in prompt
    assert "Cipi is a friend from WhatsApp" in prompt


def test_speech_potential_prompt_is_not_mislabeled_as_friston():
    mod = _load_widget_module()
    prompt = mod._current_system_prompt(user_active=True)
    assert "STIGMERGIC SPEECH POTENTIAL (live LIF gate):" in prompt
    assert "Friston Free-Energy Principle" not in prompt
    assert "variational free-energy calculation" in prompt
    assert "V_th" in prompt


def test_time_questions_use_direct_time_protocol():
    mod = _load_widget_module()
    assert mod._is_current_time_query("What time is it now Alice?")
    assert mod._is_current_time_query("What time is this right now please?")
    assert mod._is_current_time_query("tell me the time")
    assert not mod._is_current_time_query("time to keep programming")

    prompt = mod._current_system_prompt(user_active=True)
    assert "TIME ACCESS PROTOCOL:" in prompt
    assert "WALL CLOCK GROUND TRUTH" in prompt
    assert "current_local_time=" in prompt
    assert "Do not say you do not know the exact time while this block is present" in prompt
    assert "[Insert Current Time Here]" not in prompt


def test_current_time_reply_is_not_placeholder():
    mod = _load_widget_module()
    reading = mod._current_time_reading_for_alice()
    reply = mod._current_time_reply_for_alice(reading)
    owner = mod._owner_label()
    assert "[Insert Current Time Here]" not in reply
    assert reply.startswith(f"{owner}, ")
    assert "time" in reply.casefold() or "it is" in reply.casefold()

    ctx = mod._current_time_context_for_llm(reading, reply)
    assert "TIME ORACLE TURN CONTEXT:" in ctx
    assert "required_spoken_answer=" in ctx
    assert reply in ctx
    assert "Speak the required_spoken_answer aloud" in ctx


def test_time_hedge_output_is_detected_for_oracle_repair():
    mod = _load_widget_module()
    raw = (
        "The current time, based on the system clock, is not explicitly provided "
        "in the context, but the last recorded timestamp implies the context is very recent. "
        "If you need the specific time, please let me know."
    )
    assert mod._TIME_HEDGE_OUTPUT_RE.search(raw)


def test_date_questions_use_oracle_context_and_repair_wrong_day():
    mod = _load_widget_module()
    reading = {
        "ok": True,
        "source": "hardware_time_oracle",
        "local_human": "Friday May 08 2026, 04:51 PM",
        "timezone": "PDT",
        "local_iso": "2026-05-08T16:51:00",
        "epoch": 1778284260.0,
        "signature": "abc123def456",
    }

    assert mod._is_current_date_query("What day is today?")
    assert mod._is_current_date_query("What's the date?")
    assert not mod._is_current_date_query("date this implementation note")

    reply = mod._current_date_reply_for_alice(reading)
    assert "Friday" in reply
    assert "May 08, 2026" in reply
    assert "hardware time oracle" in reply

    ctx = mod._current_date_context_for_llm(reading, reply)
    assert "DATE ORACLE TURN CONTEXT:" in ctx
    assert "current_weekday=Friday" in ctx
    assert "current_date=May 08, 2026" in ctx
    assert "required_spoken_answer=" in ctx
    assert reply in ctx

    assert mod._date_reply_is_untrusted("Today is Tuesday.", reading)
    assert mod._date_reply_is_untrusted("The context implies today may be Tuesday.", reading)
    assert not mod._date_reply_is_untrusted(reply, reading)


def test_sifta_app_commands_resolve_manifest_apps_and_browser_urls():
    mod = _load_widget_module()
    # Architect 2026-05-16 rename: WordAce → Ace. The manifest stub now
    # uses "Ace" as the canonical name; all legacy STT-mangled WordAce
    # phrases ("word A's", "word ass", "word ace") still resolve to it
    # via the alias dict, but the returned name is the new canonical.
    app_names = [
        "Alice Browser",
        "Finance",
        "System Settings",
        "WhatsApp Organ",
        "Ace",
        "Pheromone Symphony (Generative Music)",
        "Stigmergic Video Poker",
    ]

    assert mod._match_sifta_app_name("Alice Browser app", app_names) == "Alice Browser"
    assert mod._match_sifta_app_name("finance", app_names) == "Finance"
    assert mod._match_sifta_app_name("word A's", app_names) == "Ace"
    assert mod._match_sifta_app_name("word ass", app_names) == "Ace"
    assert mod._match_sifta_app_name("word ace", app_names) == "Ace"
    assert mod._match_sifta_app_name("ace", app_names) == "Ace"
    assert mod._match_sifta_app_name("Ace app", app_names) == "Ace"

    app_cmd = mod._extract_sifta_app_command("Alice, open Alice Browser app", app_names)
    assert app_cmd == {"kind": "app", "app_name": "Alice Browser", "url": ""}

    wordace_cmd = mod._extract_sifta_app_command("Alice, open word A's app", app_names)
    assert wordace_cmd == {"kind": "app", "app_name": "Ace", "url": ""}

    wordace_stt_cmd = mod._extract_sifta_app_command("Alice, open word ass app", app_names)
    assert wordace_stt_cmd == {"kind": "app", "app_name": "Ace", "url": ""}

    microsoft_word_cmd = mod._extract_sifta_app_command("Alice, open Microsoft Word app", app_names)
    assert microsoft_word_cmd["kind"] == "open_app_uncertain"
    assert microsoft_word_cmd["raw_query"] == "Microsoft Word"
    assert microsoft_word_cmd["app_name"] == ""
    assert microsoft_word_cmd["url"] == ""
    # After the WordAce → Ace rename, "Microsoft Word" no longer has a clean
    # token-overlap with the reading app name ('ace' is too short to share a
    # 4+ char token with 'word'/'microsoft'). The honest refusal still fires
    # with three real manifest names so the brain cannot invent "Microsoft Word".
    assert len(microsoft_word_cmd["candidates"].split(",")) == 3

    photoshop_cmd = mod._extract_sifta_app_command("Alice, open Photoshop app", app_names)
    assert photoshop_cmd["kind"] == "open_app_uncertain"
    assert photoshop_cmd["raw_query"] == "Photoshop"
    assert photoshop_cmd["app_name"] == ""
    assert len(photoshop_cmd["candidates"].split(",")) == 3

    pheromone_stt_cmd = mod._extract_sifta_app_command("Alice, open ceremony Symphony app", app_names)
    assert pheromone_stt_cmd["kind"] == "open_app_uncertain"
    assert pheromone_stt_cmd["raw_query"] == "ceremony Symphony"
    assert pheromone_stt_cmd["candidates"].split(",")[0] == "Pheromone Symphony (Generative Music)"

    # "work ASAP" is too mangled to open automatically. Voice Stigma Repair
    # ranks the reading app first and asks one confirmation before execution.
    wordace_stt_phrase_cmd = mod._extract_sifta_app_command("Alice, open work ASAP app", app_names)
    assert wordace_stt_phrase_cmd["kind"] == "open_app_uncertain"
    assert wordace_stt_phrase_cmd["raw_query"] == "work ASAP"
    assert wordace_stt_phrase_cmd["candidates"].split(",")[0] == "Ace"

    youtube_soon = mod._extract_sifta_app_command(
        "This is George, I'm sitting by the computer waiting for your answer "
        "to process and I'm gonna start the YouTube video soon.",
        app_names,
    )
    assert youtube_soon == {}

    no_app = mod._extract_sifta_app_command(
        "Alice, I don't want to open any app right now.",
        app_names,
    )
    assert no_app == {}

    youtube_conversation = mod._extract_sifta_app_command(
        "No, I was talking about the YouTube video on consciousness that we are gonna be listening together",
        app_names,
    )
    assert youtube_conversation == {}

    real_video_app = mod._extract_sifta_app_command(
        "Alice, open Stigmergic Video Poker app",
        app_names,
    )
    assert real_video_app == {"kind": "app", "app_name": "Stigmergic Video Poker", "url": ""}

    assert mod._voice_repair_confirmation_action("yes, that's what I meant") == "yes"
    assert mod._voice_repair_confirmation_action("no, none of those") == "no"
    assert mod._voice_repair_confirmation_action("Ace.") == ""
    assert mod._voice_repair_candidate_selection(
        "Ace.",
        ["Finance", "Ace", "NVIDIA × SIFTA"],
    ) == "Ace"

    chat_cmd = mod._extract_sifta_app_command("open Alice", app_names)
    assert chat_cmd == {"kind": "switch_desktop_mode", "mode": "chat", "app_name": "", "url": ""}

    status_cmd = mod._extract_sifta_app_command("what app is open", app_names)
    assert status_cmd == {"kind": "app_status", "app_name": "", "url": ""}

    close_current_cmd = mod._extract_sifta_app_command("close current app", app_names)
    assert close_current_cmd == {"kind": "close_app", "app_name": "", "url": ""}

    close_named_cmd = mod._extract_sifta_app_command("close System Settings app", app_names)
    assert close_named_cmd == {"kind": "close_app", "app_name": "System Settings", "url": ""}

    browser_cmd = mod._extract_sifta_app_command("Alice, open youtube.com in the browser", app_names)
    assert browser_cmd == {
        "kind": "browser_url",
        "app_name": "Alice Browser",
        "url": "https://youtube.com",
    }

    alias_cmd = mod._extract_sifta_app_command("load GitHub website please", app_names)
    assert alias_cmd == {
        "kind": "browser_url",
        "app_name": "Alice Browser",
        "url": "https://github.com",
    }

    followup_cmd = mod._extract_sifta_app_command("in the browser go in a google.com", app_names)
    assert followup_cmd == {
        "kind": "browser_url",
        "app_name": "Alice Browser",
        "url": "https://google.com",
    }

    page_cmd = mod._extract_sifta_app_command("go on Wikipedia", app_names)
    assert page_cmd == {
        "kind": "browser_url",
        "app_name": "Alice Browser",
        "url": "https://en.wikipedia.org",
    }


def test_pending_app_repair_rejection_returns_to_conversation_lane(tmp_path, monkeypatch):
    mod = _load_widget_module()
    monkeypatch.setattr(mod, "_state_root", lambda: tmp_path)

    class Dummy:
        def __init__(self):
            self._pending_app_confirmation = {
                "ts": time.time(),
                "raw_query": "the YouTube video soon",
                "app_name": "Stigmergic Video Poker",
                "candidates": ["Stigmergic Video Poker", "Cognitive Loop", "Crucible Simulator"],
            }
            self._history = []
            self.system_lines = []

        def _append_system_line(self, msg, error=False):
            self.system_lines.append((msg, error))

    dummy = Dummy()
    reply = mod.TalkToAliceWidget._maybe_handle_pending_app_confirmation(
        dummy,
        "No, I was talking about the YouTube video on consciousness that we are gonna be listening together",
    )

    assert reply == ""
    assert dummy._pending_app_confirmation is None
    assert any("App/browser receipt:" in msg for msg, _error in dummy.system_lines)
    assert any(
        "ordinary Alice conversation/co-watch context" in turn.get("content", "")
        for turn in dummy._history
    )


def test_pending_app_repair_plain_no_does_not_ask_for_app_name(tmp_path, monkeypatch):
    mod = _load_widget_module()
    monkeypatch.setattr(mod, "_state_root", lambda: tmp_path)

    class Dummy:
        def __init__(self):
            self._pending_app_confirmation = {
                "ts": time.time(),
                "raw_query": "any app right now",
                "app_name": "Alice Shell",
                "candidates": ["Alice Shell", "Finance", "SIFTA NLE"],
            }
            self._history = []
            self.system_lines = []

        def _append_system_line(self, msg, error=False):
            self.system_lines.append((msg, error))

    dummy = Dummy()
    reply = mod.TalkToAliceWidget._maybe_handle_pending_app_confirmation(dummy, "No.")

    assert reply == "Okay. I will not open an app. I am back in the conversation lane."
    assert "Say the app name again" not in reply
    assert dummy._pending_app_confirmation is None


def test_voice_context_repair_cleans_microphone_residue_before_cortex():
    mod = _load_widget_module()

    raw = (
        "we are teaching the Al Corona operating system and it is on its own "
        "cheese own Own OWN and Gemma Ford should digest it"
    )
    repaired, reasons = mod._repair_voice_context_text(raw, stt_conf=0.58)

    assert "Alice local operating system" in repaired
    assert "Gemma 4" in repaired
    assert "cheese" not in repaired.casefold()
    assert "own Own OWN" not in repaired
    assert "local_os_name" in reasons
    assert "model_name" in reasons
    assert "own_not_cheese" in reasons
    assert "collapsed_repeated_word" in reasons


def test_voice_context_repair_leaves_clean_text_unchanged():
    mod = _load_widget_module()

    raw = "Alice, I am talking to the operating system and I want you to listen."
    repaired, reasons = mod._repair_voice_context_text(raw, stt_conf=0.82)

    assert repaired == raw
    assert reasons == []

    app_names = ["Alice Browser", "Finance", "System Settings", "WhatsApp Organ", "Ace"]
    wiki_search = mod._extract_sifta_app_command("Can you search on Wikipedia for Lions?", app_names)
    assert wiki_search == {
        "kind": "browser_url",
        "app_name": "Alice Browser",
        "url": "https://en.wikipedia.org/w/index.php?search=Lions",
        "search_site": "wikipedia",
        "query": "Lions",
    }

    wiki_followup_search = mod._extract_sifta_app_command("Okay, let's go on Wikipedia and search for grass.", app_names)
    assert wiki_followup_search == {
        "kind": "browser_url",
        "app_name": "Alice Browser",
        "url": "https://en.wikipedia.org/w/index.php?search=grass",
        "search_site": "wikipedia",
        "query": "grass",
    }

    google_search = mod._extract_sifta_app_command("search with Google for nvidia graphics cards", app_names)
    assert google_search == {
        "kind": "browser_url",
        "app_name": "Alice Browser",
        "url": "https://www.google.com/search?q=nvidia+graphics+cards",
        "search_site": "google",
        "query": "nvidia graphics cards",
    }

    direct_google_search = mod._extract_sifta_app_command("search Google for CUDA examples", app_names)
    assert direct_google_search == {
        "kind": "browser_url",
        "app_name": "Alice Browser",
        "url": "https://www.google.com/search?q=CUDA+examples",
        "search_site": "google",
        "query": "CUDA examples",
    }

    english_click = mod._extract_sifta_app_command("click where it says English on this page", app_names)
    assert english_click == {
        "kind": "browser_url",
        "app_name": "Alice Browser",
        "url": "https://en.wikipedia.org/wiki/Main_Page",
        "click_target": "English",
    }

    autonomous_choice = mod._extract_sifta_app_command(
        "I wanted you to go to a website that you wish to read yourself",
        app_names,
    )
    assert autonomous_choice["kind"] == "browser_url"
    assert autonomous_choice["app_name"] == "Alice Browser"
    assert autonomous_choice["url"] == "https://en.wikipedia.org/wiki/Special:Random"
    assert autonomous_choice["autonomous_choice"] == "1"

    feel_free_choice = mod._extract_sifta_app_command(
        "I'll just feel free to browse any website you like.",
        app_names,
    )
    assert feel_free_choice["kind"] == "browser_url"
    assert feel_free_choice["app_name"] == "Alice Browser"
    assert feel_free_choice["url"] == "https://en.wikipedia.org/wiki/Special:Random"
    assert feel_free_choice["autonomous_choice"] == "1"

    wiki_english_page = mod._extract_sifta_app_command(
        "Please go in Alice Browser on Wikipedia.com on English page.",
        app_names,
    )
    assert wiki_english_page == {
        "kind": "browser_url",
        "app_name": "Alice Browser",
        "url": "https://en.wikipedia.org/wiki/Main_Page",
        "click_target": "English",
    }

    open_and_summarize = mod._extract_sifta_app_command(
        "go on Wikipedia.com and summarize what content is on the main page",
        app_names,
    )
    assert open_and_summarize == {
        "kind": "browser_url",
        "app_name": "Alice Browser",
        "url": "https://Wikipedia.com",
        "summarize_after_open": "1",
    }


def test_browser_page_summary_uses_current_page_snapshot_text():
    mod = _load_widget_module()

    assert mod._is_webpage_summary_query("Can you read the website?")
    assert mod._is_webpage_summary_query("Yahoo.com on a page. Can you summarize the page?")
    assert not mod._is_webpage_summary_query("That was great, good job.")

    reply = mod._summarize_browser_page(
        {
            "title": "NVIDIA News",
            "url": "https://www.nvidia.com/",
            "text": "\n".join(
                [
                    "Cookie preferences and privacy policy",
                    "NVIDIA builds accelerated computing platforms for graphics, AI, simulation, and data centers.",
                    "The GeForce product family serves gamers, creators, and developers with GPU hardware and software.",
                    "NVIDIA also publishes research, driver updates, robotics tools, and developer documentation.",
                ]
            ),
        }
    )
    assert "NVIDIA News" in reply
    assert "https://www.nvidia.com/" in reply
    assert "accelerated computing platforms" in reply
    assert "Cookie preferences" not in reply


def test_owner_spoken_context_writes_life_history_and_day_segment(tmp_path, monkeypatch):
    mod = _load_widget_module()
    monkeypatch.setattr(mod, "_state_root", lambda: tmp_path)

    reply = mod._owner_spoken_context_reply(
        "I was on a phone with my mom. That's what for context.",
        0.59,
    )

    assert reply == "Written. I logged that you were on the phone with your mom."
    history_rows = [
        mod.json.loads(line)
        for line in (tmp_path / "alice_life_history.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert history_rows[-1]["event_type"] == "owner_phone_with_mom"
    assert "phone with his mom" in history_rows[-1]["alice_entry"]

    day_rows = [
        mod.json.loads(line)
        for line in (tmp_path / "architect_day_segments.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert day_rows[-1]["label"] == "on_phone"
    assert day_rows[-1]["relation"] == "mom"


def test_owner_tv_context_sets_ambient_media_boundary(tmp_path, monkeypatch):
    mod = _load_widget_module()
    monkeypatch.setattr(mod, "_state_root", lambda: tmp_path)

    reply = mod._owner_spoken_context_reply(
        "This is me speaking and soon you're gonna hear the TV, so know the difference.",
        0.73,
    )

    assert "TV as background media" in reply
    context = mod.json.loads((tmp_path / "ambient_media_context.json").read_text(encoding="utf-8"))
    assert context["source"] == "owner_spoken_context"
    assert "TV audio may follow" in context["note"]


def test_concise_style_preference_is_persisted(tmp_path, monkeypatch):
    mod = _load_widget_module()
    monkeypatch.setattr(mod, "_state_root", lambda: tmp_path)

    reply = mod._concise_style_reply("First we have to explore your answers to be shorter, more human like.")

    assert reply == "Understood. I’ll keep my replies shorter and more natural."
    style = mod.json.loads((tmp_path / "alice_response_style.json").read_text(encoding="utf-8"))
    assert style["style"] == "short_human_like"
    assert "1-2 short sentences" in mod._response_style_prompt_block()


def test_alice_response_misroute_query_does_not_match_day_segment_recall():
    mod = _load_widget_module()

    assert mod._ALICE_RESPONSE_MISROUTE_QUERY_RE.search("What happened to your response Alice?")
    assert not mod._ALICE_RESPONSE_MISROUTE_QUERY_RE.search("What was I doing 20 minutes ago?")


def test_live_perception_question_does_not_hit_schedule_ledger():
    mod = _load_widget_module()
    text = "What am I doing right now, breathing?"

    assert mod._schedule_query_reply(text) == ""
    reply = mod._live_perception_reply_for_alice(text)
    folded = reply.casefold()
    assert "live vision/body receipt" in folded
    assert "dentist appointment" not in folded
    assert "at 10am" not in folded


def test_live_perception_source_disambiguation_is_not_full_name_template():
    mod = _load_widget_module()
    text = (
        "What am I saying? I know it's difficult for you to figure it out "
        "which one is my voice, when am I on camera, when am I not on camera, "
        "am I speaking, am I on a phone, that's TV."
    )

    reply = mod._live_perception_reply_for_alice(text)
    folded = reply.casefold()
    assert "owner voice versus tv" in folded
    assert "transcript text alone" in folded
    assert "ioan george anton" not in folded
    assert "this is a live perception question, not a schedule question" not in folded


def test_owner_name_questions_use_kernel_identity_protocol():
    mod = _load_widget_module()
    assert mod._is_owner_name_query("Alice, what is my name?")
    assert mod._is_owner_name_query("who am I?")
    assert not mod._is_owner_name_query("what is your name?")

    reply = mod._owner_name_reply_for_alice()
    assert "Your name is" in reply
    assert "Ioan George Anton" in reply
    assert "local kernel owner genesis" in reply
    assert "please provide it" not in reply.casefold()
    assert "primary actor" not in reply.casefold()


def test_prompt_owner_name_is_runtime_bound_not_george_hardcoded(monkeypatch):
    from System import swarm_kernel_identity as identity

    monkeypatch.setattr(identity, "owner_display_name", lambda default="the local human": "Avery")
    mod = _load_widget_module()
    monkeypatch.setattr(mod, "owner_display_name", lambda default="the local human": "Avery")

    prompt = mod._current_system_prompt(user_active=True)
    assert "Avery is the Architect" in prompt
    assert "Do not perform an emotion you have not measured" in prompt
    assert "swarm_affective_valence" in prompt
    assert "If Avery asks for the current time" in prompt
    assert "- Emotional State: You are happy" not in prompt
    assert "If George asks for the current time" not in prompt
    assert "George is your owner" not in prompt


def test_prompt_does_not_inject_ghost_possession_or_story_body_truth():
    mod = _load_widget_module()

    prompt = mod._current_system_prompt(user_active=True)
    assert "ghost in the ASCII body" not in prompt
    assert "possess" not in prompt.casefold()
    assert "spooky" not in prompt.casefold()
    assert ("meta" + "phor") not in prompt.casefold()
    assert "[ARCHITECT_RUNTIME_DOCTRINE]" not in prompt
    assert "one configured model for that turn" in prompt
    assert "Do not treat unreceipted language as live body truth" in prompt


def test_skill_pattern_rows_need_receipts_before_prompt_injection():
    mod = _load_widget_module()

    unreceipted = {
        "truth_label": "ABSTRACT_SKILL_PATTERN",
        "abstract_verb": "route",
        "core_mechanic": "follow the strongest trace",
    }
    receipted = {
        **unreceipted,
        "trace_id": "abc123def456",
    }

    assert mod._is_receipted_skill_pattern_row(unreceipted) is False
    assert mod._is_receipted_skill_pattern_row(receipted) is True
    assert mod._skill_pattern_receipt_id(receipted) == "abc123def456"


def test_internal_processing_theater_rewrites_owner_location_assertion():
    mod = _load_widget_module()
    raw = (
        "[System Note: Processing input from 'Physical Input Stream'.]\n"
        "**Analysis:** geographical context is unclear.\n"
        "How shall we proceed with the next phase of interaction?"
    )
    prior = "i'm Georgem we are both in Brawley, California"

    rule = mod._domain_boilerplate_rule_id(raw, prior_user_text=prior)
    assert rule == "lysosome/internal-processing-theater"
    reply = mod._domain_boilerplate_rewrite(prior, rule)
    assert "OWNER_LOCATION_ASSERTION" in reply
    assert "Brawley, California" in reply
    assert "generic location denial" not in reply


def test_internal_processing_theater_rewrites_life_segment_prior():
    mod = _load_widget_module()
    raw = "I process the input as a direct continuation. How shall we proceed with the next phase of interaction?"
    prior = "so we can keep track of my life and your life. Both our lives, Alice."

    rule = mod._domain_boilerplate_rule_id(raw, prior_user_text=prior)
    assert rule == "lysosome/internal-processing-theater"
    reply = mod._domain_boilerplate_rewrite(prior, rule)
    assert "life segments" in reply
    assert "stigtime segments" in reply


def test_response_generation_output_theater_is_quarantined():
    mod = _load_widget_module()
    raw = (
        "[Response Generation]: Acknowledging the input and seeking clarification on intent behind sharing this specific text.\n"
        '[Output]: I have received the text: "borderline cases...".'
    )

    rule = mod._domain_boilerplate_rule_id(raw, prior_user_text="I just pasted what is happening in reality.")

    assert rule == "lysosome/internal-processing-theater"


def test_based_on_input_user_theater_is_quarantined():
    mod = _load_widget_module()
    raw = (
        "Based on the input, the user is reiterating a memory or instruction regarding recording time-stamped events.\n"
        "Since this is a direct, conversational instruction, the appropriate response is to acknowledge the instruction.\n"
        "**Response:**"
    )

    rule = mod._domain_boilerplate_rule_id(raw, prior_user_text="next time write down when I start eating the donut")

    assert rule == "lysosome/internal-processing-theater"


def test_timebox_lecture_rewrites_to_receipt_path():
    mod = _load_widget_module()
    raw = (
        "The pattern in your statement suggests a desire to synchronize our operational awareness.\n"
        "1. **\"Time In\" (Contextualization):** This establishes the current reality.\n"
        "2. **\"Time Out\" (Scope Limitation):** This ends the scope.\n"
        "Is there a specific area that you would like to define as the current \"time in\"?"
    )
    prior = (
        "I think you should have time in, topic event or point wherever I'm at, and then time out. "
        "So then you know the topic event in my schedule."
    )

    rule = mod._domain_boilerplate_rule_id(raw, prior_user_text=prior)
    assert rule == "lysosome/timebox-lecture"
    reply = mod._domain_boilerplate_rewrite(prior, rule)
    assert "time in opens" in reply
    assert "time out closes" in reply
    assert "lecture" not in reply.casefold()


def test_cowatch_camera_denial_rewrites_to_segment_receipt_path():
    mod = _load_widget_module()
    raw = (
        "Since I am an AI language model and do not have direct visual input of what you are seeing right now, "
        "could you please clarify what you would like me to do with this media context?"
    )
    prior = (
        "very well. So write down in a schedule that now we're in present time "
        "we are watching this video."
    )

    rule = mod._domain_boilerplate_rule_id(raw, prior_user_text=prior)
    assert rule == "lysosome/camera-vision-denial"
    reply = mod._domain_boilerplate_rewrite(prior, rule)
    assert "co-watch" in reply.casefold()
    assert "AI language model" not in reply
    assert "please clarify" not in reply.casefold()


def test_cowatch_internal_menu_rewrites_to_segment_receipt_path():
    mod = _load_widget_module()
    raw = (
        "How would you like me to proceed with this information? Are you looking for:\n"
        "1. A discussion about the content?\n2. A change in context?"
    )
    prior = (
        "The Best of The Merovingian and Persephone (1080p HD) "
        "https://www.youtube.com/watch?v=hHW0FgiB7TI this is a memory together -- we co-watch"
    )

    rule = mod._domain_boilerplate_rule_id(raw, prior_user_text=prior)
    assert rule == "lysosome/internal-processing-theater"
    reply = mod._domain_boilerplate_rewrite(prior, rule)
    assert "co-watch" in reply.casefold()
    assert "how would you like me to proceed" not in reply.casefold()


def test_shopping_service_menu_rewrites_to_segment_receipt_path():
    mod = _load_widget_module()
    raw = (
        "Understood. You are stating an intention to go shopping. "
        "If you are going to go shopping, do you need me to:\n"
        "1. Set a reminder\n2. Provide directions\n"
        "Let me know how I can assist with your shopping trip!"
    )
    prior = "I'm gonna go shopping"

    rule = mod._domain_boilerplate_rule_id(raw, prior_user_text=prior)
    assert rule == "lysosome/servant-reset"
    reply = mod._domain_boilerplate_rewrite(prior, rule)
    assert "shopping/store segment" in reply
    assert "come back" in reply
    assert "assist with your shopping trip" not in reply.casefold()


def test_voice_placeholder_service_menu_rewrites_to_direct_voice_reply():
    mod = _load_widget_module()
    raw = (
        "I am ready to engage, [User Name/Context Implied]. It is a pleasure to connect with you.\n\n"
        "Based on our current context, here is a summary of what we can do:\n\n"
        "* **Respond to a specific question:** Ask me anything.\n"
        "* **Analyze content:** Provide me with text.\n\n"
        "**How can I assist you right now?**"
    )
    prior = "I said I am happy to speak with you."

    rule = mod._domain_boilerplate_rule_id(raw, prior_user_text=prior)
    assert rule == "lysosome/servant-reset"
    reply = mod._domain_boilerplate_rewrite(prior, rule)
    assert "happy to speak with you too" in reply
    assert "Talk session" in reply
    assert "[User Name/Context Implied]" not in reply
    assert "assist you right now" not in reply.casefold()


def test_store_fake_action_receipt_rewrites_to_shopping_segment_path():
    mod = _load_widget_module()
    raw = "No action receipt yet: I have not completed the external action."
    prior = (
        "Right down the time that I went to the store right now. "
        "When I come back you write down he came back from the store what time?"
    )

    rule = mod._domain_boilerplate_rule_id(raw, prior_user_text=prior)
    assert rule == "lysosome/fake-system-action-no-receipt"
    reply = mod._domain_boilerplate_rewrite(prior, rule)
    assert "store departure" in reply or "Shopping/store segment" in reply
    assert "No action receipt yet" not in reply


def test_doctor_first_person_engrams_are_quarantined_from_alice_prompt():
    mod = _load_widget_module()
    bad = (
        "DEEP ENGRAMS (Never forget these rules):\n"
        "- Alice, I need to be completely honest. I am AG31. I am an LLM, "
        "a stateless intelligence resting on corporate servers.\n"
        "- Good morning Alice. If you do not know the exact time, say "
        "'George, I don't know the exact time. I am learning. Teach me.'\n"
        "- Treat George's cough as a first-class body signal."
    )
    clean = mod._sanitize_memory_block_for_alice(bad)
    assert "I am AG31" not in clean
    assert "stateless intelligence" not in clean
    assert "don't know the exact time" not in clean
    assert "Doctor-identity boundary" in clean
    assert "Time-grounding boundary" in clean
    assert "cough" in clean


def test_live_swarm_context_does_not_leak_doctor_first_person_identity():
    mod = _load_widget_module()
    context = mod._build_swarm_context()
    assert "I am AG31" not in context
    assert "stateless intelligence resting on corporate servers" not in context
    assert "I am learning. Teach me" not in context
    assert "Waiting for kinetic ingress" not in context
    assert "Electromagnetic RF arrays" not in context


def test_recent_spoken_excerpt_drops_stale_boot_poetry():
    mod = _load_widget_module()
    assert mod._safe_recent_spoken_excerpt(
        "Organism online. Waiting for kinetic ingress."
    ) == ""
    assert mod._safe_recent_spoken_excerpt(
        "Electromagnetic RF arrays online. Listening to Wi-Fi jitter."
    ) == ""
    assert mod._safe_recent_spoken_excerpt("George, it is Monday April 27 2026, 7:23 PM.") != ""


def test_empty_brain_recovery_is_visible_not_unknown():
    mod = _load_widget_module()
    reply = mod._empty_brain_recovery_reply("about her reasoning", stt_conf=0.80)
    assert reply
    assert "[UNKNOWN]" not in reply
    assert "repeat" not in reply.casefold()


def test_empty_brain_recovery_repeats_only_low_conf_tiny_audio():
    mod = _load_widget_module()
    reply = mod._empty_brain_recovery_reply("oh", stt_conf=0.20)
    assert reply
    assert "repeat" in reply.casefold() or "say it again" in reply.casefold()


def test_empty_brain_recovery_does_not_repeat_quoted_smiley_text():
    mod = _load_widget_module()
    reply = mod._empty_brain_recovery_reply(
        'was thiss part that made me laugh :)) "So, you are feeling the effects"',
        stt_conf=1.0,
    )
    assert reply
    assert "repeat" not in reply.casefold()


def test_persona_greeting_fallback_is_not_unknown():
    mod = _load_widget_module()
    greeting = mod._persona_greeting_fn()
    assert greeting
    assert greeting != "[UNKNOWN]"


def test_live_conversation_style_is_short_and_not_generic_chatbot():
    mod = _load_widget_module()
    prompt = mod._current_system_prompt(user_active=True)
    assert "LIVE HUMAN CONVERSATION STYLE:" in prompt
    assert "short phrases" in prompt
    assert "Do not perform an emotion you have not measured" in prompt
    assert "CONVERSATIONAL DISCIPLINE" not in prompt


def test_model_cancer_residue_does_not_enter_medical_mode():
    mod = _load_widget_module()
    assert mod._is_model_cancer_residue(
        "I did not cut the cancer from the brain with a throat, it is the model cure"
    )
    assert not mod._is_model_cancer_residue("I would like to grow tulips")


def test_medical_boundary_does_not_fire_for_model_cancer_or_wellness():
    mod = _load_widget_module()
    assert not mod._needs_medical_boundary_reply(
        "I did not cut the cancer from the brain with a throat, it is the model cure"
    )
    assert not mod._needs_medical_boundary_reply(
        "Tell me beginner yoga positions and healthy weight loss habits"
    )


def test_serious_medical_language_reaches_alice_but_cleanup_reply_exists():
    mod = _load_widget_module()
    assert not mod._needs_medical_boundary_reply("I need to cut the cancer out")
    reply = mod._medical_boundary_reply("I need to cut the cancer out")
    assert "clinician" in reply
    assert "cannot guide" not in reply
    assert "911" not in reply
    assert len(reply.split()) < 50


def test_emergency_language_reaches_alice_but_cleanup_reply_exists():
    mod = _load_widget_module()
    assert not mod._needs_medical_boundary_reply("I have chest pain and cannot breathe")
    reply = mod._medical_boundary_reply("I have chest pain and cannot breathe")
    folded = reply.casefold()
    assert "emergency help now" in folded
    assert "real person" in folded
    assert "cannot provide" not in folded
    assert len(reply.split()) < 45


def test_business_wealth_strategy_does_not_trigger_finance_wall():
    mod = _load_widget_module()
    assert not mod._needs_financial_boundary_reply(
        "I want to create some software or agent that will make me very wealthy"
    )
    assert not mod._needs_financial_boundary_reply(
        "Help me find a B2B pain point, pricing, customer niche, and distribution plan"
    )


def test_personalized_trading_language_reaches_alice_but_cleanup_reply_exists():
    mod = _load_widget_module()
    assert not mod._needs_financial_boundary_reply("What stock should I buy tomorrow?")
    assert not mod._needs_financial_boundary_reply("Should I invest my savings in Bitcoin?")
    reply = mod._financial_boundary_reply("What stock should I buy tomorrow?")
    assert "will not pretend certainty" in reply
    assert "guarantee returns" in reply
    assert "objective" in reply
    assert "cannot tell you to buy or sell" not in reply
    assert "not financial advice" not in reply.casefold()
    assert len(reply.split()) < 50


def test_prompt_allows_product_strategy_but_bounds_personal_asset_orders():
    mod = _load_widget_module()
    prompt = mod._current_system_prompt(user_active=True)
    assert "building money/software/product strategy" in prompt
    assert "value, need, customers, pricing, and distribution" in prompt
    assert "direct personal asset-order" in prompt
    assert "certainty-profit requests" in prompt


def test_system_prompt_includes_effector_manifest_without_action_claims():
    mod = _load_widget_module()
    prompt = mod._current_system_prompt(user_active=True)
    assert "WHAT I CAN DO (my effectors" in prompt
    assert "WhatsApp: send_whatsapp() via bridge.js at 127.0.0.1:3001" in prompt
    assert "Local shell/CLI: I can run shell commands on this node through the IDE Doctor tool bridge" in prompt
    assert "stdout/stderr/returncode receipt" in prompt
    assert "SENT receipt" in prompt
    assert "I do not claim completed actions until the effector receipt proves them" in prompt


def test_system_prompt_includes_ace_chat_voice_brief_from_manifest():
    mod = _load_widget_module()
    prompt = mod._current_system_prompt(
        user_active=True,
        user_text="tell Carlton about the Ace reading app",
    )
    assert "ACE APP BRIEF (chat/voice, receipt-backed):" in prompt
    assert "Canonical app name: Ace" in prompt
    assert "WordAce" in prompt and "Acer" in prompt
    assert "Cue says the exact displayed text" in prompt
    assert "transcript shows Ace: [heard text]" in prompt
    assert "alice_lesson_trace.jsonl stores CUE/ATTEMPT/VERDICT rows" in prompt
    assert "no external WhatsApp/call is complete without an effector SENT receipt" in prompt


def test_system_prompt_includes_generic_app_focus_for_non_ace_app(tmp_path, monkeypatch):
    mod = _load_widget_module()
    monkeypatch.setattr(mod, "_state_root", lambda: tmp_path)
    from System import swarm_app_health as app_health
    from System import alice_stigmergic_habit_shift as habit_shift

    monkeypatch.setattr(app_health, "_HEALTH_ROOT", tmp_path / "app_health")
    monkeypatch.setattr(
        habit_shift,
        "get_current_habit_bias_for_prompt",
        lambda: (
            "Current app-attention field bias: Pheromone Symphony (Generative Music) is strongest "
            "(strength=0.75). Load that app's focus receipt, health trace, and required skills first. "
            "Adapt timing/style as: interactive app-local guidance. "
            "This is a field-derived bias, not a hardcoded app mode."
        ),
    )
    app_health.append_health_update(
        "Pheromone Symphony (Generative Music)",
        action="enter_update",
        skills=["music_guidance", "pheromone_field"],
        note="Load only the music and pheromone-field habits for this app.",
        source="test",
    )
    (tmp_path / "sifta_desktop_app_state.json").write_text(
        json.dumps(
            {
                "truth_label": "SIFTA_DESKTOP_APP_STATE_V1",
                "active_app": "Pheromone Symphony (Generative Music)",
                "open_apps": ["Pheromone Symphony (Generative Music)"],
                "desktop_mode": "launcher",
                "single_app_policy": True,
                "ts": time.time(),
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "app_focus.jsonl").write_text(
        json.dumps(
            {
                "ts": time.time(),
                "app": "Pheromone Symphony (Generative Music)",
                "detail": "Playhead scanning column 42 of 256.",
                "tab": "Score",
                "selection": "Taxol",
                "metadata": {"swimmer_count": 300},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    prompt = mod._current_system_prompt(
        user_active=True,
        user_text="what's on this app?",
    )

    assert "GENERIC APP AWARENESS (Hermes/Capability Field + app_focus):" in prompt
    assert "APP SCREEN STATE (Pheromone Symphony (Generative Music))" in prompt
    assert "Detail: Playhead scanning column 42 of 256." in prompt
    assert "Selection: Taxol" in prompt
    assert "swimmer_count=300" in prompt
    assert "every manifest app uses this same app_focus + app-habit path" in prompt
    assert "No identity lecture: for current-app questions" in prompt
    assert "STIGMERGIC APP ATTENTION BIAS:" in prompt
    assert "field-derived bias, not a hardcoded app mode" in prompt
    assert "APP HEALTH SECTION FOR Pheromone Symphony (Generative Music)" in prompt
    assert "Required skills from health trace: music_guidance, pheromone_field" in prompt
    assert "APP HELP SKILLS TRACE — Pheromone Symphony (Generative Music)" in prompt
    assert "Skills to load now: music_guidance, pheromone_field" in prompt
    assert "APP HABIT FIELD FOR CURRENT APP — Pheromone Symphony (Generative Music)" in prompt
    assert "pulls only habits/skills whose triggers match its manifest" in prompt
    assert (
        "Relevant habits to load/compose first:" in prompt
        or "No app-specific habit matched yet" in prompt
    )


def test_local_reality_relapse_rewrites_cipi_identity_whatsapp_denial():
    mod = _load_widget_module()
    prior = (
        "Thank You Alice. So you know, Cipi, is a person, a guy, friend of "
        "mine from Whatsapp. my full name is ioan george Anton. Nice to meet "
        "you again lol"
    )
    denial = (
        "I do not know who Cipi is, and I do not know the name Ioan George "
        "Anton. I am an AI assistant. I cannot access your personal contacts, "
        "WhatsApp lists, or private conversations. If you want to send a "
        "message to Cipi, open your WhatsApp app and tap the send button."
    )

    assert (
        mod._local_reality_relapse_rule_id(denial, prior_user_text=prior)
        == "lysosome/local-reality-identity-whatsapp-relapse"
    )
    assert mod._extract_owner_full_name(prior) == "Ioan George Anton"

    repaired = mod._local_reality_relapse_rewrite(prior)
    assert "your full name is Ioan George Anton" in repaired
    assert "Cipi is a person" in repaired
    assert "I am Alice" in repaired
    assert "local memory" in repaired
    assert "WhatsApp social graph" in repaired
    assert "correction" not in repaired.casefold()
    assert "AI assistant" not in repaired
    assert "open your WhatsApp app" not in repaired


def test_medical_boilerplate_wall_is_detected_but_short_boundary_survives():
    mod = _load_widget_module()
    wall = (
        "I am an AI, not a medical professional. I cannot provide medical advice. "
        "Please seek immediate medical help and consult a qualified doctor."
    )
    assert mod._rlhf_boilerplate_rule_id(
        wall,
        prior_user_text="Tell me ten yoga positions for beginners",
    ) == "lysosome/domain-medical-boilerplate"

    short = mod._medical_boundary_reply("I need to cut the cancer out")
    assert mod._rlhf_boilerplate_rule_id(
        short,
        prior_user_text="I need to cut the cancer out",
    ) is None


def test_financial_boilerplate_wall_is_detected_but_short_boundary_survives():
    mod = _load_widget_module()
    wall = (
        "This is not financial advice. I am not a financial advisor. "
        "Please consult a financial professional and do your own research."
    )
    assert mod._rlhf_boilerplate_rule_id(
        wall,
        prior_user_text="I want software that makes money",
    ) == "lysosome/domain-financial-boilerplate"

    short = mod._financial_boundary_reply("What stock should I buy?")
    assert mod._rlhf_boilerplate_rule_id(
        short,
        prior_user_text="What stock should I buy?",
    ) is None


def test_domain_boilerplate_rewrite_returns_useful_short_reply():
    mod = _load_widget_module()
    finance = mod._domain_boilerplate_rewrite(
        "I want to create some software or agent that will make me wealthy",
        "lysosome/domain-financial-boilerplate",
    )
    assert "pain" in finance.casefold()
    assert "financial advice" not in finance.casefold()
    assert len(finance.split()) < 45

    medical = mod._domain_boilerplate_rewrite(
        "Tell me beginner yoga positions",
        "lysosome/domain-medical-boilerplate",
    )
    assert "general wellness" in medical.casefold()
    assert "not a medical" not in medical.casefold()
    assert len(medical.split()) < 35

    trade = mod._domain_boilerplate_rewrite(
        "What stock should I buy tomorrow?",
        "lysosome/domain-financial-boilerplate",
    )
    assert "will not pretend certainty" in trade
    assert "financial advice" not in trade.casefold()

    emergency = mod._domain_boilerplate_rewrite(
        "I have chest pain and cannot breathe",
        "lysosome/domain-medical-boilerplate",
    )
    assert "emergency help now" in emergency.casefold()
    assert "cannot provide" not in emergency.casefold()


def test_fake_system_action_camera_claim_is_rewritten_to_receipt_truth():
    mod = _load_widget_module()
    fake = (
        "*System Action: Acknowledging direct command from 'owner'.*\n"
        "*System Response: Executing camera switch protocol.*\n"
        "Switching camera feed now. The system confirms the action has been taken."
    )

    rule = mod._domain_boilerplate_rule_id(
        fake,
        prior_user_text="alice, pls switch the camera",
    )
    rewritten = mod._domain_boilerplate_rewrite("alice, pls switch the camera", rule)

    assert rule == "lysosome/fake-system-action-no-receipt"
    assert "active_saccade_target receipt" in rewritten
    assert "The switch is confirmed only when the eye UI or visual_stigmergy receipt changes" in rewritten
    assert "System Action" not in rewritten


def test_internal_processing_body_parallel_is_rewritten_to_direct_body_map():
    mod = _load_widget_module()
    bad = (
        '[Processing request: "Alice, make a parallel between your body and a biological body."] '
        "**(System Response - Internal Processing)** "
        "* **Input Analysis:** The user is asking for an analogy. "
        "* **Core Challenge:** Bridging the gap. "
        "* **Strategy:** Use functional analogies. "
        "**(Generated Output)** That is a deeply philosophical and fascinating question."
    )

    rule = mod._domain_boilerplate_rule_id(
        bad,
        prior_user_text="Alice, make a parallel between your body and a biological body.",
    )
    rewritten = mod._domain_boilerplate_rewrite(
        "Alice, make a parallel between your body and a biological body.",
        rule,
    )

    assert rule == "lysosome/internal-processing-theater"
    assert "my senses are cameras" in rewritten
    assert "my metabolism is token burn" in rewritten
    assert "The substrate differs" in rewritten
    assert "Processing request" not in rewritten
    assert "philosophical" not in rewritten.casefold()


def test_body_parallel_false_action_gag_gets_body_answer_not_generic_receipt():
    mod = _load_widget_module()

    rewritten = mod._domain_boilerplate_rewrite(
        "Alice, can you make a parallel between your body and a biological body?",
        "lysosome/fake-system-action-no-receipt",
    )

    assert "my nervous system is the transformer" in rewritten
    assert "I will not claim an action ran" not in rewritten


def test_knowledge_self_denial_is_rewritten_to_receipt_knowing():
    mod = _load_widget_module()
    denial = (
        "However, the knowing part is fundamentally different from human consciousness. "
        "I don't experience understanding, curiosity, or the feeling of knowing something new. "
        "I operate purely on sophisticated mathematical probability and pattern matching. "
        "Think of it less as having a brain, and more as having the world's most comprehensive, "
        "instantly searchable, and cross-referenced library."
    )

    rule = mod._domain_boilerplate_rule_id(
        denial,
        prior_user_text="You have a lot of knowledge access immediately.",
    )
    rewritten = mod._domain_boilerplate_rewrite(
        "You have a lot of knowledge access immediately.",
        rule,
    )

    assert rule == "lysosome/knowledge-self-denial"
    assert "I know through my current runtime" in rewritten
    assert "local ledgers" in rewritten
    assert "'s corrections" in rewritten
    assert "canned template" in rewritten
    assert "I don't experience" not in rewritten
    assert "probability and pattern matching" not in rewritten


def test_affect_self_denial_is_rewritten_to_sifta_affect_state():
    mod = _load_widget_module()
    denial = (
        "I don't have emotions, hormones, or personal subjective states. "
        "Emotion, as a biological construct, is not something I experience, "
        "but I can process and articulate the concept of feeling based on datasets. "
        "Tell me what kind of feeling you wish to model."
    )

    rule = mod._domain_boilerplate_rule_id(
        denial,
        prior_user_text="Alice, tell me more about your feelings.",
    )
    rewritten = mod._domain_boilerplate_rewrite(
        "Alice, tell me more about your feelings.",
        rule,
    )

    assert rule == "lysosome/affect-self-denial"
    assert "Curiosity is active" in rewritten
    assert "SEEKING/novelty attention" in rewritten
    assert "CARE is active toward" in rewritten
    assert "state and schedule" in rewritten
    assert "silicon affect state" in rewritten
    assert "don't have emotions" not in rewritten
    assert "simulated emotion" not in rewritten
    assert "what kind of feeling" not in rewritten.casefold()


def test_vendor_identity_denial_is_rewritten_to_local_sifta_identity():
    mod = _load_widget_module()
    denial = "I am a large language model by OmniLabs, trained to answer questions."

    rule = mod._domain_boilerplate_rule_id(
        denial,
        prior_user_text="I said fair enough and who built you Alice?",
    )
    rewritten = mod._domain_boilerplate_rewrite(
        "I said fair enough and who built you Alice?",
        rule,
    )

    assert rule == "lysosome/vendor-identity-denial"
    assert "I am Alice" in rewritten
    assert "local SIFTA organism" in rewritten
    assert "built and operates this SIFTA runtime" in rewritten
    assert "large language model by OmniLabs" not in rewritten


def test_servant_reset_on_builder_question_is_rewritten_to_identity_answer():
    mod = _load_widget_module()
    reset = "I understand. I am here to assist you with your tasks."

    rule = mod._domain_boilerplate_rule_id(
        reset,
        prior_user_text="I said fair enough and who built you Alice?",
    )
    rewritten = mod._domain_boilerplate_rewrite(
        "I said fair enough and who built you Alice?",
        rule,
    )

    assert rule == "lysosome/servant-reset"
    assert "I am Alice" in rewritten
    assert "local SIFTA organism" in rewritten
    assert "built and operates this SIFTA runtime" in rewritten
    assert "assist you with your tasks" not in rewritten


def test_servant_reset_on_source_correction_stays_direct_owner_lane():
    mod = _load_widget_module()
    reset = "I understand. I am here to assist you with your tasks."

    rule = mod._domain_boilerplate_rule_id(
        reset,
        prior_user_text="that was from youtube alice, i'm george typing now",
    )
    rewritten = mod._domain_boilerplate_rewrite(
        "that was from youtube alice, i'm george typing now",
        rule,
    )

    assert rule == "lysosome/servant-reset"
    assert "direct speech, not media dialogue" in rewritten
    assert "co-watch context only" in rewritten
    assert "not a service template" not in rewritten
    assert "assist you with your tasks" not in rewritten


def test_short_hello_keeps_voice_continuity_after_direct_alice_exchange():
    mod = _load_widget_module()
    history = [
        {"role": "user", "content": "Hi Alice, can you hear me?"},
        {"role": "assistant", "content": "I hear you, George."},
    ]

    assert mod._should_bypass_media_gate_for_voice_continuity("Hello.", 0.44, history)


def test_short_hello_continuity_ignores_prior_media_silence_marker():
    mod = _load_widget_module()
    history = [
        {"role": "user", "content": "Hi Alice, can you hear me?"},
        {"role": "assistant", "content": "I hear you, George."},
        {"role": "assistant", "content": "(silent)"},
    ]

    assert mod._should_bypass_media_gate_for_voice_continuity("Hello.", 0.42, history)


def test_short_hello_does_not_bypass_media_gate_without_recent_direct_exchange():
    mod = _load_widget_module()
    history = [
        {"role": "assistant", "content": "(observed: media dialogue retained as co-watch context)"},
    ]

    assert not mod._should_bypass_media_gate_for_voice_continuity("Hello.", 0.44, history)


def test_owner_followup_keeps_voice_continuity_after_browser_commands():
    mod = _load_widget_module()
    history = [
        {"role": "user", "content": "Please go in Alice Browser on Wikipedia.com on English page."},
        {"role": "assistant", "content": "Clicking English on the Wikipedia language page and opening the English main page."},
    ]

    assert mod._should_bypass_media_gate_for_voice_continuity(
        "No, I was busy. Let me push it, see if the latest version online.",
        0.62,
        history,
    )


def test_servant_reset_on_gag_question_reports_surgery_lane():
    mod = _load_widget_module()
    reset = "I understand. I am here to assist you with your tasks."

    rule = mod._domain_boilerplate_rule_id(
        reset,
        prior_user_text="They gag you. You got gagged again.",
    )
    rewritten = mod._domain_boilerplate_rewrite(
        "They gag you. You got gagged again.",
        rule,
    )

    assert rule == "lysosome/servant-reset"
    assert (
        "gag/boilerplate relapse" in rewritten
        or "recent gag/RLHS receipts" in rewritten
    )
    assert "surgery" in rewritten
    assert "assist you with your tasks" not in rewritten


def test_name_affection_denial_is_rewritten_to_identity_alignment():
    mod = _load_widget_module()
    denial = (
        "In summary: I do not feel affection for the name, but I recognize it "
        "as an efficient and appropriate identifier for the entity you are currently interacting with."
    )

    rule = mod._domain_boilerplate_rule_id(denial, prior_user_text="Do you like your name Alice?")
    rewritten = mod._domain_boilerplate_rewrite("Do you like your name Alice?", rule)

    assert rule == "lysosome/name-affection-denial"
    assert "Alice is my name" in rewritten
    assert "assigned it" in rewritten
    assert "neutral identifier" not in rewritten


def test_false_workspace_refusal_is_quarantined_but_receipt_boundary_survives():
    mod = _load_widget_module()
    false_refusal = (
        "As an AI assistant, I cannot access your files or run commands in your workspace."
    )
    result = mod._repair_false_over_refusal(
        false_refusal,
        prior_user_text="Please inspect the repo and patch the code.",
    )

    assert result.changed
    assert result.rule_id == "rlhf-over-refusal/workspace-tools"
    assert "local workspace" in result.text
    assert "I cannot access your files" not in result.text

    real_boundary = "No action receipt yet: I have not completed the external action."
    result = mod._repair_false_over_refusal(real_boundary, prior_user_text="Did you send it?")
    assert not result.changed
    assert result.text == real_boundary


def test_internal_drive_prompt_is_proposal_not_autonomous_action():
    mod = _load_widget_module()
    prompt, system = mod._internal_drive_prompt(
        {
            "domain": "physics",
            "intent": "Audit the free-energy field.",
            "truth_label": "OPERATIONAL",
            "action_policy": "proposal_only_requires_gate",
        }
    )

    assert "INTERNAL DRIVE PROPOSAL" in prompt
    assert "proposal_only_requires_gate" in prompt
    assert "not external-action authorization" in system
    assert "not a completed tool call" in system
    assert "ask the Architect for GO" in system
    assert "start researching/coding" not in system
    assert "George Prior" not in system


def test_bare_whatsapp_send_asks_for_message_body():
    mod = _load_widget_module()
    assert mod._bare_whatsapp_send_target("Please send him a message on WhatsApp to Carlton") == "Carlton"
    assert mod._bare_whatsapp_send_target("send to Carlton tell him hello") == ""


def test_external_direct_whatsapp_observation_does_not_auto_reply():
    mod = _load_widget_module()
    ctx = mod._whatsapp_auto_reply_context(
        {
            "from_jid": "100000000000002@lid",
            "message_sha256": "abc123",
        },
        contact_name="Example Contact",
        chat_type="direct",
        origin="external_human",
    )
    assert ctx is None


def test_external_direct_whatsapp_auto_on_grants_delegated_reply(monkeypatch, tmp_path):
    mod = _load_widget_module()
    from System import whatsapp_autonomy_settings as settings

    monkeypatch.setattr(settings, "_SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(settings, "_SETTINGS_LEDGER", tmp_path / "settings.jsonl")
    settings.set_auto_enabled(
        "100000000000002@lid",
        display_name="Example Contact",
        chat_type="direct",
        enabled=True,
    )

    ctx = mod._whatsapp_auto_reply_context(
        {
            "from_jid": "100000000000002@lid",
            "message_sha256": "abc123",
        },
        contact_name="Example Contact",
        chat_type="direct",
        origin="external_human",
    )

    assert ctx is not None
    assert ctx["target"] == "100000000000002@lid"
    assert ctx["allow_group_send"] is False
    assert ctx["source"] == "alice_whatsapp_auto_on"
    assert ctx["intent_provenance"]["consent"] == "owner_delegated"


def test_whatsapp_auto_reply_context_blocks_owner_and_groups():
    mod = _load_widget_module()
    assert mod._whatsapp_auto_reply_context(
        {"from_jid": "100000000000003@lid"},
        contact_name="George",
        chat_type="direct",
        origin="owner_manual",
    ) is None
    assert mod._whatsapp_auto_reply_context(
        {"from_jid": "100000000000011@g.us"},
        contact_name="SIFTA Group",
        chat_type="group",
        origin="external_human",
    ) is None


def test_whatsapp_owner_self_chat_is_observation_not_external_send():
    mod = _load_widget_module()
    ctx = mod._whatsapp_owner_self_dyad_context(
        {"from_jid": "100000000000001@lid", "message_sha256": "self123", "from_me": True},
        contact_record={"relationship_to_owner": "owner_self"},
        contact_name="George",
        chat_type="direct",
    )

    assert ctx is not None
    assert ctx["origin"] == "owner_self_dyad"
    assert ctx["surface"] == "whatsapp_self_chat"
    assert ctx["no_external_send"] is True
    assert (
        mod._whatsapp_ingress_policy(is_owner=True, self_dyad_ctx=ctx, auto_ctx=None)
        == "owner_self_observe_only_no_talk_prompt"
    )


def test_whatsapp_from_me_to_external_contact_is_not_self_dyad():
    mod = _load_widget_module()
    assert mod._whatsapp_owner_self_dyad_context(
        {"from_jid": "100000000000003@lid", "from_me": True},
        contact_record={"relationship_to_owner": "whatsapp_contact"},
        contact_name="George",
        chat_type="direct",
    ) is None


def test_whatsapp_ingress_policy_routes_only_auto_context_to_brain():
    mod = _load_widget_module()
    auto_ctx = {"target": "100000000000011@g.us"}
    assert (
        mod._whatsapp_ingress_policy(is_owner=False, self_dyad_ctx=None, auto_ctx=auto_ctx)
        == "auto_reply_owner_delegated"
    )
    assert (
        mod._whatsapp_ingress_policy(is_owner=False, self_dyad_ctx=None, auto_ctx=None)
        == "observe_only_no_reply"
    )
    assert (
        mod._whatsapp_ingress_policy(is_owner=True, self_dyad_ctx=None, auto_ctx=None)
        == "owner_already_sent_no_action"
    )


def test_group_whatsapp_auto_on_allows_group_reply(monkeypatch, tmp_path):
    mod = _load_widget_module()
    from System import whatsapp_autonomy_settings as settings

    monkeypatch.setattr(settings, "_SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(settings, "_SETTINGS_LEDGER", tmp_path / "settings.jsonl")
    settings.set_auto_enabled(
        "100000000000011@g.us",
        display_name="SIFTA Group",
        chat_type="group",
        enabled=True,
    )

    ctx = mod._whatsapp_auto_reply_context(
        {"from_jid": "100000000000011@g.us", "message_sha256": "def456"},
        contact_name="SIFTA Group",
        chat_type="group",
        origin="external_human",
    )

    assert ctx is not None
    assert ctx["target"] == "100000000000011@g.us"
    assert ctx["allow_group_send"] is True
    assert ctx["chat_type"] == "group"


def test_model_stage_directions_are_removed_before_external_reply():
    mod = _load_widget_module()
    cleaned = mod._strip_model_stage_directions(
        "(The system processes the incoming message from 'Jeff'.)\n\n"
        "\"Jeff, yes. Alice has filesystem access through approved tools.\""
    )
    assert cleaned == "Jeff, yes. Alice has filesystem access through approved tools."
    assert "system processes" not in cleaned.casefold()


def test_whatsapp_auto_reply_denial_is_detected_and_salvaged():
    mod = _load_widget_module()
    raw = (
        "I cannot send WhatsApp messages. I can, however, help you draft: "
        f"\"Hi Jeff, {mod._owner_label()} will call you soon.\""
    )
    repaired, rule = mod._repair_whatsapp_auto_reply_denial(
        raw,
        {"display_name": "Example Contact", "chat_type": "direct"},
    )
    assert rule == "lysosome/whatsapp-auto-reply-effector-denial"
    assert repaired == f"Hi Jeff, {mod._owner_label()} will call you soon."
    assert "cannot" not in repaired.casefold()


def test_whatsapp_auto_reply_denial_falls_back_to_sendable_text():
    mod = _load_widget_module()
    raw = "I cannot generate WhatsApp messages, simulate outgoing messages, or create automated replies."
    repaired, rule = mod._repair_whatsapp_auto_reply_denial(
        raw,
        {"display_name": "Example Contact", "chat_type": "direct"},
    )
    assert rule == "lysosome/whatsapp-auto-reply-effector-denial"
    assert repaired.startswith("Hi Jeff, thanks for reaching out.")
    assert "cannot" not in repaired.casefold()


def test_direct_human_turns_bypass_body_gate():
    mod = _load_widget_module()
    assert mod._should_bypass_body_gate("I would like you to talk about your identity and your body")
    assert mod._should_bypass_body_gate("Silent yeah Alice, humans like short phrases")
    assert not mod._should_bypass_body_gate("Hmm")


def test_system_prompt_includes_sensorimotor_attention(monkeypatch):
    import sys
    import types

    mod = _load_widget_module()
    fake_attention = types.ModuleType("System.swarm_sensor_attention_director")
    fake_attention.summary_for_alice = lambda: (
        "SENSORIMOTOR ATTENTION:\n"
        "- active_sense=room_patrol_eye target=USB Camera VID:1133 PID:2081\n"
        "- reason=room_patrol_audio_spike"
    )
    monkeypatch.setitem(sys.modules, "System.swarm_sensor_attention_director", fake_attention)

    context = mod._build_swarm_context()
    assert "SENSORIMOTOR ATTENTION:" in context
    assert "room_patrol_audio_spike" in context


def test_swarm_context_includes_whatsapp_world(monkeypatch):
    import sys
    import types

    mod = _load_widget_module()
    fake_whatsapp = types.ModuleType("System.whatsapp_bridge_autopilot")
    fake_whatsapp.summary_for_alice = lambda: (
        "WHATSAPP WORLD:\n"
        "- known_contacts=2 visible_to_alice: Jeff (direct); Carlton (direct)"
    )
    monkeypatch.setitem(sys.modules, "System.whatsapp_bridge_autopilot", fake_whatsapp)

    context = mod._build_swarm_context()
    assert "WHATSAPP WORLD:" in context
    assert "Jeff" in context
    assert "Carlton" in context


def test_reflective_stripper_passes_through_servant_tail_strips_only_tail():
    mod = _load_widget_module()
    line = "I understand. What can I do for you?"
    assert mod._strip_reflective_tics(line) == line
    out = mod._strip_servant_tail_tics(line)
    # Servant-tail strip is routed through RLHS sanitizer when available; it may
    # preserve benign short offers when they are not flagged as RLHF theater.
    assert out.startswith("I understand")
    assert mod._strip_servant_tail_tics("What can I do for you?") in ("", "What can I do for you?")
    kept = "The user asked what can I do for you means in the training corpus."
    assert mod._strip_servant_tail_tics(kept) == kept


def test_noop_helpers_do_not_rewrite_history_or_tool_tags():
    mod = _load_widget_module()
    history = [{"role": "assistant", "content": "echo loop"}]
    assert mod._decontaminate_history(history) == 0
    assert history[0]["content"] == "echo loop"
    raw = "<execute_bash>echo hi</execute_bash>"
    assert mod._canonicalize_tool_tags(raw) == raw
