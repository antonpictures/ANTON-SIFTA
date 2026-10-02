"""W5 test: repair-stale-claims self-healing pass."""
from pathlib import Path
import sys
import json
import time
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_repair_stale_claims_importable():
    from System.swarm_web_global_chat_gate import repair_stale_claims
    import inspect
    sig = inspect.signature(repair_stale_claims)
    assert "max_age_s" in sig.parameters


def test_repair_fixes_claimed_turn_without_reply():
    from System.swarm_web_global_chat_gate import repair_stale_claims
    from System import swarm_web_global_chat_night_worker as nw
    import shutil
    import os
    # Backup original ledger
    claims_path = nw.STATE_DIR / "web_global_chat_claims.jsonl"
    replies_path = nw.STATE_DIR / "web_global_chat_replies.jsonl"
    if not claims_path.exists():
        return  # nothing to repair
    
    orig_claims = claims_path.read_text()
    orig_replies = replies_path.read_text() if replies_path.exists() else ""
    
    try:
        # Seed: a claimed turn with no reply
        now = time.time()
        stale_ts = now - 1000.0  # stale by 1000s
        stale_turn = "stale_turn_" + str(int(now))
        
        # Add stale claim
        claim = {"turn_id": stale_turn, "ts": stale_ts, "claimed": True}
        with open(claims_path, "a") as f:
            f.write(json.dumps(claim) + "\n")
        
        # Ensure no reply exists
        replies = [r for r in (replies_path.read_text().strip().splitlines() if replies_path.exists() else []) if r.strip()]
        has_reply = any(stale_turn in r for r in replies)
        assert not has_reply, "test precondition: no reply for stale turn"
        
        # Run repair with max_age_s=900 (stale_ts is 1000s old)
        result = repair_stale_claims(max_age_s=900)
        
        # Verify: a reply row now exists for the turn
        replies = [json.loads(r) for r in replies_path.read_text().strip().splitlines()] if replies_path.exists() else []
        reply = next((r for r in replies if r.get("turn_id") == stale_turn), None)
        assert reply is not None, f"repair should have created a reply row for {stale_turn}"
        assert "WEB_TYPED_REPLY" in reply.get("event", "")
        
        # Run again: should be idempotent (no duplicate replies)
        result2 = repair_stale_claims(max_age_s=900)
        replies2 = [json.loads(r) for r in replies_path.read_text().strip().splitlines()] if replies_path.exists() else []
        replies_to_turn = [r for r in replies2 if r.get("turn_id") == stale_turn]
        assert len(replies_to_turn) == 1, "repair should be idempotent, no duplicate"
        
    finally:
        # Restore original state
        claims_path.write_text(orig_claims)
        if orig_replies:
            replies_path.write_text(orig_replies)


def test_repair_not_repaired_when_claim_is_new():
    from System.swarm_web_global_chat_gate import repair_stale_claims
    from System import swarm_web_global_chat_night_worker as nw
    import shutil
    import os
    claims_path = nw.STATE_DIR / "web_global_chat_claims.jsonl"
    replies_path = nw.STATE_DIR / "web_global_chat_replies.jsonl"
    if not claims_path.exists():
        return
    
    orig_claims = claims_path.read_text()
    orig_replies = replies_path.read_text() if replies_path.exists() else ""
    
    try:
        # Seed: a fresh claimed turn (not stale)
        now = time.time()
        fresh_turn = "fresh_turn_" + str(int(now))
        fresh_claim = {"turn_id": fresh_turn, "ts": now, "claimed": True}
        with open(claims_path, "a") as f:
            f.write(json.dumps(fresh_claim) + "\n")
        
        # Run repair with max_age_s=900 (fresh turn should NOT be repaired)
        result = repair_stale_claims(max_age_s=900)
        
        # Verify: no reply was created for fresh turn
        replies = [json.loads(r) for r in replies_path.read_text().strip().splitlines()] if replies_path.exists() else []
        fresh_reply = next((r for r in replies if r.get("turn_id") == fresh_turn), None)
        assert fresh_reply is None, "repair should not touch fresh claims"
        
    finally:
        claims_path.write_text(orig_claims)
        if orig_replies:
            replies_path.write_text(orig_replies)


if __name__ == "__main__":
    test_repair_stale_claims_importable()
    test_repair_fixes_claimed_turn_without_reply()
    test_repair_not_repaired_when_claim_is_new()
    print("W5 repair-stale-claims test: OK")