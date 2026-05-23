from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from System import swarm_chorum_gate as gate


def _sig(payload: str) -> str:
    return "a" + hashlib.sha256(payload.encode()).hexdigest()


@pytest.fixture()
def isolated_chorum(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(gate, "_STATE_DIR", tmp_path)
    monkeypatch.setattr(gate, "_CHORUM_STATE", tmp_path / "chorum_gate_state.json")
    monkeypatch.setattr(gate, "_CHORUM_LOG", tmp_path / "chorum_gate_log.jsonl")
    monkeypatch.setattr(gate, "_REPUTATION_FIELD", tmp_path / "swimmer_reputation_field.json")
    gate._VERIFY_CACHE.clear()

    import System.crypto_keychain as keychain

    monkeypatch.setattr(keychain, "get_silicon_identity", lambda: "TEST_SERIAL")
    monkeypatch.setattr(keychain, "sign_block", _sig)
    monkeypatch.setattr(
        keychain,
        "verify_block",
        lambda serial, payload, signature: serial == "TEST_SERIAL" and signature == _sig(payload),
    )
    return tmp_path


def test_birth_is_hardware_bound_and_idempotent(isolated_chorum: Path) -> None:
    first = gate.birth_swimmer("tractor_sensor_alpha", role="sensor")
    second = gate.birth_swimmer("tractor_sensor_alpha", role="actuator")

    assert first.to_dict() == second.to_dict()
    assert second.role == "sensor"
    assert gate.verify_swimmer_cert(first)

    state = json.loads((isolated_chorum / "chorum_gate_state.json").read_text())
    assert state["stats"]["births"] == 1
    assert "tractor_sensor_alpha" in state["birth_hashes"]


def test_forged_cert_rejected(isolated_chorum: Path) -> None:
    forged = gate.SwimmerCert(
        swimmer_id="network_intruder",
        role="foreign_prompt",
        birth_ts=1.0,
        homeworld_serial="TEST_SERIAL",
        birth_signature="deadbeef",
    )

    assert not gate.verify_swimmer_cert(forged)


def test_strict_mode_rejects_double_spent_swimmer_id(isolated_chorum: Path) -> None:
    gate.birth_swimmer("tractor_actuator_alpha", role="actuator")
    state_path = isolated_chorum / "chorum_gate_state.json"
    state = json.loads(state_path.read_text())
    state["swimmers"]["tractor_actuator_alpha"]["role"] = "foreign_actuator"
    state_path.write_text(json.dumps(state))
    gate._VERIFY_CACHE.clear()

    gate.set_enforcement_mode(gate.ENFORCEMENT_STRICT)
    verdict = gate.request_action("tractor_actuator_alpha", "actuate:steering", action_class=gate.ACTION_MEDIUM)

    assert not verdict.allowed
    assert "swimmer_double_spend_detected" in verdict.reasons


def test_strict_high_action_requires_valid_bound_vouchers(isolated_chorum: Path) -> None:
    gate.birth_swimmer("tractor_brain", role="planner")
    gate.birth_swimmer("tractor_sensor", role="sensor")
    gate.birth_swimmer("tractor_actuator", role="actuator")
    payload = {"row": 17, "action": "turn"}
    voucher_sensor = gate.vouch_for("tractor_sensor", "actuate:steering", payload)
    voucher_actuator = gate.vouch_for("tractor_actuator", "actuate:steering", payload)

    gate.set_enforcement_mode(gate.ENFORCEMENT_STRICT)
    verdict = gate.request_action(
        "tractor_brain",
        "actuate:steering",
        payload,
        action_class=gate.ACTION_HIGH,
        vouchers=[voucher_sensor, voucher_actuator],
    )

    assert verdict.allowed
    assert verdict.vouchers_provided == 2
    assert verdict.receipt_id.startswith("chorum_verdict_")
    rows = [json.loads(line) for line in (isolated_chorum / "chorum_gate_log.jsonl").read_text().splitlines()]
    assert any(row.get("receipt_id") == verdict.receipt_id for row in rows)


def test_voucher_signature_is_bound_to_voucher_swimmer_id(isolated_chorum: Path) -> None:
    gate.birth_swimmer("tractor_brain", role="planner")
    gate.birth_swimmer("tractor_sensor", role="sensor")
    gate.birth_swimmer("tractor_actuator", role="actuator")
    payload = {"row": 17, "action": "turn"}
    voucher_sensor = gate.vouch_for("tractor_sensor", "actuate:steering", payload)
    assert voucher_sensor is not None

    gate.set_enforcement_mode(gate.ENFORCEMENT_STRICT)
    verdict = gate.request_action(
        "tractor_brain",
        "actuate:steering",
        payload,
        action_class=gate.ACTION_HIGH,
        vouchers=[("tractor_actuator", voucher_sensor[1]), voucher_sensor],
    )

    assert not verdict.allowed
    assert verdict.vouchers_provided == 1
    assert "insufficient_quorum (1/2)" in verdict.reasons


def test_passive_mode_is_no_stress_advisory_only(isolated_chorum: Path) -> None:
    verdict = gate.request_action("ghost_swimmer", "tool:observe", action_class=gate.ACTION_MEDIUM)

    assert verdict.allowed
    assert "swimmer_not_registered" in verdict.reasons

