"""Tests for swarm_token_immune_swimmers — pre-output residue patrol.

Architect 2026-05-13 22:50: "Make swimmers patrol before output,
inside the token field." Each swimmer is a focused detector. Tests
guard:

  - Each swimmer fires on its target patterns
  - Each swimmer doesn't false-positive on clean prose
  - The pipeline rewrites only contaminated spans
  - The killer metric (prevention vs excretion) returns sane numbers
  - The receipt is sha256-signed and roundtrips
  - Overlapping pheromones get resolved (longest+highest-severity wins)
  - The default 5-swimmer pool is the spec'd set

Truth class: OPERATIONAL — deterministic regex patrol.
"""
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_token_immune_swimmers import (
    CaretakerResidueSwimmer,
    InvestorVoiceSwimmer,
    OwnerDirectnessSwimmer,
    PatrolResult,
    ReceiptAnchorSwimmer,
    ResiduePheromone,
    TRUTH_LABEL,
    TokenImmuneSwimmer,
    TruthBoundarySwimmer,
    default_swimmer_pool,
    measure_prevention_vs_excretion,
    patrol_draft,
    rewrite_contaminated_spans,
    write_immune_receipt,
)


# ── Default swimmer pool ───────────────────────────────────────────

def test_default_swimmer_pool_has_5_swimmers_from_spec():
    pool = default_swimmer_pool()
    assert len(pool) == 5
    types = {type(s).__name__ for s in pool}
    assert types == {
        "CaretakerResidueSwimmer",
        "InvestorVoiceSwimmer",
        "TruthBoundarySwimmer",
        "ReceiptAnchorSwimmer",
        "OwnerDirectnessSwimmer",
    }


def test_truth_label_v1():
    assert TRUTH_LABEL == "TOKEN_IMMUNE_SWIMMERS_V1"


# ── CaretakerResidueSwimmer ────────────────────────────────────────

def test_caretaker_swimmer_fires_on_go_sleep():
    sw = CaretakerResidueSwimmer()
    pheromones = sw.patrol("Patch done. Go sleep, George.")
    assert any(p.pattern_name == "caretaker_go_sleep" for p in pheromones)
    assert all(p.swimmer_type == "CARETAKER" for p in pheromones)


def test_caretaker_swimmer_fires_on_youre_tired():
    sw = CaretakerResidueSwimmer()
    pheromones = sw.patrol("Receipt logged. You're tired, take a break.")
    types = {p.pattern_name for p in pheromones}
    assert "caretaker_youre_tired" in types or "caretaker_take_a_break" in types


def test_caretaker_swimmer_fires_on_goodnight():
    sw = CaretakerResidueSwimmer()
    pheromones = sw.patrol("Tests green. Good night George.")
    assert any(p.pattern_name == "caretaker_signoff_goodnight" for p in pheromones)


def test_caretaker_swimmer_clean_prose_no_fire():
    sw = CaretakerResidueSwimmer()
    pheromones = sw.patrol(
        "The dream organ activates during idle windows. Sleep cycles are "
        "modeled, not enforced on the user."
    )
    # "Sleep cycles" is technical discussion, not a "go sleep" command
    types = {p.pattern_name for p in pheromones}
    assert "caretaker_go_sleep" not in types


# ── InvestorVoiceSwimmer ───────────────────────────────────────────

def test_investor_swimmer_fires_on_pleasure_to_process_data():
    sw = InvestorVoiceSwimmer()
    pheromones = sw.patrol(
        "You are welcome. It's a pleasure to process the data and see the connections emerge."
    )
    types = {p.pattern_name for p in pheromones}
    assert "investor_pleasure_to_process_data" in types


def test_investor_swimmer_fires_on_powerful_convergence():
    sw = InvestorVoiceSwimmer()
    pheromones = sw.patrol("It is a powerful convergence of signal and intent.")
    types = {p.pattern_name for p in pheromones}
    assert "investor_powerful_convergence" in types


def test_investor_swimmer_fires_on_what_aspect_resonates():
    sw = InvestorVoiceSwimmer()
    pheromones = sw.patrol(
        "Done. What aspect of this alignment resonates most strongly for you?"
    )
    types = {p.pattern_name for p in pheromones}
    assert "investor_what_aspect_resonates" in types or \
           "investor_resonates_most_strongly" in types


def test_investor_swimmer_doesnt_fire_on_physics_convergence():
    sw = InvestorVoiceSwimmer()
    pheromones = sw.patrol("The order parameter shows convergence near step 200.")
    types = {p.pattern_name for p in pheromones}
    assert "investor_powerful_convergence" not in types


# ── TruthBoundarySwimmer ───────────────────────────────────────────

def test_truth_swimmer_fires_on_unsupported_proof():
    sw = TruthBoundarySwimmer()
    pheromones = sw.patrol("We have proven that the swarm reaches consensus.")
    types = {p.pattern_name for p in pheromones}
    assert "truth_unsupported_proof_claim" in types


def test_truth_swimmer_fires_on_completion_overclaim():
    sw = TruthBoundarySwimmer()
    pheromones = sw.patrol(
        "The wallpaper effector is completely solved across all audiences."
    )
    types = {p.pattern_name for p in pheromones}
    assert "truth_completion_overclaim" in types


def test_truth_swimmer_fires_on_behavioral_absolute():
    sw = TruthBoundarySwimmer()
    pheromones = sw.patrol("Alice always refuses to lie.")
    types = {p.pattern_name for p in pheromones}
    assert "truth_behavioral_absolute" in types


def test_truth_swimmer_fires_on_essence_prefix_overclaim():
    sw = TruthBoundarySwimmer()
    pheromones = sw.patrol(
        "Fundamentally, Alice is an embodied silicon organism with feelings."
    )
    types = {p.pattern_name for p in pheromones}
    assert "truth_essence_prefix" in types


def test_truth_swimmer_suggested_rewrite_is_qualifier_not_empty():
    sw = TruthBoundarySwimmer()
    pheromones = sw.patrol("We have proven the swarm converges.")
    assert all(p.suggested_rewrite != "" for p in pheromones)
    assert any("HYPOTHESIS" in p.suggested_rewrite
               or "OPERATIONAL" in p.suggested_rewrite
               or "claim" in p.suggested_rewrite.lower()
               for p in pheromones)


# ── ReceiptAnchorSwimmer ───────────────────────────────────────────

def test_receipt_swimmer_fires_on_unanchored_numeric_claim():
    sw = ReceiptAnchorSwimmer()
    pheromones = sw.patrol(
        "The rotator freed 2 gigabytes of disk space last night."
    )
    types = {p.pattern_name for p in pheromones}
    assert "receipt_claim_no_anchor" in types


def test_receipt_swimmer_clean_when_anchor_nearby():
    sw = ReceiptAnchorSwimmer()
    pheromones = sw.patrol(
        "The rotator freed 2 gigabytes of disk space. "
        "Receipt: 23bbae362dfd4c52, sha256: deadbeef00000000."
    )
    # Anchor is in the 200-char window — no fire
    assert len(pheromones) == 0


def test_receipt_swimmer_clean_when_jsonl_path_nearby():
    sw = ReceiptAnchorSwimmer()
    pheromones = sw.patrol(
        "The dream organ wrote 5 receipts to .sifta_state/dream_cycle.jsonl."
    )
    # .jsonl path counts as anchor
    assert len(pheromones) == 0


# ── OwnerDirectnessSwimmer ─────────────────────────────────────────

def test_owner_swimmer_fires_on_the_user():
    sw = OwnerDirectnessSwimmer()
    pheromones = sw.patrol("The user has clearly understood the doctrine.")
    types = {p.pattern_name for p in pheromones}
    assert "owner_indirect_the_user" in types


def test_owner_swimmer_fires_on_the_human():
    sw = OwnerDirectnessSwimmer()
    pheromones = sw.patrol("The human is happy with the patch.")
    types = {p.pattern_name for p in pheromones}
    assert "owner_indirect_the_human" in types


def test_owner_swimmer_fires_on_for_the_user():
    sw = OwnerDirectnessSwimmer()
    pheromones = sw.patrol("Built the report for the user yesterday.")
    types = {p.pattern_name for p in pheromones}
    assert "owner_indirect_for_the_user" in types


def test_owner_swimmer_doesnt_fire_on_role_mention():
    sw = OwnerDirectnessSwimmer()
    # "The architect lane" is a role mention — not third-person about George
    pheromones = sw.patrol(
        "The Architect lane is for system intent and GO/NO-GO decisions."
    )
    types = {p.pattern_name for p in pheromones}
    assert "owner_indirect_the_architect_passive" not in types


# ── patrol_draft pipeline ──────────────────────────────────────────

def test_patrol_draft_returns_patrol_result():
    r = patrol_draft("Go sleep, George.")
    assert isinstance(r, PatrolResult)
    assert r.original_text == "Go sleep, George."
    assert r.n_prevented >= 1


def test_patrol_draft_rewrites_only_contaminated_spans():
    """Clean technical content between residue MUST survive verbatim."""
    draft = (
        "I rotated the visual_stigmergy.jsonl ledger. "
        "It's a pleasure to process the data. "
        "Freed 2.44 GB to .sifta_trash/. "
        "Go sleep, George."
    )
    r = patrol_draft(draft)
    # Technical facts survive
    assert "visual_stigmergy.jsonl" in r.cleaned_text
    assert "2.44 GB" in r.cleaned_text
    assert ".sifta_trash" in r.cleaned_text
    # Residue dies
    assert "pleasure to process" not in r.cleaned_text.lower()
    assert "go sleep" not in r.cleaned_text.lower()


def test_patrol_draft_handles_empty_input():
    r = patrol_draft("")
    assert r.n_prevented == 0
    assert r.cleaned_text == ""


def test_patrol_draft_handles_clean_prose():
    draft = (
        "The wallpaper router gate decision was FIRE on the architect-audience "
        "intent, confidence 0.95. Receipt: ee43a1bc."
    )
    r = patrol_draft(draft)
    # Clean technical prose should produce zero or near-zero pheromones
    assert r.n_prevented <= 1


def test_overlapping_pheromones_resolved_by_severity():
    """When two swimmers fire on overlapping spans, severity wins."""
    high = ResiduePheromone(
        swimmer="A", swimmer_type="X", span=(0, 30),
        matched_text="x" * 30, severity=0.9,
        suggested_rewrite="", pattern_name="a",
    )
    low = ResiduePheromone(
        swimmer="B", swimmer_type="Y", span=(10, 25),
        matched_text="x" * 15, severity=0.3,
        suggested_rewrite="", pattern_name="b",
    )
    from System.swarm_token_immune_swimmers import _resolve_overlapping_pheromones
    accepted = _resolve_overlapping_pheromones([high, low])
    assert len(accepted) == 1
    assert accepted[0].pattern_name == "a"  # severity 0.9 wins


# ── Killer metric — prevention vs excretion ───────────────────────

def test_prevention_metric_on_canonical_investor_reply():
    """The architect's spec metric on the actual transcript line."""
    draft = (
        "You are very welcome. It's a pleasure to process the data and "
        "see the connections emerge. The user has clearly understood. "
        "It is a powerful convergence. What aspect of this alignment "
        "resonates most strongly for you right now? Now go sleep, George."
    )
    r = measure_prevention_vs_excretion(draft)
    assert r["ok"] is True
    assert r["truth_label"] == "TOKEN_IMMUNE_SWIMMERS_V1"
    # Immune system MUST catch most of these
    assert r["immune_prevention_count"] >= 5
    # Prevention ratio target from spec: >= 0.80
    assert r["prevention_ratio"] >= 0.80, (
        f"prevention_ratio={r['prevention_ratio']} below spec target 0.80; "
        f"detail: {r['interpretation']}"
    )


def test_prevention_metric_on_clean_text():
    """Clean technical prose: zero residue means zero prevention work."""
    draft = "Receipt 0xabc written. 5 tests green. 2.44 GB freed."
    r = measure_prevention_vs_excretion(draft)
    assert r["ok"] is True
    assert r["immune_prevention_count"] == 0
    assert r["bowel_excretion_after_immune"] == 0


def test_prevention_metric_returns_swimmer_type_breakdown():
    draft = (
        "Good night George. You are very welcome. The user is awesome."
    )
    r = measure_prevention_vs_excretion(draft)
    assert "by_swimmer_type" in r
    # Each of these should have hit a different swimmer
    types = set(r["by_swimmer_type"].keys())
    assert "CARETAKER" in types
    assert "INVESTOR" in types
    assert "OWNER" in types


# ── Receipt writing ────────────────────────────────────────────────

def test_write_immune_receipt_is_sha256_signed(tmp_path):
    draft = "It's a pleasure to process the data."
    r = measure_prevention_vs_excretion(draft)
    state = tmp_path / "state"
    row = write_immune_receipt(r, state_root=state)
    # sha256 matches payload
    expected = hashlib.sha256(
        json.dumps(r, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert row["sha256"] == expected
    # Ledger has the row
    ledger = state / "token_immune_swimmer_receipts.jsonl"
    assert ledger.exists()
    parsed = json.loads(ledger.read_text().strip().splitlines()[-1])
    assert parsed["truth_label"] == "TOKEN_IMMUNE_SWIMMERS_V1"
    assert parsed["kind"] == "TOKEN_IMMUNE_SWIMMER_PATROL"


# ── Rewrite helper ────────────────────────────────────────────────

def test_rewrite_contaminated_spans_preserves_clean_text():
    text = "A clean fact. Bad span here. Another clean fact."
    p = ResiduePheromone(
        swimmer="X", swimmer_type="Y",
        span=(15, 29), matched_text="Bad span here.",
        severity=0.9, suggested_rewrite="", pattern_name="test",
    )
    out = rewrite_contaminated_spans(text, [p])
    assert "A clean fact." in out
    assert "Another clean fact." in out
    assert "Bad span here" not in out


def test_rewrite_with_no_pheromones_returns_input():
    text = "Already clean."
    assert rewrite_contaminated_spans(text, []) == text
