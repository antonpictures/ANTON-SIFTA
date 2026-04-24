#!/usr/bin/env python3
"""Integration tests for Event 51 quorum rate-gate wiring."""

import json
import time

from System.swarm_quorum_sensing import SwarmQuorumSensing


def _isolated_quorum(tmp_path) -> SwarmQuorumSensing:
    quorum = SwarmQuorumSensing()
    quorum.state_dir = tmp_path
    quorum.quorum_ledger = tmp_path / "quorum_votes.jsonl"
    quorum.secret_key_path = tmp_path / "hive_mind_secret.key"
    quorum._ensure_hive_secret()
    return quorum


def _append_vote(
    quorum: SwarmQuorumSensing,
    proposal_id: str,
    voter_id: str,
    *,
    vote: str = "YES",
    ts: float | None = None,
    signature: str | None = None,
) -> None:
    if ts is None:
        ts = time.time()
    if signature is None:
        signature = quorum._generate_hmac(proposal_id, vote, voter_id)
    quorum.quorum_ledger.parent.mkdir(parents=True, exist_ok=True)
    with quorum.quorum_ledger.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "ts": ts,
                    "proposal_id": proposal_id,
                    "voter_id": voter_id,
                    "vote": vote,
                    "signature": signature,
                }
            )
            + "\n"
        )


def test_check_quorum_uses_distinct_verified_yes_votes(tmp_path):
    quorum = _isolated_quorum(tmp_path)
    quorum.known_sibling_spores = 4  # sqrt threshold = 2
    proposal_id = "PROP_DISTINCT"

    _append_vote(quorum, proposal_id, "SPORE_A")
    _append_vote(quorum, proposal_id, "SPORE_B")
    _append_vote(quorum, proposal_id, "FORGED", signature="bad")

    assert quorum.check_quorum_and_execute(proposal_id) is True


def test_same_voter_slow_spam_does_not_reach_quorum(tmp_path):
    quorum = _isolated_quorum(tmp_path)
    quorum.known_sibling_spores = 4  # sqrt threshold = 2
    proposal_id = "PROP_DUPLICATE"
    now = time.time()

    _append_vote(quorum, proposal_id, "SPORE_A", ts=now - 1)
    _append_vote(quorum, proposal_id, "SPORE_A", ts=now - 12)
    _append_vote(quorum, proposal_id, "SPORE_A", ts=now - 23)

    assert quorum.check_quorum_and_execute(proposal_id) is False


def test_stale_verified_votes_do_not_reach_quorum(tmp_path):
    quorum = _isolated_quorum(tmp_path)
    quorum.known_sibling_spores = 4  # sqrt threshold = 2
    proposal_id = "PROP_STALE"
    now = time.time()

    _append_vote(quorum, proposal_id, "SPORE_A", ts=now - 1)
    _append_vote(quorum, proposal_id, "SPORE_B", ts=now - 120)

    assert quorum.check_quorum_and_execute(proposal_id) is False


def test_no_votes_from_other_proposals_leak_into_tally(tmp_path):
    quorum = _isolated_quorum(tmp_path)
    quorum.known_sibling_spores = 4  # sqrt threshold = 2

    _append_vote(quorum, "TARGET", "SPORE_A")
    _append_vote(quorum, "OTHER", "SPORE_B")

    assert quorum.check_quorum_and_execute("TARGET") is False
