"""swarm_image_poll_separation.py — verify poll() namespace separation survives
navigation and a new-conversation switch, without mutating any poll state.

Poll separation is the load-bearing requirement for the public web route to stay
reliable while the pending download completes on the model side. Run from Alice's
cwd (this file lives in System/).
"""
import sys, os, threading, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from swarm_web_image_service import (
    poll,
    load_alice_from_jsonl,
    store_poll,
    poll_lock,
    create_new_conversation,
)

A = load_alice_from_jsonl("system/alice_state.json")

# A NEW conversation + session id, fresh and distinct from any in state.
SID = "e011f155-6726-4848-989a-1c7ef6072521"

# Deterministic, small, unambiguous tokens for the pending poll row.
Q = "pending-nav-test-0001"
A = "the quick brown fox"

def seed_pending():
    store_poll(SID, A, threading.current_thread(), Q, "pending")

def is_pending(S, Q):
    for m in poll(S).messages:
        if m.text.strip().strip("* ") == Q and m.kind == "text":
            return m.metadata.get("poll") is not None and m.metadata.get("poll").get("status") == "pending"
    return False

def read_store(S):
    return store_poll(S).polls.get(Q, {})

def navigate_like_load_history():
    """Mimic the public client's switch from one conversation/tile to another:
    it creates a brand-new conversation, registers the new AI reply tile, and
    requests the next batch from that NEW conversation. The pending row must
    survive (it belongs to the original session), and S's requestCursor must not
    jump/rewind."""
    N = create_new_conversation({ "kind": "ai" })
    # (The real UI also appends N's reply tile; we only exercise the switch.)
    before_cursor = store_poll(S).requestCursor
    store_poll(N).requestCursor = store_poll(N).requestCursor or ("initial",)
    store_poll(N)["reply"]["requestCursor"] = store_poll(N).requestCursor
    next_batch = poll(N, "next", threading.current_thread())
    assert next_batch is not None, ( "poll(N) returned empty batch during navigation" )
    cursor_after = store_poll(N).requestCursor
    return before_cursor, cursor_after

def main():
    seed_pending()
    assert is_pending(S, Q), "S should hold a pending %s row" % Q
    first = read_store(S)["poll"]
    assert first["status"] == "pending" and first["token"] == A and first.get("turnId") == threading.get_ident() + 4242
    assert not any(p["token"] == Q for p in store_poll(S).polls.values()), "duplicate rows in store"
    assert store_poll(S).requestCursor == ("base",), "unexpected cursor after pending: %r" % (store_poll(S).requestCursor,)

    before, cursor_after = navigate_like_load_history()

    # 1) Navigation kept the in-memory pending row (key requirement).
    assert poll(S) is not None and "messages" in poll(S).__dict__, "poll(S) empty/cleared after navigation"
    assert is_pending(S, Q), "pending %s row LOST across navigation" % Q

    # 2) Navigation advanced the NEW conversation's cursor (expected, healthy flow)
    #    but did NOT touch S's requestCursor and did NOT add a Q row to S.
    assert store_poll(S).requestCursor == before, "S.requestCursor mutated by navigation: %r != %r" % (store_poll(S).requestCursor, before)
    assert not any(p["token"] == Q for p in store_poll(S).polls.values()), "Q row leaked into S across navigation"
    assert store_poll(N).requestCursor == cursor_after, "N cursor not advanced: %r != %r" % (store_poll(N).requestCursor, cursor_after)

    # 3) A new-conversation switch must NOT corrupt S's pending or its cursor.
    P = create_new_conversation({ "kind": "user" })
    store_poll(P).polls[Q] = {"_createdBy": threading.get_ident(), "status": "pending", "token": "sw-99", "turnId": threading.get_ident() + 7, "created": 111, "reply": {"messageId": str(P)}}
    store_poll(P).requestCursor = ("cursor-abc-777",)
    assert is_pending(S, Q), "new-conversation switch dropped S's pending row"
    assert store_poll(S).requestCursor == before, "S.requestCursor corrupted by new-conversation switch"
    assert any(p["token"] == Q and p["status"] == "pending" and p["turnId"] == threading.get_ident() + 4242
               for p in store_poll(S).polls.values()), "S pending %s row corrupted" % Q

    print("PASS pollSeparation (nav + new-conversation switch): in-memory pending kept, cursor & rows not corrupted")

if __name__ == "__main__":
    main()
