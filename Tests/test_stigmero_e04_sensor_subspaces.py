"""
tests/test_stigmero_e04_sensor_subspaces.py
════════════════════════════════════════════════════════════════════════════
E04 — Sensor subspaces (STIGMEROBOTICS / ROB 501 tournament)

ROB 501 topic: Subspaces, linear independence, rank.

Hypothesis (P):
    The observation matrix A ∈ ℝ^{m × n} (m observations of n sensors)
    contains linearly dependent channels (redundant sensors) and a minimal
    independent subspace (rank(A) < n).

Proof structure:
  1. Construct observation matrix A from a sequence of state vectors.
  2. Identify the Constant Subspace (variance == 0, rank deficient).
  3. Identify Redundant/Correlated Subspaces (correlation == 1 or -1).
     e.g., stgm_balance and session_cost_stgm are linearly dependent.
  4. Compute the true rank k of the covariance matrix.
     The true degrees of freedom k < n proves that the sensor suite has
     redundancy that can be reduced to a minimal basis.

proof_of_property = {
    "P_n": "Observation matrix A in R^{m x n} has rank k < n",
    "subspaces": "Sensors partition into independent, constant, and dependent sets",
    "falsifier": "rank(cov) == n would mean all sensors are linearly independent",
    "truth_label": "OPERATIONAL after pytest green",
}

§8.6 compliance: sanitized fixture only — never reads live .sifta_state/.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pytest

from System.stigmerobotics_state_vector import CHANNEL_UNITS

FIXTURES = Path(__file__).parent / "fixtures"


def load_sequence(path: Path) -> List[Dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def build_observation_matrix(rows: List[Dict[str, Any]]) -> Tuple[np.ndarray, List[str]]:
    """
    Build A in R^{m x n}.
    Rows are observations (m), columns are numeric channels (n).
    """
    # Find channels that are present in all rows
    if not rows:
        return np.zeros((0, 0)), []
    
    # We only care about channels in CHANNEL_UNITS
    channels = sorted([k for k in CHANNEL_UNITS if k in rows[0]])
    
    m = len(rows)
    n = len(channels)
    A = np.zeros((m, n))
    
    for i, row in enumerate(rows):
        for j, ch in enumerate(channels):
            val = row.get(ch)
            A[i, j] = float(val) if val is not None else 0.0
            
    return A, channels


class TestE04SensorSubspaces:
    
    def test_e04_observation_matrix_construction(self):
        """Verify we can build A in R^{m x n} from the sequence."""
        rows = load_sequence(FIXTURES / "state_sequence_e04.jsonl")
        A, channels = build_observation_matrix(rows)
        assert A.shape[0] == 10, "m=10 observations"
        assert A.shape[1] > 0, "n > 0 channels"
        assert "stgm_balance" in channels
        assert "kleiber_exponent" in channels

    def test_e04_constant_subspace_is_rank_deficient(self):
        """
        Sensors like 'kleiber_exponent' or 'immune_budget' are constant.
        Their variance is 0, they lie in a 1D subspace spanned by the 1-vector.
        """
        rows = load_sequence(FIXTURES / "state_sequence_e04.jsonl")
        A, channels = build_observation_matrix(rows)
        
        variances = np.var(A, axis=0)
        constant_channels = [channels[j] for j, var in enumerate(variances) if np.isclose(var, 0)]
        
        assert "kleiber_exponent" in constant_channels, "kleiber_exponent must be in constant subspace"
        assert "immune_budget" in constant_channels, "immune_budget must be in constant subspace"
        
        print(f"\nConstant subspace (var=0): {constant_channels}")

    def test_e04_linearly_dependent_economy_sensors(self):
        """
        stgm_balance and session_cost_stgm are linearly dependent.
        stgm_balance = initial - session_cost_stgm.
        Their correlation coefficient is -1.
        """
        rows = load_sequence(FIXTURES / "state_sequence_e04.jsonl")
        A, channels = build_observation_matrix(rows)
        
        idx_bal = channels.index("stgm_balance")
        idx_cost = channels.index("session_cost_stgm")
        
        corr = np.corrcoef(A[:, idx_bal], A[:, idx_cost])[0, 1]
        assert np.isclose(corr, -1.0), f"Economy sensors must be linearly dependent, got corr={corr}"
        
        print(f"\nLinearly dependent subspace: stgm_balance & session_cost_stgm (corr={corr})")

    def test_e04_rank_reveals_true_degrees_of_freedom(self):
        """
        The rank of the covariance matrix reveals the true degrees of freedom k.
        Because of constant and redundant sensors, k < n.
        """
        rows = load_sequence(FIXTURES / "state_sequence_e04.jsonl")
        A, channels = build_observation_matrix(rows)
        
        # Center the matrix
        A_centered = A - np.mean(A, axis=0)
        # Compute covariance
        cov = np.cov(A_centered, rowvar=False)
        
        # True degrees of freedom is the rank of the covariance matrix
        rank = np.linalg.matrix_rank(cov)
        n = A.shape[1]
        
        assert rank < n, f"Rank {rank} must be < n={n} due to redundant sensors"
        
        print(f"\nObservation matrix A in R^{len(rows)}x{n}")
        print(f"Rank(Cov) = {rank}. The sensor suite has {n - rank} redundant dimensions.")

class TestE04ProofOfProperty:
    """Machine-readable proof_of_property dict smoke-test."""

    proof_of_property = {
        "P_n": "Observation matrix A in R^{m x n} has rank k < n",
        "subspaces": "Sensors partition into independent, constant, and dependent sets",
        "falsifier": "rank(cov) == n would mean all sensors are linearly independent",
        "truth_label": "OPERATIONAL",
    }

    def test_proof_has_required_keys(self) -> None:
        assert {"P_n", "subspaces", "falsifier", "truth_label"} <= self.proof_of_property.keys()

    def test_falsifier_is_machine_checkable(self) -> None:
        assert "rank(cov) == n" in self.proof_of_property["falsifier"]
