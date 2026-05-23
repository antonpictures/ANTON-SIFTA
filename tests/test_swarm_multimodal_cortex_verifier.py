from __future__ import annotations

import json

from System import swarm_multimodal_cortex_verifier as verifier


def _passing() -> dict:
    return {"vision": 0.87, "audio": 0.91, "tool": 0.79, "owner_continuity": 0.95}


def test_run_loop_passes_when_all_probes_clear(tmp_path) -> None:
    row = verifier.run_loop("gemma4:26b", _passing(), root=tmp_path)

    assert row["truth_label"] == "MULTIMODAL_CORTEX_VERIFICATION"
    assert row["pass"] is True
    assert row["overall"] >= verifier.MIN_OVERALL
    written = json.loads(verifier.log_path(tmp_path).read_text(encoding="utf-8").strip())
    assert written["cortex_id"] == "gemma4:26b"


def test_run_loop_fails_missing_probe(tmp_path) -> None:
    row = verifier.run_loop("gemma4:26b", {"vision": 0.9, "audio": 0.9}, root=tmp_path)

    assert row["pass"] is False
    assert "tool" in row["missing_probes"]
    assert "owner_continuity" in row["missing_probes"]


def test_run_loop_fails_low_single_probe(tmp_path) -> None:
    results = _passing()
    results["tool"] = 0.7

    row = verifier.run_loop("gemma4:26b", results, root=tmp_path, write_ledger=False)

    assert row["overall"] >= verifier.MIN_OVERALL
    assert row["pass"] is False


def test_verify_after_switch_records_delta(tmp_path) -> None:
    before = {"vision": 0.8, "audio": 0.8, "tool": 0.8, "owner_continuity": 0.8}
    after = _passing()

    row = verifier.verify_after_switch("old", "new", before_results=before, after_results=after, root=tmp_path)

    assert row["pass"] is True
    assert row["delta"]["vision"] == 0.07
    assert verifier.log_path(tmp_path).exists()


def test_summary_for_prompt(tmp_path) -> None:
    verifier.run_loop("gemma4:26b", _passing(), root=tmp_path)

    assert "CORTEX VERIFICATION" in verifier.summary_for_prompt(root=tmp_path)
