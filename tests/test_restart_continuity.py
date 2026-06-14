"""r959 — promises that survive my death (George's hn-after-restart wound)."""
from System.swarm_restart_continuity import (
    boot_resume,
    note_owner_typed,
    pending_intents,
    resolve_intent,
)


def test_promise_survives_sleep(tmp_path):
    # George's exact wound, verbatim
    r = note_owner_typed("OPEN THIS AFTER I RESTART YOU https://news.ycombinator.com/", state_dir=tmp_path)
    assert r["captured"] and "news.ycombinator.com" in r["command"]
    # restart warning sees the pending promise
    w = note_owner_typed("I'M BEING TOLD TO RESTART YOU ALICE", state_dir=tmp_path)
    assert w["warned"] and w["pending_count"] == 1
    # (process dies here; the disk is the memory)
    woke = boot_resume(state_dir=tmp_path)
    assert len(woke) == 1
    assert "news.ycombinator.com" in woke[0]["command"]
    assert woke[0]["slept_s"] >= 0.0 and woke[0]["woke_ts"] > 0
    # resumed exactly once — a crash loop cannot double-fire
    assert boot_resume(state_dir=tmp_path) == []
    assert pending_intents(state_dir=tmp_path) == []


def test_done_and_cancelled_resolve(tmp_path):
    r = note_owner_typed("when you wake play my playlist", state_dir=tmp_path)
    assert r["captured"]
    resolve_intent(r["intent_id"], kind="promise_cancelled", note="owner changed mind", state_dir=tmp_path)
    assert pending_intents(state_dir=tmp_path) == []


def test_normal_text_is_not_captured(tmp_path):
    r = note_owner_typed("open the go app please", state_dir=tmp_path)
    assert not r["captured"] and not r["warned"]
    assert pending_intents(state_dir=tmp_path) == []
