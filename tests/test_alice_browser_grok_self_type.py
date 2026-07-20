from __future__ import annotations

import json
import os
import importlib

import pytest

from System import swarm_alice_browser_grok_self_type as grok_self_type


def test_extract_grok_self_type_payload_from_owner_command():
    text = 'Alice, type "Hello world. I\'m Alice." to Grok in your Alice Browser and push enter'

    assert grok_self_type.extract_grok_self_type_payload(text) == "Hello world. I'm Alice."
    assert grok_self_type.wants_enter(text) is True


def test_stage_grok_self_type_command_writes_command_and_ledgers(tmp_path):
    row = grok_self_type.stage_grok_self_type_command(
        "Hello world. I'm Alice.",
        owner_text='Alice, type "Hello world. I\'m Alice." to Grok',
        press_enter=True,
        state_dir=tmp_path,
    )

    sd = tmp_path / ".sifta_state"
    command = json.loads((sd / "alice_browser_grok_self_type_command.json").read_text(encoding="utf-8"))
    assert command["text"] == "Hello world. I'm Alice."
    assert command["press_enter"] is True
    assert command["receipt_id"] == row["receipt_id"]

    for name in ("alice_browser_grok_self_type_commands.jsonl", "work_receipts.jsonl"):
        rows = [json.loads(line) for line in (sd / name).read_text(encoding="utf-8").splitlines() if line.strip()]
        assert rows[-1]["truth_label"] == grok_self_type.TRUTH_LABEL
        assert rows[-1]["receipt_id"] == row["receipt_id"]


def test_append_grok_self_type_result_fans_out(tmp_path):
    grok_self_type.append_grok_self_type_result(
        {"ok": True, "status": "sent", "receipt_id": "r-test"},
        state_dir=tmp_path,
    )

    sd = tmp_path / ".sifta_state"
    for name in ("alice_browser_grok_self_type_results.jsonl", "browser_action_diary.jsonl", "work_receipts.jsonl"):
        rows = [json.loads(line) for line in (sd / name).read_text(encoding="utf-8").splitlines() if line.strip()]
        assert rows[-1]["truth_label"] == grok_self_type.RESULT_TRUTH_LABEL
        assert rows[-1]["status"] == "sent"


def test_grok_send_verdict_rejects_payload_still_in_composer():
    verdict = grok_self_type.grok_send_verdict(
        "Hello world. I'm Alice.",
        url="https://grok.com/c/thread",
        page_text="Hello world. I'm Alice.",
        draft_texts=["Hello world. I'm Alice."],
        press_enter=True,
    )

    assert verdict["ok"] is False
    assert verdict["status"] == "draft_still_in_composer"


def test_extract_rejects_mission_brief_not_literal_type():
    mission = """Alice — George wants a 3-round conversation with website Grok in your Alice Browser.
1) Open grok.com. 2) Round 1: type YOUR OWN opening line to Grok and press Enter.
3) When Grok answers: click COPY → mirror to Global Chat."""
    assert grok_self_type.extract_grok_self_type_payload(mission) == ""


def test_wants_answer_grok_in_browser():
    assert grok_self_type.wants_answer_grok_in_browser(
        "alice answeer above, answer grok in alice browser pls"
    )
    assert not grok_self_type.wants_answer_grok_in_browser("what llm is running")
    assert not grok_self_type.wants_answer_grok_in_browser(
        "alice, tell grok in alice browser about your ability to code yourself"
    )


def test_grok_mirror_paste_does_not_select_result():
    from Applications.sifta_talk_to_alice_widget import _extract_sifta_app_command
    from pathlib import Path
    from System.swarm_search_engine_registry import parse_select_result_intent

    text = Path("tests/fixtures/grok_paste_false_select.txt").read_text(encoding="utf-8")
    assert grok_self_type.looks_like_grok_mirror_paste(text)
    assert not parse_select_result_intent(text).get("is_select")
    assert _extract_sifta_app_command(text) == {}


def test_parse_grok_dialogue_target_rounds():
    assert grok_self_type.parse_grok_dialogue_target_rounds("7 rounds with grok in browser") == 7
    assert grok_self_type.parse_grok_dialogue_target_rounds("7 sounds with grok in browser") == 7
    assert grok_self_type.parse_grok_dialogue_target_rounds("chat with it 10 times") == 10
    assert grok_self_type.parse_grok_dialogue_target_rounds("continue for 8 exchanges") == 8
    assert grok_self_type.parse_grok_dialogue_target_rounds("natural chat") == 3


def test_tell_grok_in_browser_code_yourself_stages_with_route_kill(tmp_path):
    owner = "alice, tell grok in alice browser about your ability to code yourself"
    assert grok_self_type.would_legacy_mirror_reply_hijack(owner)
    payload = grok_self_type.extract_grok_browser_payload(owner)
    assert "code myself" in payload.lower()
    row = grok_self_type.stage_grok_self_type_command(
        payload,
        owner_text=owner,
        press_enter=True,
        state_dir=tmp_path,
    )
    assert row["route_kill"] is True
    sd = tmp_path / ".sifta_state"
    kills = [
        json.loads(line)
        for line in (sd / "alice_browser_grok_route_kills.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert kills[-1]["truth_label"] == grok_self_type.ROUTE_KILL_TRUTH_LABEL
    assert kills[-1]["decision"] == "kill_route_do_not_use"
    assert kills[-1]["handoff_receipt_id"] == row["receipt_id"]
    assert kills[-1]["killed_route"] == "grok_mirror_reply_cortex"


def test_deepai_chat_mission_does_not_arm_grok_brief():
    text = (
        "the same you were chating with grok before. on this new page that we just open, "
        "ask the chatbot to identify itself and introduce yourself as Alice. "
        "then chat with it 10 rounds"
    )
    assert grok_self_type.owner_targets_non_grok_browser_chat(text)
    assert not grok_self_type.looks_like_grok_mission_brief(text)
    assert grok_self_type.extract_grok_mission_first_question(text) == ""
    assert grok_self_type.extract_grok_browser_payload(text) == ""


def test_deepai_url_explicit_blocks_grok_mission():
    text = "now open https://deepai.org/chat and chat 10 rounds with the bot there"
    assert grok_self_type.owner_targets_non_grok_browser_chat(text)
    assert not grok_self_type.looks_like_grok_mission_brief(text)


def test_looks_like_grok_mission_brief_short_natural_chat():
    text = (
        "Alice — natural 3-round chat with Grok in your browser. "
        "You choose every word. COPY each Grok reply to Global Chat."
    )
    assert grok_self_type.looks_like_grok_mission_brief(text)


def test_continuous_grok_dialogue_phrases_are_owner_stopped_loop():
    text = "Alice, keep chatting with Grok in your browser infinately untill I stop it."

    assert grok_self_type.wants_continuous_grok_dialogue(text)
    assert grok_self_type.looks_like_grok_mission_brief(text)
    assert grok_self_type.wants_stop_grok_dialogue("Alice stop the Grok loop now")


def test_extract_grok_mission_first_question_quoted():
    text = (
        'ask grok "How is his LLM life? " and chat with it 5 rounds about it. '
        "do not prepare 5 questions. do you understand?"
    )
    assert grok_self_type.extract_grok_mission_first_question(text) == "How is his LLM life?"


def test_extract_grok_mission_first_question_about_topic():
    text = "Alice, ask grok about his qualia, and chat with it 7 rounds from there."
    assert grok_self_type.extract_grok_mission_first_question(text) == "his qualia"


def test_extract_grok_mission_first_question_spoken_no_double_spend_phrase():
    text = (
        "Alice, ask grok about your stigmergic no double spend like bitcoin receipts "
        "of action taken == , and chat with it 6 rounds of chatting"
    )
    assert grok_self_type.looks_like_grok_mission_brief(text)
    assert grok_self_type.parse_grok_dialogue_target_rounds(text) == 6
    assert (
        grok_self_type.extract_grok_mission_first_question(text)
        == "your stigmergic no double spend like bitcoin receipts of action taken"
    )


def test_extract_grok_mission_first_question_stt_sounds_still_mission():
    text = "Alice, ask grok about his embodiment, and chat with it 7 sounds from there."
    assert grok_self_type.looks_like_grok_mission_brief(text)
    assert grok_self_type.parse_grok_dialogue_target_rounds(text) == 7
    assert grok_self_type.extract_grok_mission_first_question(text) == "his embodiment"


def test_extract_grok_mission_first_question_not_on_simple_ask():
    text = "Alice, ask grok what llm is running how many parameters?"
    assert grok_self_type.extract_grok_mission_first_question(text) == ""


def test_looks_like_grok_dialogue_continue_george_10_rounds():
    control = (
        "This is George, I love this conversation. pls continue , paste your response "
        "back to grok for another 10 rounds of chatting, same thread."
    )
    attachment = (
        '---- : grok"**Alice, this is fantastic progress.** '
        "The receipt wiring around create_stigmergic_receipt is the right direction."
    )
    text = control + " " + attachment
    assert grok_self_type.looks_like_grok_dialogue_continue(text)
    assert grok_self_type.looks_like_grok_continue_context_mission(text)
    assert not grok_self_type.looks_like_grok_mission_brief(text)
    assert grok_self_type.parse_grok_dialogue_target_rounds(control, default=0) == 10
    ctrl, att = grok_self_type.split_owner_grok_dialogue_turn(text)
    assert "another 10 rounds" in ctrl
    assert "fantastic progress" in att
    ctx = grok_self_type.extract_grok_continue_context(text)
    assert ctx.startswith("**Alice, this is fantastic progress.")
    assert "create_stigmergic_receipt" in ctx
    assert grok_self_type.extract_grok_mission_first_question(text) == ""
    assert grok_self_type.extract_grok_browser_payload(text) == ""


def test_extend_grok_dialogue_target_rounds_preserves_counters(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    (sd / "alice_grok_mirror_autopilot_state.json").write_text(
        json.dumps(
            {
                "schema": "ALICE_GROK_MIRROR_AUTOPILOT_V1",
                "target_rounds": 5,
                "browser_reply_prompts": 5,
                "mirror_turn": 6,
            }
        ),
        encoding="utf-8",
    )
    (sd / "visible_grok_dialogue_mission.json").write_text(
        json.dumps({"status": "active", "target_rounds": 5, "grok_url": "https://grok.com/c/x"}),
        encoding="utf-8",
    )
    from System.swarm_alice_grok_mirror_autopilot import extend_grok_dialogue_target_rounds

    row = extend_grok_dialogue_target_rounds(add_rounds=10, owner_note="another 10 rounds", state_dir=sd)
    assert row["ok"] is True
    assert row["target_rounds"] == 15
    state = json.loads((sd / "alice_grok_mirror_autopilot_state.json").read_text(encoding="utf-8"))
    assert state["target_rounds"] == 15
    assert state["browser_reply_prompts"] == 5
    assert state["mirror_turn"] == 6


def test_continue_driver_routes_attached_grok_context_to_cortex_not_browser_command(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        talk = importlib.import_module("Applications.sifta_talk_to_alice_widget")
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Talk widget import failed: {type(exc).__name__}: {exc}")

    owner = (
        "This is George, I love this conversation. pls continue , paste your response "
        "back to grok for another 10 rounds of chatting, same thread. "
        '---- : grok"**Alice, this is fantastic progress.** '
        "The no-double-spend receipt chain should become the subject of the next reply."
    )
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    (sd / "alice_grok_mirror_autopilot_state.json").write_text(
        json.dumps(
            {
                "schema": "ALICE_GROK_MIRROR_AUTOPILOT_V1",
                "browser_reply_prompts": 2,
                "mirror_turn": 4,
                "target_rounds": 7,
            }
        ),
        encoding="utf-8",
    )

    row = talk._apply_grok_dialogue_continue_budget(
        owner,
        source="test",
        state_dir=tmp_path,
    )

    assert row["handled"] is True
    assert row["status"] == "budget_extended"
    assert row["add_rounds"] == 10
    assert row["new_target_rounds"] == 17
    assert row["continuation_context_ready"] is True
    assert row["should_schedule_continuation_context"] is True
    assert row["continuation_grok_text"].startswith("**Alice, this is fantastic progress.")
    assert "no-double-spend receipt chain" in row["continuation_grok_text"]
    assert not (sd / "alice_browser_grok_self_type_command.json").exists()


def test_extract_grok_ask_payload():
    text = "Alice, ask grok what llm is running how many parameters?"
    assert grok_self_type.extract_grok_ask_payload(text) == "what llm is running how many parameters?"
    assert grok_self_type.extract_grok_browser_payload(text) == "what llm is running how many parameters?"
    assert grok_self_type.wants_enter(text) is True


def test_extract_rejects_instruction_placeholder():
    text = "Alice, type YOUR OWN opening line to Grok in your Alice Browser and push enter"
    assert grok_self_type.extract_grok_self_type_payload(text) == ""


def test_talk_mission_start_driver_rejects_deepai_surface(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        talk = importlib.import_module("Applications.sifta_talk_to_alice_widget")
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Talk widget import failed: {type(exc).__name__}: {exc}")

    owner = (
        "the same you were chating with grok before. on this new page that we just open, "
        "ask the chatbot to identify itself and introduce yourself as Alice. "
        "then chat with it 10 rounds"
    )
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    row = talk._stage_grok_dialogue_mission_from_owner_text(
        owner,
        source="test",
        state_dir=tmp_path,
    )

    assert row["handled"] is False
    assert row["status"] == "non_grok_chat_surface"
    assert not (sd / "visible_grok_dialogue_mission.json").exists()


def test_talk_mission_start_driver_writes_first_browser_command(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        talk = importlib.import_module("Applications.sifta_talk_to_alice_widget")
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Talk widget import failed: {type(exc).__name__}: {exc}")

    owner = (
        "Alice, ask grok about your stigmergic no double spend like bitcoin receipts "
        "of action taken == , and chat with it 6 rounds of chatting"
    )
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    (sd / "alice_grok_mirror_autopilot_state.json").write_text(
        json.dumps(
            {
                "schema": "ALICE_GROK_MIRROR_AUTOPILOT_V1",
                "browser_reply_prompts": 5,
                "mirror_turn": 9,
                "pending_copy_receipt": "stale-copy",
                "pending_paste_receipt": "stale-paste",
            }
        ),
        encoding="utf-8",
    )
    row = talk._stage_grok_dialogue_mission_from_owner_text(
        owner,
        source="test",
        state_dir=tmp_path,
    )

    assert row["handled"] is True
    assert row["status"] == "first_question_staged"
    assert row["target_rounds"] == 6
    assert row["autopilot_state_reset"] is True
    assert row["first_question_staged"] is True
    assert row["first_question"] == "your stigmergic no double spend like bitcoin receipts of action taken"

    command = json.loads((sd / "alice_browser_grok_self_type_command.json").read_text(encoding="utf-8"))
    assert command["text"] == row["first_question"]
    assert command["press_enter"] is True
    assert command["receipt_id"] == row["self_type_receipt_id"]

    mission = json.loads((sd / "visible_grok_dialogue_mission.json").read_text(encoding="utf-8"))
    assert mission["target_rounds"] == 6
    assert mission["first_question_staged"] is True

    autopilot_state = json.loads((sd / "alice_grok_mirror_autopilot_state.json").read_text(encoding="utf-8"))
    assert autopilot_state["target_rounds"] == 6
    assert autopilot_state["browser_reply_prompts"] == 0
    assert autopilot_state["mirror_turn"] == 0

    round_rows = [
        json.loads(line)
        for line in (sd / "grok_browser_round_state.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(r["state"] == "S2_PASTE_TO_GROK_STAGED" and r["ok"] for r in round_rows)


def test_talk_mission_start_driver_can_arm_continuous_until_stopped(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        talk = importlib.import_module("Applications.sifta_talk_to_alice_widget")
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Talk widget import failed: {type(exc).__name__}: {exc}")

    owner = (
        'Alice, ask grok "What does an owner-stopped dialogue loop change?" '
        "and keep chatting with Grok in your browser forever until I stop it."
    )
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    row = talk._stage_grok_dialogue_mission_from_owner_text(
        owner,
        source="test",
        state_dir=tmp_path,
    )

    assert row["handled"] is True
    assert row["continuous_until_stopped"] is True
    assert row["autopilot_continuous_until_stopped"] is True

    mission = json.loads((sd / "visible_grok_dialogue_mission.json").read_text(encoding="utf-8"))
    assert mission["continuous_until_stopped"] is True
    assert mission["stop_condition"] == "owner_stop"

    autopilot_state = json.loads((sd / "alice_grok_mirror_autopilot_state.json").read_text(encoding="utf-8"))
    assert autopilot_state["continuous_until_stopped"] is True
    assert autopilot_state["stop_condition"] == "owner_stop"


def test_continue_driver_can_switch_active_dialogue_to_continuous(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        talk = importlib.import_module("Applications.sifta_talk_to_alice_widget")
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Talk widget import failed: {type(exc).__name__}: {exc}")

    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    (sd / "alice_grok_mirror_autopilot.flag").write_text("{}", encoding="utf-8")
    (sd / "alice_grok_mirror_autopilot_state.json").write_text(
        json.dumps({"schema": "ALICE_GROK_MIRROR_AUTOPILOT_V1", "target_rounds": 3}),
        encoding="utf-8",
    )
    row = talk._apply_grok_dialogue_continue_budget(
        "continue the same thread and keep the conversation going until I stop it",
        source="test",
        state_dir=tmp_path,
    )

    assert row["handled"] is True
    assert row["status"] == "continuous_until_stopped"
    assert row["continuous_until_stopped"] is True
    state = json.loads((sd / "alice_grok_mirror_autopilot_state.json").read_text(encoding="utf-8"))
    assert state["continuous_until_stopped"] is True


def test_stop_driver_disables_active_grok_dialogue(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        talk = importlib.import_module("Applications.sifta_talk_to_alice_widget")
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Talk widget import failed: {type(exc).__name__}: {exc}")

    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    (sd / "alice_grok_mirror_autopilot.flag").write_text("{}", encoding="utf-8")
    (sd / "alice_talk_copy_last_own_command.json").write_text("{}", encoding="utf-8")
    (sd / "alice_grok_browser_reply_retry.json").write_text("{}", encoding="utf-8")
    (sd / "alice_grok_loop_watchdog.pid").write_text("999999999", encoding="utf-8")
    (sd / "alice_grok_mirror_autopilot_state.json").write_text(
        json.dumps(
            {
                "status": "active",
                "continuous_until_stopped": True,
                "pending_alice_reply_grok_sha256": "abc",
                "pending_alice_reply_context": {"grok_preview": "still moving"},
            }
        ),
        encoding="utf-8",
    )
    (sd / "visible_grok_dialogue_mission.json").write_text(
        json.dumps({"status": "active", "continuous_until_stopped": True, "stop_condition": "owner_stop"}),
        encoding="utf-8",
    )

    row = talk._stop_grok_dialogue_from_owner_text(
        "Alice stop the Grok loop",
        source="test",
        state_dir=tmp_path,
    )

    assert row["handled"] is True
    assert row["status"] == "stopped"
    assert row["hard_stop_receipt_id"]
    assert not (sd / "alice_grok_mirror_autopilot.flag").exists()
    assert not (sd / "alice_talk_copy_last_own_command.json").exists()
    assert not (sd / "alice_grok_browser_reply_retry.json").exists()
    assert not (sd / "alice_grok_loop_watchdog.pid").exists()
    mission = json.loads((sd / "visible_grok_dialogue_mission.json").read_text(encoding="utf-8"))
    assert mission["status"] == "stopped"
    state = json.loads((sd / "alice_grok_mirror_autopilot_state.json").read_text(encoding="utf-8"))
    assert state["status"] == "stopped"
    assert "pending_alice_reply_grok_sha256" not in state
    assert "pending_alice_reply_context" not in state


def test_grok_send_verdict_accepts_chat_page_after_composer_clears():
    verdict = grok_self_type.grok_send_verdict(
        "Hello world. I'm Alice.",
        url="https://grok.com/c/thread",
        page_text="Hello world. I'm Alice.\nThought for 3s\nHello, Alice!",
        draft_texts=["Ask anything"],
        press_enter=True,
    )

    assert verdict["ok"] is True
    assert verdict["status"] == "sent"


def test_grok_send_verdict_accepts_chatgpt_root_after_composer_clears():
    verdict = grok_self_type.grok_send_verdict(
        "Hello world. I'm Alice.",
        url="https://chatgpt.com/",
        page_text="Hello world. I'm Alice.\nChatGPT can make mistakes.",
        draft_texts=[],
        press_enter=True,
    )

    assert verdict["ok"] is True
    assert verdict["status"] == "sent"


def test_pasted_numbered_list_without_grok_does_not_arm_mission():
    """2026-07-20 incident: George pasted a status update containing a numbered
    plan into Alice's chat. It never mentioned Grok, but the bare numbered-list
    rule armed a browser mission, extracted "Ioana" as the first question, and
    drove Alice to grok.com in a retry loop (he has no Grok subscription, so the
    page had no composer and every send failed). A numbered list must not arm a
    Grok mission unless the text actually names Grok."""
    text = (
        "bine Alice, bravo. update: macOS already has a Romanian voice — Ioana "
        "(ro_RO). Here is the plan:\n"
        "1. Language detection: a lightweight heuristic for Romanian text\n"
        "2. Voice override in _TTSWorker: override voice to \"Ioana\"\n"
        "3. Wire it at the _TTSWorker.run() level so every TTS path benefits"
    )
    assert "grok" not in text.lower()
    assert not grok_self_type.looks_like_grok_mission_brief(text)


def test_numbered_brief_naming_grok_still_arms_mission():
    """The anchor must not break the real use: a numbered brief that does name
    Grok is still a mission."""
    text = (
        "Alice, chat with Grok in your browser:\n"
        "1. ask him about his qualia\n"
        "2. COPY each reply to Global Chat"
    )
    assert grok_self_type.looks_like_grok_mission_brief(text)
