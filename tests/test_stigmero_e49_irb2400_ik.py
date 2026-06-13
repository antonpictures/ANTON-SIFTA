from pathlib import Path

import pytest

from System.stigmerobotics_irb2400_benchmark import (
    IRB2400SchemaError,
    REQUIRED_COLUMNS,
    benchmark_irb2400_csv,
    load_irb2400_rows,
    main,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_irb2400_fixture_schema_loads() -> None:
    rows = load_irb2400_rows(FIXTURES / "stigmero_irb2400_schema_sample.csv")

    assert len(rows) == 8
    assert rows[0].pose == (0.1, 0.2, 0.3, 5.0, 10.0, 15.0)
    assert rows[0].q_in == (1.0, 2.0, 3.0, 4.0, 5.0, 6.0)
    assert rows[0].q_out == (1.1, 2.1, 3.1, 4.1, 5.1, 6.1)


def test_irb2400_benchmark_reports_heldout_joint_error() -> None:
    report = benchmark_irb2400_csv(
        FIXTURES / "stigmero_irb2400_schema_sample.csv",
        holdout_stride=4,
    )

    assert report["event"] == "E49_IRB2400_IK_BENCHMARK"
    assert report["truth_label"] == "OPERATIONAL"
    assert report["data_truth_label"] == "SANITIZED_FIXTURE"
    assert report["full_kaggle_dataset_vendored"] is False
    assert report["row_count"] == 8
    assert report["train_rows"] == 6
    assert report["eval_rows"] == 2
    assert report["schema_columns"] == list(REQUIRED_COLUMNS)
    assert report["mean_abs_joint_error"] < 0.25
    assert report["max_abs_joint_error"] < 0.35
    assert report["proof_of_property"]["no_actuation"] is True
    assert report["proof_of_property"]["full_kaggle_claim"] == "not_claimed_by_code"


def test_irb2400_loader_rejects_missing_required_columns(tmp_path: Path) -> None:
    bad_csv = tmp_path / "bad_irb2400.csv"
    bad_csv.write_text("x,y,z,q1_out\n0.1,0.2,0.3,1.0\n", encoding="utf-8")

    with pytest.raises(IRB2400SchemaError, match="missing required IRB2400 columns"):
        load_irb2400_rows(bad_csv)


def test_irb2400_cli_emits_json(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main([str(FIXTURES / "stigmero_irb2400_schema_sample.csv")])

    assert rc == 0
    captured = capsys.readouterr().out
    assert '"event": "E49_IRB2400_IK_BENCHMARK"' in captured
    assert '"predictor": "stigmergic_nearest_trace_field_v1"' in captured
