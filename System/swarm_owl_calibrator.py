#!/usr/bin/env python3
# System/swarm_owl_calibrator.py
"""
Event 97 (Calibration) — Owl ITD/ILD Calibrator

Biology: Owls calibrate their spatial hearing maps continuously.
SIFTA: Sweeps `ear_distance_meters` and `sample_rate` against known lag tones
to verify mathematical recovery of ground-truth `azimuth_rad`. 
Writes regression receipts to `owl_spatial_hearing.jsonl` under `SIMULATED_SPATIAL_HEARING`.
These calibrated receipts automatically replace the naive `0.0` default in 
Event 98b (Superior Colliculus Integrator) when read from the ledger.
"""

import math
import json
from pathlib import Path
from typing import Iterable, Optional

import numpy as np
from System.jsonl_file_lock import append_line_locked
from System.swarm_owl_spatial_hearing import OwlSpatialHearing, TRUTH_LABEL, owl_ledger_path


DEFAULT_DISTANCES_M = (0.10, 0.20, 0.30)
DEFAULT_SAMPLE_RATES = (16000, 44100, 48000)
DEFAULT_AZIMUTHS_RAD = (-math.pi / 4.0, 0.0, math.pi / 4.0)
DEFAULT_SPEED_OF_SOUND = 343.0
DEFAULT_SEED = 555


def generate_lag_tone(
    lag_samples: int,
    length: int = 2000,
    *,
    rng: Optional[np.random.Generator] = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Generate stereo buffer with a known sample lag on the right channel."""
    # Use a broadband noise burst for clear cross-correlation peaks
    generator = rng or np.random.default_rng(DEFAULT_SEED)
    base = generator.normal(0, 0.5, length)
    if lag_samples >= 0:
        # Right is delayed (sound comes from the left)
        left = np.pad(base, (0, lag_samples))
        right = np.pad(base, (lag_samples, 0))
    else:
        # Left is delayed (sound comes from the right)
        left = np.pad(base, (abs(lag_samples), 0))
        right = np.pad(base, (0, abs(lag_samples)))
    return left, right


def expected_lag_samples(
    azimuth_rad: float,
    *,
    ear_distance_meters: float,
    sample_rate: int,
    speed_of_sound: float = DEFAULT_SPEED_OF_SOUND,
) -> int:
    """Expected ITD lag for a known azimuth under the simple two-ear model."""
    itd_true = math.sin(float(azimuth_rad)) * float(ear_distance_meters) / float(speed_of_sound)
    return int(round(itd_true * int(sample_rate)))


def _format_row(row: dict) -> str:
    return (
        f"{row['ear_distance_meters']:8.2f} | {row['sample_rate']:7d} | "
        f"{row['true_azimuth_rad']:13.4f} | {row['azimuth_rad']:13.4f} | "
        f"{row['angular_error_rad']:11.4f}"
    )


def run_calibration_sweep(
    *,
    distances: Iterable[float] = DEFAULT_DISTANCES_M,
    sample_rates: Iterable[int] = DEFAULT_SAMPLE_RATES,
    true_azimuths: Iterable[float] = DEFAULT_AZIMUTHS_RAD,
    speed_of_sound: float = DEFAULT_SPEED_OF_SOUND,
    seed: int = DEFAULT_SEED,
    ledger_path: Optional[Path] = None,
    state_root: Optional[Path] = None,
    deposit_receipts: bool = True,
    verbose: bool = True,
) -> dict:
    """Run a deterministic ITD/ILD sweep and optionally append calibration receipts."""
    target = ledger_path or owl_ledger_path(state_root)
    rng = np.random.default_rng(seed)
    rows: list[dict] = []

    if verbose:
        print("Commencing Owl ITD Calibration Sweep...")
        print("-" * 75)
        print(f"{'Ear Dist':>8} | {'SR (Hz)':>7} | {'True Az (rad)':>13} | {'Pred Az (rad)':>13} | {'Error (rad)':>11}")
        print("-" * 75)

    for d in distances:
        for sr in sample_rates:
            owl = OwlSpatialHearing(ear_distance_meters=float(d), speed_of_sound=float(speed_of_sound))
            for true_az in true_azimuths:
                lag_samples = expected_lag_samples(
                    true_az,
                    ear_distance_meters=float(d),
                    sample_rate=int(sr),
                    speed_of_sound=float(speed_of_sound),
                )
                
                left, right = generate_lag_tone(lag_samples, length=2000, rng=rng)
                
                receipt = owl.compute_localization(left, right, sr=int(sr))
                pred_az = receipt["azimuth_rad"]
                error = abs(true_az - pred_az)
                receipt.update(
                    {
                        "event": "owl_itd_ild_calibration",
                        "truth_label": TRUTH_LABEL,
                        "calibration_truth_label": "SIMULATED_SPATIAL_HEARING_CALIBRATION",
                        "ear_distance_meters": round(float(d), 6),
                        "sample_rate": int(sr),
                        "speed_of_sound": float(speed_of_sound),
                        "true_azimuth_rad": round(float(true_az), 6),
                        "expected_lag_samples": int(lag_samples),
                        "angular_error_rad": round(float(error), 6),
                        "seed": int(seed),
                        "raw_audio_logged": False,
                    }
                )
                rows.append(receipt)
                
                if deposit_receipts:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    append_line_locked(target, json.dumps(receipt, sort_keys=True) + "\n")
                if verbose:
                    print(_format_row(receipt))
                
    count = len(rows)
    mean_error = sum(float(r["angular_error_rad"]) for r in rows) / max(1, count)
    max_error = max((float(r["angular_error_rad"]) for r in rows), default=0.0)
    summary = {
        "event": "owl_itd_ild_calibration_summary",
        "truth_label": "SIMULATED_SPATIAL_HEARING_CALIBRATION",
        "count": count,
        "mean_angular_error_rad": round(float(mean_error), 6),
        "max_angular_error_rad": round(float(max_error), 6),
        "ledger_path": str(target),
        "deposited": bool(deposit_receipts),
        "seed": int(seed),
        "rows": rows,
    }
    if verbose:
        print("-" * 75)
        print(f"Calibration complete. Mean angular error: {summary['mean_angular_error_rad']:.4f} radians.")
        if deposit_receipts:
            print(f"Regression receipts deposited to {target}")
    return summary

if __name__ == "__main__":
    run_calibration_sweep()
