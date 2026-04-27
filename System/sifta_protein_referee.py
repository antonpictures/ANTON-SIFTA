#!/usr/bin/env python3
"""
System/sifta_protein_referee.py

Predator v7.0 — Event 79: The Scientific Referee
Cross-engine consistency checker.

SIFTA doesn't just run tools; it acts as an epistemic referee.
This module compares the outputs of different protein folding engines
(e.g., Toy vs ESMFold vs AlphaFold) using the Kabsch algorithm to
compute the Root Mean Square Deviation (RMSD) of their CA backbones.

Biology: 
RMSD < 2.0 Å  → High confidence (Engines agree on the fold)
RMSD < 5.0 Å  → Medium confidence (Broad topological agreement)
RMSD > 5.0 Å  → Contradiction (Engines disagree, epistemic uncertainty)
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


def kabsch_rmsd(P: np.ndarray, Q: np.ndarray) -> float:
    """
    Compute the optimal RMSD between two sets of 3D points
    using the Kabsch algorithm.
    """
    if P.shape != Q.shape:
        raise ValueError("Coordinate arrays must have the same shape for RMSD.")
    
    n = P.shape[0]

    # 1. Translate both to centroids
    P_centered = P - np.mean(P, axis=0)
    Q_centered = Q - np.mean(Q, axis=0)

    # 2. Computation of the covariance matrix
    C = np.dot(np.transpose(P_centered), Q_centered)

    # 3. SVD
    V, S, W = np.linalg.svd(C)
    
    # 4. Handle reflection case (ensure a right-handed coordinate system)
    d = (np.linalg.det(V) * np.linalg.det(W)) < 0.0
    if d:
        S[-1] = -S[-1]
        V[:, -1] = -V[:, -1]

    # 5. Compute rotation matrix
    U = np.dot(V, W)

    # 6. Rotate P
    P_rotated = np.dot(P_centered, U)

    # 7. Compute RMSD
    diff = P_rotated - Q_centered
    rmsd = np.sqrt((diff * diff).sum() / n)
    return float(rmsd)


def referee_judgment(meta1_path: str, meta2_path: str) -> dict:
    """
    Compare two folding jobs and return an epistemic judgment.
    """
    with open(meta1_path) as f:
        job1 = json.load(f)
    with open(meta2_path) as f:
        job2 = json.load(f)

    if job1["sequence"] != job2["sequence"]:
        return {
            "status": "rejected",
            "reason": "sequences do not match",
            "epistemic_flag": "invalid_comparison"
        }

    # Ensure both jobs successfully produced a PDB
    if job1.get("status") != "ok" or job2.get("status") != "ok":
        return {
            "status": "rejected",
            "reason": "one or both jobs failed or lack backend",
            "epistemic_flag": "insufficient_evidence"
        }

    coords1 = parse_pdb_ca_coords(job1["pdb_path"])
    coords2 = parse_pdb_ca_coords(job2["pdb_path"])

    rmsd = kabsch_rmsd(coords1, coords2)

    # Epistemic judgment thresholds
    if rmsd <= 2.0:
        flag = "HIGH_CONFIDENCE_AGREEMENT"
        verdict = "Engines independently converged on identical topology."
    elif rmsd <= 5.0:
        flag = "MEDIUM_CONFIDENCE_AGREEMENT"
        verdict = "Broad topological agreement, but localized discrepancies."
    else:
        flag = "EPISTEMIC_CONTRADICTION"
        verdict = "Engines disagree on fundamental folding pathway. Trust external experimental data."

    judgment = {
        "status": "completed",
        "sequence": job1["sequence"],
        "comparison": f"{job1['engine']} vs {job2['engine']}",
        "rmsd_angstroms": round(rmsd, 3),
        "epistemic_flag": flag,
        "referee_verdict": verdict,
        "truth_labels_compared": [job1["truth_label"], job2["truth_label"]]
    }
    
    return judgment


def referee_triangulate(meta_paths: list[str]) -> dict:
    """
    N-way consensus triangulation (Triangulate 3+ folding engines).
    Computes an all-to-all RMSD matrix to find consensus clusters and detect outliers.
    
    Biology: If 2 engines agree (RMSD < 3.0) and 1 disagrees (RMSD > 5.0),
    the disagreeing engine is flagged as an epistemic outlier.
    """
    if len(meta_paths) < 3:
        raise ValueError("Triangulation requires at least 3 models.")

    jobs = []
    for p in meta_paths:
        with open(p) as f:
            jobs.append(json.load(f))

    # Reject if sequences mismatch
    seqs = {j["sequence"] for j in jobs}
    if len(seqs) > 1:
        return {
            "status": "rejected",
            "epistemic_flag": "invalid_comparison",
            "reason": "Mismatched sequences in triangulation pool."
        }

    # Reject if missing backends
    if any(j.get("status") != "ok" for j in jobs):
        return {
            "status": "rejected",
            "epistemic_flag": "insufficient_evidence",
            "reason": "One or more engines failed to produce coordinates."
        }

    coords = [parse_pdb_ca_coords(j["pdb_path"]) for j in jobs]
    n = len(jobs)
    
    # Compute all-to-all RMSD matrix
    rmsd_matrix = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            val = kabsch_rmsd(coords[i], coords[j])
            rmsd_matrix[i, j] = val
            rmsd_matrix[j, i] = val

    # Consensus cluster detection
    # A model is in consensus if it agrees (RMSD < 3.0A) with at least one other model
    consensus_idx = set()
    for i in range(n):
        for j in range(i + 1, n):
            if rmsd_matrix[i, j] <= 3.0:
                consensus_idx.add(i)
                consensus_idx.add(j)
                
    consensus = [jobs[i]["engine"] for i in sorted(consensus_idx)]
    outliers = [jobs[i]["engine"] for i in range(n) if i not in consensus_idx]
    
    # Calculate an 'isolation score' for metadata (mean distance to consensus core)
    # If no consensus, just use mean distance to all
    mean_distances = []
    for i in range(n):
        if len(consensus_idx) > 0 and i not in consensus_idx:
            # Distance to consensus core
            dist = np.mean([rmsd_matrix[i, j] for j in consensus_idx])
        else:
            dist = np.sum(rmsd_matrix[i]) / (n - 1)
        mean_distances.append(dist)
            
    if len(consensus) >= 2 and len(outliers) > 0:
        flag = "CONSENSUS_WITH_OUTLIER"
        verdict = f"Consensus reached. Epistemic outlier detected and ejected."
    elif len(consensus) == n:
        flag = "GLOBAL_CONSENSUS"
        verdict = "All engines agree. High-confidence topological fold."
    else:
        flag = "NO_CONSENSUS"
        verdict = "Engines structurally diverge. Epistemic void."

    return {
        "status": "completed",
        "sequence": list(seqs)[0],
        "engines": [j["engine"] for j in jobs],
        "rmsd_matrix": np.round(rmsd_matrix, 2).tolist(),
        "isolation_scores": [round(d, 2) for d in mean_distances],
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
