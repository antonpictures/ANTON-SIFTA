"""Tests for System/swarm_truth_label_canon.py — covenant-canonical
truth-label registry with peer-alias normalisation.

The registry must:
  - Pass every covenant-canonical label through unchanged (§7.10.1+§7.11)
  - Map Grok's INFERRED/IMAGINED/UNVERIFIED to HYPOTHESIS
  - Default unknown values to HYPOTHESIS (safe-pending)
  - Read owner_name from owner_genesis at runtime — never hardcoded
  - Detect explicit doctrine markers (§7.13 / ARCHITECT_DOCTRINE / etc)
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from System import swarm_truth_label_canon as canon


# ── canonical pass-through ───────────────────────────────────────────────


@pytest.mark.parametrize("label", canon.CANONICAL_LABELS)
def test_canonical_labels_pass_through(label):
    assert canon.normalise_label(label) == label


def test_canonical_labels_are_case_insensitive():
    assert canon.normalise_label("observed") == "OBSERVED"
    assert canon.normalise_label("operational") == "OPERATIONAL"
    assert canon.normalise_label("hypothesis") == "HYPOTHESIS"
    assert canon.normalise_label("architect_doctrine") == "ARCHITECT_DOCTRINE"
    assert canon.normalise_label("forbidden") == "FORBIDDEN"


def test_canonical_labels_handle_whitespace_and_hyphens():
    assert canon.normalise_label("  Architect-Doctrine  ") == "ARCHITECT_DOCTRINE"


def test_canonical_set_matches_canonical_labels_tuple():
    assert canon.CANONICAL_SET == frozenset(canon.CANONICAL_LABELS)


# ── peer aliases → canonical ─────────────────────────────────────────────


def test_grok_inferred_maps_to_hypothesis():
    assert canon.normalise_label("INFERRED") == "HYPOTHESIS"


def test_grok_imagined_maps_to_hypothesis():
    assert canon.normalise_label("IMAGINED") == "HYPOTHESIS"


def test_grok_unverified_maps_to_hypothesis():
    assert canon.normalise_label("UNVERIFIED") == "HYPOTHESIS"


@pytest.mark.parametrize("alias,canonical", [
    ("OBSERVED_FACT", "OBSERVED"),
    ("PROBED", "OBSERVED"),
    ("RECEIPTED", "OBSERVED"),
    ("WORKING", "OPERATIONAL"),
    ("PROPOSED", "HYPOTHESIS"),
    ("PREDICTED", "HYPOTHESIS"),
    ("DREAMED", "HYPOTHESIS"),
    ("DOCTRINE", "ARCHITECT_DOCTRINE"),
    ("FORGED", "FORBIDDEN"),
    ("HALLUCINATED", "FORBIDDEN"),
])
def test_known_aliases_route_to_canonical(alias, canonical):
    assert canon.normalise_label(alias) == canonical


def test_unknown_value_falls_back_to_default():
    assert canon.normalise_label("MADE_UP_LABEL_NOT_IN_REGISTRY") == canon.DEFAULT_LABEL
    assert canon.DEFAULT_LABEL == "HYPOTHESIS"


def test_empty_value_falls_back_to_default():
    assert canon.normalise_label("") == canon.DEFAULT_LABEL
    assert canon.normalise_label(None) == canon.DEFAULT_LABEL


# ── label_kind instrumentation ───────────────────────────────────────────


def test_label_kind_marks_aliases_correctly():
    out = canon.label_kind("INFERRED")
    assert out["raw"] == "INFERRED"
    assert out["canonical"] == "HYPOTHESIS"
    assert out["was_alias"] is True


def test_label_kind_canonical_input_is_not_alias():
    out = canon.label_kind("OBSERVED")
    assert out["canonical"] == "OBSERVED"
    assert out["was_alias"] is False


def test_label_kind_unknown_input_is_not_alias():
    out = canon.label_kind("WHATEVER")
    assert out["canonical"] == "HYPOTHESIS"
    # Unknown → fall through to default, not via alias map
    assert out["was_alias"] is False


# ── list_aliases_for ─────────────────────────────────────────────────────


def test_list_aliases_for_hypothesis_includes_grok_three():
    aliases = canon.list_aliases_for("HYPOTHESIS")
    assert "INFERRED" in aliases
    assert "IMAGINED" in aliases
    assert "UNVERIFIED" in aliases


def test_list_aliases_for_non_canonical_returns_empty():
    assert canon.list_aliases_for("NONSENSE") == ()


# ── is_architect_doctrine (the Layer-1-safe check) ───────────────────────


def _write_genesis(tmp_path: Path, owner_name: str = "test_owner_name") -> Path:
    p = tmp_path / "owner_genesis.json"
    p.write_text(json.dumps({
        "owner_name": owner_name,
        "silicon": "TESTSILICON",
    }), encoding="utf-8")
    return p


def test_doctrine_detected_via_explicit_marker(tmp_path: Path):
    item = {"kind": "ARCHITECT_DOCTRINE", "text": "the law says X"}
    assert canon.is_architect_doctrine(item, genesis_path=tmp_path / "missing.json")


def test_doctrine_detected_via_section_reference(tmp_path: Path):
    item = {"note": "see §7.13 for the deferred care receipt boundary"}
    assert canon.is_architect_doctrine(item, genesis_path=tmp_path / "missing.json")


def test_doctrine_detected_via_owner_name_from_genesis(tmp_path: Path):
    genesis_path = _write_genesis(tmp_path, owner_name="alice_owner_runtime")
    item = {"speaker": "alice_owner_runtime said: ship it"}
    assert canon.is_architect_doctrine(item, genesis_path=genesis_path)


def test_doctrine_not_detected_without_markers_and_unknown_owner(tmp_path: Path):
    genesis_path = _write_genesis(tmp_path, owner_name="some_runtime_name_xyz")
    item = {"kind": "OBSERVED", "text": "the sensor produced a value"}
    assert not canon.is_architect_doctrine(item, genesis_path=genesis_path)


def test_doctrine_handles_missing_genesis_file(tmp_path: Path):
    # No owner_genesis.json on disk — should not crash, should still find
    # explicit doctrine markers.
    item = {"note": "ARCHITECT_DOCTRINE label applied"}
    assert canon.is_architect_doctrine(item, genesis_path=tmp_path / "nope.json")


# ── Layer-1 invariant: no hardcoded owner name in canon module ───────────


def test_canon_module_has_no_owner_name_string_literal():
    """The canon module must never hardcode a specific owner name —
    that defeats the entire point of the registry it provides.
    """
    source = Path(__file__).resolve().parent.parent / "System" / "swarm_truth_label_canon.py"
    text = source.read_text(encoding="utf-8").lower()
    # The module may mention "owner_name" as a key — but not a specific
    # human name like "ioan" or "george anton".
    for forbidden in ("ioan", "george anton"):
        assert forbidden not in text, (
            f"Layer-1 violation in canon module: literal '{forbidden}'"
        )
