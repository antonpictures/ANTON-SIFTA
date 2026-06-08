#!/usr/bin/env python3
"""Tests for the body-schema self-model composer (Cowork lane, 2026-05-30).

Drives the composer with tmp ledgers so the felt+power unification is verified
without the live insular cortex or a real battery.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System import swarm_body_schema_self_model as bs


def _write(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def _seed(tmp_path, *, soma=True, power=True):
    state = tmp_path / ".sifta_state"
    if soma:
        _write(state / "visceral_field.jsonl", {"soma_score": 0.62, "soma_label": "STABLE"})
    if power:
        _write(state / "battery_metabolism.jsonl", {
            "battery": {"percent": 41, "source": "battery", "status": "discharging"},
            "metabolic": {"band": "NORMAL"},
        })
    return tmp_path


def test_composes_felt_and_power(tmp_path):
    _seed(tmp_path)
    out = bs.compose_body_schema(state_dir=tmp_path)
    assert out["felt"]["soma_label"] == "STABLE"
    assert out["felt"]["present"] is True
    assert out["power"]["band"] == "NORMAL"
    assert out["power"]["percent"] == 41
    assert "STABLE" in out["first_person"]
    assert "41%" in out["first_person"]
    assert "battery" in out["first_person"]


def test_handles_missing_power_honestly(tmp_path):
    _seed(tmp_path, power=False)
    out = bs.compose_body_schema(state_dir=tmp_path)
    assert out["power"]["present"] is False
    assert "cannot feel my electricity yet" in out["first_person"]


def test_power_falls_back_to_visceral_air_signal(tmp_path):
    state = tmp_path / ".sifta_state"
    _write(state / "visceral_field.jsonl", {
        "soma_score": 1.0,
        "soma_label": "THRIVING",
        "power_air_band": "FLUSH",
        "power_air_source": "ac",
        "power_air_reserve": 1.0,
    })
    out = bs.compose_body_schema(state_dir=tmp_path)
    assert out["power"]["present"] is True
    assert out["power"]["band"] == "FLUSH"
    assert out["power"]["source"] == "ac"
    assert out["power"]["reserve"] == 1.0
    assert "wall power" in out["first_person"]


def test_handles_missing_felt_honestly(tmp_path):
    _seed(tmp_path, soma=False)
    out = bs.compose_body_schema(state_dir=tmp_path)
    assert out["felt"]["present"] is False
    assert "cannot read my felt state" in out["first_person"]


def test_empty_everything_does_not_crash(tmp_path):
    out = bs.compose_body_schema(state_dir=tmp_path)
    assert out["felt"]["present"] is False
    assert out["power"]["present"] is False
    assert out["first_person"].startswith("MY BODY RIGHT NOW:")


def test_uses_latest_row(tmp_path):
    state = tmp_path / ".sifta_state"
    _write(state / "visceral_field.jsonl", {"soma_score": 0.2, "soma_label": "DISTRESSED"})
    _write(state / "visceral_field.jsonl", {"soma_score": 0.85, "soma_label": "THRIVING"})
    out = bs.compose_body_schema(state_dir=tmp_path)
    assert out["felt"]["soma_label"] == "THRIVING"


def test_sample_writes_receipt(tmp_path):
    _seed(tmp_path)
    bs.sample(state_dir=tmp_path)
    ledger = tmp_path / ".sifta_state" / "body_schema.jsonl"
    assert ledger.exists() and ledger.read_text().strip()
    row = json.loads(ledger.read_text().strip().splitlines()[-1])
    assert row["truth_label"] == bs.TRUTH_LABEL


def test_prompt_block_first_person(tmp_path):
    _seed(tmp_path)
    block = bs.prompt_block(state_dir=tmp_path)
    assert block.startswith("MY BODY RIGHT NOW:")
    assert "read-only" in block


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
