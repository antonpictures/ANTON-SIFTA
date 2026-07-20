"""r1390 — unwired organ triage organ + census integration (r1387 Cursor lane)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from System.swarm_unwired_organ_triage import (
    TRUTH_LABEL,
    classify_unwired_candidate,
    load_triage_map,
    merge_triage_into_report,
    triage_unwired_rows,
)


def test_classify_legacy_as_retired() -> None:
    status, reason, proof = classify_unwired_candidate(
        {"file": "Applications/whatsapp_swarm_LEGACY.py", "stem": "whatsapp_swarm_LEGACY", "truth_labels": []}
    )
    assert status == "retired"
    assert "LEGACY" in reason
    assert proof


def test_classify_tools_as_standalone() -> None:
    status, _, _ = classify_unwired_candidate(
        {"file": "tools/rotate_sifta_ledgers.py", "stem": "rotate_sifta_ledgers", "truth_labels": []}
    )
    assert status == "intentional_standalone"


def test_classify_sim_truth_as_standalone() -> None:
    status, reason, _ = classify_unwired_candidate(
        {
            "file": "System/swarm_bose_hubbard.py",
            "stem": "swarm_bose_hubbard",
            "truth_labels": ["BOSE_HUBBARD_ANALOGUE_ONLY: sim"],
            "test_reference_count": 1,
            "test_reference_files": ["tests/test_yoshida_and_bose_hubbard.py"],
        }
    )
    assert status == "intentional_standalone"
    assert "SIM" in reason or "research" in reason


def test_triage_writes_ledger_and_merge_zero_untriaged(tmp_path: Path) -> None:
    sd = tmp_path / ".sifta_state"
    rows = [
        {
            "file": "System/swarm_bose_hubbard.py",
            "stem": "swarm_bose_hubbard",
            "status": "UNWIRED_CANDIDATE",
            "organ_score": 14,
            "truth_labels": ["SIM_ONLY"],
            "test_reference_count": 1,
            "test_reference_files": ["tests/test_x.py"],
            "has_main": False,
        },
        {
            "file": "Applications/whatsapp_swarm_LEGACY.py",
            "stem": "whatsapp_swarm_LEGACY",
            "status": "UNWIRED_CANDIDATE",
            "organ_score": 10,
            "truth_labels": [],
            "test_reference_count": 0,
            "has_main": False,
        },
    ]
    result = triage_unwired_rows(rows, state_dir=sd)
    assert result["written"] == 2
    ledger = sd / "unwired_organ_triage.jsonl"
    assert ledger.exists()
    lines = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert all(row["truth_label"] == TRUTH_LABEL for row in lines)
    merged = merge_triage_into_report({"rows": rows}, state_dir=sd)
    assert merged["untriaged_unwired"] == 0
    assert merged["by_triage_status"]["retired"] == 1
    assert merged["by_triage_status"]["intentional_standalone"] == 1
    assert load_triage_map(state_dir=sd)


def test_find_unwired_organs_cli_has_triage_flag() -> None:
    src = Path("tools/find_unwired_organs.py").read_text(encoding="utf-8")
    assert "swarm_unwired_organ_triage" in src
    assert "--triage" in src
    assert "UNTRIAGED_UNWIRED" in src


def test_live_repo_untriaged_zero_after_triage() -> None:
    """Full r1387 acceptance: census + --triage leaves UNTRIAGED_UNWIRED at 0."""
    import subprocess

    repo = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        ["python3", "tools/find_unwired_organs.py", "--triage"],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    assert "UNTRIAGED_UNWIRED: 0" in proc.stdout
    report = json.loads((repo / ".sifta_state/unwired_organs_report.json").read_text(encoding="utf-8"))
    assert report["untriaged_unwired"] == 0
    assert report["by_triage_status"]
    assert sum(report["by_triage_status"].values()) >= 190