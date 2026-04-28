#!/usr/bin/env python3
"""
tests/test_swarm_td_learning.py
Predator v7.0 — Event 76: TD Q-Learner Tests

Tests (per C55M-DR-CODEX scalpel order):
  1. positive reward increases Q(s,a) for that action
  2. negative reward decreases Q(s,a) for that action
  3. unrelated states do not leak value across state keys
  4. Q-injection shifts BG scores toward high-Q actions
  5. state extraction always returns bounded enum values
"""
import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from System.swarm_td_learning import (
    QTable, extract_state, update_from_reward,
    q_inject_scores, ACTIONS, ALPHA, GAMMA,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def fresh_qtable(tmp_path, monkeypatch):
    """Isolated Q-table backed by a temp file."""
    import System.swarm_td_learning as td
    monkeypatch.setattr(td, "_Q_TABLE_FILE", tmp_path / "td_q_table.json")
    monkeypatch.setattr(td, "_TD_LEDGER",    tmp_path / "td_receipts.jsonl")
    monkeypatch.setattr(td, "_Q",            None)
    return td


# ── Test 1: positive reward increases Q for the rewarded action ────────────────

def test_positive_reward_increases_q(fresh_qtable):
    td = fresh_qtable
    s = td.extract_state("test", stt_confidence=0.9, c1_action="ENGAGE",
                          tool="none", source="owner", social_frame="owner",
                          recent_reward=0.0)
    q_before = td.get_qtable().get(s, "ENGAGE")
    result = td.update_from_reward(s, "ENGAGE", reward=1.0, next_state=s)
    q_after = td.get_qtable().get(s, "ENGAGE")

    assert q_after > q_before, \
        f"Positive reward should increase Q(s,ENGAGE): {q_before} → {q_after}"
    assert result["td_error"] > 0, "TD error should be positive for positive reward"


# ── Test 2: negative reward decreases Q for the punished action ────────────────

def test_negative_reward_decreases_q(fresh_qtable):
    td = fresh_qtable
    s = td.extract_state("test", stt_confidence=0.9, c1_action="ENGAGE",
                          tool="none", source="owner", social_frame="owner",
                          recent_reward=0.0)
    result = td.update_from_reward(s, "ENGAGE", reward=-1.0, next_state=s)
    q_after = td.get_qtable().get(s, "ENGAGE")

    assert q_after < 0, \
        f"Negative reward should push Q(s,ENGAGE) below 0: got {q_after}"
    assert result["td_error"] < 0, "TD error should be negative for punishment"


# ── Test 3: unrelated states do not leak value ─────────────────────────────────

def test_unrelated_states_do_not_leak(fresh_qtable):
    td = fresh_qtable
    s_owner = td.extract_state("owner input", stt_confidence=0.9,
                                c1_action="TOOL", tool="stgm",
                                source="owner", social_frame="owner",
                                recent_reward=0.0)
    s_group = td.extract_state("group input", stt_confidence=0.5,
                                c1_action="SILENCE", tool="none",
                                source="group", social_frame="group",
                                recent_reward=-0.5)

    # Reward TOOL in owner state
    td.update_from_reward(s_owner, "TOOL", reward=1.0, next_state=s_owner)

    # Group state TOOL should still be 0
    q_group_tool = td.get_qtable().get(s_group, "TOOL")
    assert q_group_tool == 0.0, \
        f"Value must not leak across states: Q(s_group,TOOL)={q_group_tool}"


# ── Test 4: Q-injection shifts BG scores toward high-Q actions ─────────────────

def test_q_injection_shifts_scores(fresh_qtable):
    td = fresh_qtable
    s = td.extract_state("balance check", stt_confidence=0.85,
                          c1_action="TOOL", tool="stgm",
                          source="owner", social_frame="owner",
                          recent_reward=0.7)
    # Teach Q that TOOL is good in this state
    for _ in range(5):
        td.update_from_reward(s, "TOOL", reward=1.0, next_state=s)

    c1_raw = {"SILENCE": 0.02, "TOOL": 0.60, "ENGAGE": 0.35, "BOND": 0.03}
    c1_adj = td.q_inject_scores(s, c1_raw)

    assert c1_adj["TOOL"] > c1_raw["TOOL"], \
        "Q-injection should increase TOOL score after positive learning"
    assert c1_adj["SILENCE"] == pytest.approx(c1_raw["SILENCE"], abs=0.05), \
        "Q-injection should not inflate SILENCE when it has near-zero Q"


# ── Test 5: state extraction always returns bounded enum values ────────────────

def test_state_extraction_bounded():
    import System.swarm_td_learning as td
    from System.swarm_td_learning import (
        SOURCE_VALS, STT_VALS, C1_VALS, TOOL_VALS, FRAME_VALS, RECENT_VALS
    )

    # Edge cases
    s1 = td.extract_state("x", stt_confidence=None, c1_action="INVALID",
                           tool="UNKNOWN", source="ALIEN", social_frame="BOT",
                           recent_reward=999.0)
    assert s1[0] in SOURCE_VALS
    assert s1[1] in STT_VALS
    assert s1[2] in C1_VALS
    assert s1[3] in TOOL_VALS
    assert s1[4] in FRAME_VALS
    assert s1[5] in RECENT_VALS

    s2 = td.extract_state("x", stt_confidence=0.1, c1_action="BOND",
                           tool="whatsapp", source="group", social_frame="group",
                           recent_reward=-5.0)
    assert s2[5] == "punished"

    s3 = td.extract_state("x", stt_confidence=0.9, c1_action="SILENCE",
                           tool="none", source="owner", social_frame="owner",
                           recent_reward=5.0)
    assert s3[5] == "rewarded"


# ── Test 6: Bellman formula numerical correctness ─────────────────────────────

def test_bellman_formula(fresh_qtable):
    """
    Q(s,a) ← Q(s,a) + α · [r + γ · max_{a'} Q(s',a') − Q(s,a)]

    With a fresh table (all zeros), one update with reward=1.0, γ=0.9, α=0.15:
    δ = 1.0 + 0.9×0 − 0 = 1.0
    Q_new = 0 + 0.15×1.0 = 0.15
    """
    td = fresh_qtable
    s = td.extract_state("x", stt_confidence=0.9, c1_action="ENGAGE",
                          tool="none", source="owner", social_frame="owner",
                          recent_reward=0.0)
    result = td.update_from_reward(s, "ENGAGE", reward=1.0, next_state=s)

    expected_q = ALPHA * (1.0 + GAMMA * 0.0 - 0.0)  # = 0.15
    assert abs(result["new_q"] - expected_q) < 1e-5, \
        f"Bellman mismatch: expected {expected_q:.6f}, got {result['new_q']:.6f}"
    assert abs(result["td_error"] - 1.0) < 1e-5, \
        f"TD error mismatch: expected 1.0, got {result['td_error']}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
