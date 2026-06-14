"""r956 — the owner's live phone call is not a command stream."""
from System.swarm_call_overheard_guard import (
    call_mode_active,
    classify_spoken_during_call,
    note_owner_typed,
)


def test_call_mode_lifecycle(tmp_path):
    assert call_mode_active(state_dir=tmp_path) is False
    r = note_owner_typed("IM ON THE PHONE, SPEAKER IPHONE THAT IS THE TTS U HEAR", state_dir=tmp_path)
    assert r["changed"] and r["active"]
    assert call_mode_active(state_dir=tmp_path) is True
    # overheard call fragment goes quiet with a receipt row
    c = classify_spoken_during_call("How much for the room? Oh, special price. $300.", 0.52, state_dir=tmp_path)
    assert c["quiet"] is True and c["rule_id"] == "call_overheard/quiet"
    assert (tmp_path / "call_overheard_receipts.jsonl").exists()
    # the wake word always passes through
    w = classify_spoken_during_call("Alice, search for flights to Romania", 0.6, state_dir=tmp_path)
    assert w["quiet"] is False and "wake_word" in w["rule_id"]
    # the owner ends the call in his own words
    e = note_owner_typed("ok off the phone now", state_dir=tmp_path)
    assert e["changed"] and e["active"] is False
    assert call_mode_active(state_dir=tmp_path) is False


def test_no_call_mode_means_no_interference(tmp_path):
    c = classify_spoken_during_call("play the next song", 0.8, state_dir=tmp_path)
    assert c["quiet"] is False and c["active"] is False


def test_rhythm_relative_decay_r957(tmp_path):
    # No wall-clock TTL: the call dies when silence exceeds its OWN rhythm.
    import json, time
    import System.swarm_call_overheard_guard as G

    note_owner_typed("i'm on the phone", state_dir=tmp_path)
    # simulate a call that breathed with ~2s gaps, then went silent for 60s
    p = tmp_path / G.STATE_NAME
    row = json.loads(p.read_text())
    now = time.time()
    row.update({"ema_gap_s": 2.0, "last_evidence_ts": now - 60.0, "ts": now - 300.0, "fragments": 9})
    p.write_text(json.dumps(row))
    assert call_mode_active(state_dir=tmp_path) is False  # 60s >> 8 x 2s rhythm
    # same silence, but the call itself was slow-breathing (gaps ~20s) -> alive
    row.update({"ema_gap_s": 20.0})
    p.write_text(json.dumps(row))
    assert call_mode_active(state_dir=tmp_path) is True   # 60s < 8 x 20s
    # fragments reinforce: a new overheard line refreshes life
    G.classify_spoken_during_call("da mama, te aud", 0.5, state_dir=tmp_path)
    row2 = json.loads(p.read_text())
    assert row2["fragments"] == 10 and row2["last_evidence_ts"] > now - 5
