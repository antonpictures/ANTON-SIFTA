"""Tests for the MAMMAL modality visualization helpers.

Architect 2026-05-14: "no graphics and no drug discovery? look how
nice graphics attached for the 3 items in the stigmergic unified field"

These tests guard the deterministic data layer that the widget will
draw. Each helper takes raw biomedical input (SMILES, gene activity
dict, protein sequence) and returns layout-ready specs.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_mammal_modality_viz import (
    AA_CLASS_COLORS,
    ATOM_COLORS,
    AtomBondGraph,
    AtomNode,
    BarSpec,
    BindingHypothesis,
    BondEdge,
    DrugTargetPair,
    ResidueSpec,
    amino_acid_class,
    example_drug_target_pair,
    gene_activity_bars,
    heuristic_binding_score,
    layout_atom_graph,
    parse_smiles_to_graph,
    protein_sequence_strip,
)


# ── SMILES parser ─────────────────────────────────────────────────

def test_parse_ethanol_smiles():
    g = parse_smiles_to_graph("CCO")
    assert g.n_atoms == 3
    elements = [a.element for a in g.atoms]
    assert elements == ["C", "C", "O"]
    # Two bonds: C-C, C-O
    assert g.n_bonds == 2


def test_parse_acetaminophen_smiles():
    """Architect's canonical demo drug from the MAMMAL paper context."""
    g = parse_smiles_to_graph("CC(=O)NC1=CC=C(O)C=C1")
    # 11 heavy atoms: 2 C (acetyl), 1 O (carbonyl), 1 N, 6 ring C, 1 O (phenol)
    assert g.n_atoms == 11
    # At least the carbonyl + aromatic ring bonds present
    assert g.n_bonds >= 11
    # Ring should form — the C1...C1 closure adds an edge
    assert any(b.a != b.b for b in g.bonds)


def test_parse_aspirin_smiles():
    g = parse_smiles_to_graph("CC(=O)Oc1ccccc1C(=O)O")
    assert g.n_atoms > 10
    # Aromatic ring atoms detected
    assert any(a.aromatic for a in g.atoms)


def test_parse_empty_smiles():
    g = parse_smiles_to_graph("")
    assert g.n_atoms == 0
    assert g.n_bonds == 0


def test_parse_smiles_handles_bracket_atom():
    """[Cl] and [NH4] style bracketed atoms parse to a single AtomNode."""
    g = parse_smiles_to_graph("C[Cl]")
    assert g.n_atoms == 2
    assert g.atoms[1].element == "Cl"


def test_parse_smiles_chlorine_two_char():
    g = parse_smiles_to_graph("CCl")
    assert g.n_atoms == 2
    assert g.atoms[0].element == "C"
    assert g.atoms[1].element == "Cl"


def test_parse_smiles_double_bond_order():
    """C=C should produce a single bond record with order=2."""
    g = parse_smiles_to_graph("C=C")
    assert g.n_bonds == 1
    assert g.bonds[0].order == 2


def test_parse_smiles_triple_bond_order():
    g = parse_smiles_to_graph("C#N")
    assert g.bonds[0].order == 3


def test_parse_smiles_aromatic_lowercase():
    """Aromatic atoms (lowercase) get aromatic=True."""
    g = parse_smiles_to_graph("c1ccccc1")
    assert all(a.aromatic for a in g.atoms)


def test_atom_color_table_covers_common_elements():
    for e in ("C", "H", "N", "O", "S", "F", "Cl", "Br"):
        assert e in ATOM_COLORS


# ── Layout ────────────────────────────────────────────────────────

def test_layout_returns_position_per_atom():
    g = parse_smiles_to_graph("CCO")
    pos = layout_atom_graph(g, iterations=10, seed=1)
    assert len(pos) == 3
    for (x, y) in pos.values():
        assert -1.0 <= x <= 1.0
        assert -1.0 <= y <= 1.0


def test_layout_is_deterministic_with_seed():
    g = parse_smiles_to_graph("CC(=O)O")
    pos1 = layout_atom_graph(g, iterations=20, seed=42)
    pos2 = layout_atom_graph(g, iterations=20, seed=42)
    assert pos1 == pos2


def test_layout_empty_graph():
    g = AtomBondGraph(atoms=[], bonds=[], smiles="")
    assert layout_atom_graph(g) == {}


# ── Gene activity bars ────────────────────────────────────────────

def test_gene_bars_sorted_descending():
    bars = gene_activity_bars({"A": 0.2, "B": 0.9, "C": 0.5})
    values = [b.value for b in bars]
    assert values == sorted(values, reverse=True)
    assert bars[0].label == "B"


def test_gene_bars_color_high_value_teal():
    bars = gene_activity_bars({"high": 0.9})
    assert bars[0].color == "#4ee0a8"  # teal


def test_gene_bars_color_low_value_gray():
    bars = gene_activity_bars({"silent": 0.1})
    assert bars[0].color == "#888888"  # gray


def test_gene_bars_empty_dict():
    assert gene_activity_bars({}) == []


def test_gene_bars_clamps_values_to_max():
    bars = gene_activity_bars({"over": 5.0}, max_value=1.0)
    assert bars[0].value == 1.0


# ── Amino-acid classification ────────────────────────────────────

@pytest.mark.parametrize("letter,expected", [
    ("A", "hydrophobic"), ("V", "hydrophobic"), ("L", "hydrophobic"),
    ("F", "aromatic"), ("Y", "aromatic"), ("W", "aromatic"),
    ("S", "polar"), ("T", "polar"), ("N", "polar"),
    ("D", "acidic"), ("E", "acidic"),
    ("K", "basic"), ("R", "basic"), ("H", "basic"),
    ("X", "special"), ("Z", "special"),
])
def test_amino_acid_class(letter, expected):
    assert amino_acid_class(letter) == expected


def test_amino_acid_class_empty_returns_special():
    assert amino_acid_class("") == "special"


def test_amino_acid_class_is_case_insensitive():
    assert amino_acid_class("a") == amino_acid_class("A")


# ── Protein sequence strip ────────────────────────────────────────

def test_protein_strip_first_n_residues():
    strip = protein_sequence_strip("MKTAYIAKQRQISFVKSHFSRQ", max_residues=10)
    assert len(strip) == 10
    assert strip[0].letter == "M"
    assert strip[0].index == 0


def test_protein_strip_each_residue_has_color():
    strip = protein_sequence_strip("MKTAYIAKQR")
    for r in strip:
        assert r.color in AA_CLASS_COLORS.values()


def test_protein_strip_handles_lowercase_input():
    strip = protein_sequence_strip("mkta")
    assert [r.letter for r in strip] == ["M", "K", "T", "A"]


def test_protein_strip_filters_non_alpha():
    strip = protein_sequence_strip("M K-T@A")
    # Whitespace and punctuation removed
    assert [r.letter for r in strip] == ["M", "K", "T", "A"]


def test_protein_strip_empty_input():
    assert protein_sequence_strip("") == []


# ── Demo pair ────────────────────────────────────────────────────

def test_example_drug_target_pair_is_acetaminophen_egfr():
    pair = example_drug_target_pair()
    assert pair.drug_name == "acetaminophen"
    assert "CC(=O)N" in pair.drug_smiles
    assert "EGFR" in pair.target_name
    assert "EGFR" in pair.target_gene_activity
    # Pair note must include the truth-class caveat
    assert "not a binding assertion" in pair.note.lower()


def test_example_pair_smiles_parses():
    pair = example_drug_target_pair()
    g = parse_smiles_to_graph(pair.drug_smiles)
    assert g.n_atoms >= 10


def test_example_pair_sequence_parses():
    pair = example_drug_target_pair()
    strip = protein_sequence_strip(pair.target_sequence)
    assert len(strip) > 0


# ── Binding hypothesis ────────────────────────────────────────────

def test_heuristic_binding_score_returns_hypothesis():
    pair = example_drug_target_pair()
    g = parse_smiles_to_graph(pair.drug_smiles)
    strip = protein_sequence_strip(pair.target_sequence)
    out = heuristic_binding_score(g, strip)
    assert isinstance(out, BindingHypothesis)
    assert out.truth_class == "HYPOTHESIS"
    assert 0.0 <= out.score <= 1.0
    # Rationale must explicitly note this is NOT a real binding prediction
    assert "not a real binding prediction" in out.rationale.lower() or \
           "placeholder" in out.rationale.lower()


def test_heuristic_score_is_deterministic():
    """Same drug + target → same score, always."""
    g = parse_smiles_to_graph("CCO")
    strip = protein_sequence_strip("AAAAFF")
    s1 = heuristic_binding_score(g, strip).score
    s2 = heuristic_binding_score(g, strip).score
    assert s1 == s2


def test_heuristic_score_zero_when_no_data():
    g = AtomBondGraph(atoms=[], bonds=[], smiles="")
    out = heuristic_binding_score(g, [])
    assert out.score == 0.0
