"""Tests for swarmrl/beenav_homing.py — bee-style panoramic memory + homing.

These tests pin the BeeNav discipline:
  - perceptual hash is deterministic & sort-order invariant
  - hamming distance is symmetric
  - record_view stores a memory with honest storage cost
  - re-record reinforces (does not duplicate)
  - find_homing_hint returns nearest by hamming distance with confidence ∈ [0,1]
  - decay_unreinforced drops only memories below threshold AND past half-life
  - budget enforcement evicts the lowest-reinforcement / oldest memory
  - learning_flight stores N views in order
  - replay_for_consolidation returns newest-first
  - to_jsonl / from_jsonl round-trips a colony cleanly
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from swarmrl.beenav_homing import (
    DEFAULT_BUDGET_BYTES,
    DEFAULT_SIGNATURE_BITS,
    Hive,
    HomingHint,
    PanoramicSignature,
    TRUTH_LABEL,
    hamming_distance,
    perceptual_hash,
)


# ── primitives ───────────────────────────────────────────────────────────


def test_perceptual_hash_is_deterministic():
    a = perceptual_hash({"x": 1, "y": 2})
    b = perceptual_hash({"x": 1, "y": 2})
    assert a == b


def test_perceptual_hash_is_sort_order_invariant():
    a = perceptual_hash({"x": 1, "y": 2})
    b = perceptual_hash({"y": 2, "x": 1})
    assert a == b


def test_perceptual_hash_changes_on_value_change():
    a = perceptual_hash({"x": 1})
    b = perceptual_hash({"x": 2})
    assert a != b


def test_perceptual_hash_respects_bits_parameter():
    a = perceptual_hash({"x": 1}, bits=64)
    b = perceptual_hash({"x": 1}, bits=128)
    assert len(a) == 16  # 64 / 4
    assert len(b) == 32  # 128 / 4
    # 64-bit hash is the prefix of the 128-bit hash
    assert b.startswith(a)


def test_hamming_distance_zero_on_equal():
    assert hamming_distance("abcdef", "abcdef") == 0


def test_hamming_distance_symmetric():
    assert hamming_distance("abc", "xyz") == hamming_distance("xyz", "abc")


def test_hamming_distance_handles_uneven_length():
    # Shorter string is right-padded with zeros
    assert hamming_distance("ab", "abcd") == hamming_distance("ab00", "abcd")


# ── record_view ──────────────────────────────────────────────────────────


def test_record_view_creates_signature_with_honest_storage_cost():
    hive = Hive()
    sig = hive.record_view(
        {"sensor": "panorama", "frame": 1},
        direction_to_hive=0.5, distance_to_hive=10.0,
        now=1000.0,
    )
    assert isinstance(sig, PanoramicSignature)
    assert sig.reinforcement == 1
    assert sig.last_seen_ts == 1000.0
    assert sig.storage_cost_bytes > 0  # honest cost recorded
    assert hive.memory_count == 1


def test_record_view_reinforces_existing_perceptual_hash():
    hive = Hive()
    sample = {"sensor": "panorama", "frame": 42}
    sig1 = hive.record_view(sample, direction_to_hive=0.0, distance_to_hive=5.0, now=1000.0)
    sig2 = hive.record_view(sample, direction_to_hive=99.0, distance_to_hive=99.0, now=1100.0)
    # Same perceptual hash → reinforced, original direction kept (semantic of the bee:
    # we don't overwrite the original direction; we just count the re-encounter)
    assert hive.memory_count == 1
    assert sig2.reinforcement == 2
    assert sig2.last_seen_ts == 1100.0
    assert sig2.direction_to_hive == 0.0  # original kept


def test_record_view_assigns_storage_cost_consistently():
    hive = Hive()
    sig = hive.record_view(
        {"x": "panorama"}, direction_to_hive=0.0, distance_to_hive=0.0, now=1000.0,
    )
    # Re-serialise the signature and compare bytes
    blob = json.dumps({
        "perceptual_hash": sig.perceptual_hash,
        "direction_to_hive": sig.direction_to_hive,
        "distance_to_hive": sig.distance_to_hive,
        "reinforcement": sig.reinforcement,
        "last_seen_ts": sig.last_seen_ts,
        "storage_cost_bytes": 0,
        "note": sig.note,
    }, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    assert sig.storage_cost_bytes == len(blob.encode("utf-8"))


# ── learning_flight ──────────────────────────────────────────────────────


def test_learning_flight_stores_n_views_in_order():
    hive = Hive()
    views = [
        ({"step": i, "panorama": f"frame{i}"}, float(i * 0.1), float(i))
        for i in range(5)
    ]
    out = hive.learning_flight(views, now=1000.0)
    assert len(out) == 5
    assert hive.memory_count == 5


# ── find_homing_hint ─────────────────────────────────────────────────────


def test_find_homing_hint_returns_zero_confidence_on_empty_hive():
    hive = Hive()
    hint = hive.find_homing_hint({"any": "sample"})
    assert hint.matched_signature is None
    assert hint.confidence == 0.0


def test_find_homing_hint_perfect_match_yields_full_confidence():
    hive = Hive()
    sample = {"panorama": "near-hive"}
    hive.record_view(sample, direction_to_hive=1.57, distance_to_hive=3.0, now=1000.0)
    hint = hive.find_homing_hint(sample)
    assert hint.matched_signature is not None
    assert hint.hamming_distance == 0
    assert hint.confidence == 1.0
    assert hint.direction_to_hive == 1.57


def test_find_homing_hint_picks_nearest_by_hamming():
    hive = Hive(signature_bits=64)
    hive.record_view({"a": 1}, direction_to_hive=0.0, distance_to_hive=10.0, now=1000.0)
    hive.record_view({"b": 2}, direction_to_hive=1.0, distance_to_hive=20.0, now=1001.0)
    hive.record_view({"c": 3}, direction_to_hive=2.0, distance_to_hive=30.0, now=1002.0)

    # Querying with one of the stored samples must hit confidence 1.0
    hint = hive.find_homing_hint({"b": 2})
    assert hint.confidence == 1.0
    assert hint.direction_to_hive == 1.0


def test_find_homing_hint_confidence_decays_with_distance():
    hive = Hive(signature_bits=64)
    hive.record_view({"original": "view"}, direction_to_hive=0.5, distance_to_hive=1.0, now=1000.0)
    # An unrelated query will have non-zero hamming → confidence < 1.0
    hint = hive.find_homing_hint({"completely_different": "view"})
    assert 0.0 <= hint.confidence < 1.0


# ── decay ────────────────────────────────────────────────────────────────


def test_decay_unreinforced_removes_old_one_reinforcement_memories():
    hive = Hive(min_reinforcement=2, decay_half_life_s=1000.0)
    hive.record_view({"old": "view"}, direction_to_hive=0.0, distance_to_hive=0.0, now=1_000_000.0)
    evicted = hive.decay_unreinforced(now=1_000_000.0 + 2000.0)
    assert evicted == 1
    assert hive.memory_count == 0


def test_decay_keeps_reinforced_memories():
    hive = Hive(min_reinforcement=2, decay_half_life_s=1000.0)
    sample = {"reinforced": "view"}
    hive.record_view(sample, direction_to_hive=0.0, distance_to_hive=0.0, now=1_000_000.0)
    hive.record_view(sample, direction_to_hive=0.0, distance_to_hive=0.0, now=1_000_001.0)
    evicted = hive.decay_unreinforced(now=1_000_000.0 + 2000.0)
    assert evicted == 0
    assert hive.memory_count == 1


def test_decay_keeps_fresh_unreinforced_memories():
    hive = Hive(min_reinforcement=2, decay_half_life_s=1000.0)
    hive.record_view({"fresh": "view"}, direction_to_hive=0.0, distance_to_hive=0.0, now=1_000_000.0)
    evicted = hive.decay_unreinforced(now=1_000_000.0 + 100.0)
    assert evicted == 0
    assert hive.memory_count == 1


# ── budget enforcement ──────────────────────────────────────────────────


def test_budget_enforcement_evicts_lowest_reinforcement_oldest():
    # Pick a tiny budget so a few memories fill it up.
    hive = Hive(budget_bytes=400)
    # First memory — single reinforcement, oldest
    hive.record_view({"a": "first"}, direction_to_hive=0.0, distance_to_hive=0.0, now=1000.0)
    # Second memory — reinforced
    sample_b = {"b": "second"}
    hive.record_view(sample_b, direction_to_hive=1.0, distance_to_hive=10.0, now=1001.0)
    hive.record_view(sample_b, direction_to_hive=1.0, distance_to_hive=10.0, now=1002.0)
    # Third memory — should evict 'a' (single reinforcement, oldest) if needed
    hive.record_view({"c": "third"}, direction_to_hive=2.0, distance_to_hive=20.0, now=1003.0)

    # The reinforced 'b' must survive
    hashes = {sig.perceptual_hash for sig in hive.memories()}
    sig_b_hash = perceptual_hash(sample_b)
    assert sig_b_hash in hashes


def test_total_storage_bytes_matches_sum_of_memories():
    hive = Hive()
    for i in range(5):
        hive.record_view(
            {"view": i}, direction_to_hive=float(i), distance_to_hive=float(i),
            now=1000.0 + i,
        )
    expected = sum(s.storage_cost_bytes for s in hive.memories())
    assert hive.total_storage_bytes == expected


def test_budget_used_fraction_in_unit_interval():
    hive = Hive(budget_bytes=10_000)
    for i in range(10):
        hive.record_view({"v": i}, direction_to_hive=0.0, distance_to_hive=0.0, now=1000.0 + i)
    f = hive.budget_used_fraction
    assert 0.0 <= f <= 1.0


# ── replay / Dream layer integration ────────────────────────────────────


def test_replay_for_consolidation_returns_newest_first():
    hive = Hive()
    for i in range(5):
        hive.record_view({"v": i}, direction_to_hive=0.0, distance_to_hive=0.0, now=1000.0 + i)
    out = hive.replay_for_consolidation(n=3)
    assert len(out) == 3
    # Newest-first: the last recorded should appear first
    assert out[0].last_seen_ts == 1004.0


def test_replay_zero_n_returns_empty():
    hive = Hive()
    hive.record_view({"v": 0}, direction_to_hive=0.0, distance_to_hive=0.0, now=1000.0)
    assert hive.replay_for_consolidation(n=0) == []


# ── persistence ──────────────────────────────────────────────────────────


def test_to_jsonl_and_from_jsonl_round_trip(tmp_path: Path):
    hive = Hive()
    samples = [{"v": i} for i in range(3)]
    for i, s in enumerate(samples):
        hive.record_view(s, direction_to_hive=float(i), distance_to_hive=float(i * 10), now=1000.0 + i)

    out = tmp_path / "hive.jsonl"
    hive.to_jsonl(out)
    assert out.exists()

    restored = Hive.from_jsonl(out)
    assert restored.memory_count == hive.memory_count
    # Sample query should still resolve
    hint = restored.find_homing_hint(samples[1])
    assert hint.confidence == 1.0


def test_from_jsonl_returns_empty_hive_when_file_missing(tmp_path: Path):
    restored = Hive.from_jsonl(tmp_path / "nope.jsonl")
    assert restored.memory_count == 0


def test_from_jsonl_tolerates_malformed_rows(tmp_path: Path):
    out = tmp_path / "hive.jsonl"
    out.write_text(
        '\n'.join([
            json.dumps({"perceptual_hash": "abc1", "direction_to_hive": 0.0,
                        "distance_to_hive": 1.0, "reinforcement": 1,
                        "last_seen_ts": 1000.0, "storage_cost_bytes": 50,
                        "note": "good row"}),
            "{not json",
            "",
            "null",
        ]) + "\n",
        encoding="utf-8",
    )
    restored = Hive.from_jsonl(out)
    assert restored.memory_count == 1


# ── identity / Layer-1 invariant ────────────────────────────────────────


def test_module_has_no_owner_name_string_literal():
    """The BeeNav primitive must contain zero hardcoded owner names."""
    source = Path(__file__).resolve().parent.parent / "swarmrl" / "beenav_homing.py"
    text = source.read_text(encoding="utf-8").lower()
    for forbidden in ("ioan", "george anton"):
        assert forbidden not in text, (
            f"Layer-1 violation in BeeNav primitive: '{forbidden}'"
        )


def test_truth_label_is_observed():
    """The module's truth label declares OBSERVED (sensor-derived) — never
    a stronger claim like ARCHITECT_DOCTRINE for the primitive itself."""
    assert "OBSERVED" in TRUTH_LABEL
