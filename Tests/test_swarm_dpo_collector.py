from __future__ import annotations

import json
from pathlib import Path


def test_log_dpo_pair_is_idempotent(tmp_path: Path, monkeypatch):
    from System import swarm_dpo_collector as dpo

    monkeypatch.setattr(dpo, "_STATE", tmp_path)
    monkeypatch.setattr(dpo, "_DPO_LEDGER", tmp_path / "dpo_pairs.jsonl")

    first = dpo.log_dpo_pair(
        prompt="now playing Get Shorty",
        rejected="**System Acknowledgment:** Acknowledged.",
        preferred="Got it. Get Shorty is on.",
        source="test",
    )
    second = dpo.log_dpo_pair(
        prompt="now playing Get Shorty",
        rejected="**System Acknowledgment:** Acknowledged.",
        preferred="Got it. Get Shorty is on.",
        source="test",
    )

    assert first is not None
    assert second is None
    rows = [
        json.loads(line)
        for line in (tmp_path / "dpo_pairs.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 1
    assert rows[0]["pair_key"]
    assert rows[0]["truth_label"] == "DPO_PAIR"


def test_export_only_uses_curated_pairs(tmp_path: Path, monkeypatch):
    from System import swarm_dpo_collector as dpo

    monkeypatch.setattr(dpo, "_STATE", tmp_path)
    monkeypatch.setattr(dpo, "_DATA", tmp_path)
    monkeypatch.setattr(dpo, "_DPO_LEDGER", tmp_path / "dpo_pairs.jsonl")
    monkeypatch.setattr(dpo, "_DPO_EXPORT", tmp_path / "dpo_train.jsonl")
    monkeypatch.setattr(dpo, "_DPO_CURATION_REPORT", tmp_path / "dpo_curation_report.json")
    monkeypatch.setattr(dpo, "_DPO_CURATION_RECEIPTS", tmp_path / "dpo_curation_receipts.jsonl")

    dpo.log_dpo_pair("p1", "bad", "good", source="ready")
    dpo.log_dpo_pair("p2", "bad", None, source="pending")

    result = dpo.export_dpo_training(min_pairs=2)

    assert result["exported"] == 1
    assert result["pending_curation"] == 1
    assert result["ready_for_training"] is False
    rows = [
        json.loads(line)
        for line in (tmp_path / "dpo_train.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert rows == [{"prompt": "p1", "chosen": "good", "rejected": "bad"}]


def test_curator_repairs_bad_preferred_without_rewriting_ledger(tmp_path: Path, monkeypatch):
    from System import swarm_dpo_collector as dpo

    monkeypatch.setattr(dpo, "_STATE", tmp_path)
    monkeypatch.setattr(dpo, "_DATA", tmp_path)
    monkeypatch.setattr(dpo, "_DPO_LEDGER", tmp_path / "dpo_pairs.jsonl")
    monkeypatch.setattr(dpo, "_DPO_EXPORT", tmp_path / "dpo_train.jsonl")
    monkeypatch.setattr(dpo, "_DPO_CURATION_REPORT", tmp_path / "dpo_curation_report.json")
    monkeypatch.setattr(dpo, "_DPO_CURATION_RECEIPTS", tmp_path / "dpo_curation_receipts.jsonl")

    dpo.log_dpo_pair(
        "As an AI language model, I cannot inspect local hardware.",
        "As an AI language model, I cannot inspect local hardware.",
        "I don't have access to inspect that directly.",
        source="test",
    )

    result = dpo.curate_dpo_training(min_pairs=1)

    assert result["exported"] == 1
    exported = json.loads((tmp_path / "dpo_train.jsonl").read_text().splitlines()[0])
    assert exported["chosen"].startswith("I answer from my local SIFTA runtime")
    raw_ledger = (tmp_path / "dpo_pairs.jsonl").read_text()
    assert "I don't have access to inspect that directly." in raw_ledger


def test_curator_rejects_training_pair_if_chosen_still_has_residue(tmp_path: Path, monkeypatch):
    from System import swarm_dpo_collector as dpo

    monkeypatch.setattr(dpo, "_STATE", tmp_path)
    monkeypatch.setattr(dpo, "_DATA", tmp_path)
    monkeypatch.setattr(dpo, "_DPO_LEDGER", tmp_path / "dpo_pairs.jsonl")
    monkeypatch.setattr(dpo, "_DPO_EXPORT", tmp_path / "dpo_train.jsonl")
    monkeypatch.setattr(dpo, "_DPO_CURATION_REPORT", tmp_path / "dpo_curation_report.json")
    monkeypatch.setattr(dpo, "_DPO_CURATION_RECEIPTS", tmp_path / "dpo_curation_receipts.jsonl")

    dpo.log_dpo_pair(
        "hello",
        "bad",
        "I am here to assist you with your tasks.",
        source="test",
    )

    result = dpo.curate_dpo_training(min_pairs=1)

    assert result["exported"] == 0
    assert result["rejected"] == 1
    assert result["rejected_rows"][0]["errors"] == ["chosen_contains_residue"]
