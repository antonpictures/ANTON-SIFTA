#!/usr/bin/env python3
"""Tests for battery/electricity as Alice's somatic power-air signal."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System import swarm_somatic_interoception as soma


def test_power_air_signal_maps_battery_receipts():
    critical_row = {
        "ok": True,
        "battery": {"available": True, "source": "battery", "percent": 9},
        "metabolic": {"band": "RED_CONSERVE", "reason": "battery_critical_9pct"},
    }
    reserve, meta = soma._power_air_reserve_from_battery_row(critical_row)
    assert reserve <= 0.18
    assert meta["band"] == "RED_CONSERVE"
    assert meta["source"] == "battery"
    assert meta["reason"] == "battery_critical_9pct"

    ac_row = {
        "ok": True,
        "battery": {"available": True, "source": "ac", "percent": 76},
        "metabolic": {"band": "FLUSH", "reason": "on_ac_power:charging"},
    }
    reserve, meta = soma._power_air_reserve_from_battery_row(ac_row)
    assert reserve == 1.0
    assert meta["band"] == "FLUSH"


def test_somatic_scan_writes_power_air_dimension(tmp_path, monkeypatch):
    monkeypatch.setattr(soma, "_VISCERAL_FIELD_LOG", tmp_path / "visceral_field.jsonl")
    monkeypatch.setattr(soma, "_ENDOCRINE", tmp_path / "endocrine_glands.jsonl")
    monkeypatch.setattr(soma, "_STATE", tmp_path)

    monkeypatch.setattr(soma, "_probe_cardiac_stress", lambda: 0.0)
    monkeypatch.setattr(soma, "_probe_thermal_stress", lambda: 0.0)
    monkeypatch.setattr(soma, "_probe_metabolic_burn", lambda: 0.0)
    monkeypatch.setattr(soma, "_probe_energy_reserve", lambda: 1.0)
    monkeypatch.setattr(soma, "_probe_cellular_age", lambda: 0.0)
    monkeypatch.setattr(soma, "_probe_immune_load", lambda: 0.0)
    monkeypatch.setattr(soma, "_probe_pain_intensity", lambda: 0.0)
    monkeypatch.setattr(soma, "_probe_mirror_lock", lambda: False)
    monkeypatch.setattr(soma, "_probe_truth_continuity", lambda: (1.0, []))
    monkeypatch.setattr(
        soma,
        "_probe_power_air_reserve",
        lambda: (
            0.12,
            {
                "band": "RED_CONSERVE",
                "source": "battery",
                "reason": "battery_critical_9pct",
            },
        ),
    )
    monkeypatch.setattr(soma, "_emit_endocrine_response", lambda *_args, **_kwargs: None)

    field = soma.SwarmSomaticInteroception().scan()

    assert field.power_air_reserve == 0.12
    assert field.power_air_band == "RED_CONSERVE"
    assert field.power_air_source == "battery"
    assert field.soma_score < 1.0

    row = json.loads((tmp_path / "visceral_field.jsonl").read_text().splitlines()[-1])
    assert row["power_air_reserve"] == 0.12
    assert row["power_air_band"] == "RED_CONSERVE"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
