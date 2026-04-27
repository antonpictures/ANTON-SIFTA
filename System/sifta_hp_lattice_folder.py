#!/usr/bin/env python3
"""
System/sifta_hp_lattice_folder.py

C55M + George co-signed protein folding baseline.

This is intentionally not the existing SIFTA folding lane:
  - not Lennard-Jones
  - not Metropolis Monte Carlo
  - not ACO / pheromone search
  - not Kabsch/referee alignment

It implements the classic hydrophobic-polar lattice model as a deterministic
beam branch search over 3D self-avoiding walks.  The useful property is speed:
it can fold a panel of short sequences locally and produce falsifiable PDB
artifacts that the existing SIFTA referee can compare against other engines.

Energy model
------------
    E = - sum_{i<j-1} 1[AA_i in H] * 1[AA_j in H] * 1[Manhattan(r_i,r_j)=1]

That is the Dill HP abstraction: hydrophobic residues are rewarded for
forming non-covalent lattice contacts.  Coordinates are exported as C-alpha
PDB atoms at 3.8 Angstrom spacing so the rest of the SIFTA structural pipeline
can ingest them.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable
import hashlib
import json
import math

import numpy as np

AA20 = set("ACDEFGHIKLMNPQRSTVWY")
HYDROPHOBIC = set("AILMFWVYC")
LATTICE_DIRS: tuple[tuple[int, int, int], ...] = (
    (1, 0, 0),
    (-1, 0, 0),
    (0, 1, 0),
    (0, -1, 0),
    (0, 0, 1),
    (0, 0, -1),
)

AA3 = {
    "A": "ALA", "C": "CYS", "D": "ASP", "E": "GLU", "F": "PHE",
    "G": "GLY", "H": "HIS", "I": "ILE", "K": "LYS", "L": "LEU",
    "M": "MET", "N": "ASN", "P": "PRO", "Q": "GLN", "R": "ARG",
    "S": "SER", "T": "THR", "V": "VAL", "W": "TRP", "Y": "TYR",
}


@dataclass(frozen=True)
class _BeamState:
    coords: tuple[tuple[int, int, int], ...]
    occupied: frozenset[tuple[int, int, int]]
    energy: int
    hh_contacts: int


@dataclass
class HPLatticeFoldResult:
    sequence: str
    engine: str
    truth_label: str
    lattice_coords: list[list[int]]
    energy: int
    hydrophobic_contacts: int
    radius_gyration_lattice: float
    radius_gyration_angstrom: float
    beam_width: int
    states_expanded: int
    pruned_self_collisions: int
    structure_hash: str
    cosigned_by: list[str]

    def as_dict(self) -> dict:
        return asdict(self)


def validate_sequence(sequence: str) -> str:
    seq = "".join(sequence.upper().split())
    if not seq:
        raise ValueError("empty protein sequence")
    bad = sorted(set(seq) - AA20)
    if bad:
        raise ValueError(f"invalid amino acids: {bad}")
    return seq


def _manhattan(a: tuple[int, int, int], b: tuple[int, int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])


def _radius_gyration(coords: Iterable[tuple[int, int, int]]) -> float:
    arr = np.array(list(coords), dtype=float)
    centroid = arr.mean(axis=0)
    return float(np.sqrt(np.mean(np.sum((arr - centroid) ** 2, axis=1))))


def _new_hh_contacts(seq: str, idx: int, coord: tuple[int, int, int],
                     prior_coords: tuple[tuple[int, int, int], ...]) -> int:
    if seq[idx] not in HYDROPHOBIC:
        return 0
    contacts = 0
    for j, old in enumerate(prior_coords[:-1]):
        if seq[j] in HYDROPHOBIC and _manhattan(coord, old) == 1:
            contacts += 1
    return contacts


def _optimistic_sort_key(seq: str, state: _BeamState) -> tuple[float, int, float, str]:
    """Stable beam ranking: energy first, compactness second, coordinates last."""
    rg = _radius_gyration(state.coords)
    remaining_h = sum(aa in HYDROPHOBIC for aa in seq[len(state.coords):])
    optimistic_energy = state.energy - min(remaining_h, 4)
    digest = hashlib.sha1(repr(state.coords).encode()).hexdigest()
    return (optimistic_energy + 0.025 * rg, state.energy, rg, digest)


def fold_hp_lattice(sequence: str, *, beam_width: int = 1024) -> HPLatticeFoldResult:
    """
    Fold a sequence with deterministic 3D HP lattice beam search.

    The search is bounded by beam_width, so it is not an exact exhaustive
    solver for long chains.  It is a deterministic useful baseline: same
    sequence + same beam width produces the same PDB every time.
    """
    seq = validate_sequence(sequence)
    beam_width = max(8, int(beam_width))

    if len(seq) == 1:
        coords = ((0, 0, 0),)
        state = _BeamState(coords, frozenset(coords), 0, 0)
        states_expanded = 1
        pruned = 0
    else:
        coords = ((0, 0, 0), (1, 0, 0))
        state = _BeamState(coords, frozenset(coords), 0, 0)
        beam = [state]
        states_expanded = 0
        pruned = 0

        for idx in range(2, len(seq)):
            candidates: list[_BeamState] = []
            for st in beam:
                states_expanded += 1
                tail = st.coords[-1]
                for dx, dy, dz in LATTICE_DIRS:
                    nxt = (tail[0] + dx, tail[1] + dy, tail[2] + dz)
                    if nxt in st.occupied:
                        pruned += 1
                        continue
                    contact_gain = _new_hh_contacts(seq, idx, nxt, st.coords)
                    new_energy = st.energy - contact_gain
                    new_coords = st.coords + (nxt,)
                    candidates.append(
                        _BeamState(
                            coords=new_coords,
                            occupied=st.occupied | {nxt},
                            energy=new_energy,
                            hh_contacts=st.hh_contacts + contact_gain,
                        )
                    )

            if not candidates:
                raise RuntimeError("HP lattice search exhausted all self-avoiding walks")

            candidates.sort(key=lambda st: _optimistic_sort_key(seq, st))
            beam = candidates[:beam_width]

        state = min(beam, key=lambda st: (st.energy, _radius_gyration(st.coords)))

    rg_lattice = _radius_gyration(state.coords)
    lattice_coords = [list(c) for c in state.coords]
    structure_hash = hashlib.sha256(
        json.dumps({"seq": seq, "coords": lattice_coords}, sort_keys=True).encode()
    ).hexdigest()

    return HPLatticeFoldResult(
        sequence=seq,
        engine="c55m_hp_lattice",
        truth_label="c55m_george_hp_lattice_beam_search",
        lattice_coords=lattice_coords,
        energy=state.energy,
        hydrophobic_contacts=state.hh_contacts,
        radius_gyration_lattice=round(rg_lattice, 4),
        radius_gyration_angstrom=round(rg_lattice * 3.8, 4),
        beam_width=beam_width,
        states_expanded=states_expanded,
        pruned_self_collisions=pruned,
        structure_hash=structure_hash,
        cosigned_by=["C55M-DR-CODEX", "George Anton"],
    )


def lattice_to_angstrom(coords: list[list[int]]) -> np.ndarray:
    return np.array(coords, dtype=float) * 3.8


def save_pdb(sequence: str, coords_angstrom: np.ndarray, path: str | Path) -> None:
    path = Path(path)
    with path.open("w", encoding="utf-8") as f:
        f.write("REMARK SIFTA C55M + George HP lattice beam-search fold\n")
        f.write("REMARK Coordinates are C-alpha lattice baseline, not AlphaFold truth\n")
        for i, (aa, p) in enumerate(zip(sequence, coords_angstrom), start=1):
            f.write(
                f"ATOM  {i:5d}  CA  {AA3[aa]:>3s} A{i:4d}    "
                f"{p[0]:8.3f}{p[1]:8.3f}{p[2]:8.3f}"
                f"  1.00  0.00           C\n"
            )
        f.write("END\n")


def fold_to_pdb(sequence: str, pdb_path: str | Path, *, beam_width: int = 1024) -> dict:
    result = fold_hp_lattice(sequence, beam_width=beam_width)
    save_pdb(result.sequence, lattice_to_angstrom(result.lattice_coords), pdb_path)
    return result.as_dict()


DEFAULT_PROTEIN_PANEL: tuple[tuple[str, str], ...] = (
    ("sifta_demo_peptide", "ACFLIVGPGKTYL"),
    ("oxytocin_like_nonapeptide", "CYIQNCPLG"),
    ("insulin_a_chain", "GIVEQCCTSICSLYQLENYCN"),
    ("insulin_b_chain", "FVNQHLCGSHLVEALYLVCGERGFFYTPKT"),
    ("calmodulin_fragment", "MADQLTEEQIAEFKEAFSLFDKDGDGTITT"),
    ("albumin_signal_fragment", "MKWVTFISLLFLFSSAYSRGVFRR"),
)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="C55M + George HP lattice protein folder")
    ap.add_argument("sequence", nargs="?", default="ACFLIVGPGKTYL")
    ap.add_argument("--beam", type=int, default=1024)
    ap.add_argument("--out", default=".sifta_state/protein_folds/c55m_hp_lattice.pdb")
    args = ap.parse_args()

    meta = fold_to_pdb(args.sequence, args.out, beam_width=args.beam)
    print(json.dumps(meta, indent=2))
