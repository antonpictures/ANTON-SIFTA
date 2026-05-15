import json
from pathlib import Path

import System.swarm_mammal_weight_manager as wm
from System.swarm_mammal_weight_manager import (
    REQUIRED_FILES,
    TRUTH_LABEL,
    mammal_weight_status,
    write_mammal_weight_receipt,
)


def test_weight_status_reports_missing_snapshot(tmp_path):
    status = mammal_weight_status(tmp_path, hash_files=True)
    assert status["truth_label"] == TRUTH_LABEL
    assert status["installed"] is False
    assert set(status["missing"]) == set(REQUIRED_FILES)


def test_weight_status_reports_present_snapshot(tmp_path):
    for rel in REQUIRED_FILES:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"fixture:{rel}", encoding="utf-8")
    meta = tmp_path / ".cache/huggingface/download/model.safetensors.metadata"
    meta.parent.mkdir(parents=True, exist_ok=True)
    meta.write_text("abc123\nsha\n0\n", encoding="utf-8")
    status = mammal_weight_status(tmp_path, hash_files=True)
    assert status["installed"] is True
    assert status["revision"] == "abc123"
    assert status["n_present_files"] == len(REQUIRED_FILES)
    assert all(f["sha256"] for f in status["files"])


def test_weight_status_falls_back_to_hf_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(wm, "MAMMAL_LOCAL_DIR", tmp_path / "missing_sifta_copy")
    monkeypatch.setenv("HF_HOME", str(tmp_path / "hf"))
    snap = (
        tmp_path
        / "hf"
        / "hub"
        / "models--ibm-research--biomed.omics.bl.sm.ma-ted-458m"
        / "snapshots"
        / "rev-test"
    )
    for rel in REQUIRED_FILES:
        p = snap / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"fixture:{rel}", encoding="utf-8")
    status = mammal_weight_status(hash_files=False)
    assert status["installed"] is True
    assert status["source"] == "huggingface_cache_snapshot"
    assert status["revision"] == "rev-test"
    assert status["local_dir"] == str(snap)
    assert any("missing_sifta_copy" in root for root in status["probed_roots"])


def test_write_weight_receipt_roundtrips(tmp_path):
    status = {"truth_label": TRUTH_LABEL, "installed": True}
    row = write_mammal_weight_receipt(status, state_root=tmp_path)
    ledger = tmp_path / "mammal_weight_receipts.jsonl"
    got = json.loads(ledger.read_text().splitlines()[-1])
    assert got["trace_id"] == row["trace_id"]
    assert got["truth_label"] == TRUTH_LABEL
    assert got["payload"]["installed"] is True
    assert len(got["sha256"]) == 64
