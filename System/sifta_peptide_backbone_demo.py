#!/usr/bin/env python3
"""
System/sifta_peptide_backbone_demo.py

Predator v7.0 — SIFTA toy peptide folding engine.
Proof that sequence -> energy -> Monte Carlo -> PDB works.
"""

from __future__ import annotations
import numpy as np
import json
from pathlib import Path

AA = "ACDEFGHIKLMNPQRSTVWY"

HYDRO = {
    "A": 1.8, "C": 2.5, "D": -3.5, "E": -3.5, "F": 2.8,
    "G": -0.4, "H": -3.2, "I": 4.5, "K": -3.9, "L": 3.8,
    "M": 1.9, "N": -3.5, "P": -1.6, "Q": -3.5, "R": -4.5,
    "S": -0.8, "T": -0.7, "V": 4.2, "W": -0.9, "Y": -1.3,
}

def random_backbone(n: int, bond: float = 3.8) -> np.ndarray:
    xyz = np.zeros((n, 3), dtype=float)
    direction = np.array([1.0, 0.0, 0.0])

    for i in range(1, n):
        direction += np.random.normal(0, 0.35, 3)
        direction /= np.linalg.norm(direction)
        xyz[i] = xyz[i - 1] + bond * direction

    return xyz

def energy(seq: str, xyz: np.ndarray) -> float:
    e = 0.0
    n = len(seq)

    # bond length restraint
    for i in range(n - 1):
        d = np.linalg.norm(xyz[i + 1] - xyz[i])
        e += 10.0 * (d - 3.8) ** 2

    # nonlocal contacts
    for i in range(n):
        for j in range(i + 3, n):
            r = np.linalg.norm(xyz[i] - xyz[j]) + 1e-8

            # steric repulsion
            e += 30.0 / r**12

            # hydrophobic attraction
            hi = max(HYDRO[seq[i]], 0.0)
            hj = max(HYDRO[seq[j]], 0.0)
            e -= 0.08 * hi * hj * np.exp(-((r - 6.5) ** 2) / 8.0)

    return float(e)

def mutate_backbone(xyz: np.ndarray, scale: float = 0.45) -> np.ndarray:
    new = xyz.copy()
    k = np.random.randint(1, len(xyz) - 1)

    axis = np.random.normal(0, 1, 3)
    axis /= np.linalg.norm(axis)

    angle = np.random.normal(0, scale)

    tail = new[k:] - new[k]
    c, s = np.cos(angle), np.sin(angle)
    K = np.array([
        [0, -axis[2], axis[1]],
        [axis[2], 0, -axis[0]],
        [-axis[1], axis[0], 0],
    ])
    R = np.eye(3) + s * K + (1 - c) * (K @ K)

    new[k:] = new[k] + tail @ R.T
    return new

def fold(seq: str, steps: int = 5000, temp: float = 1.0, save_trajectory: bool = False):
    seq = seq.upper()
    assert all(a in AA for a in seq)

    xyz = random_backbone(len(seq))
    best = xyz.copy()
    e = energy(seq, xyz)
    best_e = e
    
    trajectory = []

    for step in range(steps):
        trial = mutate_backbone(xyz)
        e2 = energy(seq, trial)

        accept = e2 < e or np.random.rand() < np.exp((e - e2) / temp)

        if accept:
            xyz, e = trial, e2

        if e < best_e:
            best, best_e = xyz.copy(), e
            
        if save_trajectory and step % 50 == 0:
            # Center the backbone to origin to avoid camera drift
            centered = best - np.mean(best, axis=0)
            trajectory.append(centered.tolist())

        temp *= 0.9995

    return best, best_e, trajectory

def save_pdb(seq: str, xyz: np.ndarray, path: str):
    with open(path, "w") as f:
        for i, (aa, p) in enumerate(zip(seq, xyz), start=1):
            f.write(
                f"ATOM  {i:5d}  CA  {aa:>3s} A{i:4d}    "
                f"{p[0]:8.3f}{p[1]:8.3f}{p[2]:8.3f}"
                f"  1.00  0.00           C\n"
            )
        f.write("END\n")

if __name__ == "__main__":
    seq = "ACFLIVGPGKTYL"
    xyz, e, traj = fold(seq, steps=8000, temp=1.2)

    print("SIFTA peptide backbone proof")
    print("sequence:", seq)
    print("residues:", len(seq))
    print("final_energy:", round(e, 4))

    save_pdb(seq, xyz, "sifta_toy_fold.pdb")
    print("saved: sifta_toy_fold.pdb")
