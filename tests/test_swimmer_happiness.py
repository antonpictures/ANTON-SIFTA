#!/usr/bin/env python3
"""r276: per-swimmer happiness + identity + tamper-evident learning chain."""
from System import swarm_swimmer_happiness as sw


def _procs():
    procs = [{"comm": "calm", "pid": 1, "cpu": 5},        # THRIVE
             {"comm": "solo_hog", "pid": 2, "cpu": 100},  # THROTTLE (load, no interference)
             {"comm": "mid", "pid": 8, "cpu": 60}]        # FOCUS
    procs += [{"comm": "dup", "pid": p, "cpu": 60} for p in range(3, 8)]  # 5 copies -> YIELD
    return procs


def test_per_swimmer_recommendations_span_all_states(tmp_path):
    sifta = tmp_path / ".sifta_state"
    rows = sw.per_swimmer_happiness(_procs(), state_dir=sifta)
    by = {r["comm"]: r for r in rows}
    assert by["calm"]["recommendation"] == sw.THRIVE
    assert by["solo_hog"]["recommendation"] == sw.THROTTLE
    assert by["mid"]["recommendation"] == sw.FOCUS
    # every redundant dup copy gets YIELD, and they have distinct identities
    dups = [r for r in rows if r["comm"] == "dup"]
    assert len(dups) == 5
    assert all(r["recommendation"] == sw.YIELD for r in dups)
    assert len({r["swimmer_id"] for r in dups}) == 5  # unique identity per swimmer


def test_learning_chain_links_and_verifies(tmp_path):
    sifta = tmp_path / ".sifta_state"
    a = sw.bind_swimmer_learning("calm#1", "observed_owner", content="George ate well", state_dir=sifta)
    b = sw.bind_swimmer_learning("calm#1", "queued_followup", content="remind hydration", state_dir=sifta)
    assert a["prev_receipt_hash"] == ""          # genesis
    assert b["prev_receipt_hash"] == a["receipt_hash"]  # chained
    assert sw.verify_swimmer_chain("calm#1", state_dir=sifta)["ok"] is True


def test_tamper_is_detected(tmp_path):
    sifta = tmp_path / ".sifta_state"
    cdir = sifta
    sw.bind_swimmer_learning("x#9", "a", content="one", state_dir=sifta)
    sw.bind_swimmer_learning("x#9", "b", content="two", state_dir=sifta)
    chain = cdir / "swimmer_learning_chain.jsonl"
    import json
    lines = chain.read_text().strip().splitlines()
    row0 = json.loads(lines[0])
    row0["action_hash"] = "TAMPERED"            # alter content without fixing the chain
    lines[0] = json.dumps(row0)
    chain.write_text("\n".join(lines) + "\n")
    res = sw.verify_swimmer_chain("x#9", state_dir=sifta)
    assert res["ok"] is False
    assert res["broken_at"] == 0


def test_block_speaks_colony(tmp_path):
    blk = sw.swimmer_happiness_block(_procs(), state_dir=tmp_path / ".sifta_state")
    assert "MY SWIMMERS" in blk and "ants" in blk
    assert "yield" in blk.lower() or "throttle" in blk.lower()
