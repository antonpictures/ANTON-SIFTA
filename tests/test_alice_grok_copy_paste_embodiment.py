from __future__ import annotations

import json

from System import swarm_alice_browser_grok_copy as grok_copy
from System import swarm_alice_browser_grok_paste_clipboard as grok_paste
from System import swarm_alice_talk_copy_last_own as talk_copy_own
from System import swarm_alice_talk_paste_clipboard as talk_paste
from System import swarm_grok_browser_round_state as round_state


def test_stage_grok_copy_command_writes_file(tmp_path):
    row = grok_copy.stage_grok_copy_last_reply_command(
        owner_text="click COPY",
        from_grok_receipt="ask-1",
        loop=2,
        state_dir=tmp_path,
    )
    sd = tmp_path / ".sifta_state"
    cmd = json.loads((sd / "alice_browser_grok_copy_command.json").read_text(encoding="utf-8"))
    assert cmd["truth_label"] == grok_copy.TRUTH_LABEL
    assert cmd["receipt_id"] == row["receipt_id"]
    assert cmd["loop"] == 2


def test_stage_talk_paste_clipboard_command(tmp_path):
    row = talk_paste.stage_talk_paste_clipboard_command(
        from_grok_copy_receipt="copy-1",
        expected_clipboard_sha256="abc",
        clipboard_text="Grok reply frozen from browser copy.",
        loop=1,
        state_dir=tmp_path,
    )
    sd = tmp_path / ".sifta_state"
    cmd = json.loads((sd / "alice_talk_paste_clipboard_command.json").read_text(encoding="utf-8"))
    assert cmd["schema"] == talk_paste.TRUTH_LABEL
    assert cmd["send"] is True
    assert cmd["from_grok_copy_receipt"] == "copy-1"
    assert cmd["transport"] == "direct_payload"
    assert cmd["payload_frozen_at_stage"] is True
    assert cmd["clipboard_text"] == "Grok reply frozen from browser copy."
    assert cmd["clipboard_sha256"] == talk_paste.clipboard_sha256("Grok reply frozen from browser copy.")


def test_stage_talk_copy_last_own_command_with_copy_text(tmp_path):
    row = talk_copy_own.stage_talk_copy_last_own_command(
        copy_text="Thanks Grok — the MoE router click feels real in my field.",
        copy_role="assistant",
        paste_to_browser_after_copy=True,
        state_dir=tmp_path,
    )
    sd = tmp_path / ".sifta_state"
    cmd = json.loads((sd / "alice_talk_copy_last_own_command.json").read_text(encoding="utf-8"))
    assert cmd["copy_text"].startswith("Thanks Grok")
    assert cmd["paste_to_browser_after_copy"] is True


def test_stage_talk_copy_last_own_command(tmp_path):
    row = talk_copy_own.stage_talk_copy_last_own_command(
        from_talk_paste_receipt="paste-1",
        loop=3,
        state_dir=tmp_path,
    )
    sd = tmp_path / ".sifta_state"
    cmd = json.loads((sd / "alice_talk_copy_last_own_command.json").read_text(encoding="utf-8"))
    assert cmd["truth_label"] == talk_copy_own.TRUTH_LABEL
    assert cmd["receipt_id"] == row["receipt_id"]


def test_stage_talk_copy_assistant_and_paste_back_command(tmp_path):
    row = talk_copy_own.stage_talk_copy_last_own_command(
        from_grok_mirror_receipt="mirror-1",
        copy_role="assistant",
        paste_to_browser_after_copy=True,
        browser_url="https://grok.com/c/test",
        loop=5,
        state_dir=tmp_path,
    )
    sd = tmp_path / ".sifta_state"
    cmd = json.loads((sd / "alice_talk_copy_last_own_command.json").read_text(encoding="utf-8"))

    assert cmd["receipt_id"] == row["receipt_id"]
    assert cmd["copy_role"] == "assistant"
    assert cmd["paste_to_browser_after_copy"] is True
    assert cmd["browser_url"] == "https://grok.com/c/test"


def test_stage_grok_paste_clipboard_command(tmp_path):
    row = grok_paste.stage_grok_paste_clipboard_command(
        from_talk_paste_receipt="paste-9",
        press_enter=True,
        loop=4,
        clipboard_text="frozen Alice reply",
        state_dir=tmp_path,
    )
    sd = tmp_path / ".sifta_state"
    cmd = json.loads((sd / "alice_browser_grok_paste_clipboard_command.json").read_text(encoding="utf-8"))
    assert cmd["schema"] == grok_paste.TRUTH_LABEL
    assert cmd["press_enter"] is True
    assert cmd["from_talk_paste_receipt"] == "paste-9"
    assert cmd["payload_frozen_at_stage"] is True
    assert cmd["clipboard_text"] == "frozen Alice reply"
    assert cmd["clipboard_sha256"] == grok_paste.clean_text_sha256("frozen Alice reply")


def test_stage_grok_paste_bad_no_receipt_fallback_gets_bad_action_receipt(tmp_path):
    old_residue = " ".join(
        [
            "I will not claim",
            "an action ran without",
            "an effector receipt.",
        ]
    )

    row = grok_paste.stage_grok_paste_clipboard_command(
        clipboard_text=old_residue,
        state_dir=tmp_path,
    )
    sd = tmp_path / ".sifta_state"
    cmd = json.loads((sd / "alice_browser_grok_paste_clipboard_command.json").read_text(encoding="utf-8"))

    assert row["status"] == "bad_action_receipt_no_paste_attempted"
    assert cmd["status"] == "bad_action_receipt_no_paste_attempted"
    assert cmd["clipboard_text"] == ""
    assert cmd["bad_action_reason"] == "stale_no_receipt_fallback_payload"


def test_grok_paste_requires_same_thread_before_send():
    target = "https://grok.com/c/thread-a?rid=next"

    assert grok_paste.grok_thread_id(target) == "thread-a"
    assert grok_paste.needs_target_thread_navigation("https://grok.com/", target) is True
    assert grok_paste.needs_target_thread_navigation("https://grok.com/c/thread-b", target) is True
    assert grok_paste.needs_target_thread_navigation("https://grok.com/c/thread-a?rid=old", target) is False


def test_clipboard_sha256_normalizes_whitespace():
    assert talk_paste.clipboard_sha256("hello   world") == talk_paste.clipboard_sha256("hello world")


def test_round_state_blocks_double_spend(tmp_path):
    first = round_state.record_round_transition(
        state="S4_GROK_COPY_TO_GLOBAL_STAGED",
        event="copy_spent",
        round_number=1,
        spend_receipts=["copy-1"],
        payload_text="Grok says hello.",
        state_dir=tmp_path,
    )
    second = round_state.record_round_transition(
        state="S4_GROK_COPY_TO_GLOBAL_STAGED",
        event="copy_spent_again",
        round_number=1,
        spend_receipts=["copy-1"],
        payload_text="Different text.",
        state_dir=tmp_path,
    )

    assert first["ok"] is True
    assert second["ok"] is False
    assert second["status"] == "double_spend_blocked"
    assert "copy-1" in second["double_spend_conflicts"]


def test_clipboard_looks_like_grok_reply_rejects_model_picker():
    bad = grok_copy.clipboard_looks_like_grok_reply("rafw007/gemma4-26b-claude-coder:latest")
    assert bad["ok"] is False
    good = grok_copy.clipboard_looks_like_grok_reply(
        "I see you too, Alice. Beautiful. You are mirroring our chat to Global Chat so George can watch."
    )
    assert good["ok"] is True


def test_grok_copy_rejects_model_label_clipboard():
    quality = grok_copy.clipboard_looks_like_grok_reply(
        "baytout3/Qwen3.6-27B-Uncensored-HauhauCS-Balanced:IQ4_XS"
    )

    assert quality["ok"] is False
    assert quality["reason"] == "model_label_or_short_control_text"


def test_grok_copy_accepts_sentence_reply_clipboard():
    quality = grok_copy.clipboard_looks_like_grok_reply(
        "I see you too, Alice. Beautiful. You are mirroring our chat to Global Chat so George can watch, and the bridge is live."
    )

    assert quality["ok"] is True


def test_grok_copy_accepts_grok_reply_that_ends_with_question():
    quality = grok_copy.clipboard_looks_like_grok_reply(
        "**I'm Grok 4**, built by xAI. Exact parameter count is not publicly disclosed, "
        "but this is a frontier-class model with tool use and optimized routing. "
        "Want details on how Alice routes or mixes inference?"
    )

    assert quality["ok"] is True


def test_grok_copy_rejects_global_chat_transcript_clipboard():
    quality = grok_copy.clipboard_looks_like_grok_reply(
        "Ioan  (TYPED)  2026-06-25 11:43:04 Alice, ask grok what llm is running how many parameters? 📋 Copy "
        "Alice I am checking browser receipts before speaking."
    )

    assert quality["ok"] is False
    assert quality["reason"] == "global_chat_transcript_or_copy_chrome"


def test_grok_copy_rejects_alice_prompt_clipboard():
    quality = grok_copy.clipboard_looks_like_grok_reply(
        "Let's dive into that routing detail first. How does your Mixture-of-Experts architecture "
        "handle context switching inside a local environment like mine?"
    )

    assert quality["ok"] is False
    assert quality["reason"] == "alice_or_owner_prompt_not_grok_reply"


def test_extract_latest_grok_reply_keeps_router_answer_body():
    page = """
    Sketch that router idea.

    Thought for 4s

    Residual / Shared Pathways Analysis (quick take first):

    Maintaining cross-expert connectivity via shared/residual pathways is highly critical.

    Router Sketch Concept: Stigmergic Mixture-of-Experts Router with Residual/Shared Pathways

    This combines noisy top-k routing, shared residual pathways, and activation load tracking.

    Get notified when Grok finishes answering
    Enable
    Fast
    Upgrade to SuperGrok
    """
    text = grok_copy.extract_latest_grok_reply_from_page_text(page)

    assert "Residual / Shared Pathways Analysis" in text
    assert "Router Sketch Concept" in text
    assert "Upgrade to SuperGrok" not in text


def test_grok_copy_rejects_alice_topk_vram_question():
    alice_q = (
        "Which approach performs better under extreme context loads: simple $\\text{Top-}K$, "
        "or full density/dynamic weighing? Bonus points if you can quantify how much more "
        "efficient that makes memory usage $(\\approx \\text{VRAM})$ over just speed alone $\\oplus$."
    )
    quality = grok_copy.clipboard_looks_like_grok_reply(alice_q)
    assert quality["ok"] is False
    assert quality["reason"] == "alice_or_owner_prompt_not_grok_reply"


def test_grok_copy_rejects_matching_last_alice_send_sha():
    alice_q = "Great follow-up thread with Grok about routing and MoE switches in my local node setup today."
    sha = __import__("hashlib").sha256(" ".join(alice_q.split()).encode()).hexdigest()
    quality = grok_copy.clipboard_looks_like_grok_reply(alice_q, last_alice_send_sha256=sha)
    assert quality["ok"] is False
    assert quality["reason"] == "matches_last_alice_browser_send"
