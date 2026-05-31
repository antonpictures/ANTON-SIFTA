from __future__ import annotations

import json

from System import swarm_reachy_effector as reachy


def test_build_reachy_plan_accepts_supported_action() -> None:
    plan = reachy.build_reachy_plan("speak", {"text": "hello reachy"})
    assert plan["ok"] is True
    assert plan["action_type"] == "speak"
    assert plan["truth_label"] == "REACHY_STIGMERGIC_EFFECTOR_V1"


def test_execute_request_stub_writes_receipt_and_sensor_echo(tmp_path, monkeypatch) -> None:
    ledger = tmp_path / "reachy_effector_organ.jsonl"
    monkeypatch.setattr(reachy, "LEDGER", ledger)

    request = reachy.ReachyRequest(
        ts=100.0,
        action_type="move",
        payload={"joint_targets": {"neck_pan": 0.1}, "duration_s": 0.5},
        source_ide="unit_test",
        homeworld_serial="GTH4921YP3",
    )
    result = reachy.execute_request_stub(request)

    assert result["ok"] is True
    assert result["ledger"] == str(ledger)
    assert result["sensor_echo"]["kind"] == "reachy_motion_observation"
    assert ledger.exists()

    row = json.loads(ledger.read_text(encoding="utf-8").splitlines()[-1])
    assert row["kind"] == "reachy_effector_receipt"
    assert row["truth_label"] == "REACHY_STIGMERGIC_EFFECTOR_V1"
    assert row["status"] == "ok"


def test_unknown_action_returns_error_receipt(tmp_path, monkeypatch) -> None:
    ledger = tmp_path / "reachy_effector_organ.jsonl"
    monkeypatch.setattr(reachy, "LEDGER", ledger)

    request = reachy.ReachyRequest(
        ts=100.0,
        action_type="dance",
        payload={},
        source_ide="unit_test",
        homeworld_serial="GTH4921YP3",
    )
    result = reachy.execute_request_stub(request)

    assert result["ok"] is False
    assert "unsupported_reachy_action" in result["reason"]
    assert ledger.exists()
