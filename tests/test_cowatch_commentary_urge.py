#!/usr/bin/env python3
"""r323: the co-watch comment trigger is a PHEROMONE shaped by George's behaviour, not a timer.
George 2026-06-01: "that extra trigger has to be a stigmergic variable ... I'm the data, my
behaviour for it." These tests pin the field dynamics headless (no Qt): silence cold, urge builds
from his signals, a fresh comment refracts (no spam), his engagement lowers the bar and his
aversion raises it, the memory decays, and taste is per-context.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System import swarm_cowatch_commentary_urge as u

VID = "THE OFFICIAL 2018 VICTORIA'S SECRET FASHION SHOW"


def test_cold_field_is_silent(tmp_path):
    d = should = u.should_comment(VID, state_dir=tmp_path)
    assert d["comment"] is False
    assert d["reason"] == "urge_below_bar"


def test_owner_behaviour_builds_the_urge_until_it_crosses(tmp_path):
    t0 = 1_000_000.0
    # Cold → silent.
    assert u.should_comment(VID, state_dir=tmp_path, now=t0)["comment"] is False
    # George pauses (attending) and the scene changes — his behaviour deposits stimulus.
    u.deposit_owner_signal("owner_paused", VID, state_dir=tmp_path, now=t0)
    u.deposit_owner_signal("scene_change", VID, state_dir=tmp_path, now=t0 + 1)
    d = u.should_comment(VID, state_dir=tmp_path, now=t0 + 2)
    assert d["comment"] is True
    assert d["reason"] == "urge_crossed_bar"
    assert d["stimulus"] > 0


def test_fresh_comment_refracts_no_spam(tmp_path):
    t0 = 2_000_000.0
    u.deposit_owner_signal("owner_paused", VID, state_dir=tmp_path, now=t0)
    u.deposit_owner_signal("scene_change", VID, state_dir=tmp_path, now=t0)
    assert u.should_comment(VID, state_dir=tmp_path, now=t0)["comment"] is True
    # She comments → refractory holds her quiet immediately after.
    u.note_comment_made(VID, state_dir=tmp_path, now=t0)
    d = u.should_comment(VID, state_dir=tmp_path, now=t0 + 1)
    assert d["comment"] is False
    assert d["reason"] == "refractory_recent_comment"
    # Minutes later the refractory has decayed and the urge can rebuild.
    u.deposit_owner_signal("owner_spoke", VID, state_dir=tmp_path, now=t0 + 600)
    u.deposit_owner_signal("owner_paused", VID, state_dir=tmp_path, now=t0 + 600)
    assert u.should_comment(VID, state_dir=tmp_path, now=t0 + 601)["comment"] is True


def test_owner_engagement_lowers_bar_aversion_raises_it(tmp_path):
    t0 = 3_000_000.0
    # Baseline single weak signal that does NOT cross alone.
    u.deposit_owner_signal("dwell", VID, state_dir=tmp_path, now=t0)  # 0.4 < 1.0
    assert u.should_comment(VID, state_dir=tmp_path, now=t0)["comment"] is False
    # George engaged with past comments here → reward bias lifts this context over the bar.
    for i in range(3):
        u.reinforce(VID, engaged=True, state_dir=tmp_path, now=t0 - 10 + i)
    assert u.should_comment(VID, state_dir=tmp_path, now=t0 + 1)["reward_bias"] > 0
    assert u.should_comment(VID, state_dir=tmp_path, now=t0 + 1)["comment"] is True

    # A different video where George kept brushing comments off → aversion holds her quiet.
    other = "Nvidia RTX Spark laptop review"
    for i in range(4):
        u.reinforce(other, engaged=False, state_dir=tmp_path, now=t0 - 5 + i)
    u.deposit_owner_signal("owner_paused", other, state_dir=tmp_path, now=t0 + 2)  # 1.1 alone would cross
    d = u.should_comment(other, state_dir=tmp_path, now=t0 + 3)
    assert d["reward_bias"] < 0
    assert d["comment"] is False
    assert d["reason"] in {"owner_aversion_holding_quiet", "urge_below_bar"}


def test_taste_is_per_context(tmp_path):
    t0 = 4_000_000.0
    for i in range(4):
        u.reinforce(VID, engaged=True, state_dir=tmp_path, now=t0 + i)
    matched = u.comment_pressure(VID, state_dir=tmp_path, now=t0 + 10)["reward_bias"]
    unrelated = u.comment_pressure("Nvidia RTX Spark laptop review",
                                   state_dir=tmp_path, now=t0 + 10)["reward_bias"]
    assert matched > unrelated  # the video he engaged with carries more reward than an unrelated one


def test_urge_decays_over_time(tmp_path):
    t0 = 5_000_000.0
    u.deposit_owner_signal("owner_paused", VID, state_dir=tmp_path, now=t0)
    u.deposit_owner_signal("scene_change", VID, state_dir=tmp_path, now=t0)
    assert u.should_comment(VID, state_dir=tmp_path, now=t0)["comment"] is True
    # Hours later with no new behaviour, the stimulus pheromone has faded → silence.
    later = u.should_comment(VID, state_dir=tmp_path, now=t0 + 6 * 3600)
    assert later["comment"] is False


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
