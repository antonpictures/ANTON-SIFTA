from __future__ import annotations

import json
from pathlib import Path

from System.swarm_engram_to_weight import generate_weight_candidates, select_high_value_engrams
from System.swarm_weight_consolidator import run_consolidation_cycle, summary_for_prompt


def _append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def test_selects_high_value_engrams(tmp_path: Path) -> None:
    _append(tmp_path / "long_term_engrams.jsonl", {"ts": 1, "summary": "owner tool receipt fix passed tests", "importance": 0.9})
    _append(tmp_path / "long_term_engrams.jsonl", {"ts": 2, "summary": "small", "importance": 0.1})

    selected = select_high_value_engrams(state_dir=tmp_path)

    assert len(selected) == 1
    assert selected[0]["source"] == "long_term_engrams"
    assert "receipt fix" in selected[0]["text"]


def test_generates_weight_candidates_from_engrams_and_arm_outcomes(tmp_path: Path) -> None:
    _append(tmp_path / "long_term_engrams.jsonl", {"ts": 1, "summary": "Alice learned a grounded tool receipt pattern", "importance": 0.8})
    _append(
        tmp_path / "arm_routing_weights.jsonl",
        {
            "truth_label": "ARM_OUTCOME_LEARNING_V1",
            "arm_id": "corvid_scout",
            "task_shape": "scout",
            "profitability": 5.0,
            "status": "EVIDENCE_CAPTURED",
        },
    )

    batch = generate_weight_candidates(state_dir=tmp_path, limit=10)

    assert batch["candidate_count"] == 2
    lines = (tmp_path / "engram_weight_candidates.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert "local SIFTA receipts" in json.loads(lines[0])["system"]


def test_consolidation_writes_receipt_and_blocks_promotion_without_candidate_model(tmp_path: Path) -> None:
    _append(tmp_path / "long_term_engrams.jsonl", {"ts": 1, "summary": "owner tool receipt fix passed tests", "importance": 0.9})

    result = run_consolidation_cycle(state_dir=tmp_path, min_candidates_for_promotion=1)

    assert result["receipt"]["truth_label"] == "WEIGHT_CONSOLIDATION_RECEIPT"
    assert result["promotion"]["decision"] == "DO_NOT_PROMOTE"
    assert "no_candidate_cortex_path" in result["promotion"]["blockers"]
    assert (tmp_path / "weight_consolidation_receipt.jsonl").exists()
    assert "WEIGHT CONSOLIDATION" in summary_for_prompt(state_dir=tmp_path)
