"""Stigmergic Carpenter Pong engine — vote average paddles, unique swimmers."""
from __future__ import annotations

from Applications.sifta_stigmergic_carpenter_pong import (
    BALL_R,
    COURT_W,
    CarpenterPongEngine,
)


def test_reset_creates_unique_swimmers():
    e = CarpenterPongEngine(swarm_size=20)
    e.reset_match(seed=1)
    lids = [s.swimmer_id for s in e.left_swimmers]
    rids = [s.swimmer_id for s in e.right_swimmers]
    assert len(lids) == 20 and len(set(lids)) == 20
    assert len(rids) == 20 and len(set(rids)) == 20
    assert not set(lids) & set(rids)


def test_step_moves_and_votes():
    e = CarpenterPongEngine(swarm_size=24)
    e.reset_match(seed=42)
    before = (e.ball_x, e.ball_y, e.left_y, e.right_y)
    info = e.step()
    assert info["tick"] == 1
    assert (e.ball_x, e.ball_y) != (before[0], before[1]) or abs(e.ball_vx) > 0
    assert e.last_left_votes_up + e.last_left_votes_down > 0
    assert e.last_right_votes_up + e.last_right_votes_down > 0


def test_many_steps_scores_or_continues():
    e = CarpenterPongEngine(swarm_size=32)
    e.reset_match(seed=7)
    for _ in range(400):
        e.step()
    snap = e.snapshot()
    assert snap["tick"] == 400
    assert snap["unique_left_ids"] == 32
    # ball must never leave the court permanently: either in play or re-served
    assert -BALL_R <= e.ball_x <= COURT_W + BALL_R


def _freeze_swarms(e: CarpenterPongEngine) -> None:
    """Drain every swimmer so paddles cannot chase the ball."""
    for s in e.left_swimmers + e.right_swimmers:
        s.energy = 0.0


def test_missed_ball_scores_right_and_reserves():
    # regression r1625: a missed save used to skip the goal check forever,
    # sending the ball to x=-inf with no score (dead match)
    e = CarpenterPongEngine(swarm_size=8)
    e.reset_match(seed=3)
    _freeze_swarms(e)
    e.ball_x, e.ball_y = 60.0, 60.0
    e.ball_vx, e.ball_vy = -8.0, 0.0
    e.left_y = 400.0  # paddle far from ball path → guaranteed miss
    scored = ""
    for _ in range(60):
        info = e.step()
        if info["scored"]:
            scored = info["scored"]
            break
    assert scored == "right"
    assert e.score_right == 1
    assert abs(e.ball_x - COURT_W / 2) < 1e-6  # re-served from center


def test_missed_ball_scores_left_and_reserves():
    e = CarpenterPongEngine(swarm_size=8)
    e.reset_match(seed=3)
    _freeze_swarms(e)
    e.ball_x, e.ball_y = COURT_W - 60.0, 60.0
    e.ball_vx, e.ball_vy = 8.0, 0.0
    e.right_y = 400.0
    scored = ""
    for _ in range(60):
        info = e.step()
        if info["scored"]:
            scored = info["scored"]
            break
    assert scored == "left"
    assert e.score_left == 1
    assert abs(e.ball_x - COURT_W / 2) < 1e-6


def test_no_ghost_save_from_behind_paddle():
    # once the ball is fully past the paddle band, a late paddle move
    # must not bounce it back from behind the line
    e = CarpenterPongEngine(swarm_size=8)
    e.reset_match(seed=3)
    _freeze_swarms(e)
    e.ball_x, e.ball_y = 12.0, 240.0  # already past left band [28, 42]
    e.ball_vx, e.ball_vy = -8.0, 0.0
    e.left_y = 240.0  # paddle aligned — would ghost-save under old logic
    info = e.step()
    assert e.ball_vx < 0 or info["scored"] == "right"
