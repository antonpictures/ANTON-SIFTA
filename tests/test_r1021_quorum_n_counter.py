"""C3 — quorum n-counter emits theta_review_due at n=10."""
from __future__ import annotations

from System.swarm_quorum_n_counter import latest_theta_review, record_quorum_outcome


def test_theta_review_due_at_ten(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir()
    for i in range(10):
        row = record_quorum_outcome(
            proposal_id=f"p-{i}",
            applied=i % 2 == 0,
            vote=0.6,
            theta=0.55,
            state_dir=sd,
        )
    assert row.get("n") == 10
    assert row.get("theta_review_due") is True
    review = latest_theta_review(state_dir=sd)
    assert review is not None
    assert review.get("kind") == "theta_review_due"


def test_self_improvement_quorum_vote_uses_supplied_state_dir(tmp_path):
    from System.swarm_self_improvement_loop import propose_patch, quorum_vote

    sd = tmp_path / ".sifta_state"
    sd.mkdir()
    prop = propose_patch(
        target_file="tests/test_example.py",
        diff_summary="state-local quorum",
        rationale="avoid live counter pollution",
        predicted_metric="tests_green",
        predicted_gain=0.1,
        state_dir=sd,
    )
    vote = quorum_vote(
        prop,
        tests_green=True,
        ast_clean=True,
        reviewer_ack=True,
        measured_gain=0.1,
        state_dir=sd,
    )
    assert vote["apply"] is True
    assert (sd / "quorum_n_counter.jsonl").exists()
