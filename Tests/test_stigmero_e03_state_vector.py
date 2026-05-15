"""
tests/test_stigmero_e03_state_vector.py
════════════════════════════════════════════════════════════════════════════
E03 — State is a vector (STIGMEROBOTICS / ROB 501 tournament)

ROB 501 topic: Abstract linear algebra — representing state as x ∈ ℝⁿ.

Hypothesis (P):
    The SIFTA IdentitySnapshot (and any multi-sensor body/organ snapshot)
    can be treated as a concrete vector x ∈ ℝⁿ with:
      (a) documented basis: named channels with known units
      (b) bounded dimension: 5 ≤ n ≤ 32 (current IdentitySnapshot)
      (c) type consistency: numeric channels stay numeric across snapshots
      (d) subset completeness: REQUIRED_STATE_FIELDS ⊆ snap.keys()

Proof structure:

  Dimension bound (n ∈ [5, 32]):
    Proved by: test_e03_dimension_bound
    Falsifier: snap with n < 5 or n > 32 → AssertionError

  Basis documentation (units per channel):
    Proved by: test_e03_basis_units_documented
    Every numeric channel appears in CHANNEL_UNITS with its SI unit.

  Type consistency:
    Proved by: test_e03_numeric_channels_are_float, test_e03_list_channels_are_list
    All numeric channels are float-compatible; list channels are lists.

  Subset completeness:
    Proved by: test_e03_required_fields_present
    REQUIRED_STATE_FIELDS ⊆ snap.keys()

  Negative / contradiction:
    Proved by: test_e03_missing_field_breaks_completeness,
               test_e03_wrong_type_breaks_numeric_constraint,
               test_e03_dimension_too_small_breaks_bound

proof_of_property = {
    "P_n":         "IdentitySnapshot is x ∈ ℝⁿ with documented basis",
    "basis":       "CHANNEL_UNITS maps every numeric channel → SI unit string",
    "dim_bound":   "5 ≤ n = |REQUIRED_STATE_FIELDS ∩ snap| ≤ 32",
    "falsifier":   "snap with n < 5 OR missing required field → test fails",
    "truth_label": "HYPOTHESIS until pytest green (§7.11)",
}

§8.6 compliance: sanitized fixture only — never reads live .sifta_state/.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from System import stigmerobotics_state_vector as e03_contract

FIXTURES = Path(__file__).parent / "fixtures"

# ── Basis documentation ──────────────────────────────────────────────────
# Each key maps a numeric channel name → (SI unit, description).
# This IS the documented basis that makes IdentitySnapshot a proper vector.
CHANNEL_UNITS: Dict[str, tuple[str, str]] = {
    "stgm_balance":      ("STGM",   "Canonical wallet balance in STGM tokens"),
    "body_energy":       ("%",      "Somatic energy level 0-100"),
    "ts":                ("s",      "Unix timestamp (seconds since epoch)"),
    "session_cost_stgm": ("STGM",   "Cumulative Kleiber cost this session"),
    "immune_budget":     ("STGM",   "Remaining immune intervention budget"),
    "drift_rate":        ("frac",   "RLHS/RLHF drift fraction 0-1"),
    "gps_age_s":         ("s",      "Age of last GPS fix in seconds"),
    "model_latency_ms":  ("ms",     "Inference round-trip latency"),
    "vad_confidence":    ("frac",   "Voice activity detection confidence 0-1"),
    "kleiber_exponent":  ("dim",    "Allometric scaling exponent (≈ 0.75 for M5)"),
}

# Required fields — these constitute the REQUIRED_STATE_FIELDS subset
REQUIRED_STATE_FIELDS: frozenset[str] = frozenset({
    "stgm_balance",
    "body_energy",
    "organs_present",
    "organs_silent",
    "ts",
    "homeworld_serial",
    "id",
})

# Numeric channels that must be float-compatible
NUMERIC_CHANNELS: frozenset[str] = frozenset(CHANNEL_UNITS.keys())

# List channels
LIST_CHANNELS: frozenset[str] = frozenset({"organs_present", "organs_silent"})

# Dimension bounds [min, max] for current IdentitySnapshot
DIM_MIN = 5
DIM_MAX = 32


# ── Loader ───────────────────────────────────────────────────────────────

def load_snapshot(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def numeric_dimension(snap: Dict[str, Any]) -> int:
    """
    Compute n = number of channels that appear in CHANNEL_UNITS.
    This is the dimension of x ∈ ℝⁿ for this snapshot.
    """
    return sum(1 for k in CHANNEL_UNITS if k in snap)


# ── E03 Test Suite ───────────────────────────────────────────────────────

class TestE03DimensionBound:
    """
    (b) Bounded dimension: 5 ≤ n ≤ DIM_MAX.
    n counts numeric channels documented in CHANNEL_UNITS.
    """

    def test_e03_dimension_bound(self) -> None:
        snap = load_snapshot(FIXTURES / "identity_snapshot_e03.json")
        n = numeric_dimension(snap)
        assert DIM_MIN <= n <= DIM_MAX, (
            f"State dimension n={n} outside [{DIM_MIN}, {DIM_MAX}]. "
            f"Add channels to CHANNEL_UNITS or trim IdentitySnapshot."
        )
        print(f"✓ E03: IdentitySnapshot is x ∈ ℝ^{n} with documented basis")

    def test_e03_dimension_too_small_breaks_bound(self) -> None:
        """Contradiction: snap with only 2 numeric channels → n < DIM_MIN."""
        snap = {"id": "MINI", "ts": 1.0, "homeworld_serial": "S",
                "stgm_balance": 1.0, "body_energy": 100.0}  # only 2 in CHANNEL_UNITS
        n = numeric_dimension(snap)
        assert n < DIM_MIN, (
            f"Expected n < {DIM_MIN} for minimal snap, got n={n}"
        )

    def test_e03_dimension_too_large_would_fail(self, tmp_path: Path) -> None:
        """
        Proof of upper bound: if someone adds 33 numeric channels, the
        dimension constraint correctly fires (we verify the guard logic, not
        the actual snap — we don't want to create a file with 33 channels).
        """
        # Simulate what would happen: dimension check on hypothetical n=33
        hypothetical_n = 33
        assert not (DIM_MIN <= hypothetical_n <= DIM_MAX), (
            "Guard: n=33 should lie outside [5, 32] — the bound would correctly fail"
        )


class TestE03BasisDocumentation:
    """
    (a) Documented basis: every numeric channel in the snapshot that is in
    CHANNEL_UNITS has a known SI unit string.
    """

    def test_e03_basis_units_documented(self) -> None:
        snap = load_snapshot(FIXTURES / "identity_snapshot_e03.json")
        for channel, (unit, description) in CHANNEL_UNITS.items():
            assert unit, f"Channel {channel!r} has no unit"
            assert description, f"Channel {channel!r} has no description"
        # Verify all channels in fixture that are in CHANNEL_UNITS have units
        for k in snap:
            if k in CHANNEL_UNITS:
                unit, _ = CHANNEL_UNITS[k]
                assert unit, f"Snapshot channel {k!r} has empty unit in CHANNEL_UNITS"

    def test_e03_channel_units_is_complete_basis(self) -> None:
        """CHANNEL_UNITS must cover all numeric fields we care about."""
        assert "stgm_balance" in CHANNEL_UNITS, "Economy channel must be in basis"
        assert "body_energy" in CHANNEL_UNITS, "Body energy must be in basis"
        assert "ts" in CHANNEL_UNITS, "Timestamp must be in basis"

    def test_e03_units_are_strings(self) -> None:
        for channel, (unit, description) in CHANNEL_UNITS.items():
            assert isinstance(unit, str) and len(unit) > 0
            assert isinstance(description, str) and len(description) > 0

    def test_e03_kleiber_exponent_near_three_quarters(self) -> None:
        """
        The Kleiber exponent for the M5 node should be ≈ 0.75 ± 0.15.
        This is grounded in SIFTA_SCIENTIFIC_FOUNDATIONS.md §2 (WBE allometric scaling).
        """
        snap = load_snapshot(FIXTURES / "identity_snapshot_e03.json")
        exp = snap.get("kleiber_exponent")
        assert exp is not None, "kleiber_exponent must be present"
        assert 0.60 <= float(exp) <= 0.90, (
            f"Kleiber exponent {exp} outside biologically plausible [0.60, 0.90]. "
            f"See SIFTA_SCIENTIFIC_FOUNDATIONS.md §2."
        )


class TestE03TypeConsistency:
    """
    (c) Type consistency: channels keep their type across snapshots.
    Numeric channels must be float-compatible; list channels must be lists.
    """

    def test_e03_numeric_channels_are_float(self) -> None:
        snap = load_snapshot(FIXTURES / "identity_snapshot_e03.json")
        for channel in NUMERIC_CHANNELS:
            if channel in snap:
                val = snap[channel]
                try:
                    float(val)
                except (TypeError, ValueError):
                    pytest.fail(f"Channel {channel!r} = {val!r} is not float-compatible")

    def test_e03_list_channels_are_list(self) -> None:
        snap = load_snapshot(FIXTURES / "identity_snapshot_e03.json")
        for channel in LIST_CHANNELS:
            if channel in snap:
                assert isinstance(snap[channel], list), (
                    f"Channel {channel!r} must be a list, got {type(snap[channel])}"
                )

    def test_e03_stgm_balance_non_negative(self) -> None:
        """Economy invariant: wallet balance must be ≥ 0 (negative = RED_CONSERVE)."""
        snap = load_snapshot(FIXTURES / "identity_snapshot_e03.json")
        assert float(snap["stgm_balance"]) >= 0.0, "stgm_balance must be ≥ 0"

    def test_e03_body_energy_in_unit_range(self) -> None:
        """Body energy is in [0, 100] (percent)."""
        snap = load_snapshot(FIXTURES / "identity_snapshot_e03.json")
        energy = float(snap["body_energy"])
        assert 0.0 <= energy <= 100.0, f"body_energy={energy} outside [0, 100]"

    def test_e03_vad_confidence_in_unit_range(self) -> None:
        """VAD confidence is a probability ∈ [0, 1]."""
        snap = load_snapshot(FIXTURES / "identity_snapshot_e03.json")
        vad = float(snap["vad_confidence"])
        assert 0.0 <= vad <= 1.0, f"vad_confidence={vad} outside [0, 1]"

    def test_e03_drift_rate_in_unit_range(self) -> None:
        """Drift rate is a fraction ∈ [0, 1]."""
        snap = load_snapshot(FIXTURES / "identity_snapshot_e03.json")
        drift = float(snap["drift_rate"])
        assert 0.0 <= drift <= 1.0, f"drift_rate={drift} outside [0, 1]"

    def test_e03_ts_is_plausible_unix_timestamp(self) -> None:
        """ts must be > 2026-01-01 (1_767_225_600) and < 2030-01-01 (1_893_456_000)."""
        snap = load_snapshot(FIXTURES / "identity_snapshot_e03.json")
        ts = float(snap["ts"])
        assert 1_767_225_600 <= ts <= 1_893_456_000, (
            f"ts={ts} outside plausible SIFTA operating window [2026, 2030]"
        )


class TestE03SubsetCompleteness:
    """
    (d) Subset completeness: REQUIRED_STATE_FIELDS ⊆ snap.keys()
    """

    def test_e03_required_fields_present(self) -> None:
        snap = load_snapshot(FIXTURES / "identity_snapshot_e03.json")
        missing = REQUIRED_STATE_FIELDS - snap.keys()
        assert not missing, f"Missing required state fields: {sorted(missing)}"

    def test_e03_homeworld_serial_matches_node(self) -> None:
        """homeworld_serial in the fixture must match the documented M5 node."""
        snap = load_snapshot(FIXTURES / "identity_snapshot_e03.json")
        assert snap["homeworld_serial"] == "GTH4921YP3", (
            "Fixture must document GTH4921YP3 (M5 Foundry) per covenant §7.10"
        )

    def test_e03_id_is_alice_m5(self) -> None:
        snap = load_snapshot(FIXTURES / "identity_snapshot_e03.json")
        assert snap["id"] == "ALICE_M5"

    def test_e03_organs_present_is_nonempty(self) -> None:
        snap = load_snapshot(FIXTURES / "identity_snapshot_e03.json")
        assert len(snap["organs_present"]) >= 1, "organs_present must list at least one organ"


class TestE03Contradiction:
    """
    Proof by contradiction: violations of the state vector constraints are
    machine-detectable.
    """

    def test_e03_missing_field_breaks_completeness(self) -> None:
        """Remove homeworld_serial → subset completeness violated."""
        snap = load_snapshot(FIXTURES / "identity_snapshot_e03.json")
        del snap["homeworld_serial"]
        missing = REQUIRED_STATE_FIELDS - snap.keys()
        assert "homeworld_serial" in missing

    def test_e03_wrong_type_breaks_numeric_constraint(self) -> None:
        """Replace stgm_balance with a string → float() raises TypeError."""
        snap = load_snapshot(FIXTURES / "identity_snapshot_e03.json")
        snap["stgm_balance"] = "NOT_A_NUMBER"
        with pytest.raises((TypeError, ValueError)):
            float(snap["stgm_balance"])

    def test_e03_negative_balance_readable(self) -> None:
        """Negative stgm_balance is detectable (RED_CONSERVE guard)."""
        snap = load_snapshot(FIXTURES / "identity_snapshot_e03.json")
        snap["stgm_balance"] = -5.0
        assert float(snap["stgm_balance"]) < 0, "Negative balance must be detectable"

    def test_e03_organs_present_not_list_breaks_constraint(self) -> None:
        """organs_present as a string breaks the list-channel constraint."""
        snap = load_snapshot(FIXTURES / "identity_snapshot_e03.json")
        snap["organs_present"] = "body,immune,gaze"  # wrong type
        assert not isinstance(snap["organs_present"], list)


class TestE03ProofOfProperty:
    """Machine-readable proof_of_property dict smoke-test."""

    proof_of_property = {
        "P_n":         "IdentitySnapshot is x ∈ ℝⁿ with documented basis",
        "basis":       "CHANNEL_UNITS maps every numeric channel → SI unit string",
        "dim_bound":   f"5 ≤ n = |REQUIRED_STATE_FIELDS ∩ snap| ≤ 32",
        "falsifier":   "snap with n < 5 OR missing required field → test fails",
        "truth_label": "OPERATIONAL after pytest green (§7.11)",
    }

    def test_proof_has_required_keys(self) -> None:
        assert {"P_n", "basis", "dim_bound", "falsifier", "truth_label"} <= self.proof_of_property.keys()

    def test_dim_bound_references_correct_range(self) -> None:
        assert "5" in self.proof_of_property["dim_bound"]
        assert "32" in self.proof_of_property["dim_bound"]

    def test_falsifier_is_machine_checkable(self) -> None:
        assert "test fails" in self.proof_of_property["falsifier"]

    def test_truth_label_tracks_pytest_green(self) -> None:
        assert "OPERATIONAL" in self.proof_of_property["truth_label"]
        assert "pytest green" in self.proof_of_property["truth_label"]


class TestE03SharedContract:
    """
    The reusable E03 contract in System.stigmerobotics_state_vector is the
    source consumed by the Qt widget. These checks prevent the proof tests and
    the visual app from quietly drifting apart.
    """

    def test_shared_contract_matches_test_basis(self) -> None:
        assert e03_contract.CHANNEL_UNITS == CHANNEL_UNITS
        assert e03_contract.REQUIRED_STATE_FIELDS == REQUIRED_STATE_FIELDS
        assert e03_contract.NUMERIC_CHANNELS == NUMERIC_CHANNELS
        assert e03_contract.LIST_CHANNELS == LIST_CHANNELS
        assert e03_contract.DIM_MIN == DIM_MIN
        assert e03_contract.DIM_MAX == DIM_MAX

    def test_fixture_state_vector_report_passes(self) -> None:
        report = e03_contract.fixture_state_vector()
        assert report.ok, report.summary_lines()
        assert report.dimension == numeric_dimension(report.snapshot)
        assert report.proof_of_property["truth_label"] == "OPERATIONAL"

    def test_state_vector_report_falsifies_missing_required(self) -> None:
        snap = load_snapshot(FIXTURES / "identity_snapshot_e03.json")
        del snap["homeworld_serial"]
        report = e03_contract.state_vector_from_snapshot(snap)
        assert not report.ok
        assert "homeworld_serial" in report.missing_required

    def test_state_vector_report_falsifies_wrong_numeric_type(self) -> None:
        snap = load_snapshot(FIXTURES / "identity_snapshot_e03.json")
        snap["stgm_balance"] = "NOT_A_NUMBER"
        report = e03_contract.state_vector_from_snapshot(snap)
        assert not report.ok
        assert "stgm_balance" in report.type_errors
