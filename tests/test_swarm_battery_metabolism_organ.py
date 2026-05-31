#!/usr/bin/env python3
"""Tests for the battery-metabolism organ (Alice's wish #1, 2026-05-30).

Driven by captured `pmset -g batt` strings so the parser and the metabolic
mapping are verified without a real battery present.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System import swarm_battery_metabolism_organ as bat


AC_CHARGED = (
    "Now drawing from 'AC Power'\n"
    " -InternalBattery-0 (id=12345)\t100%; charged; 0:00 remaining present: true"
)
AC_CHARGING = (
    "Now drawing from 'AC Power'\n"
    " -InternalBattery-0 (id=12345)\t76%; charging; 1:12 remaining present: true"
)
BATT_HEALTHY = (
    "Now drawing from 'Battery Power'\n"
    " -InternalBattery-0 (id=12345)\t82%; discharging; 5:30 remaining present: true"
)
BATT_LOW = (
    "Now drawing from 'Battery Power'\n"
    " -InternalBattery-0 (id=12345)\t28%; discharging; 1:05 remaining present: true"
)
BATT_CRITICAL = (
    "Now drawing from 'Battery Power'\n"
    " -InternalBattery-0 (id=12345)\t9%; discharging; 0:18 remaining present: true"
)


# ── parsing ────────────────────────────────────────────────────────────────
def test_parse_ac_charged():
    s = bat.parse_pmset_output(AC_CHARGED)
    assert s["available"] is True
    assert s["percent"] == 100
    assert s["source"] == "ac"
    assert s["status"] == "charged"


def test_parse_battery_discharging():
    s = bat.parse_pmset_output(BATT_HEALTHY)
    assert s["source"] == "battery"
    assert s["percent"] == 82
    assert s["status"] == "discharging"
    assert s["minutes_remaining"] == 330


def test_parse_zero_time_is_unknown():
    s = bat.parse_pmset_output(AC_CHARGED)
    assert s["minutes_remaining"] is None  # 0:00 = still estimating


def test_parse_garbage_is_unavailable():
    s = bat.parse_pmset_output("not a battery line at all")
    assert s["available"] is False
    assert s["percent"] is None


# ── metabolic mapping ────────────────────────────────────────────────────────
def test_ac_power_is_flush():
    sig = bat.battery_to_metabolic_signal(bat.parse_pmset_output(AC_CHARGED))
    assert sig["band"] == "FLUSH"
    assert sig["conserve"] is False
    assert sig["activity_multiplier"] == 1.0


def test_charging_is_flush():
    sig = bat.battery_to_metabolic_signal(bat.parse_pmset_output(AC_CHARGING))
    assert sig["band"] == "FLUSH"


def test_healthy_battery_is_normal():
    sig = bat.battery_to_metabolic_signal(bat.parse_pmset_output(BATT_HEALTHY))
    assert sig["band"] == "NORMAL"
    assert sig["conserve"] is False


def test_low_battery_conserves():
    sig = bat.battery_to_metabolic_signal(bat.parse_pmset_output(BATT_LOW))
    assert sig["band"] == "CONSERVE"
    assert sig["conserve"] is True
    assert sig["activity_multiplier"] < 1.0


def test_critical_battery_red_conserve():
    sig = bat.battery_to_metabolic_signal(bat.parse_pmset_output(BATT_CRITICAL))
    assert sig["band"] == "RED_CONSERVE"
    assert sig["conserve"] is True
    assert sig["activity_multiplier"] <= 0.25


def test_unreadable_defaults_to_normal_not_conserve():
    sig = bat.battery_to_metabolic_signal({"available": False})
    assert sig["band"] == "NORMAL"
    assert sig["conserve"] is False


# ── read + receipt ───────────────────────────────────────────────────────────
def test_sample_writes_receipt(tmp_path):
    row = bat.sample(_pmset_text=BATT_LOW, root=tmp_path)
    assert row["truth_label"] == bat.TRUTH_LABEL
    assert row["metabolic"]["band"] == "CONSERVE"
    ledger = tmp_path / ".sifta_state" / "battery_metabolism.jsonl"
    assert ledger.exists() and ledger.read_text().strip()


def test_read_battery_non_macos_is_honest():
    # No _pmset_text and (in CI) no pmset binary → honest unavailable, no raise.
    out = bat.read_battery(_pmset_text=None)
    assert "available" in out


def test_status_line_and_prompt_block():
    st = bat.parse_pmset_output(BATT_HEALTHY)
    assert "82%" in bat.status_line(st)
    block = bat.prompt_block(st)
    assert "metabolic band=NORMAL" in block


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
