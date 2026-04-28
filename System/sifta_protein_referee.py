#!/usr/bin/env python3
"""
System/sifta_protein_referee.py

Predator v7.0 — Event 81: Multi-Axis Structural Referee
Upgraded from naïve RMSD to length-normalized, domain-motion robust metrics.

Scientific Anchors:
1. TM-score (Zhang & Skolnick, 2004)
2. Contact Map Overlap (CASP standards)

SIFTA judges fold topological equivalence via length-independent TM-scores
and interaction-preserving contact maps, not just rigid-body RMSD.
"""

from __future__ import annotations
import json
import numpy as np
from pathlib import Path


def parse_pdb_ca_coords(pdb_path: str) -> np.ndarray:
    """Extract CA (alpha carbon) coordinates from a PDB file."""
    coords = []
    with open(pdb_path, "r") as f:
        for line in f:
            if line.startswith("ATOM") and " CA " in line:
                x = float(line[30:38])
                y = float(line[38:46])
                z = float(line[46:54])
                coords.append([x, y, z])
    if not coords:
        raise ValueError(f"No CA atoms found in {pdb_path}")
    return np.array(coords)


def kabsch_align(P: np.ndarray, Q: np.ndarray) -> np.ndarray:
    """
    Superimposes P onto Q using the Kabsch algorithm.
    Returns the rotated and translated P' that minimizes RMSD to Q.
    """
    P_centered = P - np.mean(P, axis=0)
    Q_centered = Q - np.mean(Q, axis=0)
    C = np.dot(np.transpose(P_centered), Q_centered)
    V, S, W = np.linalg.svd(C)
    if (np.linalg.det(V) * np.linalg.det(W)) < 0.0:
        S[-1] = -S[-1]
        V[:, -1] = -V[:, -1]
    U = np.dot(V, W)
    P_rotated = np.dot(P_centered, U)
    return P_rotated + np.mean(Q, axis=0)


def tm_score_approx(P_aligned: np.ndarray, Q: np.ndarray) -> float:
    """
    Calculates an approximate TM-score (Zhang & Skolnick, 2004)
    using pre-aligned coordinates. TM-score is robust to local loops
    and length-independent.
    """
    n = len(P_aligned)
    if n <= 15:
        d0 = 0.5
    else:
        d0 = 1.24 * (n - 15) ** (1/3) - 1.8
        d0 = max(d0, 0.5)

    dist = np.linalg.norm(P_aligned - Q, axis=1)
    score = np.mean(1 / (1 + (dist / d0) ** 2))
    return float(score)


def contact_map(xyz: np.ndarray, cutoff: float = 8.0) -> np.ndarray:
    """
    Binary contact map. Residues i and j interact if their CA distance < 8.0A.
    """
    n = len(xyz)
    C = np.zeros((n, n), dtype=int)
    for i in range(n):
        for j in range(i + 3, n):  # Exclude immediate sequence neighbors
            if np.linalg.norm(xyz[i] - xyz[j]) < cutoff:
                C[i, j] = C[j, i] = 1
    return C


def contact_overlap(c1: np.ndarray, c2: np.ndarray) -> tuple[float, float]:
    """Returns Precision and Recall of contact preservation."""
    tp = np.sum((c1 == 1) & (c2 == 1))
    fp = np.sum((c1 == 1) & (c2 == 0))
    fn = np.sum((c1 == 0) & (c2 == 1))

    precision = tp / (tp + fp + 1e-8)
    recall = tp / (tp + fn + 1e-8)
    return float(precision), float(recall)


def multi_metric_compare(P: np.ndarray, Q: np.ndarray) -> dict:
    """
    Execute the multi-axis structural referee pipeline.
    """
    if P.shape != Q.shape:
        raise ValueError("Coordinate arrays must have the same shape.")

    # Structural alignment
    P_aligned = kabsch_align(P, Q)

    # Metrics
    tm = tm_score_approx(P_aligned, Q)
    rmsd = np.sqrt(np.mean(np.sum((P_aligned - Q) ** 2, axis=1)))
    
    c1 = contact_map(P)
    c2 = contact_map(Q)
    precision, recall = contact_overlap(c1, c2)

    return {
        "tm_score": round(tm, 3),
        "rmsd_angstroms": round(float(rmsd), 3),
        "contact_precision": round(precision, 3),
        "contact_recall": round(recall, 3),
    }


def referee_judgment(meta1_path: str, meta2_path: str) -> dict:
    """Compare two folding jobs using multi-metric biology truth."""
    with open(meta1_path) as f:
        job1 = json.load(f)
    with open(meta2_path) as f:
        job2 = json.load(f)

    if job1["sequence"] != job2["sequence"]:
        return {
            "status": "rejected",
            "epistemic_flag": "invalid_comparison",
            "reason": "sequences do not match"
        }
    if job1.get("status") != "ok" or job2.get("status") != "ok":
        return {
            "status": "rejected",
            "epistemic_flag": "insufficient_evidence",
            "reason": "one or both jobs lack coordinates"
        }

    coords1 = parse_pdb_ca_coords(job1["pdb_path"])
    coords2 = parse_pdb_ca_coords(job2["pdb_path"])

    metrics = multi_metric_compare(coords1, coords2)
    tm = metrics["tm_score"]
    cp = metrics["contact_precision"]

    # Smarter Classification Thresholds (TM-score normalized)
    if tm > 0.7 and cp > 0.7:
        flag = "TRUE_CONSENSUS"
        verdict = "Identical fold geometry and high interaction preservation."
    elif tm > 0.5:
        flag = "SAME_FOLD"
        verdict = "Shared global topology. Discrepancies likely flexible loops or domain motion."
    else:
        flag = "STRUCTURAL_CONTRADICTION"
        verdict = "Fundamentally distinct topological folding pathways."

    return {
        "status": "completed",
        "sequence": job1["sequence"],
        "comparison": f"{job1['engine']} vs {job2['engine']}",
        "metrics": metrics,
        "epistemic_flag": flag,
        "referee_verdict": verdict,
    }


def referee_triangulate(meta_paths: list[str]) -> dict:
    """
    N-way consensus triangulation using TM-scores.
    A TM-score > 0.5 designates two models as belonging to the same fold cluster.
    """
    if len(meta_paths) < 3:
        raise ValueError("Triangulation requires at least 3 models.")

    jobs = []
    for p in meta_paths:
        with open(p) as f:
            jobs.append(json.load(f))

    seqs = {j["sequence"] for j in jobs}
    if len(seqs) > 1:
        return {
            "status": "rejected",
            "epistemic_flag": "invalid_comparison",
            "reason": "Mismatched sequences."
        }
    if any(j.get("status") != "ok" for j in jobs):
        return {
            "status": "rejected",
            "epistemic_flag": "insufficient_evidence"
        }

    coords = [parse_pdb_ca_coords(j["pdb_path"]) for j in jobs]
    n = len(jobs)
    
    # Compute all-to-all TM-score matrix
    tm_matrix = np.zeros((n, n))
    for i in range(n):
        tm_matrix[i, i] = 1.0
        for j in range(i + 1, n):
            # TM-score is generally symmetric for same-length alignments
            m = multi_metric_compare(coords[i], coords[j])
            tm = m["tm_score"]
            tm_matrix[i, j] = tm
            tm_matrix[j, i] = tm

    # Consensus cluster detection
    # A model is in consensus if it shares the SAME FOLD (TM > 0.5) with at least one other
    consensus_idx = set()
    for i in range(n):
        for j in range(i + 1, n):
            if tm_matrix[i, j] >= 0.5:
                consensus_idx.add(i)
                consensus_idx.add(j)
                
    consensus = [jobs[i]["engine"] for i in sorted(consensus_idx)]
    outliers = [jobs[i]["engine"] for i in range(n) if i not in consensus_idx]
            
    if len(consensus) >= 2 and len(outliers) > 0:
        flag = "CONSENSUS_WITH_OUTLIER"
        verdict = "Fold topology consensus reached. Epistemic outlier ejected based on TM-score."
    elif len(consensus) == n:
        flag = "GLOBAL_CONSENSUS"
        verdict = "All engines successfully converged on the same topological fold."
    else:
        flag = "NO_CONSENSUS"
        verdict = "All engines structurally contradict. Total epistemic void."

    return {
        "status": "completed",
        "sequence": list(seqs)[0],
        "engines": [j["engine"] for j in jobs],
        "tm_matrix": np.round(tm_matrix, 3).tolist(),
        "consensus_cluster": consensus,
        "outliers_ejected": outliers,
        "epistemic_flag": flag,
        "referee_verdict": verdict
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python sifta_protein_referee.py <meta1.json> <meta2.json> [meta3.json ...]")
        sys.exit(1)
        
    if len(sys.argv) == 3:
        judgment = referee_judgment(sys.argv[1], sys.argv[2])
    else:
        judgment = referee_triangulate(sys.argv[1:])
        
    print(json.dumps(judgment, indent=2))
