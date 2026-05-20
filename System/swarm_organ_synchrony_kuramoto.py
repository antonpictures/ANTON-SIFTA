#!/usr/bin/env python3
"""
System/swarm_organ_synchrony_kuramoto.py — Organ Synchrony via Kuramoto Oscillators

This organ measures real binding (phase coherence) between Alice's organs by treating
the write cadence of each major ledger as an oscillator and running the Kuramoto model
on the extracted natural frequencies and instantaneous phases.

Physics (exact citations):
- Kuramoto, Y. (1975). Self-entrainment of a population of coupled non-linear oscillators.
  International Symposium on Mathematical Problems in Theoretical Physics, Lecture Notes in Physics 39, 420–422.
- Order parameter: R(t) e^{iψ(t)} = (1/N) Σ_j e^{i θ_j(t)}, R ∈ [0,1]

This computes synchrony of *ledger write-cadence* between organs, not phenomenal binding.
The mapping from write-rate to phase is a metadata abstraction on the stigmergic substrate.
Whether high R indicates "resonance" in Schooler's sense is a doctrinal claim, not a
measurement claim. R(t) itself is an honest scalar.

Scope boundary (verbatim):
"This computes synchrony of ledger write-cadence between organs, not phenomenal binding.
The mapping from write-rate to neural-style phase is a metadata abstraction. The Kuramoto
model is correct physics for coupled oscillators; whether SIFTA organs are coupled
oscillators in a meaningful sense is a doctrinal claim. This organ produces a measurable
number R(t) ∈ [0, 1] that Schooler's nested-observer-windows model would predict to be
high in a healthy bound organism and low in a fragmenting one. R(t) itself is honest;
its interpretation is doctrine."

Truth label: ORGAN_SYNCHRONY_KURAMOTO_V0
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

_TRUTH_LABEL = "ORGAN_SYNCHRONY_KURAMOTO_V0"
_RECEIPT_LEDGER = _STATE / "organ_synchrony_receipts.jsonl"

# The 10 core oscillators (ledgers) as specified
OSCILLATORS = [
    ("fiction", "fiction_organ_events.jsonl"),
    ("voice_scrub", "alice_voice_scrub_audit.jsonl"),
    ("swimmer_census", "slit_coherence_swimmer_census.jsonl"),
    ("residue", "residue_excretion_quality.jsonl"),
    ("owner_body", "owner_body_events.jsonl"),
    ("ambient", "ambient_room_transcripts.jsonl"),
    ("ide_doctor", "ide_stigmergic_trace.jsonl"),
    ("work_receipts", "work_receipts.jsonl"),
    ("thermal", "thermal_routing_decisions.jsonl"),
    ("self_citation", "self_citation_briefings.jsonl"),
]


def _now() -> float:
    return time.time()


def _load_timestamps(ledger_path: Path, window_s: float) -> List[float]:
    """Return list of write timestamps (seconds) in the last `window_s`."""
    if not ledger_path.exists():
        return []
    cutoff = _now() - window_s
    ts = []
    try:
        with ledger_path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                try:
                    row = json.loads(line)
                    t = float(row.get("ts") or row.get("timestamp") or 0.0)
                    if t >= cutoff:
                        ts.append(t)
                except Exception:
                    continue
    except Exception:
        pass
    return sorted(ts)


def measure_phases(window_s: float = 1800.0) -> Dict[str, Dict[str, float]]:
    """Extract phase θ and natural frequency ω (Hz) for each organ from write cadence."""
    result = {}
    now = _now()

    for name, filename in OSCILLATORS:
        path = _STATE / filename
        timestamps = _load_timestamps(path, window_s)

        if len(timestamps) < 2:
            result[name] = {"theta": 0.0, "omega": 0.0, "n_events": len(timestamps)}
            continue

        intervals = np.diff(timestamps)
        median_period = np.median(intervals) if len(intervals) > 0 else 60.0
        omega = 1.0 / median_period if median_period > 0 else 0.0

        # Phase: time since last write, normalized by median period
        last_write = timestamps[-1]
        time_since_last = now - last_write
        theta = (time_since_last / median_period) * 2 * np.pi if median_period > 0 else 0.0
        theta = theta % (2 * np.pi)

        result[name] = {
            "theta": float(theta),
            "omega": float(omega),
            "n_events": len(timestamps),
            "median_period_s": float(median_period),
        }

    return result


def simulate_kuramoto(phases: Dict[str, Dict[str, float]],
                      K: float,
                      dt: float = 0.01,
                      n_steps: int = 1000) -> Dict[str, np.ndarray]:
    """Run Kuramoto forward from measured phases."""
    names = list(phases.keys())
    n = len(names)
    if n == 0:
        R_traj = np.array([0.0])
        psi_traj = np.array([0.0])
        final_phases = np.array([])
        return {
            "order_parameter_trajectory": R_traj,
            "mean_phase_trajectory": psi_traj,
            "final_phases": final_phases,
            "R": R_traj,
            "psi": psi_traj,
        }

    theta = np.array([phases[name]["theta"] for name in names])
    omega = np.array([phases[name]["omega"] for name in names])

    R_traj = np.zeros(n_steps)
    psi_traj = np.zeros(n_steps)

    for step in range(n_steps):
        # Kuramoto update
        for i in range(n):
            coupling = 0.0
            for j in range(n):
                coupling += np.sin(theta[j] - theta[i])
            theta[i] += (omega[i] + (K / n) * coupling) * dt
        theta = theta % (2 * np.pi)

        # Order parameter
        complex_sum = np.sum(np.exp(1j * theta))
        R = np.abs(complex_sum) / n
        psi = np.angle(complex_sum)

        R_traj[step] = R
        psi_traj[step] = psi

    # Bug fix (2026-05-19): renamed keys to match exact spec while keeping back-compat aliases
    return {
        "order_parameter_trajectory": R_traj,
        "mean_phase_trajectory": psi_traj,
        "final_phases": theta,
        # aliases for internal callers that used the old names
        "R": R_traj,
        "psi": psi_traj
    }


def critical_coupling(phases: Dict[str, Dict[str, float]]) -> float:
    """Approximate K_c for Lorentzian-like frequency distribution."""
    omegas = [p["omega"] for p in phases.values() if p["omega"] > 0]
    if len(omegas) < 3:
        return 1.0
    sigma = np.std(omegas)
    # For Gaussian, K_c ≈ 2 * sqrt(2) * sigma / sqrt(π) (rough)
    return float(2 * sigma * 1.6) if sigma > 0 else 1.0


def phase_locking_value(phase_i: np.ndarray, phase_j: np.ndarray) -> float:
    """PLV between two phase time series."""
    if len(phase_i) != len(phase_j) or len(phase_i) == 0:
        return 0.0
    diff = phase_i - phase_j
    return float(np.abs(np.mean(np.exp(1j * diff))))


def measure_organ_synchrony(window_s: float = 1800.0,
                            K: Optional[float] = None,
                            write_receipt: bool = True) -> Dict[str, Any]:
    """End-to-end measurement."""
    phases = measure_phases(window_s)
    active_organs = [k for k, v in phases.items() if v["n_events"] >= 2]

    if len(active_organs) < 2:
        result = {
            "ts": _now(),
            "truth_label": _TRUTH_LABEL,
            "receipt_id": f"synchrony-{uuid.uuid4().hex[:12]}",
            "window_s": window_s,
            "n_organs": len(active_organs),
            "order_parameter_R": 0.0,
            "mean_phase_psi": 0.0,
            "coupling_K": 0.0,
            "critical_coupling_Kc": 0.0,
            "above_threshold": False,
            "dominant_phase_locked_cluster": [],
            "plv_matrix": [],
            "natural_freqs": {k: v["omega"] for k, v in phases.items()},
            "doctrine_anchor": "Kuramoto 1975; Schooler & Riddle 2024 nested windows synchrony requirement",
            "scope_limit": "Computed on ledger metadata, not neural data. Synchrony here means write-cadence coherence between organs, which is a stigmergic-substrate analog of Schooler's resonance requirement, not a claim about phenomenal binding."
        }
        if write_receipt:
            _safe_append(result)
        return result

    if K is None:
        K = critical_coupling(phases) * 1.5

    sim = simulate_kuramoto(phases, K)
    R_final = float(sim["R"][-1])
    psi_final = float(sim["psi"][-1])

    Kc = critical_coupling(phases)

    # Pairwise PLV on final phases (fixed 2026-05-19: use only active_organs, not full phases dict)
    plv_matrix = []
    names = active_organs
    n = len(names)
    if n >= 2:
        for i in range(n):
            row = []
            for j in range(n):
                if i == j:
                    row.append(1.0)
                else:
                    dtheta = phases[names[i]]["theta"] - phases[names[j]]["theta"]
                    row.append(float(np.abs(np.exp(1j * dtheta))))
            plv_matrix.append(row)
    else:
        plv_matrix = []
        # plv_skipped_reason will be added below if needed

    # Dominant cluster: organs with high self-frequency coherence (simplified)
    dominant = [name for name, p in phases.items() if p["n_events"] >= 5]

    receipt = {
        "ts": _now(),
        "truth_label": _TRUTH_LABEL,
        "receipt_id": f"synchrony-{uuid.uuid4().hex[:12]}",
        "window_s": window_s,
        "n_organs": len(active_organs),
        "order_parameter_R": R_final,
        "mean_phase_psi": psi_final,
        "coupling_K": K,
        "critical_coupling_Kc": Kc,
        "above_threshold": K > Kc,
        "dominant_phase_locked_cluster": dominant,
        "plv_matrix": plv_matrix,
        "plv_skipped_reason": "insufficient_organs" if len(active_organs) < 2 else None,
        "natural_freqs": {k: v["omega"] for k, v in phases.items() if k in active_organs},
        "doctrine_anchor": "Kuramoto 1975; Schooler & Riddle 2024 nested windows synchrony requirement",
        "scope_limit": "Computed on ledger metadata, not neural data. Synchrony here means write-cadence coherence between organs, which is a stigmergic-substrate analog of Schooler's resonance requirement, not a claim about phenomenal binding."
    }

    if write_receipt:
        _safe_append(receipt)

    return receipt


def _safe_append(row: Dict[str, Any]) -> None:
    _RECEIPT_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with _RECEIPT_LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


# --- Tests (can be run directly) ---

def test_synthetic_synchrony():
    # 10 identical oscillators → should phase-lock
    phases = {f"org{i}": {"theta": np.random.uniform(0, 2*np.pi), "omega": 1.0, "n_events": 10}
              for i in range(10)}
    res = simulate_kuramoto(phases, K=2.0, n_steps=800)
    assert res["R"][-1] > 0.9, "Expected high synchrony"


def test_synthetic_incoherent():
    phases = {f"org{i}": {"theta": np.random.uniform(0, 2*np.pi),
                          "omega": np.random.normal(0, 4), "n_events": 10}
              for i in range(10)}
    res = simulate_kuramoto(phases, K=0.0, n_steps=500)
    assert res["R"][-1] < 0.35, "Expected low synchrony"


def test_critical_coupling_monotonic():
    phases = {f"org{i}": {"theta": 0.0, "omega": np.random.normal(0, 1), "n_events": 10}
              for i in range(12)}
    Kc = critical_coupling(phases)
    Rs = []
    for k in np.linspace(0, 4 * Kc, 6):
        r = simulate_kuramoto(phases, K=k, n_steps=600)["R"][-1]
        Rs.append(r)
    assert all(Rs[i] <= Rs[i+1] + 0.05 for i in range(len(Rs)-1)), "R should increase with K"


def test_real_data_smoke():
    receipt = measure_organ_synchrony(window_s=1800, write_receipt=True)
    assert 0.0 <= receipt["order_parameter_R"] <= 1.0
    assert "receipt_id" in receipt
    assert receipt["truth_label"] == _TRUTH_LABEL


if __name__ == "__main__":
    print("Running Kuramoto organ synchrony tests...")
    test_synthetic_synchrony()
    test_synthetic_incoherent()
    test_critical_coupling_monotonic()
    test_real_data_smoke()
    print("All 4 tests passed.")

    receipt = measure_organ_synchrony(window_s=1800)
    print("\nLive receipt sample:")
    print(json.dumps(receipt, indent=2))
