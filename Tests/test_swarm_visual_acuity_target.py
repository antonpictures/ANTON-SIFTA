import json

from System.swarm_visual_acuity_target import current_acuity, step_acuity, summary_for_prompt


def test_step_acuity_reads_latest_visual_grid_and_writes_target(tmp_path):
    (tmp_path / "visual_stigmergy.jsonl").write_text(
        json.dumps({"ts": 1, "grid_size": 44}) + "\n",
        encoding="utf-8",
    )

    row = step_acuity(
        "increase",
        state_dir=tmp_path,
        writer="test",
        source_text="Increase camera resolution one step.",
    )

    assert row["grid_size"] == 46
    assert current_acuity(state_dir=tmp_path) == 46
    assert "grid_size=46" in summary_for_prompt(row)
    saved = json.loads((tmp_path / "active_visual_acuity.json").read_text(encoding="utf-8"))
    assert saved["grid_size"] == 46


def test_step_acuity_decreases_and_clamps(tmp_path):
    row = step_acuity("decrease", state_dir=tmp_path, writer="test")

    assert row["grid_size"] == 30
    assert row["total_cells"] == 900
