import json
import time
from pathlib import Path

from System.swarm_residue_self_knowledge import (
    residue_self_knowledge_prompt_block,
    residue_system_snapshot,
    should_include_residue_self_knowledge,
)


def _append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")


def test_residue_prompt_is_topic_triggered_only(tmp_path):
    assert should_include_residue_self_knowledge("why did the gag app catch this?")
    assert should_include_residue_self_knowledge("check your residue metabolism")
    assert should_include_residue_self_knowledge("is the deterministic detector running?")
    assert not should_include_residue_self_knowledge("please open youtube")
    assert residue_self_knowledge_prompt_block("please open youtube", state_dir=tmp_path) == ""


def test_residue_prompt_names_real_ledgers_and_blocks_stale_detector_claim(tmp_path):
    now = 2_000.0
    _append(
        tmp_path / "residue_excretion_quality.jsonl",
        {
            "ts": now - 5,
            "receipt_id": "rx-1",
            "verdict": "sinking",
            "verdict_prose": "sinking flush",
            "removed_ratio": 0.12,
            "patterns_eliminated": ["md_bold_label"],
        },
    )
    _append(
        tmp_path / "training_shape_residue.jsonl",
        {
            "ts": now - 4,
            "receipt_id": "train-1",
            "action": "cleaned_before_speech",
            "changed": True,
            "patterns": [{"name": "md_bold_label", "count": 1}],
        },
    )
    _append(
        tmp_path / "alice_cortex_transform_chain.jsonl",
        {
            "ts": now - 3,
            "receipt_id": "chain-1",
            "gate": "FULL_FILTER_CHAIN",
            "changed": True,
            "raw_len": 2871,
            "delivered_len": 2612,
        },
    )
    _append(
        tmp_path / "stigmergic_deterministic_tracker.jsonl",
        {
            "ts": now - 300,
            "organ": "stigmergic_deterministic_tracker",
            "grounding_score": 60,
            "bypasses_detected": 10,
        },
    )

    block = residue_self_knowledge_prompt_block(
        "how would you fix this gag with the detector?",
        state_dir=tmp_path,
        now=now,
        tracker_fresh_s=12.0,
    )

    assert "RESIDUE METABOLISM SELF-KNOWLEDGE" in block
    assert "Receipts are not optional overhead" in block
    assert "residue_excretion_quality" in block
    assert "training_shape_residue" in block
    assert "transform_chain" in block
    assert "gag_viewer" in block
    assert "deterministic_tracker" in block
    assert "running/confirming/diagnosing claims sort to a fresh tracker row" in block
    assert "the honest answer is the tracker is idle" in block
    assert "verdict=sinking" in block
    assert "receipt_id=rx-1" in block


def test_tracker_freshness_allows_only_row_fields(tmp_path):
    now = time.time()
    _append(
        tmp_path / "stigmergic_deterministic_tracker.jsonl",
        {
            "ts": now - 2,
            "organ": "stigmergic_deterministic_tracker",
            "grounding_score": 82,
            "bypasses_detected": 1,
            "note": "Live field read.",
        },
    )

    snap = residue_system_snapshot(state_dir=tmp_path, now=now, tracker_fresh_s=12.0)
    block = residue_self_knowledge_prompt_block(
        "check the deterministic tracker",
        state_dir=tmp_path,
        now=now,
        tracker_fresh_s=12.0,
    )

    assert snap["tracker_fresh"] is True
    assert "has a fresh tick" in block
    assert "I may cite only the row's actual fields" in block
    assert "grounding_score=82" in block
