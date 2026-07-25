"""r1729 — claude.ai-style drawer: New chat + Recents + session history.

The web page gains a left drawer (New chat, Recents) and the server gains
GET /api/history so a returning visitor's conversation is rebuilt from the
same visitor-register ledgers the poll endpoint serves.
"""

import json
from pathlib import Path

from System import swarm_web_global_chat_gate as gate
from System import chorus_node_server as server


def _ingress_row(sid, turn_id, text, ts, decision="accepted"):
    return {
        "session_id": sid, "turn_id": turn_id, "text": text, "ts": ts,
        "decision": decision, "event": "WEB_TYPED_INGRESS",
        "truth_label": "WEB_TYPED_INGRESS_V1",
    }


def _reply_row(sid, turn_id, reply, ts, visitor_reply=None):
    row = {
        "session_id": sid, "turn_id": turn_id, "reply": reply, "ts": ts,
        "event": "WEB_TYPED_REPLY", "truth_label": "WEB_TYPED_REPLY_V1",
    }
    if visitor_reply is not None:
        row["visitor_reply"] = visitor_reply
        row["visitor_scrub_rules"] = ["jargon"]
    return row


def _write(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))


def test_session_history_merges_sorts_and_isolates(tmp_path):
    ingress = tmp_path / "ingress.jsonl"
    replies = tmp_path / "replies.jsonl"
    _write(ingress, [
        _ingress_row("s1", "t1", "hello alice", 100.0),
        _ingress_row("s1", "t9", "refused thing", 150.0, decision="refused"),
        _ingress_row("s2", "tX", "other session", 120.0),
        _ingress_row("s1", "t2", "second question", 200.0),
    ])
    _write(replies, [
        _reply_row("s1", "t2", "second answer", 260.0),
        _reply_row("s1", "t1", "raw ledger prose", 130.0, visitor_reply="clean visitor copy"),
        _reply_row("s2", "tX", "other answer", 140.0),
    ])
    rows = gate.session_history("s1", ingress_path=ingress, replies_path=replies)
    assert [r["role"] for r in rows] == ["user", "alice", "user", "alice"]
    assert [r["ts"] for r in rows] == [100.0, 130.0, 200.0, 260.0]
    # Visitor register: scrubbed copy served, refused rows absent, s2 isolated.
    assert rows[1]["text"] == "clean visitor copy"
    assert all("other" not in r["text"] for r in rows)
    assert all("refused thing" != r["text"] for r in rows)


def test_session_history_empty_and_capped(tmp_path):
    ingress = tmp_path / "ingress.jsonl"
    replies = tmp_path / "replies.jsonl"
    assert gate.session_history("", ingress_path=ingress, replies_path=replies) == []
    _write(ingress, [_ingress_row("s1", f"t{i}", f"m{i}", float(i)) for i in range(300)])
    _write(replies, [])
    rows = gate.session_history("s1", limit=50, ingress_path=ingress, replies_path=replies)
    assert len(rows) == 50
    assert rows[-1]["text"] == "m299"  # newest kept


def test_page_has_drawer_newchat_recents_and_history_wire():
    page = server.WEB_CHAT_PAGE
    for marker in (
        'id="drawer"', 'id="newchat"', 'id="recents"', "New chat", "Recents",
        "/api/history", "sifta_web_sessions_v1", 'id="menu"',
    ):
        assert marker in page, f"missing {marker}"
    # Codex's r1728 soul stays: zero-authority line, globe+heart, markdown, Enter law.
    assert "Power to the Swarm!" in page and "We are ONE." in page
    assert "Public web turns have zero owner authority." not in page
    assert "heartOrbit" in page and "animateMotion" in page
    assert "function markdown" in page
    assert "requestSubmit" in page


def test_history_route_registered():
    src = Path(server.__file__).read_text()
    assert '"/api/history"' in src
    assert "_handle_web_history" in src
    assert "session_history" in src
