"""
Event 132 — Statistical transfer proof (bootstrap), numpy-only.

Pairs with **Event 127** ``swarm_transfer_gain_evaluator`` (scalar A/B rows).
This module logs **controlled experiment** aggregates and closes a **numeric**
significance loop without SciPy: one-sided bootstrap *p*-value for
``mean(transfer_gain) > 0``.

Truth label: **OPERATIONAL** — statistics on logged runs; not causal discovery.
Kill-switch: ``SIFTA_TRANSFER_PROOF_DISABLE=1``.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from System.jsonl_file_lock import append_line_locked
from System.swarm_persistent_owner_history import state_dir

LEDGER_NAME = "transfer_proof_runs.jsonl"


def proof_runs_path(root: Optional[Path] = None) -> Path:
    return state_dir(root) / LEDGER_NAME


def _disabled() -> bool:
    return os.environ.get("SIFTA_TRANSFER_PROOF_DISABLE", "").strip() == "1"


def compute_gain(baseline: float, transfer: float) -> float:
    b = float(baseline)
    t = float(transfer)
    return (t - b) / max(abs(b), 1e-6)


def compute_novelty_mean_l2(src_states: np.ndarray, tgt_states: np.ndarray) -> float:
    """Mean-state L2 distance (MMD placeholder = future work)."""
    s = np.asarray(src_states, dtype=np.float64)
    t = np.asarray(tgt_states, dtype=np.float64)
    if s.ndim == 1:
        s = s.reshape(1, -1)
    if t.ndim == 1:
        t = t.reshape(1, -1)
    if s.shape[1] != t.shape[1]:
        raise ValueError("state dimension mismatch")
    return float(np.linalg.norm(s.mean(axis=0) - t.mean(axis=0)))


@dataclass
class TransferProofRun:
    """One line per run / aggregate (tournament Q7 schema)."""

    run_id: str
    source: str
    target: str
    baseline_reward: float
    transfer_reward: float
    transfer_gain: float
    novelty_score: float
    n_seeds: int = 1
    p_value: Optional[float] = None


class TransferStatisticalProof:
    """Append-only ``transfer_proof_runs.jsonl`` + bootstrap ``prove``."""

    def __init__(self, *, root: Optional[Path] = None):
        self._root = root

    def log(self, row: TransferProofRun) -> None:
        if _disabled():
            return
        payload = asdict(row)
        payload["kind"] = "TRANSFER_PROOF_RUN"
        payload["ts"] = time.time()
        payload["trace_id"] = str(uuid.uuid4())
        append_line_locked(
            proof_runs_path(self._root),
            json.dumps(payload, ensure_ascii=False, default=str) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def bootstrap_pvalue_positive(
        gains: np.ndarray,
        *,
        n_bootstrap: int = 4000,
        seed: int = 0,
    ) -> Tuple[float, float]:
        """
        One-sided *p*-value ≈ P_bootstrap(mean* <= 0) with resampled means.
        Low *p* supports ``mean(gain) > 0`` when observed mean is positive.
        """
        g = np.asarray(gains, dtype=np.float64).ravel()
        n = int(g.size)
        if n == 0:
            return 0.0, 1.0
        obs = float(np.mean(g))
        if n == 1:
            return obs, 0.0 if obs > 0 else 1.0
        rng = np.random.default_rng(seed)
        boots = np.empty(n_bootstrap, dtype=np.float64)
        for i in range(n_bootstrap):
            idx = rng.integers(0, n, size=n)
            boots[i] = float(np.mean(g[idx]))
        p = float(np.mean(boots <= 0.0))
        return obs, p

    def prove(
        self,
        rows: List[TransferProofRun],
        *,
        alpha: float = 0.05,
        n_bootstrap: int = 4000,
        seed: int = 0,
    ) -> Dict[str, Any]:
        if not rows:
            return {
                "mean_gain": 0.0,
                "p_value": 1.0,
                "significant": False,
                "n": 0,
            }
        gains = np.array([float(r.transfer_gain) for r in rows], dtype=np.float64)
        mean_gain, p = self.bootstrap_pvalue_positive(
            gains, n_bootstrap=n_bootstrap, seed=seed
        )
        sig = bool(mean_gain > 0 and p < alpha)
        return {
            "mean_gain": round(mean_gain, 6),
            "p_value": round(p, 6),
            "significant": sig,
            "n": len(rows),
            "alpha": alpha,
        }


__all__ = [
    "TransferProofRun",
    "TransferStatisticalProof",
    "compute_gain",
    "compute_novelty_mean_l2",
    "proof_runs_path",
]
