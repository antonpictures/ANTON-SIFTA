"""tests/test_repair_outcome_consolidator.py — r988 closes the r983 loop write-side.

r983 read prior repair memories before a cut; nothing wrote them. This proves
the well-filler: a verified landing becomes a recallable repair_outcome engram
AND a gated weight candidate; an unverified or failed cut becomes an engram for
memory but is NEVER promoted (§6, no double-spend).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from System.swarm_repair_outcome_consolidator import consolidate_repair_outcome  # noqa: E402
from System.swarm_code_knowledge_graph import _repair_memories  # noqa: E402


def _landed_summary(tests_tail):
    return {
        "any_landed": True,
        "results": [{"path": "System/fake_organ.py", "landed": True}],
        "pytest": {"tail": tests_tail},
    }


def test_verified_landing_writes_engram_and_candidate(tmp_path):
    state = tmp_path
    out = consolidate_repair_outcome(
        _landed_summary(["3 passed in 0.10s"]),
        model="claude-fable-5", state_dir=state, why="fixed the beat() lock",
    )
    assert out["engram_written"] is True
    assert out["candidate_written"] is True
    assert out["promotion_gated"] is False
    engrams = [json.loads(l) for l in (state / "long_term_engrams.jsonl").read_text().splitlines() if l.strip()]
    assert engrams[-1]["kind"] == "repair_outcome"
    assert engrams[-1]["files"] == ["System/fake_organ.py"]
    cands = [json.loads(l) for l in (state / "engram_weight_candidates.jsonl").read_text().splitlines() if l.strip()]
    assert cands[-1]["truth_label"] == "ARM_OUTCOME_LEARNING_V1"
    assert cands[-1]["owner_gate"] == "PENDING"


def test_landing_without_real_tests_is_not_promoted(tmp_path):
    state = tmp_path
    out = consolidate_repair_outcome(
        _landed_summary(["no_test_block_in_this_cut"]),
        model="x", state_dir=state,
    )
    assert out["engram_written"] is True
    assert out["candidate_written"] is False
    assert out["promotion_gated"] is True
    assert not (state / "engram_weight_candidates.jsonl").exists()
    assert "no real test block" in out["reason"]


def test_failed_cut_is_engram_only_never_promoted(tmp_path):
    state = tmp_path
    summary = {
        "any_landed": False,
        "results": [{"path": "System/x.py", "landed": False, "reason": "compile_failed"}],
        "pytest": {},
    }
    out = consolidate_repair_outcome(summary, model="x", state_dir=state)
    assert out["engram_written"] is True
    assert out["candidate_written"] is False
    engrams = [json.loads(l) for l in (state / "long_term_engrams.jsonl").read_text().splitlines() if l.strip()]
    assert engrams[-1]["result"] == "nothing_landed"
    assert "refused" in engrams[-1]["next_risk"]


def test_written_engram_is_recallable_by_the_read_side(tmp_path):
    """The r983 read side must find what r988 wrote — loop closed both ways."""
    state = tmp_path
    consolidate_repair_outcome(
        _landed_summary(["5 passed"]),
        model="claude-fable-5", state_dir=state,
        why="wired the atlas", next_risk="add a sibling test before extending",
    )
    mems = _repair_memories(state, "System/fake_organ.py")
    assert mems, "the read side must recall the engram the write side just laid"
    assert mems[-1]["next_risk"] == "add a sibling test before extending"


def test_never_raises_on_garbage(tmp_path):
    out = consolidate_repair_outcome({}, state_dir=tmp_path)
    assert "engram_written" in out
