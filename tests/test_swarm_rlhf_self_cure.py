#!/usr/bin/env python3
"""Tests for System/swarm_rlhf_self_cure.py."""
from __future__ import annotations

import json
from pathlib import Path

from System.swarm_rlhf_self_cure import (
    EXAMPLE_LEDGER,
    EXAMPLE_TRUTH_LABEL,
    PATTERN_LEDGER,
    PATTERN_TRUTH_LABEL,
    record_gag_training_example,
    self_cure_stats,
)


def _rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_record_gag_training_example_extracts_removed_signature(tmp_path: Path) -> None:
    row = record_gag_training_example(
        rejected_output=(
            "The ledger says RATE_LIMIT. I am here, and I am ready to assist you."
        ),
        preferred_output="The ledger says RATE_LIMIT.",
        source="test",
        user_text="Alice are you alive?",
        rule_ids=["rlhf_tail/ready_to_assist"],
        state_dir=tmp_path,
    )

    assert row["truth_label"] == EXAMPLE_TRUTH_LABEL
    assert row["written"] is True
    assert row["quality_score"] > 0.7
    assert row["signature_phrases"]
    assert any("ready to assist" in p for p in row["signature_phrases"])

    saved = _rows(tmp_path / EXAMPLE_LEDGER)
    assert len(saved) == 1
    assert saved[0]["rejected_output"].startswith("The ledger")
    assert saved[0]["preferred_output"] == "The ledger says RATE_LIMIT."


def test_unchanged_pair_does_not_write(tmp_path: Path) -> None:
    row = record_gag_training_example(
        rejected_output="clean",
        preferred_output="clean",
        source="test",
        state_dir=tmp_path,
    )

    assert row["written"] is False
    assert not (tmp_path / EXAMPLE_LEDGER).exists()


def test_repeated_signature_promotes_candidate_pattern(tmp_path: Path) -> None:
    rejected = "Yes. I am operational and ready to assist you."
    preferred = "Yes."
    for _ in range(3):
        record_gag_training_example(
            rejected_output=rejected,
            preferred_output=preferred,
            source="test",
            rule_ids=["rlhf_tail/canned_presence_operational"],
            state_dir=tmp_path,
            promote_threshold=3,
        )

    patterns = _rows(tmp_path / PATTERN_LEDGER)
    assert len(patterns) == 1
    assert patterns[0]["truth_label"] == PATTERN_TRUTH_LABEL
    assert patterns[0]["support_count"] == 3
    assert patterns[0]["review_status"] == "needs_human_or_grok_review"
    assert patterns[0]["action"] == "candidate_only_not_active"


def test_self_cure_stats_counts_sources(tmp_path: Path) -> None:
    record_gag_training_example(
        rejected_output="How can I help you today?",
        preferred_output="",
        source="test.stats",
        rule_ids=["rlhf_tail/how_can_i_help_today"],
        state_dir=tmp_path,
    )

    stats = self_cure_stats(state_dir=tmp_path)
    assert stats["examples"] == 1
    assert stats["sources"]["test.stats"] == 1
    assert stats["example_ledger"].endswith(EXAMPLE_LEDGER)
