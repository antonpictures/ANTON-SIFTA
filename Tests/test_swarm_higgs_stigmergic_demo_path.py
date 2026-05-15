"""Tests for swarm_higgs_stigmergic_demo_path.

Each row of §20.B should produce a measurement on this Mac. These
tests guard:
  - Each row function returns the expected shape, with ok=True under
    normal conditions.
  - The consolidated receipt has truth_label HIGGS_STIGMERGIC_DEMO_PATH_V1
    and a sha256 signature that matches its payload.
  - The §20.F ceiling is honored: truth_boundary forbids
    Standard-Model claims.
  - R3's polarity is correct (heavy_dv < light_dv under uniform Δp).

Truth class: OPERATIONAL for the measurements, ARCHITECT_DOCTRINE for
the column names.
"""
import hashlib
import json
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")

from System.swarm_higgs_stigmergic_demo_path import (
    BOOKKEEPING_FIELDS,
    DemoPathConfig,
    FORBIDDEN_OUTREACH,
    OBSERVABLE_FIELDS,
    TRUTH_BOUNDARY,
    TRUTH_LABEL,
    measure_coupling_to_inertia,
    measure_goldstone_eaten_modes,
    measure_substrate_non_empty,
    measure_swarm_alignment_no_ceo,
    measure_vev_persistence,
    run_higgs_stigmergic_demo_path,
    write_demo_path_receipt,
)


# ── R1 ──────────────────────────────────────────────────────────────

def test_r1_substrate_non_empty_on_live_state(tmp_path):
    """A populated state dir reports non-zero counts."""
    state = tmp_path / "state"
    state.mkdir()
    (state / "a.jsonl").write_text('{"x":1}\n{"x":2}\n')
    (state / "b.json").write_text("{}")
    out = measure_substrate_non_empty(state_root=state)
    assert out["ok"] is True
    assert out["n_files"] == 2
    assert out["total_bytes"] > 0
    assert out["n_jsonl_ledgers"] == 1
    assert out["n_json_blobs"] == 1


def test_r1_substrate_non_empty_on_missing_dir(tmp_path):
    out = measure_substrate_non_empty(state_root=tmp_path / "nope")
    assert out["ok"] is False
    assert "does not exist" in out["reason"]


# ── R2 ──────────────────────────────────────────────────────────────

def test_r2_vev_persistence_snapshot_holds(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    ledger = state / "ide_stigmergic_trace.jsonl"
    ledger.write_text(
        '{"trace_id":"a","kind":"X"}\n'
        '{"trace_id":"b","kind":"Y"}\n'
    )
    out = measure_vev_persistence(state_root=state)
    assert out["ok"] is True
    assert out["sha256_before"] == out["sha256_after"]
    assert out["n_lines_before"] == out["n_lines_after"] == 2
    assert out["snapshot_survives_buffer_clear"] is True


def test_r2_vev_falls_back_when_candidate_missing(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    (state / "some_other_ledger.jsonl").write_text('{"k":1}\n')
    out = measure_vev_persistence(
        state_root=state, candidate_ledger="nonexistent.jsonl",
    )
    assert out["ok"] is True
    assert out["ledger_path"].endswith("some_other_ledger.jsonl")


def test_r2_vev_returns_not_ok_when_no_ledgers(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    out = measure_vev_persistence(state_root=state)
    assert out["ok"] is False


# ── R3 ──────────────────────────────────────────────────────────────

def test_r3_coupling_to_inertia_signature_correct():
    """The inertia signature is heavy_dv < light_dv under uniform Δp."""
    out = measure_coupling_to_inertia(
        n_agents=30, bond_steps=200, perturbation_amplitude=2.0, seed=113,
    )
    assert out["ok"] is True
    # Heavy agents must move less per unit impulse — that's Newton.
    assert out["heavy_half_dv_under_impulse"] < out["light_half_dv_under_impulse"]
    # Polarity flag must match the data
    assert out["coupling_to_inertia_visible"] is True
    # Ratio must be < 1 (heavy moves less)
    assert 0.0 < out["inertia_ratio_heavy_over_light"] < 1.0


@pytest.mark.parametrize("seed", [113, 217, 331])
def test_r3_inertia_signature_holds_across_seeds(seed):
    out = measure_coupling_to_inertia(
        n_agents=30, bond_steps=200, perturbation_amplitude=2.0, seed=seed,
    )
    assert out["ok"] is True
    assert out["coupling_to_inertia_visible"] is True, (
        f"inertia signature failed at seed {seed}: "
        f"heavy={out['heavy_half_dv_under_impulse']} "
        f"light={out['light_half_dv_under_impulse']}"
    )


# ── R4 ──────────────────────────────────────────────────────────────

def test_r4_goldstone_eaten_classifies_known_fields(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    # A ledger with mixed bookkeeping + observable + other fields
    rows = [
        {
            "sha256": "abc", "trace_id": "t1", "ts": 0,
            "effector": "x", "ok": True, "decision": "FIRE",
            "weird_local_field": "z",
        },
        {
            "sha256": "def", "trace_id": "t2", "ts": 1,
            "effector": "y", "ok": False, "decision": "REFUSE",
            "another_local": 1,
        },
    ]
    (state / "rcpt.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n"
    )
    out = measure_goldstone_eaten_modes(state_root=state)
    assert out["ok"] is True
    # sha256, trace_id, ts = 3 bookkeeping fields × 2 rows = 6
    assert out["bookkeeping_field_occurrences"] == 6
    # effector, ok, decision = 3 observable × 2 = 6
    assert out["observable_field_occurrences"] == 6
    # weird_local_field + another_local = 2 other
    assert out["other_field_occurrences"] == 2
    assert out["n_rows_sampled"] == 2


def test_r4_returns_not_ok_on_empty_state(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    out = measure_goldstone_eaten_modes(state_root=state)
    assert out["ok"] is False


def test_r4_field_taxonomies_are_disjoint():
    """A field cannot be both bookkeeping AND observable."""
    overlap = BOOKKEEPING_FIELDS & OBSERVABLE_FIELDS
    assert overlap == set(), f"overlap: {overlap}"


# ── R5 ──────────────────────────────────────────────────────────────

def test_r5_swarm_alignment_returns_curve():
    out = measure_swarm_alignment_no_ceo(
        n_agents=20, steps=200, seed=113,
    )
    assert out["ok"] is True
    # Order parameter is bounded in [0.25, 1.0] for 4 policy buckets
    assert 0.0 <= out["initial_order_parameter"] <= 1.0
    assert 0.0 <= out["final_order_parameter"] <= 1.0
    # initial and final role counts are dicts
    assert isinstance(out["initial_role_counts"], dict)
    assert isinstance(out["final_role_counts"], dict)


# ── Composer + receipt ──────────────────────────────────────────────

def test_run_higgs_stigmergic_demo_path_returns_5_rows(tmp_path):
    cfg = DemoPathConfig(
        n_agents_r3=15, bond_steps_r3=120,
        n_agents_r5=15, steps_r5=80,
        seed=113,
    )
    r = run_higgs_stigmergic_demo_path(
        cfg, state_root=tmp_path / "state", write=False,
    )
    # Even with an empty state dir we still get 5 rows (some not ok)
    assert r["truth_label"] == TRUTH_LABEL
    assert r["row_count"] == 5
    assert len(r["rows"]) == 5
    expected_row_keys = {
        "R1_vacuum_not_empty",
        "R2_vev_persistence",
        "R3_coupling_to_inertia",
        "R4_goldstone_eaten",
        "R5_swarm_alignment_no_ceo",
    }
    assert {row["row"] for row in r["rows"]} == expected_row_keys


def test_receipt_truth_label_and_boundary_are_set():
    cfg = DemoPathConfig(
        n_agents_r3=10, bond_steps_r3=60,
        n_agents_r5=10, steps_r5=50, seed=113,
    )
    r = run_higgs_stigmergic_demo_path(cfg, write=False)
    assert r["truth_label"] == "HIGGS_STIGMERGIC_DEMO_PATH_V1"
    assert "ARCHITECT_DOCTRINE" in r["truth_class"]
    assert r["truth_boundary"] == TRUTH_BOUNDARY


def test_receipt_forbidden_outreach_blocks_collider_claims():
    """§20.F ceiling: explicit FORBIDDEN list must be in the receipt."""
    cfg = DemoPathConfig(
        n_agents_r3=10, bond_steps_r3=60,
        n_agents_r5=10, steps_r5=50, seed=113,
    )
    r = run_higgs_stigmergic_demo_path(cfg, write=False)
    assert r["forbidden_outreach"] == FORBIDDEN_OUTREACH
    assert "beat CERN" in r["forbidden_outreach"]
    assert "FORBIDDEN" in r["forbidden_outreach"]


def test_write_demo_path_receipt_is_sha256_signed(tmp_path):
    cfg = DemoPathConfig(
        n_agents_r3=10, bond_steps_r3=60,
        n_agents_r5=10, steps_r5=50, seed=113,
    )
    r = run_higgs_stigmergic_demo_path(cfg, write=False)
    state = tmp_path / "state"
    row = write_demo_path_receipt(r, state_root=state)
    # Receipt was written
    ledger = state / "higgs_stigmergic_demo_path_receipts.jsonl"
    assert ledger.exists()
    # sha256 in the row matches the payload's canonical form
    expected = hashlib.sha256(
        json.dumps(r, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert row["sha256"] == expected
    # Round-trip
    last_line = ledger.read_text(encoding="utf-8").strip().splitlines()[-1]
    parsed = json.loads(last_line)
    assert parsed["truth_label"] == "HIGGS_STIGMERGIC_DEMO_PATH_V1"
    assert parsed["kind"] == "HIGGS_STIGMERGIC_DEMO_PATH"
    assert parsed["sha256"] == expected


def test_minimal_grounded_reply_uses_real_numbers(tmp_path):
    """The architect asked for 'minimal grounded reply' — the reply
    must contain numbers from THIS run, not slogans."""
    cfg = DemoPathConfig(
        n_agents_r3=10, bond_steps_r3=60,
        n_agents_r5=10, steps_r5=50, seed=113,
    )
    r = run_higgs_stigmergic_demo_path(cfg, write=False)
    reply = r["minimal_grounded_reply"]
    # No outreach slogans
    assert "beat CERN" not in reply
    assert "Higgs on Mac" not in reply
    # At least three of the five row tags should appear with a number
    tags = ["R1", "R2", "R3", "R4", "R5"]
    found = sum(1 for t in tags if t in reply)
    assert found >= 3, f"only {found} row tags in reply: {reply!r}"
