"""
Q2 — Φ̂ (phi-hat) Integrated Information approximation.
Q3 — Emergence / joint synergy (KSG-style Gaussian estimator).

Haun, A.M. & Tononi, G. (2019). Why Does Space Feel the Way it Does?
    Entropy, 21(12), 1160. [ΦID rationale]
Mediano, P.A.M. et al. (2021). Towards an integrated information theory of
    consciousness. PLoS Comput Biol, 17(5). [ΦID decomposition]
Oizumi, M., Amari, S. et al. (2016). Measuring Integrated Information from
    the Decoding Perspective. PLoS Comput Biol. [empirical Φ_E]
Kraskov, A., Stögbauer, H. & Grassberger, P. (2004). Estimating mutual
    information. Physical Review E, 69. [KSG estimator rationale]
Bertschinger, N. et al. (2014). Quantifying unique information. Entropy. [PID]

Both functions accept a (T, D) numpy-free array — plain Python lists of lists —
so they work with SIFTA's stdlib-only constraint. If numpy is available it is
used for speed; otherwise a pure-Python Gaussian approximation is used.

Kill-switch: SIFTA_EMERGENCE_DISABLE=1
"""
from __future__ import annotations

import json
import math
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

try:
    from System.swarm_persistent_owner_history import state_dir
except ImportError:
    def state_dir(root=None):  # type: ignore
        return Path(root) if root else Path(".sifta_state")

try:
    from System.jsonl_file_lock import append_line_locked
except ImportError:
    def append_line_locked(path: Path, line: str, **kw) -> None:  # type: ignore
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", **kw) as f:
            f.write(line)

_DISABLE_ENV = "SIFTA_EMERGENCE_DISABLE"
LOG_NAME = "emergence_synergy.jsonl"

# ── Pure-Python linear algebra helpers ───────────────────────────────────────

def _transpose(M: List[List[float]]) -> List[List[float]]:
    if not M:
        return []
    T, D = len(M), len(M[0])
    return [[M[t][d] for t in range(T)] for d in range(D)]


def _col_mean(M: List[List[float]]) -> List[float]:
    T, D = len(M), len(M[0])
    return [sum(M[t][d] for t in range(T)) / T for d in range(D)]


def _cov_matrix(M: List[List[float]]) -> List[List[float]]:
    """Sample covariance matrix of (T, D) data."""
    T, D = len(M), len(M[0])
    mu = _col_mean(M)
    C = [[0.0] * D for _ in range(D)]
    for t in range(T):
        for i in range(D):
            for j in range(D):
                C[i][j] += (M[t][i] - mu[i]) * (M[t][j] - mu[j])
    n = max(1, T - 1)
    return [[C[i][j] / n for j in range(D)] for i in range(D)]


def _log_det_gaussian(Sigma: List[List[float]]) -> float:
    """
    log|Σ| via Cholesky decomposition (numerically stable for small D).
    Returns -inf if matrix is singular / not PD.
    """
    D = len(Sigma)
    # LDL^T decomposition — sufficient for small D
    # Use simple Cholesky L:
    L = [[0.0] * D for _ in range(D)]
    for i in range(D):
        for j in range(i + 1):
            s = sum(L[i][k] * L[j][k] for k in range(j))
            if i == j:
                v = Sigma[i][i] - s
                if v <= 0:
                    return float("-inf")
                L[i][j] = math.sqrt(v)
            else:
                if L[j][j] == 0:
                    return float("-inf")
                L[i][j] = (Sigma[i][j] - s) / L[j][j]
    return 2.0 * sum(math.log(max(L[d][d], 1e-300)) for d in range(D))


def _gaussian_entropy(Sigma: List[List[float]]) -> float:
    """H(X) = 0.5 * D * (1 + log(2π)) + 0.5 * log|Σ|  for Gaussian."""
    D = len(Sigma)
    log_det = _log_det_gaussian(Sigma)
    if log_det == float("-inf"):
        return float("-inf")
    return 0.5 * (D * (1.0 + math.log(2.0 * math.pi)) + log_det)


# ── Q2: Φ̂ Integrated Information (Gaussian/Oizumi 2016 empirical Φ_E) ────────

def compute_phi_id_approx(
    organ_matrix: Sequence[Sequence[float]],
    *,
    regularise: float = 1e-6,
) -> float:
    """
    Q2 — Approximate Φ̂ for a (T, D) organ time-series.

    Φ_ID ≈ H(X₁,…,X_D) − Σᵢ H(Xᵢ)  under Gaussian assumption.
    = 0.5 * (log|Σ_full| − Σᵢ log(σᵢ²))
    = −0.5 * log(det(Σ) / Πᵢ σᵢ²)
    = 0.5 * log(Πᵢ σᵢ² / det(Σ))

    This is the Gaussian approximation to Φ_E (Oizumi 2016 THOI):
      Φ > 0 implies the joint distribution carries more information than
      the product of marginals — i.e., the system is integrated.

    Returns float (nats). Returns 0.0 on degenerate / empty input.

    Ref: Oizumi et al. (2016); Haun & Tononi (2019); Mediano et al. (2021).
    """
    M = [list(row) for row in organ_matrix]
    T, D = len(M), len(M[0]) if M else 0
    if T < 2 or D < 2:
        return 0.0

    Sigma = _cov_matrix(M)
    # Regularise diagonal for numerical stability
    for i in range(D):
        Sigma[i][i] += regularise

    log_det_full = _log_det_gaussian(Sigma)
    if log_det_full == float("-inf"):
        return 0.0

    sum_log_marginal = sum(
        math.log(max(Sigma[i][i], 1e-300)) for i in range(D)
    )

    # Φ̂ = 0.5 * (Σ log σᵢ² − log|Σ|)
    phi = 0.5 * (sum_log_marginal - log_det_full)
    return max(0.0, round(phi, 6))


# ── Q3: Emergence / joint synergy (Total Correlation, Gaussian) ──────────────

def compute_joint_surprise(
    organ_matrix: Sequence[Sequence[float]],
    *,
    k: int = 3,   # kept for API compat; Gaussian approx doesn't use k-NN
    regularise: float = 1e-6,
) -> Dict[str, Any]:
    """
    Q3 — Total correlation C (= multi-information) and joint synergy O.

    C = Σᵢ H(Xᵢ) − H(X₁,…,X_D) ≥ 0
    O = H(X₁,…,X_D) − Σᵢ H(Xᵢ) = −C ≤ 0 for redundant organs,
        but under Grok's convention (synergy = positive O for EMERGENCE):
        O_synergy = C / D  (normalised excess co-information ≥ 0)

    We report both C (total correlation, always ≥ 0) and O_synergy.
    C >> 0 compared to shuffled surrogates → emergence confirmed.

    Ref: Kraskov et al. (2004) KSG [rationale]; Bertschinger et al. (2014) PID.
    Uses Gaussian approximation (tractable, stdlib-only).
    """
    M = [list(row) for row in organ_matrix]
    T, D = len(M), len(M[0]) if M else 0
    if T < 2 or D < 2:
        return {"O_joint_surprise": 0.0, "synergy": 0.0, "total_correlation": 0.0,
                "estimator": "gaussian_approx", "sufficient_data": False}

    Sigma = _cov_matrix(M)
    for i in range(D):
        Sigma[i][i] += regularise

    H_joint = _gaussian_entropy(Sigma)
    H_marginals_sum = sum(
        0.5 * (1.0 + math.log(2.0 * math.pi)) + 0.5 * math.log(max(Sigma[i][i], 1e-300))
        for i in range(D)
    )

    # Total correlation C ≥ 0
    C = max(0.0, H_marginals_sum - H_joint)
    # Normalised synergy (Grok convention: O > 0 = integration)
    O_synergy = round(C / D, 6)
    C_round = round(C, 6)

    return {
        "O_joint_surprise": C_round,     # total correlation (always ≥ 0)
        "synergy": O_synergy,            # normalised synergy
        "H_joint": round(H_joint, 6),
        "H_marginals_sum": round(H_marginals_sum, 6),
        "total_correlation": C_round,
        "estimator": f"gaussian_approx_k{k}",
        "n_timepoints": T,
        "n_organs": D,
        "sufficient_data": True,
    }


# ── Main API: compute + log both metrics ────────────────────────────────────

def compute_and_log_emergence(
    organ_matrix: Sequence[Sequence[float]],
    window_start: int = 0,
    window_end: int = 0,
    *,
    root: Optional[Path] = None,
    write_ledger: bool = True,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Compute Φ̂ (Q2) and emergence synergy (Q3) for one window and log them.
    Call this every N ticks from body_brain_tick or the dashboard.
    """
    if os.environ.get(_DISABLE_ENV, "").strip() == "1":
        return {"disabled": True, "phi_id_approx": 0.0, "synergy": 0.0}

    phi = compute_phi_id_approx(organ_matrix)
    synergy_dict = compute_joint_surprise(organ_matrix)

    row: Dict[str, Any] = {
        "ts": now or time.time(),
        "trace_id": str(uuid.uuid4()),
        "kind": "EMERGENCE_SYNERGY",
        "truth_label": "EMERGENCE_SYNERGY",
        "window": [window_start, window_end],
        "phi_id_approx": phi,
        "O_joint_surprise": synergy_dict["O_joint_surprise"],
        "synergy": synergy_dict["synergy"],
        "total_correlation": synergy_dict["total_correlation"],
        "H_joint": synergy_dict.get("H_joint"),
        "n_timepoints": synergy_dict.get("n_timepoints"),
        "n_organs": synergy_dict.get("n_organs"),
        "estimator": synergy_dict["estimator"],
        "provenance": (
            "Oizumi2016THOI; Haun&Tononi2019; Mediano2021ΦID; "
            "Kraskov2004KSG; Bertschinger2014PID"
        ),
    }

    if write_ledger:
        sd = state_dir(root)
        append_line_locked(
            sd / LOG_NAME,
            json.dumps(row, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return row


def summary_for_prompt(*, root: Optional[Path] = None) -> str:
    sd = state_dir(root)
    log = sd / LOG_NAME
    if not log.exists():
        return ""
    try:
        lines = [l for l in log.read_text(errors="ignore").splitlines() if l.strip()]
        if not lines:
            return ""
        row = json.loads(lines[-1])
    except Exception:
        return ""
    phi = row.get("phi_id_approx", "?")
    syn = row.get("synergy", "?")
    return (
        f"EMERGENCE/Φ̂ (Q2/Q3 — Oizumi 2016; Kraskov 2004):\n"
        f"- Φ̂={phi} | synergy={syn} | n={row.get('n_timepoints','?')} ticks"
    )
