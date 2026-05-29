"""Round 83 tests — Stigmergic memory field.

The architect's rule (verbatim 2026-05-27): "if it does not match well,
computer just learned how to better connect memories how to discuss them
... if it doesn't [match] she marks it that shit doesn't so we have real
data."

Translation: the recall attempt itself is the stigmergic deposit. The
miss is data. Every turn writes a receipt; the cortex prompt either
sees the full match block OR a one-line self-narrate noting the
attempt and the weak score. Censoring the attempt is the bug.

Tests:
  - every recall_attempt writes a row to
    .sifta_state/hippocampus/recall_attempts.jsonl
  - strong-match turn returns threshold_crossed=True and the prompt
    block contains the match lines
  - weak-match turn returns threshold_crossed=False and the prompt
    block contains the self-narrate sentinel
  - empty query handled cleanly (no crash, attempt row still optional)
  - the attempt row carries query_hash (privacy) NOT raw text
  - real .sifta_state isolation
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from System import swarm_hippocampus as hip


def _append_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def _seed_strong_match(state: Path) -> None:
    _append_jsonl(
        state / "work_receipts.jsonl",
        [
            {
                "ts": 100.0,
                "receipt_id": "r-camera-1",
                "action": "camera hotplug probe reconnect",
                "truth_note": "camera reconnect after USB unplug — frame stream live again",
            },
        ],
    )


# ─── recall_attempt always writes a receipt ───────────────────────────────


def test_strong_match_writes_receipt_and_crosses_threshold(tmp_path: Path):
    state = tmp_path / ".sifta_state"
    _seed_strong_match(state)
    out = hip.recall_attempt("camera reconnect probe", state_dir=state)
    assert out["matches"], "strong overlap should return matches"
    assert out["threshold_crossed"] is True
    assert out["top_score"] >= out["threshold"]
    # Receipt landed
    attempts_path = state / "hippocampus" / "recall_attempts.jsonl"
    assert attempts_path.exists(), "recall attempt must write a receipt row"
    rows = [json.loads(l) for l in attempts_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(rows) == 1
    row = rows[0]
    assert row["truth_label"] == "HIPPOCAMPUS_RECALL_ATTEMPT_V1"
    assert row["threshold_crossed"] is True
    assert row["top_score"] == out["top_score"]


def test_weak_match_still_writes_receipt(tmp_path: Path):
    """The whole architect's point: even when nothing matches well, we
    write the row so the body learns. Censoring the attempt = throwing
    away the learning signal."""
    state = tmp_path / ".sifta_state"
    _seed_strong_match(state)
    # Query about totally unrelated content — should yield no overlap
    # or trivial overlap below threshold.
    out = hip.recall_attempt("good morning sunshine", state_dir=state)
    assert out["threshold_crossed"] is False
    # Receipt MUST still land
    attempts_path = state / "hippocampus" / "recall_attempts.jsonl"
    assert attempts_path.exists()
    rows = [json.loads(l) for l in attempts_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(rows) == 1
    row = rows[0]
    assert row["threshold_crossed"] is False
    # Privacy: raw text never stored; only the hash
    assert "good morning" not in json.dumps(row)
    assert row["query_hash"]


def test_empty_query_does_not_crash(tmp_path: Path):
    state = tmp_path / ".sifta_state"
    out = hip.recall_attempt("", state_dir=state)
    assert out["matches"] == []
    assert out["threshold_crossed"] is False
    assert out["top_score"] == 0.0


def test_two_calls_produce_two_attempt_rows(tmp_path: Path):
    """Every turn writes a receipt — even back-to-back calls."""
    state = tmp_path / ".sifta_state"
    _seed_strong_match(state)
    hip.recall_attempt("camera reconnect probe", state_dir=state)
    hip.recall_attempt("totally unrelated phrase", state_dir=state)
    rows = [
        json.loads(l)
        for l in (state / "hippocampus" / "recall_attempts.jsonl").read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    assert len(rows) == 2
    assert rows[0]["threshold_crossed"] is True
    assert rows[1]["threshold_crossed"] is False


# ─── prompt block: full vs self-narrate ───────────────────────────────────


def test_prompt_block_strong_match_emits_full(tmp_path: Path):
    state = tmp_path / ".sifta_state"
    _seed_strong_match(state)
    block = hip.associative_recall_prompt_block("camera reconnect probe", state_dir=state)
    assert "HIPPOCAMPAL ASSOCIATIVE RECALL" in block
    assert "receipt-backed lexical semantic hash" in block
    # full block has match lines, NOT the self-narrate sentinel
    assert "attempt receipted, no strong match" not in block
    assert "r-camera-1" in block


def test_prompt_block_weak_match_emits_self_narrate(tmp_path: Path):
    state = tmp_path / ".sifta_state"
    _seed_strong_match(state)
    block = hip.associative_recall_prompt_block("good morning sunshine", state_dir=state)
    assert "HIPPOCAMPAL ASSOCIATIVE RECALL" in block
    assert "attempt receipted, no strong match" in block
    assert "do not invent" in block
    # And it MUST include the score so Alice can see how close the recall was
    assert "top_score=" in block
    assert "threshold=" in block


def test_prompt_block_writes_receipt_even_for_weak_match(tmp_path: Path):
    """Critical architect rule: ALWAYS write the receipt even when the
    cortex won't see the full block."""
    state = tmp_path / ".sifta_state"
    _seed_strong_match(state)
    _ = hip.associative_recall_prompt_block("xyz uncorrelated tokens", state_dir=state)
    attempts_path = state / "hippocampus" / "recall_attempts.jsonl"
    assert attempts_path.exists()
    rows = [
        json.loads(l)
        for l in attempts_path.read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    # exactly one row from the one call
    assert len(rows) == 1


# ─── threshold override ────────────────────────────────────────────────────


def test_threshold_override_can_force_inject(tmp_path: Path):
    """Lowering inject_threshold can surface borderline matches if the
    caller knows the context warrants it."""
    state = tmp_path / ".sifta_state"
    _seed_strong_match(state)
    # First call uses a HIGH threshold — even strong match falls below
    high_threshold = hip.recall_attempt(
        "camera reconnect", state_dir=state, inject_threshold=0.99,
    )
    assert high_threshold["threshold_crossed"] is False
    # Lower threshold — same query crosses
    low_threshold = hip.recall_attempt(
        "camera reconnect", state_dir=state, inject_threshold=0.01,
    )
    assert low_threshold["threshold_crossed"] is True


def test_recall_threshold_learns_from_attempt_receipts(tmp_path: Path):
    """The surfacing threshold is not a permanent magic number.

    Bootstrap is allowed while the ledger is empty, but once recall attempts
    exist the hippocampus derives the threshold from its own score field.
    """
    state = tmp_path / ".sifta_state"
    attempts = state / "hippocampus" / "recall_attempts.jsonl"
    _append_jsonl(
        attempts,
        [
            {"truth_label": "HIPPOCAMPUS_RECALL_ATTEMPT_V1", "top_score": 0.08},
            {"truth_label": "HIPPOCAMPUS_RECALL_ATTEMPT_V1", "top_score": 0.16},
            {"truth_label": "HIPPOCAMPUS_RECALL_ATTEMPT_V1", "top_score": 0.34},
            {"truth_label": "HIPPOCAMPUS_RECALL_ATTEMPT_V1", "top_score": 0.52},
        ],
    )

    learned = hip.learned_recall_inject_threshold(
        state_dir=state,
        min_rows=4,
        quantile=0.70,
    )

    assert learned == 0.34
    assert learned != hip.DEFAULT_RECALL_INJECT_THRESHOLD


# ─── Real ledger isolation ─────────────────────────────────────────────────


def test_real_ledger_untouched(tmp_path: Path):
    real_state = Path(".sifta_state")
    real_attempts = real_state / "hippocampus" / "recall_attempts.jsonl"
    real_before = real_attempts.stat().st_size if real_attempts.exists() else 0
    # Also watch the bulk-ledger surface — no surgery should mutate it
    work_path = real_state / "work_receipts.jsonl"
    work_before = work_path.stat().st_size if work_path.exists() else 0

    state = tmp_path / ".sifta_state"
    _seed_strong_match(state)
    hip.recall_attempt("camera probe", state_dir=state)
    hip.associative_recall_prompt_block("good morning", state_dir=state)

    real_after = real_attempts.stat().st_size if real_attempts.exists() else 0
    work_after = work_path.stat().st_size if work_path.exists() else 0
    assert real_after == real_before, "recall_attempt mutated real recall ledger"
    assert work_after == work_before, "recall_attempt mutated real work_receipts"
