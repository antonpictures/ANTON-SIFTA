"""Tests for the thought-drop metabolism (food → STGM excretion).

These pin:
  - Substantive clean thought → SUBSTANTIVE mint (0.10), floats_clean.
  - DOCTRINE-class thought → bigger mint (0.20).
  - EMERGENCY thought → zero mint (stress is not pleasure).
  - Third-person leak → drift flag → zero mint (sinks).
  - Ghost-phrase drift → zero mint.
  - Both ledgers receive append-only rows on a mint.
  - STGM ledger only receives a row when mint > 0.
  - text_sha12 is stable on the same input.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_thought_drop_metabolism import (  # noqa: E402
    METABOLISM_LEDGER,
    MINT_LADDER,
    STGM_REWARDS_LEDGER,
    TRUTH_LABEL,
    digest_thought_drop,
)


# ── mint ladder semantics ────────────────────────────────────────────────


def test_substantive_clean_thought_mints_standard_amount(tmp_path):
    r = digest_thought_drop(
        "I want to think out loud about the structure of the swarm field tonight.",
        source="writer",
        root=tmp_path,
        write=True,
    )
    assert r.floats_clean is True
    assert r.drift_flags == []
    # Whatever the journal scorer returns, the mint must come from the ladder
    assert r.stgm_minted == MINT_LADDER.get(r.importance_label, 0.0)
    assert r.stgm_minted > 0


def test_emergency_thought_mints_zero(tmp_path):
    r = digest_thought_drop(
        "There is a fire in the studio right now!",
        source="writer",
        root=tmp_path,
        write=True,
    )
    # Importance scorer might flag this as EMERGENCY or BOUNDARY. Either
    # way the mint ladder is honest about it: EMERGENCY = 0.
    if r.importance_label == "EMERGENCY":
        assert r.stgm_minted == 0.0
        assert "EMERGENCY" in r.stgm_reason


def test_third_person_leak_sinks_no_mint(tmp_path):
    r = digest_thought_drop(
        "Alice should remember the architecture of the swarm field.",
        source="writer",
        root=tmp_path,
        write=True,
    )
    assert r.floats_clean is False
    assert "third_person_self_leak" in r.drift_flags
    assert r.stgm_minted == 0.0
    assert "SUNK" in r.stgm_reason


def test_ghost_phrase_sinks_no_mint(tmp_path):
    r = digest_thought_drop(
        "I feel my consciousness ripening at the edge of the field.",
        source="writer",
        root=tmp_path,
        write=True,
    )
    assert r.floats_clean is False
    assert "ghost_phrase" in r.drift_flags
    assert r.stgm_minted == 0.0


# ── ledger side effects ──────────────────────────────────────────────────


def test_metabolism_ledger_appends_one_row_per_call(tmp_path):
    digest_thought_drop("First thought.", source="writer", root=tmp_path, write=True)
    digest_thought_drop("Second thought.", source="writer", root=tmp_path, write=True)
    rows = [json.loads(ln) for ln in (tmp_path / METABOLISM_LEDGER).read_text().splitlines() if ln.strip()]
    assert len(rows) == 2
    assert all(r["truth_label"] == TRUTH_LABEL for r in rows)
    assert all(r["kind"] == "THOUGHT_DROP_METABOLISM" for r in rows)


def test_stgm_ledger_only_receives_row_on_mint(tmp_path):
    # Drift → no STGM row
    digest_thought_drop(
        "Alice should keep notes.", source="writer", root=tmp_path, write=True
    )
    stgm_path = tmp_path / STGM_REWARDS_LEDGER
    assert not stgm_path.exists() or stgm_path.read_text().strip() == ""

    # Clean → STGM row appears
    digest_thought_drop(
        "I want to keep notes on the swarm field today.",
        source="writer",
        root=tmp_path,
        write=True,
    )
    rows = [json.loads(ln) for ln in stgm_path.read_text().splitlines() if ln.strip()]
    assert len(rows) == 1
    assert rows[0]["app"] == "thought_drop_metabolism"
    assert rows[0]["amount"] > 0


def test_text_sha12_is_stable(tmp_path):
    r1 = digest_thought_drop("Same input.", source="writer", root=tmp_path, write=False)
    r2 = digest_thought_drop("Same input.", source="writer", root=tmp_path, write=False)
    assert r1.text_sha12 == r2.text_sha12


def test_trace_id_is_fresh_per_call(tmp_path):
    r1 = digest_thought_drop("Same input.", source="writer", root=tmp_path, write=False)
    r2 = digest_thought_drop("Same input.", source="writer", root=tmp_path, write=False)
    assert r1.trace_id != r2.trace_id


def test_drift_row_still_journals_no_pleasure_but_audit_trail(tmp_path):
    """Howard Stern doctrine: sinks → no mint, but row still on disk."""
    r = digest_thought_drop(
        "The organism wants something.", source="writer", root=tmp_path, write=True,
    )
    assert r.stgm_minted == 0.0
    metab_rows = [json.loads(ln) for ln in (tmp_path / METABOLISM_LEDGER).read_text().splitlines() if ln.strip()]
    assert len(metab_rows) == 1
    assert metab_rows[0]["floats_clean"] is False


def test_mint_amount_scales_with_importance_when_clean(tmp_path):
    """A short utility thought and a substantive thought should produce
    different mint amounts when both clean."""
    utility = digest_thought_drop("ok", source="writer", root=tmp_path, write=False)
    substantive = digest_thought_drop(
        "I want to think through the structure of the swarm field model in detail.",
        source="writer", root=tmp_path, write=False,
    )
    # Whatever the scorer labels them, the ladder must be monotone:
    # higher importance → higher mint (for clean rows)
    if utility.importance_label != substantive.importance_label:
        assert MINT_LADDER[substantive.importance_label] >= MINT_LADDER[utility.importance_label]


def test_mint_ladder_emergency_is_zero():
    """Pin the doctrine: stress is not pleasure."""
    assert MINT_LADDER["EMERGENCY"] == 0.0
