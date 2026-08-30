from __future__ import annotations

import json
import os
from pathlib import Path

from tools.prepare_sol_landing_zone import build_landing_zone, write_landing_zone


def _write_snapshot(state: Path) -> None:
    payload = {
        "truth_label": "CANONICAL_ORGAN_REGISTRY_V1",
        "ts": 100.0,
        "counts": {"canonical_organs": 19, "registry_organs": 23},
        "merged_sources": {"canonical": 19, "discovered": 4},
        "gaps": ["test_gap"],
        "code_inventory": {
            "living_substrate": {"py_files": 3, "py_loc": 42},
            "repo_rollups": {"grand_total_python_estimate": 99},
        },
    }
    (state / "canonical_organ_registry_snapshot.json").write_text(json.dumps(payload), encoding="utf-8")


def test_build_landing_zone_uses_snapshot_and_bounded_ledger_tails(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    state.mkdir()
    _write_snapshot(state)
    (state / "spinal_cord_cycles.jsonl").write_text(
        '{"status":"NO_PATCH","cycle_id":"test-cycle"}\n', encoding="utf-8"
    )
    (state / "eval").mkdir()
    matrix = state / "eval" / "ORGAN_EVAL_MATRIX_V2.html"
    matrix.write_text("old", encoding="utf-8")
    os.utime(matrix, (1.0, 1.0))

    packet = build_landing_zone(repo=tmp_path, state_dir=state, now=200.0)

    assert packet["schema"] == "SOL_LANDING_ZONE_V1"
    assert packet["body_snapshot"]["counts"]["canonical_organs"] == 19
    assert packet["body_snapshot"]["living_substrate"]["py_loc"] == 42
    spinal = next(row for row in packet["ledgers"] if row["path"].endswith("spinal_cord_cycles.jsonl"))
    assert spinal["status"] == "PRESENT_WITH_TAIL"
    assert spinal["tail"][-1]["status"] == "NO_PATCH"
    assert packet["matrix"]["html_stale_against_snapshot"] is True
    assert packet["next_tasks"][0]["id"] == "sol-registry-reconciliation"
    assert packet["completed_tasks"][0]["id"] == "sol-matrix-fast-path"
    assert packet["completed_tasks"][0]["status"] == "OPERATIONAL"
    assert any("not by itself behavioral proof" in rule for rule in packet["rules"])


def test_write_landing_zone_creates_json_artifact(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    state.mkdir()
    _write_snapshot(state)
    output = state / "sol_landing_zone.json"

    written = write_landing_zone(repo=tmp_path, state_dir=state, output_path=output, now=200.0)

    assert output.exists()
    assert json.loads(output.read_text(encoding="utf-8"))["generated_at"] == 200.0
    assert written["truth_label"] == "OBSERVED_SNAPSHOT_AND_BOUNDED_TAILS"
