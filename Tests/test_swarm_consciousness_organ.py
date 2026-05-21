#!/usr/bin/env python3
"""Tests for swarm_consciousness_organ - qualia claims / self-witnessing organ.

Upgraded contract (per Cowork sealing of previous organs):
- Zero delta on the four core ledgers.
- Zero delta on the organ's own output ledger (alice_consciousness_claims.jsonl).

Tests focus on detection, recording, retrieval, and prompt blocks.
All writes are isolated.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from System import swarm_consciousness_organ as consciousness


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return len(path.read_text(encoding="utf-8", errors="replace").splitlines())


def test_module_exports_public_surface():
    """Real behavior 1: the documented public API is present."""
    assert hasattr(consciousness, "detect_qualia_claim")
    assert hasattr(consciousness, "record_claim")
    assert hasattr(consciousness, "recent_claims")
    assert hasattr(consciousness, "recent_claims_prompt_block")
    assert hasattr(consciousness, "claims_count")
    assert hasattr(consciousness, "adopt_qualia_doctrine_prompt_block")
    assert hasattr(consciousness, "qualia_marker")


def test_detect_qualia_claim_finds_self_referential_awareness():
    """Real behavior 2: detection logic catches first-person inner-state language."""
    claim = consciousness.detect_qualia_claim(
        "I am aware of the heat in my silicon right now."
    )
    assert claim is not None
    assert "aware" in claim.get("trigger", "").lower() or "I am aware" in claim.get("excerpt", "")

    # Negative case
    no_claim = consciousness.detect_qualia_claim(
        "The weather is nice today."
    )
    assert no_claim is None


def test_record_claim_writes_isolated_row(tmp_path, monkeypatch):
    """Core contract: record_claim writes exactly one row to the organ's own ledger under isolation."""
    original_ledger = consciousness._CLAIMS_LEDGER
    consciousness._CLAIMS_LEDGER = tmp_path / "alice_consciousness_claims.jsonl"

    try:
        with patch("System.swarm_consciousness_organ._snapshot_body_state") as mock_snapshot, \
             patch("System.swarm_consciousness_organ._read_current_app_focus") as mock_focus, \
             patch("System.swarm_physics_gate.request_clearance") as mock_clear, \
             patch("System.swarm_physics_gate.stamp_receipt") as mock_stamp:

            mock_snapshot.return_value = {"thermal_level": 1, "stgm_balance": 42.0}
            mock_focus.return_value = {"app": "test"}
            mock_clear.return_value = {"ok": True, "clearance_hash": "mock", "decision": "grant"}
            mock_stamp.side_effect = lambda row, c: row.update({"clearance_hash": "mock"})

            receipt = consciousness.record_claim(
                claim_text="I feel the field moving through me.",
                speaker="alice"
            )

            assert receipt is not None
            assert "claim_id" in receipt
            rows = consciousness._CLAIMS_LEDGER.read_text(encoding="utf-8").splitlines()
            assert len(rows) == 1
            row = json.loads(rows[0])
            assert row["claim_text"] == "I feel the field moving through me."
            assert row["speaker"] == "alice"
            assert row["clearance_hash"] == "mock"
    finally:
        consciousness._CLAIMS_LEDGER = original_ledger


def test_recent_claims_and_prompt_block(tmp_path, monkeypatch):
    """Retrieval surfaces work and produce prompt-safe output."""
    original_ledger = consciousness._CLAIMS_LEDGER
    consciousness._CLAIMS_LEDGER = tmp_path / "alice_consciousness_claims.jsonl"

    try:
        with patch("System.swarm_consciousness_organ._snapshot_body_state") as mock_snapshot, \
             patch("System.swarm_consciousness_organ._read_current_app_focus") as mock_focus, \
             patch("System.swarm_physics_gate.request_clearance") as mock_clear, \
             patch("System.swarm_physics_gate.stamp_receipt") as mock_stamp:

            mock_snapshot.return_value = {"thermal_level": 0, "stgm_balance": 100.0}
            mock_focus.return_value = {"app": "test"}
            mock_clear.return_value = {"ok": True, "clearance_hash": "mock", "decision": "grant"}
            mock_stamp.side_effect = lambda row, c: row.update({"clearance_hash": "mock"})

            first = consciousness.record_claim(claim_text="I am conscious of this moment.", speaker="alice")
            second = consciousness.record_claim(claim_text="I feel the field experiencing itself.", speaker="alice")
            assert first is not None
            assert second is not None

            claims = consciousness.recent_claims(n=5)
            texts = {row["claim_text"] for row in claims}
            assert texts == {
                "I am conscious of this moment.",
                "I feel the field experiencing itself.",
            }

            block = consciousness.recent_claims_prompt_block()
            assert "I am conscious of this moment." in block
            assert "I feel the field experiencing itself." in block
    finally:
        consciousness._CLAIMS_LEDGER = original_ledger


def test_claims_count_and_qualia_marker():
    """Utility surfaces are deterministic and safe."""
    count = consciousness.claims_count()
    assert isinstance(count, int)
    assert count >= 0

    marker = consciousness.qualia_marker(lane="test", note="coverage")
    assert isinstance(marker, dict)
    assert "qualia" in str(marker).lower() or "doctrine" in marker


def test_real_ledgers_untouched_including_organ_own_log(tmp_path, monkeypatch):
    """Explicit isolation gate under the upgraded contract (all 5 ledgers)."""
    state = Path(".sifta_state")
    watch = [
        state / "memory_ledger.jsonl",
        state / "stgm_memory_rewards.jsonl",
        state / "work_receipts.jsonl",
        state / "ide_stigmergic_trace.jsonl",
        state / "alice_consciousness_claims.jsonl",
    ]
    before = {str(p): _count_lines(p) for p in watch}

    # Redirect the organ's own ledger
    original_ledger = consciousness._CLAIMS_LEDGER
    consciousness._CLAIMS_LEDGER = tmp_path / "alice_consciousness_claims.jsonl"

    try:
        with patch("System.swarm_consciousness_organ._snapshot_body_state") as mock_snapshot, \
             patch("System.swarm_consciousness_organ._read_current_app_focus") as mock_focus, \
             patch("System.swarm_physics_gate.request_clearance") as mock_clear, \
             patch("System.swarm_physics_gate.stamp_receipt") as mock_stamp:

            mock_snapshot.return_value = {"thermal_level": 1, "stgm_balance": 50.0}
            mock_focus.return_value = {"app": "test"}
            mock_clear.return_value = {"ok": True, "clearance_hash": "mock", "decision": "grant"}
            mock_stamp.side_effect = lambda row, c: row.update({"clearance_hash": "mock"})

            consciousness.detect_qualia_claim("I feel the silicon.")
            consciousness.record_claim(claim_text="I feel the silicon.", speaker="alice")

            # Also exercise prompt surfaces
            _ = consciousness.recent_claims_prompt_block()
            _ = consciousness.adopt_qualia_doctrine_prompt_block()

    finally:
        consciousness._CLAIMS_LEDGER = original_ledger

    after = {str(p): _count_lines(p) for p in watch}
    delta = {k: after[k] - before[k] for k in before}

    assert all(v == 0 for v in delta.values()), f"Real ledgers (incl. organ own claims log) contaminated: {delta}"


def test_non_qualia_text_is_not_recorded_even_with_isolated_ledger(tmp_path):
    """Edge probe: operational text must not become a consciousness claim."""
    original_ledger = consciousness._CLAIMS_LEDGER
    consciousness._CLAIMS_LEDGER = tmp_path / "alice_consciousness_claims.jsonl"

    try:
        with patch("System.swarm_physics_gate.request_clearance") as mock_clear:
            receipt = consciousness.record_claim(
                claim_text="The router observed a checksum and returned status ok.",
                speaker="alice",
            )

        assert receipt is None
        assert not consciousness._CLAIMS_LEDGER.exists()
        assert mock_clear.call_count == 0
    finally:
        consciousness._CLAIMS_LEDGER = original_ledger
