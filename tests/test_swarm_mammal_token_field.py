"""Tests for swarm_mammal_token_field — living MAMMAL token ecology.

Architect spec checklist (each test pins one bullet):
  ✓ 7 MAMMAL token types (PROTEIN, SMALL_MOLECULE, GENE_EXPRESSION,
    ANTIBODY, SCALAR_ATTR, TOKEN_ATTR, TIME_TAG)
  ✓ 7 swimmer types (Binding, Contradiction, Inflammation, Mutation,
    Toxicity, Memory, DreamReplay)
  ✓ Token metabolism — decay each step
  ✓ Reinforce / destabilize via swimmer patrol
  ✓ Dead tokens get culled
  ✓ Dream replay only fires when dream_mode True
  ✓ Each receipt kind (HYPOTHESIS / CONTRADICTION / LOW_CONFIDENCE /
    REPLAY_REINFORCED / TOXICITY_CLUSTER) is reachable
  ✓ Snapshot is sha256-signed
  ✓ Field doesn't crash on swimmer exceptions
"""
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_mammal_token_field import (
    BindingSwimmer,
    ContradictionSwimmer,
    DreamReplaySwimmer,
    InflammationSwimmer,
    MAMMAL_TOKEN_TYPES,
    MammalToken,
    MammalTokenField,
    MemorySwimmer,
    MutationSwimmer,
    RECEIPT_KINDS,
    RK_CONTRADICTION,
    RK_HYPOTHESIS,
    RK_LOW_CONFIDENCE,
    RK_REPLAY_REINFORCED,
    RK_TOXICITY_CLUSTER,
    TRUTH_LABEL,
    TT_ANTIBODY,
    TT_GENE_EXPRESSION,
    TT_PROTEIN,
    TT_SCALAR_ATTR,
    TT_SMALL_MOLECULE,
    TT_TIME_TAG,
    TT_TOKEN_ATTR,
    ToxicitySwimmer,
    TokenSwimmer,
    default_swimmer_pool,
    seed_demo_field,
)


# ── Taxonomy ──────────────────────────────────────────────────────

def test_mammal_token_types_match_paper():
    assert MAMMAL_TOKEN_TYPES == {
        TT_PROTEIN, TT_SMALL_MOLECULE, TT_GENE_EXPRESSION, TT_ANTIBODY,
        TT_SCALAR_ATTR, TT_TOKEN_ATTR, TT_TIME_TAG,
    }
    assert len(MAMMAL_TOKEN_TYPES) == 7


def test_receipt_kinds_match_architect_spec():
    """All 5 receipt kinds the architect named must exist."""
    assert RK_HYPOTHESIS in RECEIPT_KINDS
    assert RK_CONTRADICTION in RECEIPT_KINDS
    assert RK_LOW_CONFIDENCE in RECEIPT_KINDS
    assert RK_REPLAY_REINFORCED in RECEIPT_KINDS
    assert RK_TOXICITY_CLUSTER in RECEIPT_KINDS
    assert len(RECEIPT_KINDS) == 5


def test_truth_label_v1():
    assert TRUTH_LABEL == "STIGMERGIC_MAMMAL_FIELD_V1"


def test_default_pool_is_7_distinct_species():
    pool = default_swimmer_pool(seed=113)
    assert len(pool) == 7
    types = {type(s).__name__ for s in pool}
    assert types == {
        "BindingSwimmer", "ContradictionSwimmer", "InflammationSwimmer",
        "MutationSwimmer", "ToxicitySwimmer", "MemorySwimmer",
        "DreamReplaySwimmer",
    }


# ── Token spawning + lifecycle ────────────────────────────────────

def test_spawn_token_rejects_unknown_type():
    f = MammalTokenField(seed=1)
    with pytest.raises(ValueError):
        f.spawn_token("UNKNOWN_TYPE", "x")


def test_spawn_token_assigns_random_position_when_unset():
    f = MammalTokenField(width=10, height=10, seed=1)
    t = f.spawn_token(TT_PROTEIN, "EGFR")
    assert 0 <= t.x <= 10
    assert 0 <= t.y <= 10


def test_token_alive_initially():
    f = MammalTokenField(seed=1)
    t = f.spawn_token(TT_PROTEIN, "p53", x=5, y=5)
    assert t.alive is True
    assert t.energy == 1.0
    assert t.visit_count == 0


def test_token_dies_when_energy_below_threshold():
    f = MammalTokenField(seed=1, lambda_decay=0.5, death_threshold=0.1)
    f.spawn_token(TT_PROTEIN, "weak", x=5, y=5, energy=0.2)
    # Two steps should decay below threshold
    f.step()
    f.step()
    assert len(f.tokens) == 0  # weakling died
    assert f.tokens_died == 1


# ── Token metabolism (epistemic thermodynamics) ───────────────────

def test_decay_reduces_energy_each_step():
    f = MammalTokenField(seed=1, lambda_decay=0.1)
    t = f.spawn_token(TT_PROTEIN, "decaying", x=5, y=5, energy=1.0)
    # No swimmers, just decay
    f.step()
    assert 0.85 < f.tokens[0].energy < 0.95


def test_reinforce_boosts_energy_clamped_to_one():
    f = MammalTokenField(seed=1)
    f.spawn_token(TT_PROTEIN, "x", x=5, y=5, energy=0.5)
    f.reinforce(0, amount=0.3)
    assert f.tokens[0].energy == pytest.approx(0.8)
    f.reinforce(0, amount=1.0)
    assert f.tokens[0].energy == 1.0  # clamped


def test_destabilize_drops_energy_clamped_to_zero():
    f = MammalTokenField(seed=1)
    f.spawn_token(TT_PROTEIN, "x", x=5, y=5, energy=0.4)
    f.destabilize(0, amount=0.1)
    # destabilize multiplies amount by 2.0 internally
    assert f.tokens[0].energy == pytest.approx(0.2)


def test_reinforce_increments_visit_count():
    f = MammalTokenField(seed=1)
    f.spawn_token(TT_PROTEIN, "x", x=5, y=5)
    assert f.tokens[0].visit_count == 0
    f.reinforce(0, 0.1)
    f.reinforce(0, 0.1)
    assert f.tokens[0].visit_count == 2


# ── Per-swimmer firing (architect spec coverage) ──────────────────

def test_binding_swimmer_fires_on_protein_plus_ligand():
    f = MammalTokenField(width=12, height=12, seed=1)
    f.spawn_token(TT_PROTEIN, "EGFR", x=6, y=6)
    f.spawn_token(TT_SMALL_MOLECULE, "imatinib", x=6.5, y=6)
    sw = BindingSwimmer("B", x=5.5, y=6, sensing_radius=3.0)
    f.swimmers.append(sw)
    out = f.step()
    assert RK_HYPOTHESIS in out["receipts_by_kind"]
    assert out["receipts_by_kind"][RK_HYPOTHESIS] >= 1


def test_contradiction_swimmer_fires_on_opposite_sign_scalars():
    f = MammalTokenField(width=12, height=12, seed=2)
    f.spawn_token(TT_SCALAR_ATTR, "0.7", x=5, y=5)
    f.spawn_token(TT_SCALAR_ATTR, "-0.5", x=5.3, y=5)
    sw = ContradictionSwimmer("C", x=5, y=5, sensing_radius=2.0)
    f.swimmers.append(sw)
    out = f.step()
    assert RK_CONTRADICTION in out["receipts_by_kind"]


def test_contradiction_swimmer_extracts_suffixed_numerics():
    """'hERG_0.8' should parse to +0.8, paired with -0.4 → contradiction."""
    f = MammalTokenField(width=12, height=12, seed=3)
    f.spawn_token(TT_SCALAR_ATTR, "hERG_0.8", x=5, y=5)
    f.spawn_token(TT_SCALAR_ATTR, "potency:-0.4", x=5.3, y=5)
    sw = ContradictionSwimmer("C", x=5, y=5, sensing_radius=2.0)
    f.swimmers.append(sw)
    out = f.step()
    assert RK_CONTRADICTION in out["receipts_by_kind"]


def test_inflammation_swimmer_fires_on_TNF_token():
    f = MammalTokenField(width=12, height=12, seed=4)
    f.spawn_token(TT_PROTEIN, "TNF-alpha", x=5, y=5)
    sw = InflammationSwimmer("I", x=5, y=5, sensing_radius=2.0)
    f.swimmers.append(sw)
    out = f.step()
    assert RK_HYPOTHESIS in out["receipts_by_kind"]


def test_inflammation_swimmer_fires_on_any_antibody():
    """Antibodies are inflammation markers regardless of value text."""
    f = MammalTokenField(width=12, height=12, seed=5)
    f.spawn_token(TT_ANTIBODY, "some-ab", x=5, y=5)
    sw = InflammationSwimmer("I", x=5, y=5, sensing_radius=2.0)
    f.swimmers.append(sw)
    out = f.step()
    assert RK_HYPOTHESIS in out["receipts_by_kind"]


def test_mutation_swimmer_fires_on_mutation_signature():
    f = MammalTokenField(width=12, height=12, seed=6)
    f.spawn_token(TT_PROTEIN, "p53_mut_R175H", x=5, y=5)
    sw = MutationSwimmer("Mu", x=5, y=5, sensing_radius=2.0)
    f.swimmers.append(sw)
    out = f.step()
    assert RK_HYPOTHESIS in out["receipts_by_kind"]


def test_toxicity_swimmer_fires_on_small_molecule_plus_hERG():
    f = MammalTokenField(width=12, height=12, seed=7)
    f.spawn_token(TT_SMALL_MOLECULE, "drugX", x=5, y=5)
    f.spawn_token(TT_SCALAR_ATTR, "hERG_0.8", x=5.3, y=5)
    sw = ToxicitySwimmer("T", x=5, y=5, sensing_radius=2.0)
    f.swimmers.append(sw)
    out = f.step()
    assert RK_TOXICITY_CLUSTER in out["receipts_by_kind"]


def test_memory_swimmer_fires_only_on_revisited_token():
    f = MammalTokenField(width=12, height=12, seed=8)
    t = f.spawn_token(TT_PROTEIN, "p53", x=5, y=5)
    t.visit_count = 5  # already revisited
    sw = MemorySwimmer("Me", x=5, y=5, sensing_radius=2.0)
    f.swimmers.append(sw)
    out = f.step()
    assert RK_REPLAY_REINFORCED in out["receipts_by_kind"]


def test_memory_swimmer_silent_on_fresh_token():
    """A token with visit_count < 3 should NOT trigger a memory receipt."""
    f = MammalTokenField(width=12, height=12, seed=9)
    f.spawn_token(TT_PROTEIN, "p53", x=5, y=5)  # visit_count = 0
    sw = MemorySwimmer("Me", x=5, y=5, sensing_radius=2.0)
    f.swimmers.append(sw)
    out = f.step()
    assert out["receipts_by_kind"].get(RK_REPLAY_REINFORCED, 0) == 0


def test_dream_replay_only_active_in_dream_mode():
    f = MammalTokenField(width=12, height=12, seed=10)
    f.spawn_token(TT_PROTEIN, "strong", x=5, y=5, energy=0.9)
    sw = DreamReplaySwimmer("D", x=5, y=5, sensing_radius=3.0)
    f.swimmers.append(sw)
    # Dream mode OFF — no receipts
    f.dream_mode = False
    out_off = f.step()
    assert out_off["receipts_by_kind"].get(RK_REPLAY_REINFORCED, 0) == 0
    # Dream mode ON — should fire on a high-energy token
    f.dream_mode = True
    out_on = f.step()
    assert RK_REPLAY_REINFORCED in out_on["receipts_by_kind"]


# ── Long-run ecology ──────────────────────────────────────────────

def test_long_run_emits_multiple_receipt_kinds():
    """End-to-end: 200-step run with the full pool should emit at least
    3 distinct receipt kinds and demonstrate token mortality."""
    f = MammalTokenField(width=16, height=12, seed=113)
    f.install_default_pool(seed=113)
    for sw in f.swimmers:
        sw.sensing_radius = 4.5
    seed_demo_field(f, n_each=6)
    for step in range(200):
        if step == 120:
            f.dream_mode = True
        f.step()
    snap = f.snapshot()
    # At least 3 receipt kinds fired
    assert len(snap["receipts_by_kind"]) >= 3
    # Token metabolism: tokens died (epistemic thermodynamics)
    assert snap["n_tokens_died_total"] > 0
    # Some receipts of each main kind
    assert snap["receipts_by_kind"].get(RK_HYPOTHESIS, 0) > 0


# ── Defensive: swimmer exception must not crash the field ─────────

def test_field_survives_swimmer_exception():
    class BadSwimmer(TokenSwimmer):
        swimmer_type = "BAD"

        def patrol(self, field):
            raise RuntimeError("intentional test failure")

    f = MammalTokenField(seed=1)
    f.spawn_token(TT_PROTEIN, "x", x=5, y=5)
    f.add_swimmer(BadSwimmer("buggy"))
    out = f.step()
    # Field didn't crash; the failure was recorded as a LOW_CONFIDENCE receipt
    assert out["receipts_by_kind"].get(RK_LOW_CONFIDENCE, 0) >= 1


# ── Snapshot / receipt ────────────────────────────────────────────

def test_snapshot_carries_truth_label():
    f = MammalTokenField(seed=1)
    f.spawn_token(TT_PROTEIN, "x", x=5, y=5)
    snap = f.snapshot()
    assert snap["truth_label"] == "STIGMERGIC_MAMMAL_FIELD_V1"
    assert "ARCHITECT_DOCTRINE" in snap["truth_class"]


def test_write_receipt_is_sha256_signed(tmp_path):
    f = MammalTokenField(seed=1)
    f.spawn_token(TT_PROTEIN, "x", x=5, y=5)
    f.step()
    row = f.write_receipt(state_root=tmp_path)
    expected = hashlib.sha256(
        json.dumps(row["payload"], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert row["sha256"] == expected
    ledger = tmp_path / "stigmergic_mammal_receipts.jsonl"
    assert ledger.exists()
    parsed = json.loads(ledger.read_text().strip().splitlines()[-1])
    assert parsed["kind"] == "STIGMERGIC_MAMMAL_FIELD_SNAPSHOT"


def test_truth_boundary_forbids_collider_claims():
    from System.swarm_mammal_token_field import TRUTH_BOUNDARY
    assert "§20.F" in TRUTH_BOUNDARY or "CERN" in TRUTH_BOUNDARY
    assert "HYPOTHESIS" in TRUTH_BOUNDARY
