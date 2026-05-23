import json
import math
from pathlib import Path

from System import swarm_owl_calibrator as cal


def test_expected_lag_samples_preserves_direction() -> None:
    left = cal.expected_lag_samples(-math.pi / 6, ear_distance_meters=0.2, sample_rate=48_000)
    center = cal.expected_lag_samples(0.0, ear_distance_meters=0.2, sample_rate=48_000)
    right = cal.expected_lag_samples(math.pi / 6, ear_distance_meters=0.2, sample_rate=48_000)

    assert left < 0
    assert center == 0
    assert right > 0


def test_calibration_sweep_is_deterministic_and_accurate_without_deposit(tmp_path: Path) -> None:
    kwargs = dict(
        distances=(0.2,),
        sample_rates=(48_000,),
        true_azimuths=(-math.pi / 6, 0.0, math.pi / 6),
        state_root=tmp_path,
        deposit_receipts=False,
        verbose=False,
        seed=123,
    )

    first = cal.run_calibration_sweep(**kwargs)
    second = cal.run_calibration_sweep(**kwargs)

    assert first["count"] == 3
    assert first["mean_angular_error_rad"] < 0.002
    assert first["max_angular_error_rad"] < 0.003
    assert [r["azimuth_rad"] for r in first["rows"]] == [r["azimuth_rad"] for r in second["rows"]]
    assert not (tmp_path / "owl_spatial_hearing.jsonl").exists()


def test_calibration_sweep_writes_feature_only_receipts(tmp_path: Path) -> None:
    summary = cal.run_calibration_sweep(
        distances=(0.2,),
        sample_rates=(16_000,),
        true_azimuths=(-math.pi / 4, 0.0, math.pi / 4),
        state_root=tmp_path,
        deposit_receipts=True,
        verbose=False,
        seed=555,
    )

    ledger = tmp_path / "owl_spatial_hearing.jsonl"
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]

    assert summary["deposited"] is True
    assert len(rows) == summary["count"] == 3
    assert all(row["event"] == "owl_itd_ild_calibration" for row in rows)
    assert all(row["truth_label"] == "SIMULATED_SPATIAL_HEARING" for row in rows)
    assert all(row["calibration_truth_label"] == "SIMULATED_SPATIAL_HEARING_CALIBRATION" for row in rows)
    assert all(row["raw_audio_logged"] is False for row in rows)
