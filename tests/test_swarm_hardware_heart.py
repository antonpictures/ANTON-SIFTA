import json
from pathlib import Path

from System.swarm_hardware_heart import (
    format_heart_reply,
    pulse_hardware_heart,
)


def test_hardware_heart_writes_monotonic_and_sensor_fields(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("System.swarm_hardware_heart.platform.system", lambda: "Darwin")
    monkeypatch.setattr("System.swarm_hardware_heart.platform.platform", lambda: "macOS-test")
    monkeypatch.setattr("System.swarm_hardware_heart.shutil.which", lambda exe: "/usr/bin/powermetrics")

    def fake_run(cmd, timeout):
        assert "powermetrics" in cmd[0]
        return 0, "Average package power: 7.25 W\nCPU die temperature: 51.5 C\n", ""

    row = pulse_hardware_heart(
        state_dir=tmp_path,
        run_cmd=fake_run,
        monotonic_ns_fn=lambda: 123456789,
        now_fn=lambda: 1781226000.0,
    )

    assert row["schema"] == "SIFTA_HARDWARE_HEART_V1"
    assert row["monotonic_ns"] == 123456789
    assert row["power_watts"] == 7.25
    assert row["temperature_c"] == 51.5
    assert row["sensor_status"] == "ok"
    ledger = tmp_path / "hardware_heart.jsonl"
    saved = json.loads(ledger.read_text(encoding="utf-8").splitlines()[-1])
    assert saved["receipt_id"] == row["receipt_id"]
    reply = format_heart_reply(row)
    assert "power=7.25 W" in reply
    assert "temp=51.5 C" in reply


def test_hardware_heart_receipts_unavailable_sensor_without_faking(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("System.swarm_hardware_heart.platform.system", lambda: "Darwin")
    monkeypatch.setattr("System.swarm_hardware_heart.shutil.which", lambda exe: None)
    monkeypatch.setattr(
        "System.swarm_hardware_heart._probe_unprivileged_body",
        lambda: {
            "sensor_source": "alice_hardware_body",
            "sensor_tier": "unprivileged_body",
            "sensor_status": "unavailable",
            "sensor_reason": "test no body sensor",
            "power_watts": None,
            "temperature_c": None,
        },
    )

    row = pulse_hardware_heart(
        state_dir=tmp_path,
        monotonic_ns_fn=lambda: 987,
        now_fn=lambda: 1781226001.0,
    )

    assert row["monotonic_ns"] == 987
    assert row["power_watts"] is None
    assert row["temperature_c"] is None
    assert row["sensor_status"] == "unavailable"
    assert "sensor unavailable" in format_heart_reply(row)


def test_hardware_heart_writes_alias_snapshot_and_derived_bpm(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("System.swarm_hardware_heart.platform.system", lambda: "Darwin")
    monkeypatch.setattr("System.swarm_hardware_heart.platform.platform", lambda: "macOS-test")
    monkeypatch.setattr(
        "System.swarm_hardware_heart._probe_unprivileged_body",
        lambda: {
            "sensor_source": "alice_hardware_body",
            "sensor_tier": "unprivileged_body",
            "sensor_status": "partial",
            "sensor_reason": "battery/source/thermal-pressure observed",
            "power_watts": None,
            "temperature_c": None,
            "battery_percent": 91,
            "power_source": "AC Power",
            "metabolic_band": "FLUSH",
            "activity_multiplier": 1.25,
            "conserve": False,
        },
    )

    pulse_hardware_heart(
        state_dir=tmp_path,
        monotonic_ns_fn=lambda: 1_000_000_000,
        now_fn=lambda: 1781226001.0,
        privileged_probe=False,
        source="test_first",
    )
    row = pulse_hardware_heart(
        state_dir=tmp_path,
        monotonic_ns_fn=lambda: 3_000_000_000,
        now_fn=lambda: 1781226003.0,
        privileged_probe=False,
        source="test_second",
    )

    assert row["last_interval_s"] == 2.0
    assert row["bpm_derived"] == 30.0
    assert row["sensor_tier"] == "unprivileged_body"
    assert row["battery_percent"] == 91
    assert row["metabolic_band"] == "FLUSH"

    primary_rows = (tmp_path / "hardware_heart.jsonl").read_text(encoding="utf-8").splitlines()
    alias_rows = (tmp_path / "alice_body_heart.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(primary_rows) == 2
    assert len(alias_rows) == 2
    assert json.loads(alias_rows[-1])["receipt_id"] == row["receipt_id"]
    assert json.loads((tmp_path / "hardware_heart.json").read_text(encoding="utf-8"))["receipt_id"] == row["receipt_id"]
    assert json.loads((tmp_path / "alice_body_heart.json").read_text(encoding="utf-8"))["receipt_id"] == row["receipt_id"]

    reply = format_heart_reply(row)
    assert "30.0 bpm" in reply
    assert "battery: 91%" in reply
    assert "budget: FLUSH" in reply
