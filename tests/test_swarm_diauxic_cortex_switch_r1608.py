#!/usr/bin/env python3
"""r1608 Gift 4 — diauxic local-first cortex switch."""
from __future__ import annotations

from System.swarm_diauxic_cortex_switch import (
    TIER_LOCAL,
    TIER_CLOUD,
    TIER_HOLD,
    assess_local_depletion,
    choose_cortex_tier,
    write_lag_phase_receipt,
)


def test_cheap_substrate_preferred():
    d = choose_cortex_tier(local_available=True, cloud_available=True)
    assert d["tier"] == TIER_LOCAL
    assert d["reason"] == "cheap_substrate_available"
    assert d["lag_phase"] is False


def test_depletion_triggers_lag_phase_before_cloud():
    d = choose_cortex_tier(
        local_available=True,
        local_empty_replies=2,
        cloud_available=True,
        lag_phase_already_receipted=False,
    )
    assert d["tier"] == TIER_HOLD
    assert d["lag_phase"] is True
    assert d.get("next_tier") == TIER_CLOUD


def test_after_lag_escalates_to_cloud():
    d = choose_cortex_tier(
        local_available=True,
        local_empty_replies=3,
        cloud_available=True,
        lag_phase_already_receipted=True,
    )
    assert d["tier"] == TIER_CLOUD
    assert d["lag_phase"] is False


def test_battery_low_stays_local():
    d = choose_cortex_tier(
        local_available=True,
        local_empty_replies=5,
        cloud_available=True,
        battery_low=True,
    )
    assert d["tier"] == TIER_LOCAL
    assert "battery" in d["reason"]


def test_offline_required_stays_local():
    d = choose_cortex_tier(force_cloud=True, offline_required=True, cloud_available=True)
    assert d["tier"] == TIER_LOCAL


def test_assess_depletion():
    a = assess_local_depletion(local_empty_replies=0)
    assert a["depleted"] is False
    b = assess_local_depletion(local_timeouts=2)
    assert b["depleted"] is True
    assert "timeouts" in b["reasons"]


def test_lag_receipt(tmp_path):
    d = choose_cortex_tier(local_empty_replies=2, cloud_available=True)
    row = write_lag_phase_receipt(d, state_dir=tmp_path)
    assert row["event"] == "lag_phase"
    assert (tmp_path / "diauxic_cortex_switch_receipts.jsonl").exists()
