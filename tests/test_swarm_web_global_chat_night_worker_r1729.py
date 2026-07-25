"""R1729 overnight WEB TYPED availability regressions."""
from __future__ import annotations

import json
import plistlib
from pathlib import Path

from System.swarm_web_global_chat_gate import (
    claim_next_web_turn,
    complete_web_turn,
    submit_web_message,
)
from System import swarm_web_global_chat_night_worker as worker


def _rows(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_claim_is_leased_then_recoverable_and_answered_turn_stays_closed(tmp_path):
    ingress = tmp_path / "ingress.jsonl"
    claims = tmp_path / "claims.jsonl"
    replies = tmp_path / "replies.jsonl"
    queued = submit_web_message("hello overnight", "s", now=90, ingress_path=ingress)
    first = claim_next_web_turn(
        ingress_path=ingress,
        claim_path=claims,
        replies_path=replies,
        consumer_id="talk",
        lease_s=180,
        now=100,
    )
    assert first["turn_id"] == queued["turn_id"]
    assert claim_next_web_turn(
        ingress_path=ingress,
        claim_path=claims,
        replies_path=replies,
        consumer_id="night",
        now=101,
    ) is None
    recovered = claim_next_web_turn(
        ingress_path=ingress,
        claim_path=claims,
        replies_path=replies,
        consumer_id="night",
        now=500,
    )
    assert recovered["turn_id"] == queued["turn_id"]
    assert _rows(claims)[-1]["consumer_id"] == "night"
    complete_web_turn(
        queued["turn_id"],
        "Answered.",
        session_id="s",
        replies_path=replies,
        conversation_path=tmp_path / "conversation.jsonl",
        metabolism_path=tmp_path / "metabolism.jsonl",
        scrub_path=tmp_path / "scrub.jsonl",
    )
    assert claim_next_web_turn(
        ingress_path=ingress,
        claim_path=claims,
        replies_path=replies,
        consumer_id="night",
        now=900,
    ) is None


def test_legacy_claim_expires_instead_of_poisoning_turn_forever(tmp_path):
    ingress = tmp_path / "ingress.jsonl"
    claims = tmp_path / "claims.jsonl"
    replies = tmp_path / "replies.jsonl"
    queued = submit_web_message("legacy crash", "s", now=90, ingress_path=ingress)
    claims.write_text(
        json.dumps({"ts": 100, "turn_id": queued["turn_id"]}) + "\n",
        encoding="utf-8",
    )
    assert claim_next_web_turn(
        ingress_path=ingress,
        claim_path=claims,
        replies_path=replies,
        consumer_id="night",
        now=200,
    ) is None
    recovered = claim_next_web_turn(
        ingress_path=ingress,
        claim_path=claims,
        replies_path=replies,
        consumer_id="night",
        now=401,
    )
    assert recovered["turn_id"] == queued["turn_id"]
    assert _rows(claims)[-1]["truth_label"] == "WEB_TYPED_CLAIM_V2"


def test_web_turns_bypass_owner_schedule_and_whatsapp_shortcuts():
    source = (
        Path(__file__).parents[1] / "Applications" / "sifta_talk_to_alice_widget.py"
    ).read_text(encoding="utf-8")
    assert "if _wa_explicit and chat_reflexes_enabled" in source
    assert "answer_query_for_alice(text)\n            except Exception" in source
    assert "_whatsapp_reschedule_reply(text) if chat_reflexes_enabled" in source
    assert "_schedule_query_reply(text) if chat_reflexes_enabled" in source
    assert "_schedule_add_parse(text) if chat_reflexes_enabled" in source


def test_night_worker_waits_for_talk_grace(tmp_path):
    ingress = tmp_path / "ingress.jsonl"
    queued = submit_web_message("fresh", "s", now=100, ingress_path=ingress)
    assert claim_next_web_turn(
        ingress_path=ingress,
        claim_path=tmp_path / "claims.jsonl",
        replies_path=tmp_path / "replies.jsonl",
        consumer_id="night",
        min_age_s=8,
        now=105,
    ) is None
    claimed = claim_next_web_turn(
        ingress_path=ingress,
        claim_path=tmp_path / "claims.jsonl",
        replies_path=tmp_path / "replies.jsonl",
        consumer_id="night",
        min_age_s=8,
        now=109,
    )
    assert claimed["turn_id"] == queued["turn_id"]


def test_answer_uses_zero_authority_prompt_and_binds_ollama_stamp(tmp_path, monkeypatch):
    from System import swarm_kv_cache_continuity

    ingress = tmp_path / "ingress.jsonl"
    replies = tmp_path / "replies.jsonl"
    queued = submit_web_message("Who are you?", "night-session", now=1, ingress_path=ingress)
    seen = []

    def fake_turn(model, messages, *, timeout_s):
        seen.append({"model": model, "messages": messages, "timeout_s": timeout_s})
        return {
            "message": {"content": "I am Alice, awake through the public text lane."},
            "done_reason": "stop",
            "prompt_eval_count": 41,
            "eval_count": 12,
            "load_duration": 10,
            "prompt_eval_duration": 20,
            "eval_duration": 30,
        }

    monkeypatch.setattr(worker, "_ollama_turn", fake_turn)
    monkeypatch.setattr(swarm_kv_cache_continuity, "_STATE", tmp_path / "state")
    reply, model, stamp, reason = worker.answer_web_turn(
        queued,
        model="local-test",
        ingress_path=ingress,
        replies_path=replies,
    )
    system = seen[0]["messages"][0]["content"]
    assert reply.endswith("lane.") and model == "local-test" and reason == "STOP"
    assert "zero owner authority" in system
    assert "Do not execute effectors" in system
    assert stamp["prompt_eval_count"] == 41 and stamp["eval_count"] == 12
    assert stamp["truth_label"] == "KV_CACHE_RESIDENCY_V1"


def test_night_worker_launchagent_keeps_system_not_display_awake():
    path = Path(__file__).parents[1] / "launchd" / "com.sifta.web-global-chat-night-worker.plist"
    data = plistlib.loads(path.read_bytes())
    args = data["ProgramArguments"]
    assert data["KeepAlive"] is True and data["RunAtLoad"] is True
    assert args[:2] == ["/usr/bin/caffeinate", "-ims"]
    assert "-d" not in args
    assert args[-1].endswith("swarm_web_global_chat_night_worker.py")
    assert "--token" not in args
