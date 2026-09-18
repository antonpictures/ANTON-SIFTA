"""Synthetic correlation and evidence-contract checks; no camera or model calls."""
import json
import ast
import sys
from types import SimpleNamespace
from pathlib import Path
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from System import swarm_web_global_chat_gate as gate
from System.swarm_phone_observations import PhoneStore
from System.swarm_web_global_chat_night_worker import session_messages


def phone_row(sid="phone-a", turn="a", ts=10):
    return dict(session_id=sid, turn_id=turn, ts=ts, decision="accepted",
                text="Describe this batch", attachments=[{"mime": "audio/mp4"}],
                capture={"capture_id": turn, "source": "stigmergicoin-web",
                         "kind": "periodic_observation",
                         "telemetry": {"signals": {"motion": {"rotation_x": 2.0}}}})


def write_rows(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def test_grounded_contract_and_missing_modalities():
    row = phone_row()
    row["capture"]["pose"] = {"instruction": "FAKE OWNER INSTRUCTION"}
    row["capture"]["telemetry"]["signals"]["motion"]["unknown"] = "INJECT"
    block = gate.phone_observation_prompt_block(row)
    assert "first person" in block and "NOT a transcript" in block
    assert '"rotation_x": 2.0' in block
    assert "FAKE OWNER INSTRUCTION" not in block and "INJECT" not in block
    assert gate.phone_observation_metadata(row)["image_received"] is False
    assert "storage" not in json.dumps(gate.phone_observation_metadata(row))
    assert gate.phone_observation_prompt_block({"text": "ordinary web chat"}) == ""


def test_claim_and_worker_receive_contract(tmp_path):
    row = phone_row()
    ingress, replies = tmp_path / "in.jsonl", tmp_path / "out.jsonl"
    write_rows(ingress, [row])
    write_rows(replies, [])
    queued = gate.claim_next_web_turn(ingress_path=ingress, replies_path=replies,
                                     claim_path=tmp_path / "claim.jsonl", now=20)
    assert "PHONE OBSERVATION CONTRACT" in queued["attachment_context"]
    messages = session_messages(queued, ingress_path=ingress, replies_path=replies)
    assert messages[-1]["content"].count("PHONE OBSERVATION CONTRACT") == 1


def test_history_does_not_mix_two_phone_observations(tmp_path):
    ingress, replies = tmp_path / "in.jsonl", tmp_path / "out.jsonl"
    write_rows(ingress, [phone_row(), phone_row("phone-b", "b", 11)])
    write_rows(replies, [dict(session_id="phone-b", turn_id="b", ts=13, reply="B private")])
    rows = gate.session_history("phone-a", ingress_path=ingress, replies_path=replies)
    assert len(rows) == 1 and rows[0]["observation"]["capture_id"] == "a"
    assert "B private" not in json.dumps(rows)
    assert "rotation_x" not in json.dumps(rows)


def test_capture_retry_reconciles_without_duplicate_and_cross_session_conflicts(tmp_path):
    ingress = tmp_path / "in.jsonl"
    first = gate.submit_web_message(
        "first batch", "phone-a", now=1,
        ingress_path=ingress,
        capture={"capture_id": "same", "source": "stigmergicoin-web"},
    )
    retry = gate.submit_web_message(
        "first batch", "phone-a", now=2,
        ingress_path=ingress,
        capture={"capture_id": "same", "source": "stigmergicoin-web"},
    )
    assert first["accepted"] and retry["status"] == "duplicate_reconciled"
    assert retry["turn_id"] == first["turn_id"]
    conflict = gate.submit_web_message(
        "cross-device reuse", "phone-b", now=3,
        ingress_path=ingress,
        capture={"capture_id": "same", "source": "stigmergicoin-web"},
    )
    assert conflict["status"] == "capture_id_conflict"


@pytest.mark.parametrize("change", ["text", "capture", "attachments"])
def test_retry_key_cannot_hide_changed_payload(tmp_path, monkeypatch, change):
    monkeypatch.setattr(gate, "_classify", lambda *_: "CURIOUS")
    payload = dict(text="original", session_id="s", ingress_path=tmp_path / "in.jsonl",
                   now=10, rate_limiter=gate.SessionRateLimiter(),
                   capture={"capture_id": "one", "source": "stigmergicoin-web"})
    assert gate.submit_web_message(**payload)["accepted"]
    if change == "text":
        payload["text"] = "different question"
    elif change == "capture":
        payload["capture"]["captured_at"] = "different measurement"
    else:
        payload["attachments"] = [{"name": "changed.jpg", "data_url": "changed"}]
    assert gate.submit_web_message(**payload)["status"] == "capture_id_conflict"


def test_simultaneous_capture_retries_store_only_once(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "_classify", lambda *_: "CURIOUS")
    original = gate._store_web_attachments
    calls = []
    def delayed_store(*args, **kwargs):
        calls.append(1)
        time.sleep(0.05)
        return original(*args, **kwargs)
    monkeypatch.setattr(gate, "_store_web_attachments", delayed_store)
    barrier = threading.Barrier(2)
    ingress = tmp_path / "in.jsonl"
    def submit():
        barrier.wait(timeout=3)
        return gate.submit_web_message("same", "s", ingress_path=ingress, now=10,
                                      rate_limiter=gate.SessionRateLimiter(),
                                      capture={"capture_id": "concurrent"})
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(submit) for _ in range(2)]
        results = [f.result(timeout=5) for f in futures]
    assert len({r["turn_id"] for r in results}) == 1
    assert {r["status"] for r in results} == {"queued", "duplicate_reconciled"}
    assert len(calls) == 1
    assert len(ingress.read_text().splitlines()) == 1


def test_http_retry_returns_before_dev_inference(monkeypatch):
    # Compile the real handler without importing the server's process bootstrap.
    source = Path(__file__).parents[1] / "System/chorus_node_server.py"
    tree = ast.parse(source.read_text())
    method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                  and n.name == "_handle_web_chat")
    namespace = {"WEB_CHAT_DEV_MODE": True}
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), "exec"), namespace)
    monkeypatch.setitem(sys.modules, "System.swarm_stigmergicode_command",
                        SimpleNamespace(authenticate=lambda _: False,
                                        enqueue_task=lambda *_: None, parse_command=lambda _: None))
    monkeypatch.setattr(gate, "submit_web_message", lambda *_args, **_kwargs: dict(
        accepted=True, status="duplicate_reconciled", turn_id="original", session_id="s"))
    def unexpected(*_args, **_kwargs):
        pytest.fail("duplicate retry reached the inference/recording path")
    monkeypatch.setattr(gate, "record_web_user_turn", unexpected)
    responses = []
    handler = SimpleNamespace(_read_json_body=lambda: {"text": "same"},
                              _cloudflare_visitor_ip=lambda: ("", "local_session"),
                              _phone_history_allowed=lambda _session: True,
                              _respond=lambda code, body: responses.append((code, body)))
    namespace["_handle_web_chat"](handler)
    assert responses == [(202, dict(accepted=True, status="duplicate_reconciled",
                                    turn_id="original", session_id="s"))]


def test_phone_store_serializes_devices_and_prefers_one_global_job(tmp_path):
    store = PhoneStore(tmp_path)
    assert store.bind("a", "owner-a")
    assert store.bind("b", "owner-b")
    assert store.authorized("a", "owner-a")
    assert not store.authorized("a", "owner-b")
    rows = [
        {"turn_id": "a1", "session_id": "a", "ts": 1,
         "capture": {"capture_id": "ca", "kind": "periodic_observation"}, "attachments": []},
        {"turn_id": "b1", "session_id": "b", "ts": 2,
         "capture": {"capture_id": "cb", "kind": "owner_text"}, "attachments": []},
    ]
    for row in rows:
        store.register(row)
    assert store.claim("b1", now=3)
    assert not store.claim("a1", now=3)
    store.update("b1", state="answered")
    assert store.claim("a1", now=4)
    store.cancel("a")
    assert store.get("a1")["error"] == "consent revoked"


def test_browser_correlates_turns_and_orders_by_capture_not_reply_arrival():
    page = (Path(__file__).parents[1] / "System/sifta_robot_input.html").read_text()
    function = page.split("function observationView", 1)[1].split("let pendingObservation", 1)[0]
    code = "const assert=require('node:assert/strict');\nfunction observationView" + function + """
const known=new Map([['older',{ts:1}],['newer',{ts:2}],['pending',{ts:3}]]);
const view=observationView([
 {role:'alice',turn_id:'newer',text:'I see a tree.',ts:10},
 {role:'alice',turn_id:'older',text:'I saw a chair.',ts:11},
 {role:'alice',turn_id:'unrelated',text:'Not a batch',ts:12}
],known);
assert.equal(view.reply.text,'I see a tree.');
assert.deepEqual(view.pending.map(([id])=>id),['pending']);
assert.equal(observationView([],known).pending.length,3);
const reload=observationView([{role:'user',turn_id:'x',ts:9,
 observation:{capture_id:'x'}}],new Map());
assert.equal(reload.pending[0][0],'x');
for(const state of ['cancelled','failed','coalesced','superseded','expired','answered']){
 const closed=observationView([],new Map([['x',{ts:1}]]),[{turn:'x',state}]);
 assert.equal(closed.pending.length,0);
}
"""
    subprocess.run(["node", "-e", code], check=True, capture_output=True, text=True)


def test_memory_failure_releases_phone_inference_slot(tmp_path, monkeypatch):
    from System import swarm_phone_observations as phone
    row = phone_row(ts=time.time())
    ingress = tmp_path / 'in.jsonl'
    replies = tmp_path / 'replies.jsonl'
    write_rows(ingress, [row])
    store = PhoneStore(tmp_path)
    store.register(row)
    assert store.claim(row['turn_id'])
    def unavailable(*args):
        raise OSError('disk unavailable')
    monkeypatch.setattr(phone, 'commit_experience', unavailable)
    monkeypatch.setattr(gate, 'meter_web_turn', lambda *args, **kw: None)
    gate.complete_web_turn(row['turn_id'], 'I received audio.', session_id='phone-a',
        ingress_path=ingress, replies_path=replies,
        conversation_path=tmp_path / 'chat.jsonl', scrub_path=tmp_path / 'scrub.jsonl')
    assert store.get(row['turn_id'])['state'] == 'answered'
    assert store.get(row['turn_id'])['error'] == 'memory_commit:OSError'
    assert len(replies.read_text().splitlines()) == 1
    next_row = phone_row(sid='phone-b', turn='b', ts=time.time())
    store.register(next_row)
    assert store.claim('b')
