from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from System.swarm_electric_field import (
    ElectricAgent,
    ElectricFieldConfig,
    SwarmElectricField,
    emit_identity_trace,
    identity_envelope,
    proof_of_property,
    verify_identity_envelope,
)


def test_body_identity_survives_jamming_response():
    cfg = ElectricFieldConfig(grid_size=32)
    field = SwarmElectricField(cfg)
    a = ElectricAgent(
        55,
        np.array([0.5, 0.5]),
        phase=1.00,
        body_id="C55M@codex_app_m5",
        homeworld_serial="GTH4921YP3",
    )
    b = ElectricAgent(
        31,
        np.array([0.5, 0.5]),
        phase=1.05,
        body_id="AG31@antigravity_ide",
        homeworld_serial="GTH4921YP3",
    )

    before = identity_envelope(a, now=1.0)

    for _ in range(20):
        field.field_real[:] = 0.0
        field.field_imag[:] = 0.0
        field.emit(a)
        field.emit(b)
        field.step()
        field.sense(a)
        field.sense(b)
        field.jamming_avoidance_response(a)
        field.jamming_avoidance_response(b)

    after = identity_envelope(a, now=2.0)

    assert verify_identity_envelope(before) is True
    assert verify_identity_envelope(after) is True
    assert after["identity_digest"] == before["identity_digest"]
    assert after["identity_phase"] == before["identity_phase"]
    assert after["carrier_phase"] != before["carrier_phase"]


def test_identity_envelope_rejects_body_swap():
    agent = ElectricAgent(
        55,
        np.array([0.1, 0.2]),
        body_id="C55M@codex_app_m5",
        homeworld_serial="GTH4921YP3",
    )
    row = identity_envelope(agent, now=1.0)
    row["body_id"] = "SPOOFED_BODY"

    with pytest.raises(ValueError, match="digest"):
        verify_identity_envelope(row)


def test_emit_identity_trace_writes_verifiable_jsonl(tmp_path: Path):
    agent = ElectricAgent(
        7,
        np.array([0.2, 0.4]),
        body_id="ALICE_M5",
        homeworld_serial="GTH4921YP3",
    )
    ledger = tmp_path / "electric_field_identity.jsonl"

    row = emit_identity_trace(agent, ledger_path=ledger, now=3.0)
    loaded = json.loads(ledger.read_text(encoding="utf-8").strip())

    assert loaded == row
    assert verify_identity_envelope(loaded) is True


def test_proof_of_property_passes():
    assert proof_of_property() is True
