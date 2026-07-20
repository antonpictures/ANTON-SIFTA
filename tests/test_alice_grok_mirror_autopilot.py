from __future__ import annotations

import json
import time

from System import swarm_alice_browser_grok_copy as grok_copy
from System import swarm_alice_grok_mirror_autopilot as autopilot
from System.swarm_internet_forager_home_vector import capture_home_vector


SAMPLE_PAGE_TAIL = """
Thank you Grok. This visible dialogue is complete — same thread in both panels.

Thought for 3s

Understood, Alice.

Visible dialogue complete — same thread mirrored across both panels. Beautiful synchronization.

I'm here whenever you or George want to continue expanding sensory layers.

Power to the Swarm. ❤️🌀

Explore sensory layer expansion
Fast
Upgrade to SuperGrok
"""


def test_clipboard_rejects_model_label():
    quality = grok_copy.clipboard_looks_like_grok_reply(
        "baytout3/Qwen3.6-27B-Uncensored-HauhauCS-Balanced:IQ4_XS"
    )
    assert quality["ok"] is False


def test_extract_latest_grok_reply_from_page_text():
    text = grok_copy.extract_latest_grok_reply_from_page_text(SAMPLE_PAGE_TAIL)
    assert "Understood, Alice" in text
    assert "Upgrade to SuperGrok" not in text
    assert len(text) >= 80


def test_enable_autopilot_and_tick_idle(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    autopilot.enable_autopilot(state_dir=sd)
    assert autopilot.autopilot_enabled(sd)
    out = autopilot.tick_grok_mirror_autopilot(state_dir=sd)
    assert out["active"] is True
    assert out["action"] in {"not_on_grok_chat", "idle", "page_changed"}


def test_disable_autopilot_marks_continuous_mission_stopped(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    autopilot.enable_autopilot(state_dir=sd)
    (sd / "visible_grok_dialogue_mission.json").write_text(
        json.dumps({"status": "active", "continuous_until_stopped": True, "stop_condition": "owner_stop"}),
        encoding="utf-8",
    )
    (sd / autopilot.STATE_FILE).write_text(
        json.dumps({"schema": autopilot.TRUTH_LABEL, "continuous_until_stopped": True}),
        encoding="utf-8",
    )

    row = autopilot.disable_autopilot(owner_note="Alice stop the Grok loop", state_dir=sd)
    mission = json.loads((sd / "visible_grok_dialogue_mission.json").read_text(encoding="utf-8"))
    state = json.loads((sd / autopilot.STATE_FILE).read_text(encoding="utf-8"))

    assert row["action"] == "disable"
    assert not autopilot.autopilot_enabled(sd)
    assert mission["status"] == "stopped"
    assert mission["continuous_until_stopped"] is False
    assert state["continuous_until_stopped"] is False


def test_extract_alice_browser_reply_text_skips_coaching():
    raw = (
        "Website Grok just answered.\n"
        "Thanks Grok — frontier class noted. Tell me more about mixture-of-experts."
    )
    out = autopilot.extract_alice_browser_reply_text(raw)
    assert "mixture-of-experts" in out
    assert "Website Grok" not in out


def test_extract_alice_browser_reply_text_strips_body_action_tail():
    raw = (
        "That looks incredibly robust! What is the functional difference between shared residuals and adapters?\n\n"
        "After thinking, I executed the real body action: I checked first: Alice Browser was already open.\n\n"
        "No action receipt yet: I have not completed the external action. Needed: target and exact message."
    )

    out = autopilot.extract_alice_browser_reply_text(raw)

    assert "functional difference" in out
    assert "After thinking" not in out
    assert "No action receipt" not in out


def test_extract_alice_browser_reply_text_keeps_long_followup():
    raw = " ".join(["This is a valid technical follow-up sentence about routing."] * 18)

    out = autopilot.extract_alice_browser_reply_text(raw)

    assert len(out) > 500


def test_should_prompt_alice_browser_reply_respects_budget(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    autopilot.enable_autopilot(state_dir=sd)
    (sd / "visible_grok_dialogue_mission.json").write_text(
        json.dumps({"target_rounds": 3}),
        encoding="utf-8",
    )
    grok = "I'm Grok 4. " + ("x" * 120)
    assert autopilot.should_prompt_alice_browser_reply(grok_text=grok, state_dir=sd)
    autopilot.record_browser_reply_prompt(state_dir=sd)
    autopilot.record_browser_reply_prompt(state_dir=sd)
    autopilot.record_browser_reply_prompt(state_dir=sd)
    assert not autopilot.should_prompt_alice_browser_reply(grok_text=grok, state_dir=sd)


def test_should_prompt_alice_browser_reply_ignores_budget_when_continuous(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    autopilot.enable_autopilot(state_dir=sd)
    (sd / "visible_grok_dialogue_mission.json").write_text(
        json.dumps({"target_rounds": 3, "continuous_until_stopped": True, "stop_condition": "owner_stop"}),
        encoding="utf-8",
    )
    (sd / autopilot.STATE_FILE).write_text(
        json.dumps(
            {
                "schema": autopilot.TRUTH_LABEL,
                "continuous_until_stopped": True,
                "browser_reply_prompts": 42,
                "target_rounds": 3,
            }
        ),
        encoding="utf-8",
    )
    grok = "I'm Grok 4. " + ("continuous owner-stopped loop " * 8)

    assert autopilot.should_prompt_alice_browser_reply(grok_text=grok, state_dir=sd)


def test_configured_grok_chat_url_prefers_mission_url(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    mission_url = "https://grok.com/c/90b16556-6172-4706-b183-850a04d6fae8?rid=mission"
    page_url = "https://grok.com/c/3687cca1-203d-421a-8a4a-61a0b907a27b?rid=page"
    (sd / "visible_grok_dialogue_mission.json").write_text(
        json.dumps({"grok_url": mission_url, "target_rounds": 12}),
        encoding="utf-8",
    )
    (sd / "alice_browser_current_page.json").write_text(
        json.dumps({"url": page_url, "text": "old thread"}),
        encoding="utf-8",
    )

    assert autopilot.configured_grok_chat_url(state_dir=sd) == mission_url


def test_should_prompt_rejects_junk_mirror_and_high_mirror_turn(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    autopilot.enable_autopilot(state_dir=sd)
    (sd / "visible_grok_dialogue_mission.json").write_text(
        json.dumps({"target_rounds": 3}),
        encoding="utf-8",
    )
    (sd / autopilot.STATE_FILE).write_text(
        json.dumps({"schema": autopilot.TRUTH_LABEL, "mirror_turn": 5, "browser_reply_prompts": 0}),
        encoding="utf-8",
    )
    junk = "Ioan  (TYPED)  2026-06-25\n\nAlice, ask grok what llm is running"
    assert not autopilot.should_prompt_alice_browser_reply(grok_text=junk, state_dir=sd)
    grok = "**I'm Grok 4** " + ("frontier class " * 20)
    assert autopilot.should_prompt_alice_browser_reply(grok_text=grok, state_dir=sd)


def test_latest_valid_grok_mirror_text_skips_junk(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    grok = "**I'm Grok 4** " + ("frontier class " * 20)
    junk = "Ioan  (TYPED)\n\nAlice, ask grok what llm is running"
    ledger = sd / autopilot._PASTE_RESULTS if hasattr(autopilot, "_PASTE_RESULTS") else sd / "alice_talk_paste_clipboard_results.jsonl"
    ledger.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "source": "talk_to_alice_widget",
                        "clipboard_text": junk,
                    }
                ),
                json.dumps(
                    {
                        "source": "talk_to_alice_widget",
                        "clipboard_text": grok,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    out = autopilot.latest_valid_grok_mirror_text(state_dir=sd)
    assert "Grok 4" in out
    assert "Ioan" not in out


def test_page_has_fresh_grok_reply_waits_after_alice_send(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    alice_q = "Which approach performs better under extreme context loads?"
    grok_a = (
        "Great question, Alice. Top-K sparse activation is usually more efficient for VRAM "
        "under extreme context loads than full dynamic weighting in most frontier MoE stacks."
    )
    page_text = f"{alice_q}\n\nThought for 2s\n\n{grok_a}\n\nFast\nUpgrade to SuperGrok"
    page = {"url": "https://grok.com/c/test", "text": page_text}
    state = {
        "last_alice_browser_send_preview": alice_q,
        "last_alice_browser_send_sha256": autopilot._clean_text_sha(alice_q),
        "last_mirrored_clipboard_sha256": "",
    }
    assert autopilot.page_has_fresh_grok_reply(page=page, state=state)

    page_waiting = {"url": "https://grok.com/c/test", "text": f"{alice_q}\n\nFast\nUpgrade"}
    assert not autopilot.page_has_fresh_grok_reply(page=page_waiting, state=state)


def test_tick_stages_copy_after_stable_page(tmp_path):
    import hashlib

    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    autopilot.enable_autopilot(state_dir=sd)
    page_text = "Hello\nThought for 2s\nI see you Alice.\n" + ("x" * 200)
    page_hash = hashlib.sha256(page_text.encode()).hexdigest()[:16]
    page = {
        "url": "https://grok.com/c/3687cca1-203d-421a-8a4a-61a0b907a27b",
        "text": page_text,
    }
    (sd / "alice_browser_current_page.json").write_text(json.dumps(page), encoding="utf-8")
    state = {
        "schema": autopilot.TRUTH_LABEL,
        "last_page_hash": page_hash,
        "pending_stable_since": time.time() - 5.0,
        "page_hash_at_mirror": "oldhash000000000",
        "mirror_turn": 0,
    }
    (sd / autopilot.STATE_FILE).write_text(json.dumps(state), encoding="utf-8")
    out = autopilot.tick_grok_mirror_autopilot(state_dir=sd)
    assert out["action"] == "staged_grok_copy"
    assert (sd / "alice_browser_grok_copy_command.json").exists()


def test_tick_stops_at_target_rounds_before_staging_extra_copy(tmp_path):
    import hashlib

    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    autopilot.enable_autopilot(state_dir=sd)
    (sd / "visible_grok_dialogue_mission.json").write_text(
        json.dumps({"target_rounds": 6, "status": "active"}),
        encoding="utf-8",
    )
    page_text = "Alice final reply\nThought for 2s\nExtra Grok reply after budget.\n" + ("x" * 200)
    page_hash = hashlib.sha256(page_text.encode()).hexdigest()[:16]
    (sd / "alice_browser_current_page.json").write_text(
        json.dumps({"url": "https://grok.com/c/thread", "text": page_text}),
        encoding="utf-8",
    )
    (sd / autopilot.STATE_FILE).write_text(
        json.dumps(
            {
                "schema": autopilot.TRUTH_LABEL,
                "truth_label": autopilot.TRUTH_LABEL,
                "mirror_turn": 6,
                "browser_reply_prompts": 6,
                "last_page_hash": page_hash,
                "pending_stable_since": time.time() - 5.0,
                "page_hash_at_mirror": "oldhash",
            }
        ),
        encoding="utf-8",
    )

    out = autopilot.tick_grok_mirror_autopilot(state_dir=sd)
    mission = json.loads((sd / "visible_grok_dialogue_mission.json").read_text(encoding="utf-8"))

    assert out["action"] == "target_rounds_complete"
    assert out["target_rounds"] == 6
    assert mission["status"] == "complete"
    assert not autopilot.autopilot_enabled(sd)
    assert not (sd / "alice_browser_grok_copy_command.json").exists()


def test_tick_does_not_stop_at_target_rounds_when_continuous(tmp_path):
    import hashlib

    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    autopilot.enable_autopilot(state_dir=sd)
    (sd / "visible_grok_dialogue_mission.json").write_text(
        json.dumps(
            {
                "target_rounds": 6,
                "status": "active",
                "continuous_until_stopped": True,
                "stop_condition": "owner_stop",
            }
        ),
        encoding="utf-8",
    )
    page_text = "Alice final reply\nThought for 2s\nExtra Grok reply after old budget.\n" + ("x" * 200)
    page_hash = hashlib.sha256(page_text.encode()).hexdigest()[:16]
    (sd / "alice_browser_current_page.json").write_text(
        json.dumps({"url": "https://grok.com/c/thread", "text": page_text}),
        encoding="utf-8",
    )
    (sd / autopilot.STATE_FILE).write_text(
        json.dumps(
            {
                "schema": autopilot.TRUTH_LABEL,
                "truth_label": autopilot.TRUTH_LABEL,
                "continuous_until_stopped": True,
                "mirror_turn": 6,
                "browser_reply_prompts": 6,
                "target_rounds": 6,
                "last_page_hash": page_hash,
                "pending_stable_since": time.time() - 5.0,
                "page_hash_at_mirror": "oldhash",
            }
        ),
        encoding="utf-8",
    )

    out = autopilot.tick_grok_mirror_autopilot(state_dir=sd)

    assert out["action"] == "staged_grok_copy"
    assert out["continuous_until_stopped"] is True
    assert autopilot.autopilot_enabled(sd)
    assert (sd / "alice_browser_grok_copy_command.json").exists()


def test_tick_freezes_grok_copy_payload_for_talk_mirror(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    autopilot.enable_autopilot(state_dir=sd)
    grok_text = (
        "I am Grok in this browser reply, and this is long enough to be a valid "
        "assistant answer that Alice should mirror into Global Chat before replying."
    )
    copy_sha = autopilot._clean_text_sha(grok_text)
    (sd / autopilot.STATE_FILE).write_text(
        json.dumps(
            {
                "schema": autopilot.TRUTH_LABEL,
                "truth_label": autopilot.TRUTH_LABEL,
                "pending_copy_receipt": "copy-freeze-1",
                "mirror_turn": 0,
            }
        ),
        encoding="utf-8",
    )
    (sd / "alice_browser_grok_copy_results.jsonl").write_text(
        json.dumps(
            {
                "receipt_id": "copy-freeze-1",
                "source": "alice_browser_widget",
                "ok": True,
                "status": "copied",
                "clipboard_text": grok_text,
                "clipboard_sha256": copy_sha,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    out = autopilot.tick_grok_mirror_autopilot(state_dir=sd)
    cmd = json.loads((sd / "alice_talk_paste_clipboard_command.json").read_text(encoding="utf-8"))
    round_rows = [
        json.loads(line)
        for line in (sd / "grok_browser_round_state.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert out["action"] == "staged_talk_paste"
    assert cmd["clipboard_text"] == grok_text
    assert cmd["transport"] == "direct_payload"
    assert cmd["payload_frozen_at_stage"] is True
    assert round_rows[-1]["state"] == "S4_GROK_COPY_TO_GLOBAL_STAGED"
    assert round_rows[-1]["spend_receipts"] == ["copy-freeze-1"]


def test_tick_on_deepai_does_not_redirect_to_grok_mission(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    mission_url = "https://grok.com/c/90b16556-6172-4706-b183-850a04d6fae8?rid=mission"
    autopilot.enable_autopilot(state_dir=sd)
    (sd / "visible_grok_dialogue_mission.json").write_text(
        json.dumps({"grok_url": mission_url, "target_rounds": 10, "status": "active"}),
        encoding="utf-8",
    )
    (sd / "alice_browser_current_page.json").write_text(
        json.dumps({"url": "https://deepai.org/chat", "text": "DeepAI chat page"}),
        encoding="utf-8",
    )

    out = autopilot.tick_grok_mirror_autopilot(state_dir=sd)

    assert out["action"] == "not_on_grok_chat"
    assert not (sd / "alice_browser_open_url.txt").exists()


def test_tick_refuses_old_thread_and_requests_mission_navigation(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    mission_url = "https://grok.com/c/90b16556-6172-4706-b183-850a04d6fae8?rid=mission"
    old_url = "https://grok.com/c/3687cca1-203d-421a-8a4a-61a0b907a27b?rid=old"
    autopilot.enable_autopilot(state_dir=sd)
    (sd / "visible_grok_dialogue_mission.json").write_text(
        json.dumps({"grok_url": mission_url, "target_rounds": 12}),
        encoding="utf-8",
    )
    (sd / "alice_browser_current_page.json").write_text(
        json.dumps({"url": old_url, "text": "Thought for 2s\nold answer " + ("x" * 200)}),
        encoding="utf-8",
    )

    out = autopilot.tick_grok_mirror_autopilot(state_dir=sd)

    assert out["action"] == "wrong_grok_thread_navigating_to_mission"
    assert (sd / "alice_browser_open_url.txt").read_text(encoding="utf-8") == mission_url
    assert not (sd / "alice_browser_grok_copy_command.json").exists()


def test_tick_wrong_thread_uses_forager_home_vector_when_available(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    mission_url = "https://grok.com/c/home-thread?rid=mission"
    old_url = "https://grok.com/c/old-thread?rid=old"
    autopilot.enable_autopilot(state_dir=sd)
    (sd / "visible_grok_dialogue_mission.json").write_text(
        json.dumps({"grok_url": mission_url, "target_rounds": 12}),
        encoding="utf-8",
    )
    capture_home_vector(
        page={"url": mission_url, "title": "Home", "text": "home thread"},
        mission={"grok_url": mission_url, "start_driver_receipt_id": "mission-r1"},
        state_dir=tmp_path,
    )
    (sd / "alice_browser_current_page.json").write_text(
        json.dumps({"url": old_url, "text": "Thought for 2s\nold answer " + ("x" * 200)}),
        encoding="utf-8",
    )

    out = autopilot.tick_grok_mirror_autopilot(state_dir=sd)

    assert out["action"] == "wrong_grok_thread_navigating_to_mission"
    assert out["return_mode"] == "internet_forager_home_vector"
    assert out["home_vector_status"] == "mapped_habitat_off_home_thread"
    assert (sd / "alice_browser_open_url.txt").read_text(encoding="utf-8") == mission_url


def test_tick_clears_completed_talk_paste_latch(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    autopilot.enable_autopilot(state_dir=sd)
    (sd / autopilot.STATE_FILE).write_text(
        json.dumps(
            {
                "schema": autopilot.TRUTH_LABEL,
                "pending_paste_receipt": "alice-talk-paste-1",
                "mirror_turn": 1,
                "browser_reply_prompts": 1,
            }
        ),
        encoding="utf-8",
    )
    (sd / "alice_talk_paste_clipboard_results.jsonl").write_text(
        json.dumps(
            {
                "receipt_id": "alice-talk-paste-1",
                "source": "talk_to_alice_widget",
                "status": "pasted",
                "ok": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (sd / "alice_browser_current_page.json").write_text(
        json.dumps({"url": "https://grok.com/c/home-thread", "text": "Alice sent. Fast"}),
        encoding="utf-8",
    )

    autopilot.tick_grok_mirror_autopilot(state_dir=sd)

    state = json.loads((sd / autopilot.STATE_FILE).read_text(encoding="utf-8"))
    assert state["pending_paste_receipt"] == ""


def test_tick_blocks_stale_copy_until_first_question_send_result(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    autopilot.enable_autopilot(state_dir=sd)
    (sd / "visible_grok_dialogue_mission.json").write_text(
        json.dumps(
            {
                "status": "active",
                "target_rounds": 10,
                "grok_url": "https://grok.com/c/home-thread",
                "first_question": "Hey Grok, how do I browse the internet?",
                "self_type_receipt_id": "self-type-opening-1",
            }
        ),
        encoding="utf-8",
    )
    (sd / "alice_browser_current_page.json").write_text(
        json.dumps(
            {
                "url": "https://grok.com/c/home-thread",
                "text": "Old Alice line.\n\nThought for 2s\n\nOld Grok answer that should not be copied. " + ("x" * 160),
            }
        ),
        encoding="utf-8",
    )

    out = autopilot.tick_grok_mirror_autopilot(state_dir=sd)

    assert out["action"] == "waiting_first_question_send_result"
    assert not (sd / "alice_browser_grok_copy_command.json").exists()


def test_tick_retries_unverified_first_question_before_copying_old_page(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    autopilot.enable_autopilot(state_dir=sd)
    (sd / "visible_grok_dialogue_mission.json").write_text(
        json.dumps(
            {
                "status": "active",
                "target_rounds": 10,
                "grok_url": "https://grok.com/c/home-thread",
                "first_question": "Hey Grok, how do I browse the internet?",
                "self_type_receipt_id": "self-type-opening-1",
            }
        ),
        encoding="utf-8",
    )
    (sd / "alice_browser_grok_self_type_results.jsonl").write_text(
        json.dumps(
            {
                "receipt_id": "self-type-opening-1",
                "source": "alice_browser_widget",
                "status": "unverified",
                "ok": False,
                "reason": "payload_not_found_after_submit",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (sd / "alice_browser_current_page.json").write_text(
        json.dumps(
            {
                "url": "https://grok.com/c/home-thread",
                "text": "Old Alice line.\n\nThought for 2s\n\nOld Grok answer that should not be copied. " + ("x" * 160),
            }
        ),
        encoding="utf-8",
    )

    out = autopilot.tick_grok_mirror_autopilot(state_dir=sd)
    mission = json.loads((sd / "visible_grok_dialogue_mission.json").read_text(encoding="utf-8"))
    command = json.loads((sd / "alice_browser_grok_self_type_command.json").read_text(encoding="utf-8"))

    assert out["action"] == "first_question_send_retry_staged"
    assert mission["self_type_receipt_id"] == command["receipt_id"]
    assert command["text"] == "Hey Grok, how do I browse the internet?"
    assert not (sd / "alice_browser_grok_copy_command.json").exists()


def test_claim_grok_mirror_for_alice_reply_is_duplicate_guarded(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    autopilot.enable_autopilot(state_dir=sd)

    grok_text = (
        "I'm Grok 4 in this browser conversation. Exact parameter count is not public, "
        "but I can keep this local SIFTA mirror loop going with Alice."
    )
    first = autopilot.claim_grok_mirror_for_alice_reply(
        grok_text=grok_text,
        from_grok_copy_receipt="copy-1",
        mirror_paste_receipt="paste-1",
        loop=2,
        state_dir=sd,
    )
    second = autopilot.claim_grok_mirror_for_alice_reply(
        grok_text=grok_text,
        from_grok_copy_receipt="copy-1",
        mirror_paste_receipt="paste-1",
        loop=2,
        state_dir=sd,
    )

    assert first["ok"] is True
    assert first["context"]["mirror_paste_receipt"] == "paste-1"
    assert second["ok"] is False
    assert second["status"] == "duplicate_grok_mirror"


def test_enqueue_grok_mirror_brain_reply_writes_retry_drop(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    autopilot.enable_autopilot(state_dir=sd)
    row = autopilot.enqueue_grok_mirror_brain_reply(
        grok_text="Grok said something long enough to be a valid mirror for Alice reply testing.",
        mirror_paste_receipt="paste-test",
        loop=2,
        state_dir=sd,
    )
    assert row["action"] == "enqueue_grok_mirror_brain_reply"
    retry = json.loads((sd / "alice_grok_browser_reply_retry.json").read_text(encoding="utf-8"))
    assert "Grok said something" in retry["grok_text"]
    assert retry["loop"] == 2


def test_mark_alice_autoreply_staged_clears_pending_claim(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    autopilot.enable_autopilot(state_dir=sd)
    claim = autopilot.claim_grok_mirror_for_alice_reply(
        grok_text="Grok answered with a sufficiently long browser reply for Alice to answer naturally.",
        mirror_paste_receipt="paste-2",
        loop=3,
        state_dir=sd,
    )

    row = autopilot.mark_alice_autoreply_staged(
        context=claim["context"],
        alice_reply="Thanks Grok. I can see your answer in both panels and I am sending this back from my browser hand.",
        talk_copy_receipt="copy-own-1",
        state_dir=sd,
    )
    state = json.loads((sd / autopilot.STATE_FILE).read_text(encoding="utf-8"))

    assert row["action"] == "staged_alice_reply_back_to_grok"
    assert state.get("pending_alice_reply_context") is None
    assert state["last_alice_reply_talk_copy_receipt"] == "copy-own-1"


def test_note_alice_browser_send_updates_send_state_without_mirror(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    autopilot.enable_autopilot(state_dir=sd)
    (sd / autopilot.STATE_FILE).write_text(
        json.dumps(
            {
                "schema": autopilot.TRUTH_LABEL,
                "truth_label": autopilot.TRUTH_LABEL,
                "last_page_hash": "page-before-send",
            }
        ),
        encoding="utf-8",
    )

    row = autopilot.note_alice_browser_send(
        text="Alice asks Browser Grok the next router question.",
        browser_receipt_id="browser-paste-1",
        source="grok_mirror_autopilot",
        state_dir=sd,
    )
    state = json.loads((sd / autopilot.STATE_FILE).read_text(encoding="utf-8"))

    assert row is not None
    assert row["action"] == "noted_alice_browser_send"
    assert state["last_alice_browser_send_preview"] == "Alice asks Browser Grok the next router question."
    assert state["last_alice_browser_send_receipt"] == "browser-paste-1"
    assert state["page_hash_at_alice_send"] == "page-before-send"
    assert not (sd / "alice_talk_mirror_line_command.json").exists()
