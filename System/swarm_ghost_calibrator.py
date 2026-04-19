#!/usr/bin/env python3
"""
swarm_ghost_calibrator.py — The Homeostatic Baseline
═══════════════════════════════════════════════════════
SIFTA OS — DeepMind Cognitive Suite

Implements a purely Graph-Aligned Ghost calibrator. Instead of statically
triggering shockwaves across the filesystem, the system continually profiles
localized "Normal" topological arrival timings (`T_mean`, `T_std`).
If an anomalous structural damage event strikes, it combines the Z-score of
the time deviation with physical severity to dynamically extract Immune Confidence.
"""

import json
from pathlib import Path
from typing import Dict, Optional

MODULE_VERSION = "2026-04-19.v1"


class GhostCalibrator:
    """
    Learns topological normalcy to govern biological shock cascades.
    """
    # C47H BUG-22 fix: minimum observations before a baseline is trusted enough
    # to participate in scoring. Below this, the calibrator refuses to inflate
    # severity with a confabulated z-score (the original code returned
    # severity+0.50 for unknown files, causing a fresh organism to trigger
    # Cherenkov shockwaves on every routine compilation error).
    MIN_OBSERVATIONS_TO_SCORE = 3

    def __init__(self, state_dir: Optional[Path] = None):
        if state_dir:
            self.registry = Path(state_dir) / "ghost_calibration.json"
        else:
            self.registry = Path(__file__).resolve().parent.parent / ".sifta_state" / "ghost_calibration.json"
            
        self.registry.parent.mkdir(parents=True, exist_ok=True)
        # Structure: {path: {"T_mean": float, "T_std": float, "n": int}}
        self.baseline: Dict[str, Dict[str, float]] = {}
        self.dir_baseline: Dict[str, Dict[str, float]] = {}
        
        self.threshold = 0.85
        self._load()

    def _bucket(self, path_str: str) -> str:
        parts = path_str.replace("\\", "/").split("/")
        return "/".join(parts[:-1]) or "root"

    def _load(self):
        # C47H BUG-32 fix: backward-compatible schema migration. The pre-sigmoid
        # refactor wrote `self.baseline` directly as the JSON root. The new
        # schema wraps it in {"path": ..., "dir": ...}. Without this guard, any
        # pre-existing production ghost_calibration.json was silently dropped
        # on first load — all prior learning erased on upgrade.
        try:
            with open(self.registry, "r") as f:
                data = json.load(f)
            if isinstance(data, dict) and ("path" in data or "dir" in data):
                self.baseline = data.get("path", {})
                self.dir_baseline = data.get("dir", {})
            elif isinstance(data, dict):
                # Legacy schema — assume root dict IS the per-path baseline
                self.baseline = data
                self.dir_baseline = {}
            else:
                self.baseline = {}
                self.dir_baseline = {}
        except Exception:
            self.baseline = {}
            self.dir_baseline = {}

    def _persist(self):
        try:
            with open(self.registry, "w") as f:
                json.dump({"path": self.baseline, "dir": self.dir_baseline}, f)
        except Exception:
            pass

    def learn_normal(self, node: Path, localized_delta_t: float):
        """
        Updates the biological 'resting heartbeat' (temporal interaction frequency)
        for a localized geometry. Each observation feeds BOTH the per-file
        baseline AND its parent-directory bucket so under-sampled siblings can
        fall back to the directory aggregate (see C47H BUG-28).
        """
        node_str = str(Path(node).resolve())
        dir_str = self._bucket(node_str)
        # Update both the per-file and the parent-directory bucket so the
        # fallback path in score() actually has data to fall back to.
        self._update_welford(self.baseline, node_str, localized_delta_t)
        self._update_welford(self.dir_baseline, dir_str, localized_delta_t)
        self._persist()

    @staticmethod
    def _update_welford(table: Dict[str, Dict[str, float]], key: str, x: float) -> None:
        """C47H BUG-28 fix helper: shared Welford online update so the per-file
        and per-directory baselines stay in sync. Was duplicated inline; the
        directory branch was missing entirely (dead infrastructure)."""
        b = table.get(key)
        if not b:
            table[key] = {
                "T_mean": x,
                "T_std": 1.0,  # Prevent div-by-zero for single observation
                "n": 1.0,
            }
            return
        n = b["n"] + 1
        old_mean = b["T_mean"]
        new_mean = old_mean + (x - old_mean) / n
        old_std = b["T_std"]
        variance = (old_std ** 2 * (n - 1) + (x - old_mean) * (x - new_mean)) / n
        table[key] = {
            "T_mean": new_mean,
            "T_std": max(variance ** 0.5, 0.1),
            "n": n,
        }

    def score(self, node: Path, T_obs: float, severity: float) -> float:
        """
        Calculates Ghost Confidence.
        Combines topological Z-score (deviation from baseline frequency) with raw pain severity.
        """
        import math
        node_str = str(Path(node).resolve())
        dir_str = self._bucket(node_str)
        
        b = self.baseline.get(node_str)
        # Try finding exact file baseline. If missing or under-sampled, fall back to directory baseline.
        if (not b or b["n"] < getattr(self, "MIN_OBSERVATIONS_TO_SCORE", 2)) and dir_str in self.dir_baseline:
            b = self.dir_baseline[dir_str]

        # C47H BUG-22 fix: epistemological correction.
        if not b or b["n"] < getattr(self, "MIN_OBSERVATIONS_TO_SCORE", 2):
            return min(1.0, max(0.0, severity))

        zT = abs(T_obs - b["T_mean"]) / b["T_std"]
        mapped_z = min(zT, 6.0)
        
        # Perplexity Sigmoid Activation (BioLogicalNeuron)
        confidence = 1.0 / (1.0 + math.exp(-(mapped_z - 1.5)))
        confidence = min(1.0, confidence + severity * 0.25)
        return min(1.0, max(0.0, confidence))

    def should_trigger(self, confidence: float) -> bool:
        """
        Returns True if the system mathematically confirms a Ghost Particle event.
        """
        return confidence >= self.threshold


if __name__ == "__main__":
    import shutil
    import tempfile

    # Smoke Test
    print("═" * 58)
    print("  SIFTA — HOMEOSTATIC GHOST CALIBRATION")
    print("═" * 58 + "\n")
    
    _tmp = Path(tempfile.mkdtemp())
    try:
        calibrator = GhostCalibrator(state_dir=_tmp)
        target = Path("/sifta/Core/Memory/hippocampus.py")
        
        print("[TEST] Immune Baseline Profiling (Clean Samples)")
        # SIFTA learns the normal edit/touch frequency of the file (e.g. around ~10 seconds)
        for val in [10.0, 9.0, 11.0, 10.5, 9.5]:
            calibrator.learn_normal(target, val)
            
        baseline = calibrator.baseline.get(str(target.resolve()))
        assert 9.5 <= baseline["T_mean"] <= 10.5, "Failed to calculate localized topological mean."
        print(f"  [PASS] T_mean converged natively: {baseline['T_mean']:.3f}")
        
        print("\n[TEST] Ghost Detection Confidence")
        # Scenario A: Benign minor edit close to temporal baseline (12 seconds later)
        benign_score = calibrator.score(target, T_obs=12.0, severity=0.30)
        assert calibrator.should_trigger(benign_score) is False, "Calibrator hallucinated a shockwave for benign editing."
        print(f"  [PASS] Benign deviation suppressed locally (Score: {benign_score:.3f} < {calibrator.threshold})")
        
        # Scenario B: Ghost Particle (File hasn't been touched in 6000 seconds, takes violent 0.85 damage)
        ghost_score = calibrator.score(target, T_obs=6000.0, severity=0.85)
        assert calibrator.should_trigger(ghost_score) is True, "Calibrator failed to detect massive Temporal Z-score deviation."
        print(f"  [PASS] Ghost Neutrino detected! (Z-Score fused Score: {ghost_score:.3f} >= {calibrator.threshold})")
        
        print("\n[SUCCESS] Homeostatic Ghost Control flawless.")

    finally:
        shutil.rmtree(_tmp, ignore_errors=True)
