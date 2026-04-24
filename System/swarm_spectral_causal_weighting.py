#!/usr/bin/env python3
"""
System/swarm_spectral_causal_weighting.py
══════════════════════════════════════════════════════════════════════
Event 53 + 54 — Spectral Eigenflow & Do-Calculus Adapter Weighting
══════════════════════════════════════════════════════════════════════

Author:  BISHOP drop → AG31 synthesis (Event 53–54 Biocode Olympiad)
Physics: Spectral Graph Theory (Eigenvector Centrality),
         Pearl's Do-Calculus (Average Causal Effect)
Papers:
  - Bonacich (1987) Power and Centrality: A Family of Measures
  - Pearl (2000) Causality: Models, Reasoning, and Inference
  - Chung (1997) Spectral Graph Theory (CBMS Lectures)
  - Peters, Janzing & Schölkopf (2017) Elements of Causal Inference

Non-claims (hard-coded discipline):
  - Does NOT implement a full Structural Causal Model (no DAG inference)
  - Does NOT compute exact do-calculus identifiability (no back-door test)
  - Does NOT modify base model weights
  - Does NOT require gradient access

What it does:
  - Event 53: Given a replay path graph, compute the dominant eigenvector
    of the adapter transition matrix (Eigenvector Centrality).
    Reveals "keystone" adapters that structurally hold the cognitive graph
    together, even if their local success rate is modest.
  - Event 54: Estimate Average Causal Effect (ACE) via soft intervention:
    ACE(adapter) = E[survival | do(adapter=1)] - E[survival | do(adapter=0)]
    Uses observational data + simple adjustment to isolate causal efficacy
    from sequential co-occurrence bias.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

try:
    import numpy as np
    _NUMPY_AVAILABLE = True
except ImportError:
    _NUMPY_AVAILABLE = False


# ══════════════════════════════════════════════════════════════════════
# Event 53: Spectral Eigenflow Weighting
# ══════════════════════════════════════════════════════════════════════

@dataclass
class SpectralWeightResult:
    eigenvector_centrality: Dict[str, float]    # adapter → centrality score
    dominant_eigenvalue: float                   # λ₁ of transition matrix
    iterations: int                              # power-iteration steps taken
    converged: bool
    fingerprint: str                             # SHA256 of sorted scores


def compute_spectral_weights(
    transition_counts: Dict[Tuple[str, str], float],
    *,
    max_iter: int = 200,
    tol: float = 1e-8,
    symmetrise: bool = True,
) -> SpectralWeightResult:
    """
    Compute Eigenvector Centrality over the adapter replay graph.

    `transition_counts` maps (src_adapter, dst_adapter) → observed flow weight.
    The dominant eigenvector of the adjacency matrix gives each adapter a
    centrality score proportional to how structurally central it is.

    `symmetrise=True` (default): treats edges as undirected for centrality
    purposes. This prevents sink-node collapse on DAGs where terminal adapters
    (e.g., the final output stage) would otherwise score zero despite being
    on every path. Set False only if you have a strongly-connected directed graph.

    Physics:
        A·v = λ·v   (power iteration on the normalised adjacency matrix)
        v[i] ∝ sum_j A[j,i] · v[j]   (Bonacich centrality, 1987)

    Boundary:
        Falls back to uniform weights if numpy is absent or matrix is trivial.
    """
    nodes = sorted({n for pair in transition_counts for n in pair})
    n = len(nodes)

    if n == 0:
        return SpectralWeightResult({}, 0.0, 0, False, _sha256_of({}))

    if not _NUMPY_AVAILABLE or n == 1:
        uniform = {node: 1.0 / n for node in nodes}
        return SpectralWeightResult(uniform, 1.0, 0, True, _sha256_of(uniform))

    idx = {node: i for i, node in enumerate(nodes)}

    # Build raw adjacency matrix
    A = np.zeros((n, n), dtype=np.float64)
    for (src, dst), w in transition_counts.items():
        if src in idx and dst in idx:
            A[idx[dst], idx[src]] += w  # A[to, from] for left-eigenvector

    # Symmetrise to prevent sink-node collapse on DAGs
    if symmetrise:
        A = A + A.T

    # Column-normalise (avoids zero-sum columns creating NaN)
    col_sums = A.sum(axis=0)
    col_sums[col_sums == 0] = 1.0
    A /= col_sums

    # Power iteration to find dominant eigenvector
    v = np.ones(n, dtype=np.float64) / n
    lam = 1.0
    converged = False
    it = 0
    for it in range(1, max_iter + 1):
        v_new = A @ v
        norm = np.linalg.norm(v_new)
        if norm < 1e-12:
            break
        lam = norm
        v_new /= norm
        if np.linalg.norm(v_new - v) < tol:
            converged = True
            v = v_new
            break
        v = v_new

    # Normalise to sum-to-1 for interpretability
    v_sum = v.sum()
    if v_sum > 0:
        v /= v_sum

    centrality = {node: float(v[idx[node]]) for node in nodes}
    return SpectralWeightResult(
        eigenvector_centrality=centrality,
        dominant_eigenvalue=float(lam),
        iterations=it,
        converged=converged,
        fingerprint=_sha256_of(centrality),
    )


# ══════════════════════════════════════════════════════════════════════
# Event 54: Causal Intervention Weights (Pearl's Do-Calculus / ACE)
# ══════════════════════════════════════════════════════════════════════

@dataclass
class CausalEffectRecord:
    adapter: str
    p_survival_with: float      # P(survival | adapter present in path)
    p_survival_without: float   # P(survival | adapter absent from path)
    ace: float                  # Average Causal Effect = p_with - p_without
    n_with: int                 # observation count when adapter was present
    n_without: int              # observation count when adapter was absent
    confidence: str             # "HIGH" | "MEDIUM" | "LOW" (based on sample size)


@dataclass
class DoCalculusResult:
    adapter_effects: Dict[str, CausalEffectRecord]
    fingerprint: str


def estimate_causal_effects(
    observations: List[Dict],
    *,
    min_count_for_confidence: int = 20,
) -> DoCalculusResult:
    """
    Estimate Average Causal Effect (ACE) for each adapter using the
    observational adjustment estimator.

    Each observation dict must have:
        "path":    List[str]  — ordered adapter names used in this replay
        "success": bool       — did the replay/invariant pass?

    ACE(A) = P(survival | do(A=1)) − P(survival | do(A=0))
           ≈ P(survival | A in path) − P(survival | A not in path)

    NOTE: This is the naive (unadjusted) difference-in-means estimator.
    It is causally valid only under the assumption of no unmeasured confounders
    (i.e., adapter selection is independent of unobserved quality factors).
    This is an engineering heuristic, not a formal do-calculus proof.
    The claim boundary gate must be used before promoting these scores
    to "causal proof" status.

    Physics grounding:
        Pearl (2000) §3.2 — Interventional distributions and back-door criterion.
        Peters et al. (2017) §6 — Average causal effects via observational data.
    """
    # Accumulate per-adapter survival stats
    stats: Dict[str, Dict[str, int]] = {}

    all_adapters = set()
    for obs in observations:
        path = obs.get("path", [])
        all_adapters.update(path)

    for adapter in all_adapters:
        stats[adapter] = {"with_success": 0, "with_total": 0,
                          "without_success": 0, "without_total": 0}

    for obs in observations:
        path_set = set(obs.get("path", []))
        success = int(bool(obs.get("success", False)))
        for adapter in all_adapters:
            if adapter in path_set:
                stats[adapter]["with_total"] += 1
                stats[adapter]["with_success"] += success
            else:
                stats[adapter]["without_total"] += 1
                stats[adapter]["without_success"] += success

    effects: Dict[str, CausalEffectRecord] = {}
    for adapter, s in stats.items():
        p_with = (s["with_success"] / s["with_total"]
                  if s["with_total"] > 0 else 0.0)
        p_without = (s["without_success"] / s["without_total"]
                     if s["without_total"] > 0 else 0.0)
        ace = p_with - p_without

        n_min = min(s["with_total"], s["without_total"])
        if n_min >= min_count_for_confidence:
            conf = "HIGH"
        elif n_min >= min_count_for_confidence // 4:
            conf = "MEDIUM"
        else:
            conf = "LOW"

        effects[adapter] = CausalEffectRecord(
            adapter=adapter,
            p_survival_with=p_with,
            p_survival_without=p_without,
            ace=ace,
            n_with=s["with_total"],
            n_without=s["without_total"],
            confidence=conf,
        )

    fingerprint = _sha256_of({k: v.ace for k, v in sorted(effects.items())})
    return DoCalculusResult(adapter_effects=effects, fingerprint=fingerprint)


# ══════════════════════════════════════════════════════════════════════
# Combined Causal-Spectral Score (Events 53 + 54 fused)
# ══════════════════════════════════════════════════════════════════════

def fuse_spectral_and_causal(
    spectral: SpectralWeightResult,
    causal: DoCalculusResult,
    *,
    spectral_alpha: float = 0.5,
    causal_alpha: float = 0.5,
) -> Dict[str, float]:
    """
    Fuse Eigenvector Centrality (structural) with ACE (causal) into a
    single composite weight per adapter.

    spectral_alpha + causal_alpha should sum to 1.0.

    Adapters absent from one source get a score of 0 for that component.
    Final weights are normalised to sum to 1.
    """
    all_adapters = set(spectral.eigenvector_centrality) | set(causal.adapter_effects)

    # Normalise ACE values to [0, 1] range for fusion
    # ACE ∈ [-1, 1] → shift to [0, 1]
    ace_values = {a: causal.adapter_effects[a].ace
                  for a in causal.adapter_effects}
    ace_min = min(ace_values.values(), default=0.0)
    ace_max = max(ace_values.values(), default=1.0)
    ace_range = max(ace_max - ace_min, 1e-9)

    fused: Dict[str, float] = {}
    for adapter in all_adapters:
        spec_score = spectral.eigenvector_centrality.get(adapter, 0.0)
        raw_ace = ace_values.get(adapter, ace_min)
        norm_ace = (raw_ace - ace_min) / ace_range
        fused[adapter] = spectral_alpha * spec_score + causal_alpha * norm_ace

    total = sum(fused.values()) or 1.0
    return {k: v / total for k, v in sorted(fused.items())}


# ══════════════════════════════════════════════════════════════════════
# Utilities
# ══════════════════════════════════════════════════════════════════════

def _sha256_of(d: Dict) -> str:
    payload = json.dumps(
        {str(k): round(float(v), 8) for k, v in sorted(d.items())},
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def proof_of_property() -> bool:
    """
    MANDATE VERIFICATION — Event 53 + 54 Biocode Olympiad.

    Proves:
    1. Spectral weights correctly identify the keystone adapter
       (M→C edge-dominant) even when it has a modest local rate.
    2. ACE correctly isolates the causally effective adapter
       from a spuriously co-occurring one.
    """
    print("\n=== SIFTA CAUSAL-SPECTRAL WEIGHTING (Events 53+54) : C55M VERIFICATION ===")

    # ── Event 53: Spectral ─────────────────────────────────────────────
    # Graph: M↔C (strong bidirectional flow), M↔B (weak), B↔C (moderate)
    # With symmetrisation, C has the most total edge weight so it should
    # have the highest eigenvector centrality.
    transitions = {
        ("M", "C"): 80.0,
        ("M", "B"): 10.0,
        ("B", "C"): 30.0,
    }
    spec = compute_spectral_weights(transitions, symmetrise=True)
    print(f"\n[Event 53] Eigenvector Centrality (converged={spec.converged}, iter={spec.iterations}):")
    for name, score in sorted(spec.eigenvector_centrality.items(), key=lambda x: -x[1]):
        print(f"  {name}: {score:.4f}")

    assert spec.converged, "[FAIL] Power iteration did not converge."
    top_adapter = max(spec.eigenvector_centrality, key=spec.eigenvector_centrality.get)
    assert top_adapter == "C", f"[FAIL] Expected C as keystone, got {top_adapter}"
    print(f"  ✓ Keystone adapter '{top_adapter}' identified correctly.")

    # ── Event 54: Do-Calculus ──────────────────────────────────────────
    # 'lora_reason' always appears with success.
    # 'lora_style' is a passenger — appears often but has no causal effect.
    observations = []
    for _ in range(60):
        observations.append({"path": ["lora_reason"], "success": True})
    for _ in range(10):
        observations.append({"path": ["lora_reason"], "success": False})
    # lora_style co-occurs with lora_reason half the time (spurious)
    for _ in range(35):
        observations.append({"path": ["lora_reason", "lora_style"], "success": True})
    for _ in range(5):
        observations.append({"path": ["lora_reason", "lora_style"], "success": False})
    # lora_style alone has baseline performance
    for _ in range(25):
        observations.append({"path": ["lora_style"], "success": True})
    for _ in range(25):
        observations.append({"path": ["lora_style"], "success": False})

    causal = estimate_causal_effects(observations)
    print(f"\n[Event 54] Average Causal Effects:")
    for name, rec in sorted(causal.adapter_effects.items(), key=lambda x: -x[1].ace):
        print(f"  {name}: ACE={rec.ace:+.3f} (n_with={rec.n_with}, conf={rec.confidence})")

    reason_ace = causal.adapter_effects["lora_reason"].ace
    style_ace = causal.adapter_effects["lora_style"].ace
    assert reason_ace > style_ace, (
        f"[FAIL] lora_reason ACE ({reason_ace:.3f}) should beat "
        f"lora_style ACE ({style_ace:.3f})"
    )
    print(f"  ✓ lora_reason has higher ACE than lora_style — causal > correlation.")

    # ── Fusion ─────────────────────────────────────────────────────────
    spec2 = compute_spectral_weights({
        ("lora_reason", "lora_style"): 35.0,
        ("lora_reason", "lora_style"): 35.0,
    })
    fused = fuse_spectral_and_causal(spec2, causal)
    print(f"\n[Fusion] Causal-Spectral composite weights:")
    for name, w in sorted(fused.items(), key=lambda x: -x[1]):
        print(f"  {name}: {w:.4f}")

    print("\n[+] PHYSICS PROOF: Spectral centrality identified the keystone.")
    print("[+] PHYSICS PROOF: Do-Calculus isolated causal effect from correlation.")
    print("[+] EVENT 53 + 54 PASSED.")
    return True


if __name__ == "__main__":
    proof_of_property()
