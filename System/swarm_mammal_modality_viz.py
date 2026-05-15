#!/usr/bin/env python3
"""swarm_mammal_modality_viz.py — pure helpers for MAMMAL modality graphics.

Architect 2026-05-14 (after watching the MAMMAL paper video):
    "i love the app, very nice explanation, but no graphics and no
    drug discovery? look how nice graphics attached for the 3 items
    in the stigmergic unified field?"

The MAMMAL paper figure he attached shows three modalities flowing
into one shared embedding space:

  ┌────────────────┬────────────────┬────────────────┐
  │ SMALL MOLECULE │ GENE EXPRESSION│   PROTEIN      │
  │  ⚛-⚛-⚛-⚛       │  ACTB ▆▆▆▆▂   │  IRLRNVMEEM... │
  │  (atoms+bonds) │  GAPDH ▆▆▆▂▂   │  (sequence)    │
  │                │  CD4 ▆▂▂▂▂     │  (3D ribbon)   │
  │                │  IL2RA ▆▆▂▂▂   │                │
  ├────────────────┴────────────────┴────────────────┤
  │            shared multi-dimensional space        │
  └──────────────────────────────────────────────────┘

This module exposes pure helpers (no Qt, no matplotlib) that compute
the LAYOUT data for each modality. The widget can then draw them with
any backend. Helpers tested headlessly with deterministic outputs.

  parse_smiles_to_graph(smiles)        → AtomBondGraph
  gene_activity_bars(genes_dict)       → list[BarSpec]
  protein_sequence_strip(sequence)     → list[ResidueSpec]
  amino_acid_class(letter)             → 'hydrophobic'|'polar'|'acidic'|
                                          'basic'|'aromatic'|'special'
  example_drug_target_pair()           → canonical demo pair
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Optional


# ──────────────────────────────────────────────────────────────────────
# Small molecule — toy SMILES parser
# ──────────────────────────────────────────────────────────────────────

# Atom colors used in the chemistry community (Corey–Pauling–Koltun-ish).
ATOM_COLORS = {
    "C": "#404040",  # gray
    "H": "#e8e8e8",  # near-white
    "N": "#3060ff",  # blue
    "O": "#ff3030",  # red
    "S": "#e0e040",  # yellow
    "P": "#ff9040",  # orange
    "F": "#80ff80",  # green
    "Cl": "#80ff80",
    "Br": "#a04040",
    "I": "#9040b0",
}

# Bond-order tokens in SMILES (and double/triple via = / #)
_BOND_ORDERS = {"-": 1, "=": 2, "#": 3, ":": 1}


@dataclass
class AtomNode:
    """One atom in the parsed SMILES graph."""
    idx: int
    element: str
    aromatic: bool = False
    explicit_h: int = 0

    def color(self) -> str:
        return ATOM_COLORS.get(self.element, "#a0a0a0")


@dataclass
class BondEdge:
    """One bond between two atoms (a, b are atom indices)."""
    a: int
    b: int
    order: int = 1  # 1 single, 2 double, 3 triple


@dataclass
class AtomBondGraph:
    """Parsed SMILES — atoms + bonds. NOT a chemistry-correct structure,
    just enough to draw a recognizable 2D ball-and-stick diagram."""
    atoms: list[AtomNode]
    bonds: list[BondEdge]
    smiles: str

    @property
    def n_atoms(self) -> int:
        return len(self.atoms)

    @property
    def n_bonds(self) -> int:
        return len(self.bonds)

    def to_dict(self) -> dict[str, Any]:
        return {
            "smiles": self.smiles,
            "atoms": [asdict(a) for a in self.atoms],
            "bonds": [asdict(b) for b in self.bonds],
        }


# Two-char elements first, then single-char (regex alternation order matters).
_ATOM_RE = re.compile(
    r"\[([A-Za-z][a-z]?\d*)\]|"      # bracketed [Cl] [NH4] [13C]
    r"(Cl|Br)|"                         # 2-char halogens
    r"([CNOSPFIBcnosp])"                # 1-char + aromatic
)


def parse_smiles_to_graph(smiles: str) -> AtomBondGraph:
    """Toy SMILES parser. Handles atoms (incl. brackets), bonds (single
    = # :), branches (), and ring-closure digits 0-9. Returns a flat
    atom+bond graph suitable for 2D layout.

    Out of scope (intentionally — keeps the widget light):
      - Stereochemistry (@, /, \\)
      - Charges in brackets
      - Isotopes
      - Multi-component dot notation (.)

    Test scenes from the architect's video:
      CC(=O)Oc1ccccc1C(=O)O   → aspirin
      CC(=O)NC1=CC=C(O)C=C1   → acetaminophen (paracetamol)
      CCO                       → ethanol
    """
    if not smiles or not isinstance(smiles, str):
        return AtomBondGraph(atoms=[], bonds=[], smiles=smiles or "")
    atoms: list[AtomNode] = []
    bonds: list[BondEdge] = []
    branch_stack: list[int] = []
    ring_openings: dict[str, int] = {}
    last_atom: Optional[int] = None
    pending_bond_order: int = 1
    i = 0
    n = len(smiles)
    while i < n:
        c = smiles[i]
        # Bond token
        if c in _BOND_ORDERS:
            pending_bond_order = _BOND_ORDERS[c]
            i += 1
            continue
        # Branch open
        if c == "(":
            if last_atom is not None:
                branch_stack.append(last_atom)
            i += 1
            continue
        if c == ")":
            if branch_stack:
                last_atom = branch_stack.pop()
            i += 1
            continue
        # Ring-closure digit
        if c.isdigit():
            key = c
            if key in ring_openings:
                a = ring_openings.pop(key)
                if last_atom is not None and a != last_atom:
                    bonds.append(BondEdge(a=a, b=last_atom, order=pending_bond_order or 1))
                    pending_bond_order = 1
            else:
                if last_atom is not None:
                    ring_openings[key] = last_atom
            i += 1
            continue
        # Bracketed atom [Cl] / [NH4] etc.
        if c == "[":
            end = smiles.find("]", i)
            if end == -1:
                i += 1
                continue
            inner = smiles[i + 1:end]
            element_match = re.match(r"([A-Z][a-z]?)", inner)
            element = element_match.group(1) if element_match else inner
            new_idx = len(atoms)
            atoms.append(AtomNode(
                idx=new_idx, element=element,
                aromatic=element[0].islower(),
            ))
            if last_atom is not None:
                bonds.append(BondEdge(a=last_atom, b=new_idx, order=pending_bond_order or 1))
            last_atom = new_idx
            pending_bond_order = 1
            i = end + 1
            continue
        # Two-char halogen
        if c == "C" and i + 1 < n and smiles[i + 1] == "l":
            new_idx = len(atoms)
            atoms.append(AtomNode(idx=new_idx, element="Cl"))
            if last_atom is not None:
                bonds.append(BondEdge(a=last_atom, b=new_idx, order=pending_bond_order or 1))
            last_atom = new_idx
            pending_bond_order = 1
            i += 2
            continue
        if c == "B" and i + 1 < n and smiles[i + 1] == "r":
            new_idx = len(atoms)
            atoms.append(AtomNode(idx=new_idx, element="Br"))
            if last_atom is not None:
                bonds.append(BondEdge(a=last_atom, b=new_idx, order=pending_bond_order or 1))
            last_atom = new_idx
            pending_bond_order = 1
            i += 2
            continue
        # 1-char element (incl. aromatic lowercase)
        if c in "CNOSPFIBcnosp":
            element = c.upper()
            new_idx = len(atoms)
            atoms.append(AtomNode(
                idx=new_idx, element=element, aromatic=c.islower(),
            ))
            if last_atom is not None:
                bonds.append(BondEdge(a=last_atom, b=new_idx, order=pending_bond_order or 1))
            last_atom = new_idx
            pending_bond_order = 1
            i += 1
            continue
        # Anything else — skip silently
        i += 1
    return AtomBondGraph(atoms=atoms, bonds=bonds, smiles=smiles)


# ──────────────────────────────────────────────────────────────────────
# 2D layout — simple spring-style placement
# ──────────────────────────────────────────────────────────────────────

def layout_atom_graph(
    graph: AtomBondGraph, *, iterations: int = 60, seed: int = 113,
) -> dict[int, tuple[float, float]]:
    """Spring-layout in 2D, returns dict[atom_idx → (x, y)] in [-1, 1]^2.

    Pure stdlib + math (no numpy / networkx dependency to keep the
    widget lightweight). Deterministic given seed.
    """
    import math
    import random

    if graph.n_atoms == 0:
        return {}
    rng = random.Random(seed)
    pos = {a.idx: (rng.uniform(-0.5, 0.5), rng.uniform(-0.5, 0.5))
           for a in graph.atoms}
    # Adjacency
    adj: dict[int, set[int]] = {a.idx: set() for a in graph.atoms}
    for b in graph.bonds:
        adj[b.a].add(b.b)
        adj[b.b].add(b.a)
    k = 0.5  # ideal edge length
    for step in range(iterations):
        # Repulsive force between every pair
        forces = {idx: [0.0, 0.0] for idx in pos}
        for ai in pos:
            for aj in pos:
                if ai == aj:
                    continue
                dx = pos[ai][0] - pos[aj][0]
                dy = pos[ai][1] - pos[aj][1]
                d2 = dx * dx + dy * dy + 0.01
                f = 0.02 / d2
                forces[ai][0] += f * dx
                forces[ai][1] += f * dy
        # Attractive force along edges
        for b in graph.bonds:
            dx = pos[b.b][0] - pos[b.a][0]
            dy = pos[b.b][1] - pos[b.a][1]
            d = math.hypot(dx, dy) + 0.01
            f = 0.1 * (d - k)
            forces[b.a][0] += f * dx / d
            forces[b.a][1] += f * dy / d
            forces[b.b][0] -= f * dx / d
            forces[b.b][1] -= f * dy / d
        # Apply with decay
        rate = 0.1 * (1 - step / iterations)
        new_pos: dict[int, tuple[float, float]] = {}
        for idx, (x, y) in pos.items():
            nx = max(-1.0, min(1.0, x + forces[idx][0] * rate))
            ny = max(-1.0, min(1.0, y + forces[idx][1] * rate))
            new_pos[idx] = (nx, ny)
        pos = new_pos
    return pos


# ──────────────────────────────────────────────────────────────────────
# Gene activity — bar chart specs
# ──────────────────────────────────────────────────────────────────────

@dataclass
class BarSpec:
    label: str
    value: float
    color: str


def gene_activity_bars(
    genes: dict[str, float],
    *,
    max_value: float = 1.0,
) -> list[BarSpec]:
    """Render a dict of gene → activity (0..max_value) as bar specs.

    Colors come from a small palette by relative magnitude — bright
    teal for high, dim gray for low. The MAMMAL paper figure uses this
    "priority list" framing where the loudest genes go first.
    """
    if not isinstance(genes, dict) or not genes:
        return []
    items = sorted(genes.items(), key=lambda kv: -float(kv[1]))
    bars: list[BarSpec] = []
    for label, value in items:
        v = max(0.0, min(float(value), max_value))
        ratio = v / max_value if max_value > 0 else 0
        if ratio >= 0.75:
            color = "#4ee0a8"   # teal — high
        elif ratio >= 0.5:
            color = "#ffcc44"   # gold — moderate
        elif ratio >= 0.25:
            color = "#ff8c42"   # orange — low
        else:
            color = "#888888"   # gray — silent
        bars.append(BarSpec(label=str(label), value=v, color=color))
    return bars


# ──────────────────────────────────────────────────────────────────────
# Protein — amino-acid class strip
# ──────────────────────────────────────────────────────────────────────

# Standard amino-acid grouping (Lehninger / textbook).
_AA_CLASS = {
    # Hydrophobic (nonpolar aliphatic)
    "A": "hydrophobic", "V": "hydrophobic", "L": "hydrophobic",
    "I": "hydrophobic", "M": "hydrophobic", "G": "hydrophobic",
    "P": "hydrophobic",
    # Aromatic
    "F": "aromatic", "Y": "aromatic", "W": "aromatic",
    # Polar uncharged
    "S": "polar", "T": "polar", "C": "polar",
    "N": "polar", "Q": "polar",
    # Acidic
    "D": "acidic", "E": "acidic",
    # Basic
    "K": "basic", "R": "basic", "H": "basic",
}

AA_CLASS_COLORS = {
    "hydrophobic": "#ffd54a",  # gold
    "aromatic":    "#b76eff",  # violet
    "polar":       "#4ee0a8",  # teal
    "acidic":      "#ff6e6e",  # red
    "basic":       "#5aa8ff",  # blue
    "special":     "#888888",  # gray (X, B, Z, U, …)
}


def amino_acid_class(letter: str) -> str:
    if not letter:
        return "special"
    return _AA_CLASS.get(letter.upper(), "special")


@dataclass
class ResidueSpec:
    """One residue tick in the protein sequence strip."""
    index: int
    letter: str
    classification: str
    color: str


def protein_sequence_strip(sequence: str, *, max_residues: int = 80) -> list[ResidueSpec]:
    """Render a protein sequence as a colored strip — first
    `max_residues` residues, each carrying its class + color."""
    if not isinstance(sequence, str) or not sequence:
        return []
    cleaned = "".join(ch for ch in sequence.upper() if ch.isalpha())
    out: list[ResidueSpec] = []
    for i, letter in enumerate(cleaned[:max_residues]):
        cls = amino_acid_class(letter)
        out.append(ResidueSpec(
            index=i, letter=letter,
            classification=cls,
            color=AA_CLASS_COLORS[cls],
        ))
    return out


# ──────────────────────────────────────────────────────────────────────
# Demo drug-target pair (from the MAMMAL paper context)
# ──────────────────────────────────────────────────────────────────────

@dataclass
class DrugTargetPair:
    """A canonical demo pair for the unified-field widget.

    Acetaminophen + EGFR is just a recognizable contrast — a familiar
    OTC small molecule against a famous cancer-relevant protein. We do
    NOT claim a binding result; the widget's HYPOTHESIS panel is the
    only place a prediction may appear, and it inherits truth_class=
    HYPOTHESIS per §20.F.
    """
    drug_name: str
    drug_smiles: str
    target_name: str
    target_sequence: str
    target_gene_activity: dict[str, float]
    note: str


def example_drug_target_pair() -> DrugTargetPair:
    """The default demo pair the widget seeds on open."""
    return DrugTargetPair(
        drug_name="acetaminophen",
        drug_smiles="CC(=O)NC1=CC=C(O)C=C1",
        target_name="EGFR (epidermal growth factor receptor) extracellular fragment",
        # First 80 residues of the EGFR extracellular domain (Uniprot P00533).
        # Used only as a visualization seed — not a binding assertion.
        target_sequence=(
            "LEEKKVCQGTSNKLTQLGTFEDHFLSLQRMFNNCEVVLGNLEITYVQRNYDLSFLKTIQEVAGYVLIALNTVERIPL"
        ),
        target_gene_activity={
            "ACTB": 0.85,
            "GAPDH": 0.78,
            "CD4": 0.45,
            "IL2RA": 0.32,
            "EGFR": 0.92,
        },
        note=(
            "Demo pair for the Unified Field widget. Not a binding "
            "assertion — the HYPOTHESIS panel below shows the predicted "
            "interaction class only, never wet-lab certainty."
        ),
    )


# ──────────────────────────────────────────────────────────────────────
# Simple "binding hypothesis" — heuristic, NOT MAMMAL-derived
# ──────────────────────────────────────────────────────────────────────

@dataclass
class BindingHypothesis:
    """A pure-heuristic hypothesis used when MAMMAL is not loaded.
    Once MAMMAL is wired live, this fallback is replaced by a real
    embedding-dot-product score. All outputs inherit HYPOTHESIS class."""
    drug_name: str
    target_name: str
    score: float            # 0..1 heuristic, NOT a real binding affinity
    rationale: str
    truth_class: str = "HYPOTHESIS"


def heuristic_binding_score(
    drug_graph: AtomBondGraph,
    target_residues: list[ResidueSpec],
) -> BindingHypothesis:
    """A deterministic heuristic — co-counts of aromatic/polar/acidic
    features. NOT predictive of real binding. Use only as a visible
    fallback so the widget has SOMETHING to show when MAMMAL isn't
    queried.

    Score formula:
        drug_aromatic_count * 0.1
        + drug_polar_atom_count * 0.05
        + (target_aromatic_fraction * 0.4)
        + (target_polar_fraction * 0.3)
    Clamped to [0, 1].
    """
    drug_aromatic = sum(1 for a in drug_graph.atoms if a.aromatic)
    drug_polar = sum(1 for a in drug_graph.atoms if a.element in ("N", "O", "S"))
    n_res = len(target_residues) or 1
    target_aromatic = sum(1 for r in target_residues if r.classification == "aromatic") / n_res
    target_polar = sum(1 for r in target_residues if r.classification == "polar") / n_res
    score = (
        drug_aromatic * 0.1
        + drug_polar * 0.05
        + target_aromatic * 0.4
        + target_polar * 0.3
    )
    score = max(0.0, min(1.0, score))
    rationale = (
        f"heuristic: drug has {drug_aromatic} aromatic atoms + "
        f"{drug_polar} polar heteroatoms; target shows "
        f"{target_aromatic:.0%} aromatic and {target_polar:.0%} polar "
        f"residues in the first {n_res} positions. NOT a real binding "
        f"prediction — placeholder until MAMMAL embeddings are wired."
    )
    return BindingHypothesis(
        drug_name="", target_name="", score=round(score, 3),
        rationale=rationale,
    )


if __name__ == "__main__":
    import json
    pair = example_drug_target_pair()
    drug_g = parse_smiles_to_graph(pair.drug_smiles)
    print(f"drug {pair.drug_name}: {drug_g.n_atoms} atoms, {drug_g.n_bonds} bonds")
    target_strip = protein_sequence_strip(pair.target_sequence)
    print(f"target {pair.target_name}: {len(target_strip)} residues")
    bars = gene_activity_bars(pair.target_gene_activity)
    for b in bars:
        print(f"  {b.label}: {b.value:.2f}  [{b.color}]")
    hyp = heuristic_binding_score(drug_g, target_strip)
    hyp.drug_name = pair.drug_name
    hyp.target_name = pair.target_name
    print(f"\nheuristic score: {hyp.score}  (truth_class={hyp.truth_class})")
    print(hyp.rationale)
