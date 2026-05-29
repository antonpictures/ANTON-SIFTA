#!/usr/bin/env python3
"""Round 51 tests for arm skills catalog. Real ledger isolation (delta=0)."""

import json
import os
import tempfile
from pathlib import Path

import pytest

# Import the module under test (pure, no side effects on import)
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from System import swarm_arm_skills_catalog as cat


def test_load_catalog_returns_all_four_arm_ids_when_briefs_exist(tmp_path, monkeypatch):
    # Point the module at the real skills dir; current repo may contain more
    # than the original four briefs as new arms are added.
    real_dir = Path(__file__).resolve().parents[1] / "Documents" / "arm_skills"
    monkeypatch.setattr(cat, "_ARM_SKILLS_DIR", real_dir)
    c = cat.load_catalog()
    assert {"hermes_agent", "codex_agent", "grok_agent", "claude_agent"}.issubset(set(c.keys()))
    for aid in c:
        assert "arm_id" in c[aid] or "raw" in c[aid]


def test_catalog_summary_prompt_block_contains_each_arm_display_name(tmp_path, monkeypatch):
    real_dir = Path(__file__).resolve().parents[1] / "Documents" / "arm_skills"
    monkeypatch.setattr(cat, "_ARM_SKILLS_DIR", real_dir)
    block = cat.catalog_summary_prompt_block()
    assert "hermes_agent" in block
    assert "codex_agent" in block
    assert "grok_agent" in block
    assert "claude_agent" in block
    assert "corvid_scout" in block
    assert "armed by registry; no owner env unlock needed" in block


def test_smoke_probe_for_returns_expected_shape_for_each_arm(tmp_path, monkeypatch):
    real_dir = Path(__file__).resolve().parents[1] / "Documents" / "arm_skills"
    monkeypatch.setattr(cat, "_ARM_SKILLS_DIR", real_dir)
    for aid in ("hermes_agent", "codex_agent", "grok_agent", "claude_agent"):
        probe = cat.smoke_probe_for(aid)
        assert probe["arm_id"] == aid
        assert "prompt" in probe and isinstance(probe["prompt"], str)
        assert "expected_receipt_shape" in probe
        assert "max_wall_s" in probe and isinstance(probe["max_wall_s"], int)


def test_allowed_arm_ids_for_current_stability_conserve_repair(tmp_path):
    from System.swarm_stability_audit import enforce_stability_clamps

    snap = {
        "lyapunov_energy": 0.9,
        "delta_lyapunov_energy": 0.0,
        "terms": {"astrocyte_heat_norm": 0.0},
        "stable": True,
    }
    enforce_stability_clamps(snap, root=tmp_path, write_ledger=True)

    allowed = cat.allowed_arm_ids_for_current_stability(
        root=tmp_path,
        arm_ids=("codex_agent", "claude_agent", "corvid_scout"),
    )

    assert allowed == ("corvid_scout",)


def test_real_ledger_isolation_delta_zero(tmp_path, monkeypatch):
    """No test may mutate real .sifta_state ledgers. All writes go to tmp."""
    state_root = tmp_path / "sifta_state"
    state_root.mkdir()
    # Force any future ledger writes in the module (none exist today) to tmp
    # by monkeypatching the state dir if the module ever grows writes.
    # Current catalog is read-only; this test documents the contract.
    real_ledger = Path("/Users/ioanganton/Music/ANTON_SIFTA/.sifta_state/agent_arm_receipts.jsonl")
    before = real_ledger.stat().st_size if real_ledger.exists() else 0
    # Call the public functions — they must not touch disk outside tmp
    _ = cat.load_catalog()
    _ = cat.catalog_summary_prompt_block(str(state_root))
    _ = cat.smoke_probe_for("hermes_agent")
    after = real_ledger.stat().st_size if real_ledger.exists() else 0
    assert after == before, "catalog functions must not append to real ledgers (delta=0 required)"
