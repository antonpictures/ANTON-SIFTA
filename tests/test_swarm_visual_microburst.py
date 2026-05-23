"""Tests for the visual micro-burst rule (Vision Tournament P1).

Covers all 8 acceptance criteria from §7 of
SIFTA_Vision_Optimization_Tournament.docx where applicable to this
module:
  3. "exactly one bounded micro-burst, not an infinite loop" — cooldown
  4. "raw burst frames discarded by default" — persist_raw=False
  5. "OCR remains opt-in" — ocr_allowed=False unless explicitly set
  6. "fallback metronome fires when delta path fails"
  7. "STGM/thermal budget records cost"
"""
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_visual_microburst import (
    DEFAULT_COOLDOWN_MS,
    DEFAULT_MASS_THRESHOLD,
    HIGH_MASS_ENTITY_PREFIXES,
    LEDGER_NAME,
    SURPRISE_REASONS,
    TRUTH_LABEL,
    BurstScheduler,
    MicroBurstPolicy,
    VisualBurstRequest,
    VisualToken,
    evaluate_token,
    write_burst_receipt,
)


# ── Decision logic ──────────────────────────────────────────────

def test_truth_label_is_v1():
    assert TRUTH_LABEL == "MICRO_BURST_V1"


def test_mass_above_threshold_fires_mass():
    sched = BurstScheduler()
    tok = VisualToken(entity="motion:1", mass=0.9, wake_reason="static")
    fire, reason = sched.should_burst(tok, now=1000.0)
    assert fire is True
    assert reason == "mass"


def test_mass_below_threshold_does_not_fire():
    sched = BurstScheduler()
    tok = VisualToken(entity="motion:1", mass=0.2, wake_reason="static")
    fire, reason = sched.should_burst(tok, now=1000.0)
    assert fire is False
    assert reason == "below_threshold"


def test_surprise_wake_reason_fires_even_at_low_mass():
    sched = BurstScheduler()
    tok = VisualToken(entity="motion:1", mass=0.1, wake_reason="surprise")
    fire, reason = sched.should_burst(tok, now=1000.0)
    assert fire is True
    assert reason == "surprise"


def test_high_mass_entity_prefix_fires_at_low_mass():
    sched = BurstScheduler()
    tok = VisualToken(entity="owner_face:Ioan", mass=0.1, wake_reason="static")
    fire, reason = sched.should_burst(tok, now=1000.0)
    assert fire is True
    assert reason == "high_mass_entity"


def test_empty_entity_does_not_fire():
    sched = BurstScheduler()
    tok = VisualToken(entity="", mass=0.99, wake_reason="surprise")
    fire, reason = sched.should_burst(tok, now=1000.0)
    assert fire is False
    assert reason == "empty_entity"


def test_surprise_reasons_taxonomy_includes_canonical_set():
    """The four surprise reasons must all be recognized."""
    for r in ("surprise", "high_delta", "novel_face", "wake_owner"):
        assert r in SURPRISE_REASONS


def test_high_mass_entity_prefixes_present():
    for p in ("owner_face:", "architect:", "named_person:"):
        assert p in HIGH_MASS_ENTITY_PREFIXES


# ── Cooldown — §7 acceptance test 3 ─────────────────────────────

def test_cooldown_prevents_infinite_loop_on_same_entity():
    """The same hot token must not infinite-loop the burst rule."""
    sched = BurstScheduler(MicroBurstPolicy(cooldown_ms=500))
    tok = VisualToken(entity="motion:hot", mass=0.95, wake_reason="surprise")
    # First fire
    fire1, reason1 = sched.should_burst(tok, now=1000.0)
    assert fire1 is True
    sched.mark_fired(tok.entity, now=1000.0)
    # Immediate re-check → suppressed by cooldown
    fire2, reason2 = sched.should_burst(tok, now=1000.1)
    assert fire2 is False
    assert reason2 == "cooldown_suppressed"
    # After cooldown elapsed → can fire again
    fire3, reason3 = sched.should_burst(tok, now=1001.0)
    assert fire3 is True


def test_cooldown_is_per_entity():
    """Two different entities can fire in the same tick."""
    sched = BurstScheduler(MicroBurstPolicy(cooldown_ms=10_000))
    tok_a = VisualToken(entity="motion:a", mass=0.95)
    tok_b = VisualToken(entity="motion:b", mass=0.95)
    fa, _ = sched.should_burst(tok_a, now=1000.0)
    sched.mark_fired(tok_a.entity, now=1000.0)
    fb, _ = sched.should_burst(tok_b, now=1000.0)
    assert fa is True and fb is True


def test_evaluate_token_does_not_double_fire(tmp_path):
    """End-to-end: feeding the same hot token twice in a row writes
    exactly ONE receipt and yields exactly one fired=True."""
    sched = BurstScheduler(MicroBurstPolicy(cooldown_ms=500))
    tok = VisualToken(entity="motion:hot", mass=0.9, wake_reason="surprise")
    r1 = evaluate_token(sched, tok, now=1000.0, state_root=tmp_path)
    r2 = evaluate_token(sched, tok, now=1000.05, state_root=tmp_path)
    assert r1["fired"] is True
    assert r2["fired"] is False
    assert r2["reason"] == "cooldown_suppressed"
    ledger = tmp_path / LEDGER_NAME
    # Only one receipt row
    assert ledger.exists()
    lines = ledger.read_text().strip().splitlines()
    assert len(lines) == 1


# ── Privacy — §7 acceptance tests 4 and 5 ───────────────────────

def test_default_request_does_not_persist_raw_frames():
    """§7 acceptance: raw burst frames discarded by default."""
    sched = BurstScheduler()
    tok = VisualToken(entity="motion:1", mass=0.9)
    req = sched.make_request(tok, "mass")
    assert req.persist_raw is False
    assert req.persist_tokens is True


def test_default_request_does_not_allow_ocr():
    """§7 acceptance: OCR is opt-in. mass / surprise alone never OCRs."""
    sched = BurstScheduler()
    tok = VisualToken(entity="text:url-bar", mass=0.95, wake_reason="surprise")
    req = sched.make_request(tok, "surprise")
    assert req.ocr_allowed is False


def test_explicit_opt_in_can_enable_raw_persist():
    """The mechanism exists but requires an explicit caller flag."""
    sched = BurstScheduler()
    tok = VisualToken(entity="owner_face:Ioan", mass=0.9)
    req = sched.make_request(tok, "high_mass_entity", persist_raw=True)
    assert req.persist_raw is True


def test_explicit_opt_in_can_enable_ocr():
    """OCR can only be on if the caller explicitly sets ocr_allowed=True."""
    sched = BurstScheduler()
    tok = VisualToken(entity="text:url-bar", mass=0.95)
    req = sched.make_request(tok, "mass", ocr_allowed=True)
    assert req.ocr_allowed is True


# ── Frame bounds — §5 spec: 3..5 ────────────────────────────────

def test_frames_clamped_to_min_max():
    sched = BurstScheduler(MicroBurstPolicy(min_frames=3, max_frames=5))
    tok = VisualToken(entity="x", mass=0.9)
    # Too low → clamped up
    r_low = sched.make_request(tok, "mass", frames=1)
    assert r_low.frames == 3
    # Too high → clamped down
    r_high = sched.make_request(tok, "mass", frames=20)
    assert r_high.frames == 5


def test_burst_duration_bounded():
    """A request's max_duration_ms must come from policy, not unbounded."""
    sched = BurstScheduler(MicroBurstPolicy(burst_max_duration_ms=400))
    tok = VisualToken(entity="x", mass=0.9)
    req = sched.make_request(tok, "mass")
    assert req.max_duration_ms == 400


# ── Fallback metronome — §7 acceptance test 6 ───────────────────

def test_fallback_metronome_fires_when_delta_path_dead():
    sched = BurstScheduler(MicroBurstPolicy(fallback_metronome_ms=800))
    # last frame was 1s ago → should fire
    assert sched.fallback_metronome_should_fire(now=10.0, last_frame_ts=9.0) is True
    # last frame 200ms ago → should NOT fire
    assert sched.fallback_metronome_should_fire(now=10.0, last_frame_ts=9.8) is False


# ── STGM / thermal cost recorded — §7 acceptance test 7 ─────────

def test_request_carries_stgm_and_thermal_cost():
    sched = BurstScheduler()
    tok = VisualToken(entity="x", mass=0.9)
    req = sched.make_request(tok, "mass", frames=5)
    assert req.stgm_cost_estimate > 0
    assert req.thermal_cost_estimate > 0
    # 5 frames should cost more than 3 frames
    req_small = sched.make_request(tok, "mass", frames=3)
    assert req.stgm_cost_estimate > req_small.stgm_cost_estimate


# ── Receipts ────────────────────────────────────────────────────

def test_receipt_is_sha256_signed(tmp_path):
    sched = BurstScheduler()
    tok = VisualToken(entity="motion:1", mass=0.9, wake_reason="surprise")
    req = sched.make_request(tok, "mass")
    row = write_burst_receipt(req, state_root=tmp_path)
    ledger = tmp_path / LEDGER_NAME
    assert ledger.exists()
    line = ledger.read_text().strip().splitlines()[-1]
    parsed = json.loads(line)
    assert parsed["truth_label"] == TRUTH_LABEL
    assert parsed["kind"] == "MICRO_BURST"
    assert len(parsed["sha256"]) == 64


def test_receipt_records_outcome_label(tmp_path):
    sched = BurstScheduler()
    tok = VisualToken(entity="motion:1", mass=0.9)
    req = sched.make_request(tok, "mass")
    row = write_burst_receipt(req, outcome="fired", state_root=tmp_path)
    parsed = json.loads(
        (tmp_path / LEDGER_NAME).read_text().strip().splitlines()[-1]
    )
    assert parsed["payload"]["outcome"] == "fired"


# ── Truth boundary discipline ───────────────────────────────────

def test_truth_boundary_forbids_animal_vision_claim():
    from System.swarm_visual_microburst import TRUTH_BOUNDARY
    assert "engineering analogue" in TRUTH_BOUNDARY.lower()
    assert ("NOT an animal-vision claim" in TRUTH_BOUNDARY
            or "animal-vision" in TRUTH_BOUNDARY.lower())


# ── Env config ──────────────────────────────────────────────────

def test_policy_from_env_picks_up_overrides(monkeypatch):
    monkeypatch.setenv("SIFTA_VISION_BURST_MASS_THRESHOLD", "0.42")
    monkeypatch.setenv("SIFTA_VISION_BURST_MAX_FRAMES", "7")
    pol = MicroBurstPolicy.from_env()
    assert pol.mass_threshold == 0.42
    assert pol.max_frames == 7
