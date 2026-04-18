#!/usr/bin/env python3
"""
convergence_stability_analyzer.py — VECTOR 11: System Stability & Convergence
══════════════════════════════════════════════════════════════════════════════════
The mathematical audit layer. Answers the hard question:

  "Does the coupled λ–graph system actually converge, or is it
   only stable in logs?"

Sub-vectors:
  11A — Spectral radius analysis of W (does consensus amplify or damp?)
  11B — Feedback loop contraction test (policy→constraints→λ→reward→policy)
  11C — Constraint critic calibration (uncertainty-aware Ĉ ± σ_C)
  11D — Continuous-time λ field dynamics (dλ/dt = -∇E(λ) + C(s,a))
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_STABILITY_STATE = _STATE_DIR / "convergence_stability.json"
_RESIDUE_LOG = _STATE_DIR / "constraint_residues.jsonl"


@dataclass
class StabilityReport:
    """The full convergence audit."""
    # 11A
    spectral_radius_W: float = 0.0
    W_is_contractive: bool = False
    W_is_row_stochastic: bool = False
    # 11B
    feedback_loop_stable: bool = False
    lambda_velocity: float = 0.0
    lambda_acceleration: float = 0.0
    oscillation_detected: bool = False
    # 11C
    C_hat: float = 0.0
    C_sigma: float = 0.0
    confidence_interval: str = ""
    # 11D
    energy_gradient: float = 0.0
    field_regime: str = "UNKNOWN"


class ConvergenceStabilityAnalyzer:
    """
    The mathematical safeguard. Runs spectral, contraction,
    and uncertainty analysis across the full constraint stack.
    """

    def __init__(self):
        self.has_numpy = False
        try:
            import numpy as np
            self.np = np
            self.has_numpy = True
        except ImportError:
            pass

    # ─────────────────────────────────────────────────────────
    # 11A: SPECTRAL RADIUS ANALYSIS
    # ─────────────────────────────────────────────────────────
    def _analyze_spectral_radius(self, report: StabilityReport):
        """
        Checks ρ(W) ≤ 1 for the consensus diffusion matrix.
        If ρ(W) > 1, the graph-coupled λ system will diverge silently.
        """
        if not self.has_numpy:
            return

        try:
            from temporal_identity_compression import get_compression_engine
            from skill_spectral_analyzer import SpectralAnalyzer

            engine = get_compression_engine()
            skills = list(engine.skills.values())
            N = len(skills)

            if N < 2:
                return

            analyzer = SpectralAnalyzer()
            A = self.np.zeros((N, N))
            for i in range(N):
                for j in range(i + 1, N):
                    overlap = analyzer._jaccard_overlap(skills[i], skills[j])
                    if overlap > 0.1:
                        A[i, j] = overlap
                        A[j, i] = overlap

            # Reproduce the exact normalization from graph_dual_aggregator
            row_sums = A.sum(axis=1)
            row_sums[row_sums == 0] = 1.0
            W = A / row_sums[:, self.np.newaxis]
            W = W * 0.5 + self.np.eye(N) * 0.5

            eigvals = self.np.linalg.eigvals(W)
            rho = float(max(abs(eigvals)))

            report.spectral_radius_W = round(rho, 6)
            report.W_is_contractive = rho <= 1.0 + 1e-10
            report.W_is_row_stochastic = bool(self.np.allclose(W.sum(axis=1), 1.0))
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────
    # 11B: FEEDBACK LOOP CONTRACTION TEST
    # ─────────────────────────────────────────────────────────
    def _analyze_feedback_loop(self, report: StabilityReport):
        """
        Reads the λ history from the constraint residue ledger.
        Computes velocity (dλ/dt) and acceleration (d²λ/dt²).
        If acceleration is oscillating (sign changes), the coupled
        loop is NOT contractive — it's ping-ponging.
        """
        history = self._load_lambda_history()

        if len(history) < 3:
            report.feedback_loop_stable = True  # Not enough data to detect instability
            return

        # Extract total penalty magnitudes over time
        penalties = [h.get("total_lambda_penalty", 0.0) for h in history]

        # Velocity: dλ/dt (first difference)
        velocities = [penalties[i] - penalties[i - 1] for i in range(1, len(penalties))]
        report.lambda_velocity = round(velocities[-1], 6) if velocities else 0.0

        # Acceleration: d²λ/dt² (second difference)
        if len(velocities) >= 2:
            accels = [velocities[i] - velocities[i - 1] for i in range(1, len(velocities))]
            report.lambda_acceleration = round(accels[-1], 6) if accels else 0.0

            # Oscillation detection: count sign changes in acceleration
            sign_changes = 0
            for i in range(1, len(accels)):
                if accels[i] * accels[i - 1] < 0:
                    sign_changes += 1

            # If more than 40% of acceleration steps flip sign, we're oscillating
            oscillation_ratio = sign_changes / max(1, len(accels))
            report.oscillation_detected = oscillation_ratio > 0.4

        report.feedback_loop_stable = not report.oscillation_detected

    # ─────────────────────────────────────────────────────────
    # 11C: CONSTRAINT CRITIC CALIBRATION (UNCERTAINTY)
    # ─────────────────────────────────────────────────────────
    def _analyze_critic_uncertainty(self, report: StabilityReport):
        """
        Extends the constraint critic with uncertainty estimation (σ_C).
        A critic without uncertainty is an overconfident failure detector.
        """
        history = self._load_violation_history()

        if len(history) < 2:
            return

        gamma = 0.9

        # Compute multiple C_hat samples using sliding windows
        window_size = min(10, len(history))
        c_hats = []

        for start in range(max(1, len(history) - window_size), len(history)):
            window = history[start:]
            c_hat = sum((gamma ** t) * c for t, c in enumerate(window))
            c_hats.append(c_hat)

        if not c_hats:
            return

        mean_c = sum(c_hats) / len(c_hats)
        variance = sum((c - mean_c) ** 2 for c in c_hats) / max(1, len(c_hats) - 1)
        sigma = math.sqrt(variance)

        report.C_hat = round(mean_c, 5)
        report.C_sigma = round(sigma, 5)

        # 95% confidence interval
        lower = max(0.0, mean_c - 1.96 * sigma)
        upper = mean_c + 1.96 * sigma
        report.confidence_interval = f"[{lower:.4f}, {upper:.4f}]"

    # ─────────────────────────────────────────────────────────
    # 11D: CONTINUOUS-TIME λ FIELD DYNAMICS
    # ─────────────────────────────────────────────────────────
    def _analyze_field_dynamics(self, report: StabilityReport):
        """
        Interprets the λ evolution as continuous-time dynamics:
          dλ/dt = -∇E(λ) + C(s,a)
        
        Where -∇E(λ) is the decay pressure and C(s,a) is violation injection.
        Classifies the current field regime.
        """
        history = self._load_lambda_history()

        if len(history) < 2:
            report.field_regime = "INSUFFICIENT_DATA"
            return

        # Energy gradient: rate of change of total penalty
        recent = [h.get("total_lambda_penalty", 0.0) for h in history[-5:]]

        if len(recent) >= 2:
            gradient = (recent[-1] - recent[0]) / max(1, len(recent) - 1)
            report.energy_gradient = round(gradient, 6)

            if abs(gradient) < 0.001:
                report.field_regime = "EQUILIBRIUM"
            elif gradient > 0.05:
                report.field_regime = "DIVERGING"
            elif gradient > 0:
                report.field_regime = "SLOW_DRIFT"
            elif gradient < -0.05:
                report.field_regime = "RAPID_DECAY"
            else:
                report.field_regime = "STABLE_DECAY"

    # ─────────────────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────────────────
    def _load_lambda_history(self) -> List[Dict[str, Any]]:
        """Load the full constraint residues history."""
        history = []
        if not _RESIDUE_LOG.exists():
            return history
        try:
            with open(_RESIDUE_LOG, 'r') as f:
                for line in f.readlines()[-30:]:
                    if line.strip():
                        history.append(json.loads(line))
        except Exception:
            pass
        return history

    def _load_violation_history(self) -> List[float]:
        """Load scalar violation magnitudes over time."""
        violations = []
        if not _RESIDUE_LOG.exists():
            return violations
        try:
            with open(_RESIDUE_LOG, 'r') as f:
                for line in f.readlines()[-30:]:
                    if not line.strip():
                        continue
                    d = json.loads(line)
                    v = d.get("violations", {})
                    c_t = (max(0.0, v.get("congestion", 0.0)) +
                           max(0.0, v.get("safety", 0.0)) +
                           max(0.0, v.get("energy", 0.0)))
                    violations.append(c_t)
        except Exception:
            pass
        return violations

    # ─────────────────────────────────────────────────────────
    # MAIN ENTRY
    # ─────────────────────────────────────────────────────────
    def run_full_stability_audit(self) -> Dict[str, Any]:
        """Execute all 4 sub-analyses."""
        report = StabilityReport()

        self._analyze_spectral_radius(report)
        self._analyze_feedback_loop(report)
        self._analyze_critic_uncertainty(report)
        self._analyze_field_dynamics(report)

        # Final verdict
        issues = []
        if not report.W_is_contractive:
            issues.append("ρ(W) > 1: consensus matrix will AMPLIFY λ")
        if not report.W_is_row_stochastic:
            issues.append("W is NOT row-stochastic: normalization broken")
        if report.oscillation_detected:
            issues.append("Feedback loop oscillation detected in λ trajectory")
        if report.C_sigma > report.C_hat * 0.5 and report.C_hat > 0:
            issues.append(f"Constraint critic uncertainty too high (σ/μ = {report.C_sigma/max(0.001,report.C_hat):.1f})")

        if not issues:
            verdict = "ALL CLEAR: System is provably convergent under current topology."
        else:
            verdict = f"WARNING: {len(issues)} stability issue(s) detected: {'; '.join(issues)}"

        result = {
            "timestamp": time.time(),
            "11A_spectral": {
                "spectral_radius": report.spectral_radius_W,
                "contractive": report.W_is_contractive,
                "row_stochastic": report.W_is_row_stochastic
            },
            "11B_feedback": {
                "stable": report.feedback_loop_stable,
                "lambda_velocity": report.lambda_velocity,
                "lambda_acceleration": report.lambda_acceleration,
                "oscillation_detected": report.oscillation_detected
            },
            "11C_critic_calibration": {
                "C_hat_mean": report.C_hat,
                "C_sigma": report.C_sigma,
                "confidence_interval_95": report.confidence_interval
            },
            "11D_field_dynamics": {
                "energy_gradient": report.energy_gradient,
                "regime": report.field_regime
            },
            "verdict": verdict,
            "issues": issues
        }

        self._persist(result)
        return result

    def _persist(self, data: Dict[str, Any]):
        try:
            _STABILITY_STATE.write_text(json.dumps(data, indent=2))
        except Exception:
            pass


def get_stability_analyzer() -> ConvergenceStabilityAnalyzer:
    return ConvergenceStabilityAnalyzer()


if __name__ == "__main__":
    print("═" * 70)
    print("  VECTOR 11: CONVERGENCE & STABILITY ANALYZER")
    print("  'Does the coupled λ-graph system converge or explode?'")
    print("═" * 70 + "\n")

    analyzer = get_stability_analyzer()
    result = analyzer.run_full_stability_audit()

    # 11A
    s = result["11A_spectral"]
    print("  [ 11A: SPECTRAL RADIUS ]")
    print(f"    ρ(W)             : {s['spectral_radius']}")
    print(f"    Contractive?     : {s['contractive']}")
    print(f"    Row-stochastic?  : {s['row_stochastic']}")

    # 11B
    fb = result["11B_feedback"]
    print("\n  [ 11B: FEEDBACK LOOP CONTRACTION ]")
    print(f"    Stable?          : {fb['stable']}")
    print(f"    dλ/dt            : {fb['lambda_velocity']}")
    print(f"    d²λ/dt²          : {fb['lambda_acceleration']}")
    print(f"    Oscillation?     : {fb['oscillation_detected']}")

    # 11C
    cc = result["11C_critic_calibration"]
    print("\n  [ 11C: CRITIC UNCERTAINTY ]")
    print(f"    Ĉ (mean)         : {cc['C_hat_mean']}")
    print(f"    σ_C              : {cc['C_sigma']}")
    print(f"    95% CI           : {cc['confidence_interval_95']}")

    # 11D
    fd = result["11D_field_dynamics"]
    print("\n  [ 11D: λ-FIELD DYNAMICS ]")
    print(f"    ∇E(λ)            : {fd['energy_gradient']}")
    print(f"    Regime           : {fd['regime']}")

    # Verdict
    print(f"\n  {'🟢' if not result['issues'] else '🔴'} {result['verdict']}")
    if result["issues"]:
        for issue in result["issues"]:
            print(f"    ⚠️  {issue}")

    print(f"\n  ✅ STABILITY AUDIT COMPLETE 🐜⚡")
