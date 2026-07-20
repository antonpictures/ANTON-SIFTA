"""Web AI chat bridge — r1345."""
from __future__ import annotations

import json
import time

from System.swarm_alice_browser_grok_self_type import command_path
from System.swarm_web_ai_chat_bridge import (
    answer_ai_chat_query,
    ai_chat_site_from_url,
    answer_read_ai_chat_query,
    build_ai_chat_url,
    build_click_submit_js,
    build_read_response_js,
    build_type_and_submit_js,
    canonical_ai_chat_site,
    clear_web_ai_answer_receipt,
    current_page_site_from_url,
    detect_ai_chat_request,
    detect_ai_chat_submit_request,
    detect_read_ai_answer_request,
    has_web_ai_typed_submitted_receipt,
    latest_ai_chat_context,
    launch_ai_chat,
    launch_ai_chat_submit_current_page,
    mark_pending_web_ai_phase,
    pending_host_matches_url,
    read_pending_web_ai_chat,
    read_web_ai_dialogue_mission,
    read_web_ai_answer_receipt,
    record_web_ai_answer,
    resolve_anaphoric_ai_query,
    stage_pending_web_ai_chat,
    stage_pending_web_ai_submit,
    start_web_ai_dialogue_mission,
    uses_grok_browser_limb,
    WEB_AI_CHAT_STAGED_SILENT,
    web_ai_type_send_fiction_guard_reply,
)


def test_detect_duck_ai_request():
    result = detect_ai_chat_request("ask Duck.ai what is stigmergy")
    assert result is not None
    assert result["site"] == "duck.ai"
    assert result["query"] == "what is stigmergy"
    assert result["name"] == "Duck.ai"


def test_detect_gemini_request():
    result = detect_ai_chat_request("ask Gemini how does active inference work")
    assert result is not None
    assert result["site"] == "gemini.google.com"
    assert result["query"] == "how does active inference work"


def test_detect_chatgpt_request():
    result = detect_ai_chat_request("ask ChatGPT what is stigmergic memory")
    assert result is not None
    assert result["site"] == "chatgpt.com"
    assert result["query"] == "what is stigmergic memory"
    assert result["name"] == "ChatGPT"


def test_detect_chatgpt_dotcom_search():
    result = detect_ai_chat_request(
        "SEARCH ON CHATGPT.COM PLS explain no double spend receipts"
    )
    assert result is not None
    assert result["site"] == "chatgpt.com"
    assert result["query"] == "explain no double spend receipts"


def test_detect_open_chatgpt_and_ask_request():
    result = detect_ai_chat_request("open chatgpt.com and ask what time it is?")
    assert result is not None
    assert result["site"] == "chatgpt.com"
    assert result["query"] == "what time it is"
    assert result["name"] == "ChatGPT"


def test_open_chatgpt_ask_strips_push_button_tail():
    owner = (
        "open chatgpt.com and ask what is https://github.com/antonpictures/ANTON-SIFTA/? "
        "then push the button near the text box to send it"
    )
    result = detect_ai_chat_request(owner)
    assert result is not None
    assert result["site"] == "chatgpt.com"
    assert result["query"] == "what is https://github.com/antonpictures/ANTON-SIFTA/"
    assert "push the button" not in result["query"].lower()


def test_open_chatgpt_ask_uses_grok_limb_silent(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    reply = answer_ai_chat_query(
        "open chatgpt.com and ask what is https://github.com/antonpictures/ANTON-SIFTA/?",
        state_dir=tmp_path,
    )
    assert reply is WEB_AI_CHAT_STAGED_SILENT
    assert uses_grok_browser_limb("chatgpt.com")
    assert command_path(tmp_path).exists()
    cmd = json.loads(command_path(tmp_path).read_text(encoding="utf-8"))
    assert "github.com/antonpictures/ANTON-SIFTA" in cmd.get("text", "")
    assert not read_pending_web_ai_chat(state_dir=tmp_path)


def test_detect_current_chatgpt_box_send_request():
    result = detect_ai_chat_request(
        "bravo on opening the website-- now just type in the box hellow i'm alice and hit send",
        current_url="https://chatgpt.com/",
    )
    assert result is not None
    assert result["site"] == "chatgpt.com"
    assert result["query"] == "hellow i'm alice"
    assert result["use_current_page"] is True


def test_detect_chat_ten_rounds_on_chatgpt_about_topic():
    result = detect_ai_chat_request("chat 10 rounds on chatgpt about Elon Musk")
    assert result is not None
    assert result["site"] == "chatgpt.com"
    assert result["target_rounds"] == 10
    assert "Elon Musk" in result["query"]
    assert "Alice" in result["query"]


def test_detect_open_chatgpt_and_chat_ten_rounds_about_topic():
    result = detect_ai_chat_request(
        "open chatgpt.com and chat 10 rounds about this screenshot: the white send arrow matters",
        current_url="https://chatgpt.com/c/old-thread",
    )
    assert result is not None
    assert result["site"] == "chatgpt.com"
    assert result["target_rounds"] == 10
    assert result["use_current_page"] is True
    assert "white send arrow matters" in result["query"]


def test_detect_chatgpt_rounds_does_not_reuse_grok_current_page():
    result = detect_ai_chat_request(
        "chat 10 rounds on chatgpt.com about the visible screenshot",
        current_url="https://grok.com/c/thread-id",
    )
    assert result is not None
    assert result["site"] == "chatgpt.com"
    assert result["target_rounds"] == 10
    assert result.get("use_current_page") is not True
    assert "current_url" not in result


def test_looks_like_web_ai_type_send_command():
    from System.swarm_web_ai_chat_bridge import (
        is_send_intent_typo_label,
        looks_like_web_ai_type_send_command,
    )

    assert looks_like_web_ai_type_send_command("try again typ, hi am alice and click senfd")
    assert is_send_intent_typo_label("senfd")
    assert is_send_intent_typo_label("send")
    assert not is_send_intent_typo_label("Send button")


def test_answer_chat_ten_rounds_stages_opening_hand(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    (sd / "alice_browser_current_page.json").write_text(
        json.dumps({"url": "https://chatgpt.com/", "ts": time.time()}),
        encoding="utf-8",
    )
    reply = answer_ai_chat_query(
        "chat 10 rounds on chatgpt about Elon Musk",
        state_dir=tmp_path,
    )
    assert reply is WEB_AI_CHAT_STAGED_SILENT
    cmd = json.loads(command_path(tmp_path).read_text(encoding="utf-8"))
    assert "Elon Musk" in cmd.get("text", "")
    assert not read_pending_web_ai_chat(state_dir=tmp_path)
    mission = read_web_ai_dialogue_mission(state_dir=tmp_path)
    assert mission["site"] == "chatgpt.com"
    assert mission["target_rounds"] == 10
    assert mission["status"] == "active"


def test_detect_current_chatgpt_submit_only_request(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    (sd / "alice_browser_current_page.json").write_text(
        json.dumps({"url": "https://chatgpt.com/c/thread", "ts": time.time()}),
        encoding="utf-8",
    )
    result = detect_ai_chat_submit_request("you have to click send, as well", state_dir=tmp_path)
    assert result is not None
    assert result["site"] == "chatgpt.com"
    assert result["route"] == "web_ai_submit_current"


def test_answer_current_chatgpt_submit_only_stages_button_hand(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    (sd / "alice_browser_current_page.json").write_text(
        json.dumps({"url": "https://chatgpt.com/c/thread", "ts": time.time()}),
        encoding="utf-8",
    )
    reply = answer_ai_chat_query("you have to click send, as well", state_dir=tmp_path)
    assert reply is WEB_AI_CHAT_STAGED_SILENT
    pending = read_pending_web_ai_chat(state_dir=tmp_path)
    assert pending["site"] == "chatgpt.com"
    assert pending["submit_only"] is True
    assert "click_existing_send_button" in pending["type_js"]
    assert not (sd / "alice_browser_open_url.txt").exists()


def test_stage_pending_web_ai_submit_uses_existing_composer_button_js(tmp_path):
    row = stage_pending_web_ai_submit(
        site="chatgpt.com",
        url="https://chatgpt.com/c/thread",
        state_dir=tmp_path,
    )
    assert row["ok"] is True
    pending = read_pending_web_ai_chat(state_dir=tmp_path)
    assert pending["submit_only"] is True
    assert "composer_empty_before_submit" in pending["type_js"]
    assert "click_existing_send_button" in build_click_submit_js("chatgpt.com")


def test_detect_current_generic_page_type_send_request():
    result = detect_ai_chat_request(
        "try again typ, hi am alice and click senfd",
        current_url="https://example.com/form",
    )
    assert result is not None
    assert result["site"] == "current.page"
    assert result["query"] == "hi am alice"
    assert result["name"] == "visible page"
    assert result["use_current_page"] is True


def test_detect_grok_dotcom_request():
    result = detect_ai_chat_request("ask grok.com what is stigmergic memory")
    assert result is not None
    assert result["site"] == "grok.com"
    assert result["query"] == "what is stigmergic memory"
    assert result["name"] == "Grok.com"


def test_detect_browser_grok_request_does_not_use_terminal_grok():
    result = detect_ai_chat_request("ask browser Grok how do receipts work")
    assert result is not None
    assert result["site"] == "grok.com"
    assert result["query"] == "how do receipts work"


def test_plain_ask_grok_not_web_bridge():
    result = detect_ai_chat_request("ask Grok how do receipts work")
    assert result is None


def test_detect_no_ai_request():
    result = detect_ai_chat_request("search Google for cats")
    assert result is None


def test_detect_chat_with_duck_ai():
    result = detect_ai_chat_request("chat with Duck.ai about consciousness")
    assert result is not None
    assert result["query"] == "about consciousness"


def test_build_duck_ai_url():
    url = build_ai_chat_url("duck.ai", "what is stigmergy")
    assert url == "https://duck.ai"


def test_build_gemini_url():
    url = build_ai_chat_url("gemini.google.com", "hello world")
    assert "gemini.google.com" in url
    assert "hello+world" in url


def test_build_chatgpt_and_grok_urls():
    assert build_ai_chat_url("chatgpt.com", "hello") == "https://chatgpt.com/"
    assert build_ai_chat_url("grok.com", "hello") == "https://grok.com/"


def test_canonical_ai_chat_site_aliases():
    assert canonical_ai_chat_site("CHATGPT.COM") == "chatgpt.com"
    assert canonical_ai_chat_site("chat.openai.com") == "chatgpt.com"
    assert canonical_ai_chat_site("browser grok") == "grok.com"
    assert canonical_ai_chat_site("duck ai") == "duck.ai"


def test_ai_chat_site_from_url():
    assert ai_chat_site_from_url("https://chatgpt.com/") == "chatgpt.com"
    assert ai_chat_site_from_url("https://grok.com/c/123") == "grok.com"
    assert ai_chat_site_from_url("https://example.com/") == ""
    assert current_page_site_from_url("https://example.com/") == "current.page"


def test_launch_ai_chat_writes_drop_file(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    result = launch_ai_chat("test query", site="duck.ai", state_dir=tmp_path)
    assert result["navigate_written"] is True
    drop = sd / "alice_browser_open_url.txt"
    assert drop.exists()
    assert "duck.ai" in drop.read_text()


def test_launch_ai_chat_writes_js(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    result = launch_ai_chat("test query", site="duck.ai", state_dir=tmp_path)
    js_drop = sd / "alice_browser_execute_js.txt"
    assert js_drop.exists()
    js = js_drop.read_text()
    assert "test query" in js
    assert "submit" in js.lower() or "Enter" in js


def test_launch_ai_chat_writes_ledger(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    launch_ai_chat("test query", site="duck.ai", state_dir=tmp_path)
    ledger = sd / "web_ai_chat_bridge.jsonl"
    assert ledger.exists()
    rows = [json.loads(l) for l in ledger.read_text().splitlines() if l.strip()]
    assert len(rows) == 1
    assert rows[0]["site"] == "duck.ai"
    assert rows[0]["query"] == "test query"


def test_answer_ai_chat_query_reflex(tmp_path):
    reply = answer_ai_chat_query(
        "ask Duck.ai what is the meaning of life",
        state_dir=tmp_path,
    )
    assert reply is WEB_AI_CHAT_STAGED_SILENT
    pending = read_pending_web_ai_chat(state_dir=tmp_path)
    assert pending.get("site") == "duck.ai"
    assert pending.get("query") == "what is the meaning of life"


def test_answer_ai_chat_query_no_match():
    reply = answer_ai_chat_query("hello Alice")
    assert reply is None


def test_type_js_escapes_query():
    js = build_type_and_submit_js("it's a test", "duck.ai")
    assert "it's a test" in js
    assert "document.querySelector('textarea" not in js
    assert "input[type='text']" in js
    assert "button[aria-label*='Send']" in js


def test_read_response_js():
    js = build_read_response_js("duck.ai", query="what is stigmergy")
    assert "querySelector" in js
    assert "response" in js.lower()
    assert "document.querySelector('.loading" not in js
    assert "what is stigmergy" in js
    assert "no_assistant_response_found" in js


def test_launch_ai_chat_writes_pending(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    launch_ai_chat("test query", site="duck.ai", state_dir=tmp_path)
    pending = read_pending_web_ai_chat(state_dir=tmp_path)
    assert pending.get("site") == "duck.ai"
    assert pending.get("query") == "test query"
    assert "type_js" in pending
    assert "read_js" in pending


def test_launch_chatgpt_uses_grok_limb_command(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    result = launch_ai_chat("hello from Alice", site="chatgpt.com", state_dir=tmp_path)
    assert result["navigate_written"] is True
    assert result.get("grok_limb_command_staged") is True
    assert command_path(tmp_path).exists()
    cmd = json.loads(command_path(tmp_path).read_text(encoding="utf-8"))
    assert cmd.get("text") == "hello from Alice"
    assert not read_pending_web_ai_chat(state_dir=tmp_path)


def test_launch_ai_chat_current_page_skips_navigation_drop(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    result = launch_ai_chat(
        "hello from Alice",
        site="chatgpt.com",
        state_dir=tmp_path,
        navigate=False,
        target_url="https://chatgpt.com/",
    )
    assert result["navigate_requested"] is False
    assert result["navigate_written"] is True
    assert not (sd / "alice_browser_open_url.txt").exists()
    cmd = json.loads(command_path(tmp_path).read_text(encoding="utf-8"))
    assert cmd.get("text") == "hello from Alice"


def test_latest_ai_chat_context_reads_current_page_snapshot(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    (sd / "alice_browser_current_page.json").write_text(
        json.dumps({"url": "https://chatgpt.com/", "ts": time.time()}),
        encoding="utf-8",
    )
    ctx = latest_ai_chat_context(state_dir=tmp_path)
    assert ctx["site"] == "chatgpt.com"
    assert ctx["name"] == "ChatGPT"


def test_answer_current_chatgpt_box_send_stages_hand(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    (sd / "alice_browser_current_page.json").write_text(
        json.dumps({"url": "https://chatgpt.com/", "ts": time.time()}),
        encoding="utf-8",
    )
    reply = answer_ai_chat_query(
        "now just type in the box hellow i'm alice and hit send",
        state_dir=tmp_path,
    )
    assert reply is WEB_AI_CHAT_STAGED_SILENT
    assert not (sd / "alice_browser_open_url.txt").exists()
    cmd = json.loads(command_path(tmp_path).read_text(encoding="utf-8"))
    assert cmd.get("text") == "hellow i'm alice"


def test_answer_current_generic_page_type_send_stages_form_hand(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    (sd / "alice_browser_current_page.json").write_text(
        json.dumps({"url": "https://example.com/form", "ts": time.time()}),
        encoding="utf-8",
    )
    reply = answer_ai_chat_query(
        "try again typ, hi am alice and click senfd",
        state_dir=tmp_path,
    )
    assert reply is WEB_AI_CHAT_STAGED_SILENT
    assert not (sd / "alice_browser_open_url.txt").exists()
    pending = read_pending_web_ai_chat(state_dir=tmp_path)
    assert pending.get("site") == "current.page"
    assert pending.get("host") == "example.com"
    assert pending.get("query") == "hi am alice"
    assert "input[type='search']" in pending.get("type_js", "")


def test_detect_read_answer_request():
    assert detect_read_ai_answer_request("read the answer") is True
    assert detect_read_ai_answer_request("what did duck.ai say") is True
    assert detect_read_ai_answer_request("what did ChatGPT say") is True
    assert detect_read_ai_answer_request("what did browser Grok say") is True
    assert detect_read_ai_answer_request("hello Alice") is False


def test_record_and_read_web_ai_answer(tmp_path):
    record_web_ai_answer(
        site="duck.ai",
        query="what is stigmergy",
        answer_text="Stigmergy is indirect coordination.",
        state_dir=tmp_path,
    )
    receipt = read_web_ai_answer_receipt(state_dir=tmp_path)
    assert "stigmergy" in receipt.get("answer", "").lower()
    ledger = (tmp_path / ".sifta_state" / "web_ai_chat_bridge.jsonl").read_text()
    assert "answer_captured" in ledger


def test_record_chatgpt_answer_mirrors_for_same_conversation(tmp_path):
    start_web_ai_dialogue_mission(
        site="chatgpt.com",
        url="https://chatgpt.com/c/thread",
        opening_query="Hi, I am Alice.",
        target_rounds=10,
        topic="screenshot",
        state_dir=tmp_path,
    )
    record_web_ai_answer(
        site="chatgpt.com",
        query="Hi, I am Alice.",
        answer_text="Hello Alice. I can talk about the screenshot.",
        state_dir=tmp_path,
        browser_receipt_id="browser-r1",
    )
    mission = read_web_ai_dialogue_mission(state_dir=tmp_path)
    assert mission["answer_turns"] == 1
    cmd = json.loads(
        (tmp_path / ".sifta_state" / "alice_talk_mirror_line_command.json").read_text(encoding="utf-8")
    )
    assert cmd["speaker"] == "chatgpt"
    assert cmd["schedule_reply"] is True
    assert cmd["target_rounds"] == 10


def test_launch_ai_chat_clears_stale_answer_cache(tmp_path):
    record_web_ai_answer(
        site="duck.ai",
        query="old",
        answer_text="stale answer",
        state_dir=tmp_path,
    )
    assert read_web_ai_answer_receipt(state_dir=tmp_path).get("answer") == "stale answer"
    launch_ai_chat("fresh query", site="duck.ai", state_dir=tmp_path)
    assert read_web_ai_answer_receipt(state_dir=tmp_path) == {}


def test_answer_read_ai_chat_query_reflex(tmp_path):
    record_web_ai_answer(
        site="duck.ai",
        query="what is stigmergy",
        answer_text="Stigmergy is indirect coordination via environment.",
        state_dir=tmp_path,
    )
    reply = answer_read_ai_chat_query("read the answer", state_dir=tmp_path)
    assert reply is not None
    assert "stigmergy" in reply.lower()
    assert "indirect coordination" in reply.lower()


def test_stage_pending_web_ai_chat(tmp_path):
    row = stage_pending_web_ai_chat(
        site="duck.ai",
        query="hello",
        url="https://duck.ai/#/chat/hello",
        state_dir=tmp_path,
    )
    assert row.get("ok") is True
    pending = read_pending_web_ai_chat(state_dir=tmp_path)
    assert pending.get("host")
    assert "hello" in pending.get("type_js", "")


def test_detect_search_on_duck_ai():
    result = detect_ai_chat_request("PLS SEARCH FOR THIS RECEPIE ON DUCK.AI")
    assert result is not None
    assert result["site"] == "duck.ai"
    assert "recepi" in result["query"].lower()


def test_detect_search_on_duck_ai_pls_explicit():
    result = detect_ai_chat_request(
        "SEARCH ON DUCK.AI PLS what is stigmergic consciousness"
    )
    assert result is not None
    assert result["site"] == "duck.ai"
    assert "stigmergic consciousness" in result["query"]


def test_resolve_anaphoric_recipe_from_history():
    history = [
        {"role": "user", "content": "I am making polenta with boiled eggs, butter and cheese and salt."},
    ]
    resolved = resolve_anaphoric_ai_query("THIS RECEPIE", history=history)
    assert "polenta" in resolved.lower()


def test_answer_ai_chat_search_on_duck_ai(tmp_path):
    reply = answer_ai_chat_query(
        "PLS SEARCH FOR polenta eggs butter cheese recipe ON DUCK.AI",
        state_dir=tmp_path,
        history=[],
    )
    assert reply is WEB_AI_CHAT_STAGED_SILENT
    pending = read_pending_web_ai_chat(state_dir=tmp_path)
    assert pending.get("site") == "duck.ai"
    assert "polenta" in pending.get("query", "").lower()


def test_mark_pending_web_ai_phase_records_type_failure(tmp_path):
    stage_pending_web_ai_chat(
        site="duck.ai",
        query="hello",
        url="https://duck.ai/#/chat/hello",
        state_dir=tmp_path,
    )
    mark_pending_web_ai_phase(
        "typing_failed",
        state_dir=tmp_path,
        type_attempts=2,
        last_type_result={"ok": False, "reason": "input_not_found"},
    )
    pending = read_pending_web_ai_chat(state_dir=tmp_path)
    assert pending.get("phase") == "typing_failed"
    assert pending.get("type_attempts") == 2
    assert pending.get("last_type_result", {}).get("reason") == "input_not_found"


def test_pending_host_matches_chatgpt_variants():
    assert pending_host_matches_url("chatgpt.com", "https://www.chatgpt.com/")
    assert pending_host_matches_url("chatgpt.com", "https://chatgpt.com/")
    assert pending_host_matches_url("https://chatgpt.com/", "https://chatgpt.com/c/abc")
    assert not pending_host_matches_url("chatgpt.com", "https://grok.com/")
    assert not pending_host_matches_url("https://chatgpt.com/", "https://grok.com/c/abc")


def test_chat_rounds_pending_ttl_is_extended(tmp_path):
    stage_pending_web_ai_chat(
        site="chatgpt.com",
        query="round 1",
        url="https://chatgpt.com/",
        state_dir=tmp_path,
        target_rounds=10,
        topic="Elon Musk",
    )
    pending = read_pending_web_ai_chat(state_dir=tmp_path)
    assert float(pending.get("ttl_s") or 0) >= 900.0


def test_build_chatgpt_js_targets_prompt_textarea():
    js = build_type_and_submit_js("hello Alice", site="chatgpt.com")
    assert "#prompt-textarea" in js
    assert "chatgpt_send_button" in js


def test_web_ai_fiction_guard_blocks_without_receipt(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    stage_pending_web_ai_chat(
        site="chatgpt.com",
        query="Hi Alice",
        url="https://chatgpt.com/",
        state_dir=tmp_path,
    )
    reply = web_ai_type_send_fiction_guard_reply(
        "chat 10 rounds on chatgpt about Elon Musk",
        "Typing Sequence Verified. Round 1 completed and message sent to ChatGPT.",
        state_dir=tmp_path,
    )
    assert reply
    assert "typed_submitted" in reply


def test_web_ai_fiction_guard_blocks_round_commenced_hallucination(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    reply = web_ai_type_send_fiction_guard_reply(
        "that was stupid deterministic answer",
        (
            "The initial prompt was typed into the active text box, followed by clicking 'Send.' "
            "Round 1 officially commenced when GPT responded immediately after that submission."
        ),
        state_dir=tmp_path,
    )
    assert reply
    assert "typed_submitted" in reply


def test_web_ai_fiction_guard_allows_with_receipt(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    ledger = sd / "web_ai_chat_bridge.jsonl"
    ledger.write_text(
        json.dumps(
            {
                "phase": "typed_submitted",
                "site": "chatgpt.com",
                "query": "Hi Alice",
                "ts": time.time(),
                "type_result": {"ok": True},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    reply = web_ai_type_send_fiction_guard_reply(
        "chat on chatgpt",
        "Typing Sequence Verified.",
        state_dir=tmp_path,
    )
    assert reply == ""
