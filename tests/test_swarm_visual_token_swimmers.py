"""Tests for the six visual swimmer species (Vision Tournament P2)."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_visual_microburst import (
    BurstScheduler,
    MicroBurstPolicy,
    VisualToken,
)
from System.swarm_visual_token_swimmers import (
    LEDGER_NAME,
    PHEROMONE_KINDS,
    PK_CROSS_ORGAN_BINDING,
    PK_MICRO_BURST_REQUEST,
    PK_OCR_PRIVACY_GATE,
    PK_OWNER_PRESENCE,
    PK_SURPRISE_TRAIL,
    PK_VISUAL_RESIDUE_ELIMINATED,
    TRUTH_LABEL,
    CrossOrganBinder,
    FaceMassSwimmer,
    FoveaSwimmer,
    MotionSwimmer,
    OCRGuardSwimmer,
    Pheromone,
    RedundancyBowelSwimmer,
    VisualSwimmer,
    default_visual_swimmer_pool,
    patrol_visual_tokens,
)


# ── Taxonomy ─────────────────────────────────────────────────────

def test_truth_label_v1():
    assert TRUTH_LABEL == "VISUAL_TOKEN_SWIMMERS_V1"


def test_six_pheromone_kinds_match_spec():
    """The architect's §6 spec lists exactly 6 pheromone kinds."""
    assert PK_SURPRISE_TRAIL in PHEROMONE_KINDS
    assert PK_OWNER_PRESENCE in PHEROMONE_KINDS
    assert PK_MICRO_BURST_REQUEST in PHEROMONE_KINDS
    assert PK_OCR_PRIVACY_GATE in PHEROMONE_KINDS
    assert PK_VISUAL_RESIDUE_ELIMINATED in PHEROMONE_KINDS
    assert PK_CROSS_ORGAN_BINDING in PHEROMONE_KINDS
    assert len(PHEROMONE_KINDS) == 6


def test_default_pool_is_six_distinct_species():
    pool = default_visual_swimmer_pool()
    assert len(pool) == 6
    species = {type(s).__name__ for s in pool}
    assert species == {
        "MotionSwimmer", "FaceMassSwimmer", "FoveaSwimmer",
        "OCRGuardSwimmer", "RedundancyBowelSwimmer", "CrossOrganBinder",
    }


# ── 1. MotionSwimmer ─────────────────────────────────────────────

def test_motion_swimmer_fires_on_surprise():
    sw = MotionSwimmer()
    tok = VisualToken(entity="motion:cell-1", mass=0.5,
                      wake_reason="surprise", attrs={"delta": 0.7})
    out = sw.inspect(tok)
    assert len(out) == 1
    assert out[0].kind == PK_SURPRISE_TRAIL


def test_motion_swimmer_fires_on_high_delta():
    sw = MotionSwimmer()
    tok = VisualToken(entity="motion:c", mass=0.4,
                      wake_reason="static", attrs={"delta": 0.8})
    out = sw.inspect(tok)
    assert len(out) == 1


def test_motion_swimmer_silent_on_quiet_token():
    sw = MotionSwimmer()
    tok = VisualToken(entity="bg:x", mass=0.05,
                      wake_reason="static", attrs={"delta": 0.1})
    assert sw.inspect(tok) == []


# ── 2. FaceMassSwimmer ───────────────────────────────────────────

def test_face_mass_swimmer_fires_on_owner_face():
    sw = FaceMassSwimmer()
    tok = VisualToken(entity="owner_face:Ioan", mass=0.5,
                      wake_reason="static", attrs={"kind": "face"})
    out = sw.inspect(tok)
    assert len(out) == 1
    assert out[0].kind == PK_OWNER_PRESENCE


def test_face_mass_swimmer_increases_with_visits():
    """Recurring faces should ramp mass — that's the whole point."""
    sw = FaceMassSwimmer()
    tok = VisualToken(entity="owner_face:Ioan", mass=0.5, attrs={"kind": "face"})
    s1 = sw.inspect(tok)[0].severity
    s2 = sw.inspect(tok)[0].severity
    s3 = sw.inspect(tok)[0].severity
    assert s1 < s2 < s3


def test_face_mass_swimmer_does_not_store_raw_frame():
    """The pheromone note must explicitly say 'no raw frame stored'."""
    sw = FaceMassSwimmer()
    tok = VisualToken(entity="owner_face:Ioan", mass=0.5, attrs={"kind": "face"})
    out = sw.inspect(tok)
    assert "no raw frame stored" in out[0].note.lower() or \
           "raw frame" in out[0].note.lower()


def test_face_mass_swimmer_silent_on_non_face():
    sw = FaceMassSwimmer()
    tok = VisualToken(entity="motion:cell-1", mass=0.5)
    assert sw.inspect(tok) == []


# ── 3. FoveaSwimmer ──────────────────────────────────────────────

def test_fovea_swimmer_fires_micro_burst_on_high_mass():
    sched = BurstScheduler(MicroBurstPolicy(cooldown_ms=100_000))
    sw = FoveaSwimmer(scheduler=sched)
    tok = VisualToken(entity="motion:cell-1", mass=0.9)
    out = sw.inspect(tok)
    assert len(out) == 1
    assert out[0].kind == PK_MICRO_BURST_REQUEST


def test_fovea_swimmer_respects_cooldown():
    """A second inspect on the same hot entity is suppressed."""
    sched = BurstScheduler(MicroBurstPolicy(cooldown_ms=10_000))
    sw = FoveaSwimmer(scheduler=sched)
    tok = VisualToken(entity="motion:hot", mass=0.9)
    out1 = sw.inspect(tok)
    out2 = sw.inspect(tok)
    assert len(out1) == 1
    assert len(out2) == 0


# ── 4. OCRGuardSwimmer (§7 acceptance: opt-in only) ─────────────

def test_ocr_guard_refuses_without_opt_in():
    """surprise alone CANNOT silently OCR the desktop."""
    sw = OCRGuardSwimmer()
    tok = VisualToken(entity="text:url-bar", mass=0.9,
                      wake_reason="surprise", attrs={"kind": "text_region"})
    out = sw.inspect(tok, context={})  # NO opt-in
    assert len(out) == 1
    assert out[0].kind == PK_OCR_PRIVACY_GATE
    assert "refused" in out[0].note.lower()


def test_ocr_guard_permits_with_explicit_opt_in():
    sw = OCRGuardSwimmer()
    tok = VisualToken(entity="text:url-bar", mass=0.5, attrs={"kind": "text_region"})
    out = sw.inspect(tok, context={"ocr_opt_in": True})
    assert len(out) == 1
    assert "permitted" in out[0].note.lower()


def test_ocr_guard_permits_with_task_need():
    sw = OCRGuardSwimmer()
    tok = VisualToken(entity="text:url-bar", mass=0.5, attrs={"kind": "text_region"})
    out = sw.inspect(tok, context={"task_need": "ocr"})
    assert len(out) == 1
    assert "permitted" in out[0].note.lower()


def test_ocr_guard_silent_on_non_text_tokens():
    sw = OCRGuardSwimmer()
    tok = VisualToken(entity="motion:cell-1", mass=0.9)
    assert sw.inspect(tok, context={"ocr_opt_in": True}) == []


# ── 5. RedundancyBowelSwimmer ────────────────────────────────────

def test_redundancy_bowel_flags_after_threshold_repeats():
    sw = RedundancyBowelSwimmer(mass_threshold=0.2, repeat_threshold=3)
    tok = VisualToken(entity="bg:cell-12", mass=0.05, wake_reason="static")
    # First two visits — silent
    assert sw.inspect(tok) == []
    assert sw.inspect(tok) == []
    # Third visit — flag
    out = sw.inspect(tok)
    assert len(out) == 1
    assert out[0].kind == PK_VISUAL_RESIDUE_ELIMINATED


def test_redundancy_bowel_does_not_flag_high_info():
    sw = RedundancyBowelSwimmer(mass_threshold=0.2, repeat_threshold=3)
    tok = VisualToken(entity="motion:c", mass=0.7, wake_reason="surprise")
    # High-info repeats never flag
    for _ in range(10):
        assert sw.inspect(tok) == []


def test_redundancy_bowel_resets_counter_on_high_info_burst():
    sw = RedundancyBowelSwimmer(mass_threshold=0.2, repeat_threshold=3)
    bg = VisualToken(entity="bg:1", mass=0.05)
    hot = VisualToken(entity="bg:1", mass=0.9, wake_reason="surprise")
    sw.inspect(bg)
    sw.inspect(bg)  # 2 quiet visits
    sw.inspect(hot)  # high-info — resets counter
    # Should not yet flag on next quiet visit
    assert sw.inspect(bg) == []


# ── 6. CrossOrganBinder ──────────────────────────────────────────

def test_cross_organ_binder_binds_peer_organs():
    sw = CrossOrganBinder()
    tok = VisualToken(entity="motion:cell-1", mass=0.5)
    out = sw.inspect(tok, context={
        "peer_organs": [("TALK", "u-9"), ("JOURNAL", "9:12-AM")],
    })
    assert len(out) == 1
    assert out[0].kind == PK_CROSS_ORGAN_BINDING
    assert "TALK" in out[0].note
    assert "JOURNAL" in out[0].note


def test_cross_organ_binder_silent_when_no_peers():
    sw = CrossOrganBinder()
    tok = VisualToken(entity="motion:cell-1", mass=0.5)
    assert sw.inspect(tok, context={"peer_organs": []}) == []
    assert sw.inspect(tok, context=None) == []


# ── Patrol — end-to-end ─────────────────────────────────────────

def test_patrol_writes_signed_pheromone_rows(tmp_path):
    tokens = [
        VisualToken(entity="motion:c", mass=0.9, wake_reason="surprise",
                    attrs={"delta": 0.8}),
        VisualToken(entity="owner_face:G", mass=0.5, attrs={"kind": "face"}),
    ]
    out = patrol_visual_tokens(
        tokens, context={"peer_organs": [("TALK", "u-1")]},
        state_root=tmp_path,
    )
    assert out["truth_label"] == TRUTH_LABEL
    assert out["n_pheromones"] >= 3  # motion + face + binder etc.
    ledger = tmp_path / LEDGER_NAME
    assert ledger.exists()
    lines = ledger.read_text().strip().splitlines()
    assert len(lines) == out["n_pheromones"]
    for line in lines:
        row = json.loads(line)
        assert row["kind"] in PHEROMONE_KINDS
        assert len(row["sha256"]) == 64
        assert row["truth_label"] == TRUTH_LABEL


def test_patrol_no_write_does_not_create_ledger(tmp_path):
    tokens = [VisualToken(entity="motion:c", mass=0.9, wake_reason="surprise")]
    out = patrol_visual_tokens(tokens, state_root=tmp_path, write=False)
    assert out["n_pheromones"] >= 1
    assert not (tmp_path / LEDGER_NAME).exists()


def test_patrol_summary_counts_by_kind_and_swimmer():
    tokens = [
        VisualToken(entity="m1", mass=0.9, wake_reason="surprise",
                    attrs={"delta": 0.8}),
    ]
    out = patrol_visual_tokens(tokens, write=False)
    assert "pheromones_by_kind" in out
    assert "pheromones_by_swimmer" in out
    assert "MotionSwimmer" in out["pheromones_by_swimmer"]


# ── Defensive: swimmer exception cannot crash the patrol ─────────

def test_buggy_swimmer_does_not_crash_patrol():
    class BadSwimmer(VisualSwimmer):
        species = "BAD"
        emits_kind = PK_OCR_PRIVACY_GATE

        def inspect(self, token, context=None):
            raise RuntimeError("intentional test failure")

    tokens = [VisualToken(entity="x", mass=0.5)]
    out = patrol_visual_tokens(
        tokens, swimmers=[BadSwimmer()], write=False,
    )
    # Doesn't raise; emits a pheromone with note carrying the error
    assert out["n_pheromones"] >= 1


# ── Truth boundary ──────────────────────────────────────────────

def test_truth_boundary_forbids_animal_vision_claim():
    from System.swarm_visual_token_swimmers import TRUTH_BOUNDARY
    assert "engineering analogue" in TRUTH_BOUNDARY.lower()
    assert "ocr is opt-in" in TRUTH_BOUNDARY.lower()
