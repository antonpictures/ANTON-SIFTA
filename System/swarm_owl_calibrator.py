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
import numpy as np
from System.swarm_owl_spatial_hearing import OwlSpatialHearing

def generate_lag_tone(lag_samples: int, length: int = 2000) -> tuple[np.ndarray, np.ndarray]:
    """Generate stereo buffer with a known sample lag on the right channel."""
    # Use a broadband noise burst for clear cross-correlation peaks
    base = np.random.normal(0, 0.5, length)
    if lag_samples >= 0:
        # Right is delayed (sound comes from the left)
        left = np.pad(base, (0, lag_samples))
        right = np.pad(base, (lag_samples, 0))
    else:
        # Left is delayed (sound comes from the right)
        left = np.pad(base, (abs(lag_samples), 0))
        right = np.pad(base, (0, abs(lag_samples)))
    return left, right

def run_calibration_sweep():
    distances = [0.10, 0.20, 0.30]  # meters
    sample_rates = [16000, 44100, 48000]  # Hz
    true_azimuths = [-math.pi/4, 0.0, math.pi/4]  # radians (-45, 0, 45 deg)
    speed_of_sound = 343.0

    print("🦉 Commencing Owl ITD Calibration Sweep...")
    print("-" * 75)
    print(f"{'Ear Dist':>8} | {'SR (Hz)':>7} | {'True Az (rad)':>13} | {'Pred Az (rad)':>13} | {'Error (rad)':>11}")
    print("-" * 75)

    total_error = 0.0
    count = 0

    for d in distances:
        for sr in sample_rates:
            owl = OwlSpatialHearing(ear_distance_meters=d, speed_of_sound=speed_of_sound)
            for true_az in true_azimuths:
                # Math: sin(theta) = ITD * c / d => ITD = sin(theta) * d / c
                itd_true = math.sin(true_az) * d / speed_of_sound
                lag_samples = int(round(itd_true * sr))
                
                left, right = generate_lag_tone(lag_samples, length=2000)
                
                # compute_localization and log to ledger
                # This naturally feeds calibrated azimuth_rad into Event 98b via ledger
                receipt = owl.log_localization(left, right, sr=sr)
                pred_az = receipt["azimuth_rad"]
                error = abs(true_az - pred_az)
                
                print(f"{d:8.2f} | {sr:7} | {true_az:13.4f} | {pred_az:13.4f} | {error:11.4f}")
                
                total_error += error
                count += 1
                
    mean_error = total_error / count
    print("-" * 75)
    print(f"Calibration complete. Mean angular error: {mean_error:.4f} radians.")
    print("Regression receipts deposited to .sifta_state/owl_spatial_hearing.jsonl")

if __name__ == "__main__":
    run_calibration_sweep()
