#!/usr/bin/env python3
"""r307: command routing LEARNS from the field + owner corrections — no hardcoded regex.

George: "do not hardcode — I'm unpredictable — only stigmergy can do it." These prove the
field learns: a cold field yields to the caller; accepted routings let a NEW unpredictable
phrasing route correctly; an owner correction retrains it; and recent pheromone outweighs
stale (decay).
"""
from System import swarm_stigmergic_intent as si

NOW = 1_000_000_000.0
DAY = 86400.0


def test_cold_field_yields_to_caller(tmp_path):
    r = si.suggest("search youtube victoria secret", ["youtube_search", "search_web"],
                   state_dir=tmp_path, now=NOW)
    assert r["decided"] is False          # nothing learned yet → caller uses its own rules


def test_learns_routing_for_a_new_unpredictable_phrasing(tmp_path):
    for txt in ("search youtube victoria secret fashion show",
                "open youtube and play the runway show",
                "youtube the fashion runway models"):
        si.record_intent(txt, "browser_url", "youtube_search", state_dir=tmp_path, now=NOW)
    # a phrasing George never typed before:
    r = si.suggest("pull up victoria secret runway on the tube", ["youtube_search", "search_web"],
                   state_dir=tmp_path, now=NOW)
    assert r["decided"] is True and r["target"] == "youtube_search"


def test_owner_correction_retrains_the_field(tmp_path):
    si.correct_intent("victoria secret models runway", wrong_target="search_web",
                      right_target="youtube_search", right_lane="browser_url",
                      state_dir=tmp_path, now=NOW)
    r = si.suggest("victoria secret models runway please", ["youtube_search", "search_web"],
                   state_dir=tmp_path, now=NOW)
    assert r["best_target"] == "youtube_search"        # the field now leans the right way
    assert r["scores"].get("search_web", 0.0) < 0      # the wrong target was pushed down


def test_recent_pheromone_outweighs_stale(tmp_path):
    si.record_intent("show me the cats clip", "browser_url", "A_old", state_dir=tmp_path, now=NOW - 60 * DAY)
    si.record_intent("show me the cats clip", "browser_url", "B_recent", state_dir=tmp_path, now=NOW - 60)
    r = si.suggest("show me the cats clip", state_dir=tmp_path, now=NOW)
    assert r["scores"]["B_recent"] > r["scores"]["A_old"]   # decay: recent trace is stronger
