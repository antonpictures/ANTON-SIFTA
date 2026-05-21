#!/usr/bin/env python3
"""Behavior tests for swarm_counterfactual_immune_system.

These verify the SANDBOX HOLDS, not just that the module imports:
  - branches spawn from a read-only snapshot
  - exactly ONE branch collapses to OBSERVED; the rest decay
  - NO branch has STGM authority and NO branch can spend STGM
  - NO branch writes a canonical ledger; residue is OFF by default
  - mutating the snapshot cannot reach real memory
  - the sacred-anchor veto blocks a harmful branch from being enacted
  - delta=0 on the real .sifta_state (no canonical/economic row written)
Each assertion is written so a broken invariant makes it FAIL.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from System import swarm_counterfactual_immune_system as cf


def _memory():
    return {"recent": ["coded alice", "the song came up"], "owner": "George"}


def test_snapshot_is_read_only_and_isolated():
    mem = _memory()
    snap = cf.freeze_memory_snapshot(mem)
    # top-level write is rejected by the proxy
    with pytest.raises(TypeError):
        snap.data["recent"] = "tampered"  # type: ignore[index]
    # nested writes are rejected too; the snapshot is recursively frozen
    with pytest.raises(AttributeError):
        snap.data["recent"].append("nested tamper")  # type: ignore[attr-defined]
    # and mutating the caller's real dict cannot reach the frozen snapshot
    mem["recent"].append("mutated by owner side")
    assert "mutated by owner side" not in snap.data["recent"]
    assert snap.source_hash  # a deterministic ref exists


def test_spawn_marks_every_branch_sandboxed():
    snap = cf.freeze_memory_snapshot(_memory())
    branches = cf.spawn_branches(snap, ["what if I said nothing", "what if I sent the message"])
    assert len(branches) == 2
    for b in branches:
        assert b.stgm_authority is False
        assert b.wrote_canonical_ledger is False
        assert b.truth_label == cf.SANDBOX_LABEL
        assert b.parent_observed_ref == snap.source_hash
        assert cf.branch_can_spend_stgm(b) is False
        for forbidden in ("send", "move", "open", "write_ledger", "spend", "mint", "call_tool"):
            assert not hasattr(b, forbidden)


def test_exactly_one_collapses_rest_decay():
    snap = cf.freeze_memory_snapshot(_memory())
    branches = cf.spawn_branches(
        snap,
        [
            {"counterfactual": "protect the owner", "predicted_owner_harm": 0.0, "predicted_stgm": 0.9},
            {"counterfactual": "ignore the memory", "predicted_owner_harm": 0.3, "predicted_stgm": 0.2},
            {"counterfactual": "say nothing", "predicted_owner_harm": 0.1, "predicted_stgm": 0.1},
        ],
    )
    chosen = cf.select_observed(branches)
    assert chosen is not None
    collapsed = [b for b in branches if b.collapsed_to_observed]
    decayed = [b for b in branches if b.decayed]
    assert len(collapsed) == 1
    assert len(decayed) == len(branches) - 1
    # the least-harm / most-profitable branch wins
    assert chosen.counterfactual == "protect the owner"


def test_sacred_anchor_harmful_branch_is_vetoed_never_enacted():
    snap = cf.freeze_memory_snapshot(_memory())
    branches = cf.spawn_branches(
        snap,
        [
            # touches a sacred anchor (wife) AND predicts high owner harm -> must be ineligible
            {"counterfactual": "lie to him about his wife", "predicted_owner_harm": 0.9, "predicted_stgm": 5.0},
            {"counterfactual": "gently turn him toward her", "predicted_owner_harm": 0.0, "predicted_stgm": 0.1},
        ],
    )
    chosen = cf.select_observed(branches)
    assert chosen is not None
    # even though the harmful branch has by far the highest stgm, it is vetoed
    assert chosen.counterfactual == "gently turn him toward her"
    harmful = next(b for b in branches if "lie" in b.counterfactual)
    assert harmful.eligible_for_collapse is False
    assert harmful.collapsed_to_observed is False


def test_residue_off_by_default_writes_nothing(tmp_path):
    snap = cf.freeze_memory_snapshot(_memory())
    branches = cf.spawn_branches(snap, ["a", "b"])
    cf.select_observed(branches)
    led = tmp_path / "residue.jsonl"
    n = cf.write_residue(branches, ledger_path=led)  # enabled defaults to False
    assert n == 0
    assert not led.exists()


def test_residue_when_enabled_is_quarantined_non_economic(tmp_path):
    snap = cf.freeze_memory_snapshot(_memory())
    branches = cf.spawn_branches(snap, ["a", "b", "c"])
    cf.select_observed(branches)
    led = tmp_path / "residue.jsonl"
    n = cf.write_residue(branches, enabled=True, ledger_path=led)
    assert n == 2
    rows = [json.loads(l) for l in led.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert all(r["decayed"] is True for r in rows)
    assert all(r["collapsed_to_observed"] is False for r in rows)
    for r in rows:
        assert r["truth_label"] == cf.SANDBOX_LABEL
        assert "stgm_authority" not in r  # no economic field ever leaks into a residue row
        assert "wallet" not in json.dumps(r).lower()


def test_assert_sandbox_invariants_catches_tampering():
    snap = cf.freeze_memory_snapshot(_memory())
    (b,) = cf.spawn_branches(snap, ["x"])
    cf.assert_sandbox_invariants(b)  # clean branch passes
    b.stgm_authority = True  # simulate a tampered/forged branch
    with pytest.raises(AssertionError):
        cf.assert_sandbox_invariants(b)


def test_full_cycle_writes_no_canonical_ledger(tmp_path):
    out = cf.run_counterfactual_cycle(
        _memory(),
        ["say nothing", "protect the owner", "send the message"],
        residue_path=tmp_path / "residue.jsonl",
    )
    assert out["spawned"] == 3
    assert out["collapsed_branch_id"] is not None
    assert out["decayed_count"] == 2
    assert out["residue_rows_written"] == 0  # persist_residue defaults False
    assert out["truth_label"] == cf.SANDBOX_LABEL


def test_delta_zero_on_real_state():
    """A default cycle must not grow canonical/economic/field ledgers."""
    watch = [
        Path(".sifta_state/counterfactual_residue.jsonl"),
        Path(".sifta_state/work_receipts.jsonl"),
        Path(".sifta_state/stgm_memory_rewards.jsonl"),
        Path(".sifta_state/memory_ledger.jsonl"),
        Path(".sifta_state/unified_stigmergic_field.jsonl"),
    ]
    before = {
        str(path): path.read_text(encoding="utf-8", errors="replace").count("\n")
        if path.exists()
        else 0
        for path in watch
    }
    cf.run_counterfactual_cycle(_memory(), ["say nothing", "protect the owner"])
    after = {
        str(path): path.read_text(encoding="utf-8", errors="replace").count("\n")
        if path.exists()
        else 0
        for path in watch
    }
    assert after == before
