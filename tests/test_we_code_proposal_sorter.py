from __future__ import annotations

import json
from pathlib import Path

from System.swarm_we_code_proposal_sorter import score_and_clean_backlog


def _append_jsonl(path: Path, row: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_score_and_clean_backlog_collapses_duplicates_without_rewriting_raw_backlog(tmp_path: Path) -> None:
    backlog = tmp_path / "we_code_together_to_be_coded.jsonl"
    duplicate_title = "Implement relational_coherence_score in intentional/stigmergic receipts"
    proposal = (
        "```python\n"
        "def calculate_relational_coherence(mutation_score, attention_magnitude, hex_energy_reading):\n"
        "    return round(mutation_score * 0.25 + attention_magnitude * 0.25 + hex_energy_reading * 0.15, 4)\n"
        "```\n"
        "Add tests and write future receipts with relational_coherence_score."
    )
    _append_jsonl(
        backlog,
        {
            "truth_label": "WE_CODE_TOGETHER_TO_BE_CODED_V1",
            "ts": 10.0,
            "receipt_id": "proposal-old",
            "status": "proposal_queued",
            "priority": 2,
            "title": duplicate_title,
            "task": duplicate_title,
            "proposal_preview": proposal,
            "source_receipt_id": "source-old",
            "expected_receipts": ["code patch receipt", "focused tests"],
        },
    )
    _append_jsonl(
        backlog,
        {
            "truth_label": "WE_CODE_TOGETHER_TO_BE_CODED_V1",
            "ts": 20.0,
            "receipt_id": "proposal-new",
            "status": "proposal_queued",
            "priority": 2,
            "title": duplicate_title,
            "task": duplicate_title,
            "proposal_preview": proposal + "\nUse browser_stigmergic_memory receipts.",
            "source_receipt_id": "source-new",
            "expected_receipts": ["code patch receipt", "focused tests", "WCT coded receipt"],
        },
    )
    _append_jsonl(
        backlog,
        {
            "truth_label": "WE_CODE_TOGETHER_TO_BE_CODED_V1",
            "ts": 30.0,
            "receipt_id": "weak-proposal",
            "status": "proposal_queued",
            "priority": 2,
            "title": "Vague beautiful field prose",
            "task": "Vague beautiful field prose",
            "proposal_preview": "This is beautiful and fully present, but not real code.",
        },
    )

    first = score_and_clean_backlog(state_dir=tmp_path)
    second = score_and_clean_backlog(state_dir=tmp_path)

    raw_rows = _read_jsonl(backlog)
    clean_rows = _read_jsonl(tmp_path / "we_code_together_to_be_coded.clean.jsonl")
    score_rows = _read_jsonl(tmp_path / "we_code_together_proposal_scores.jsonl")
    stgm_rows = _read_jsonl(tmp_path / "stgm_memory_rewards.jsonl")

    assert len(raw_rows) == 3
    assert first["clean_count"] == 2
    assert first["duplicates_found"] == 1
    assert first["new_duplicate_scores"] == 1
    assert second["new_score_rows"] == 0
    assert len(clean_rows) == 2
    assert clean_rows[0]["receipt_id"] == "proposal-new"
    assert clean_rows[0]["duplicate_count"] == 2
    assert clean_rows[0]["sorter_decision"] == "code_next"
    assert any(row["decision"] == "duplicate_archive" and row["duplicate_of"] == "proposal-new" for row in score_rows)
    assert len(score_rows) == 3
    assert stgm_rows
    assert stgm_rows[0]["truth_label"] == "WE_CODE_TOGETHER_PROPOSAL_STGM_V1"
