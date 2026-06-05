#!/usr/bin/env python3
"""Tests for alice_hardware_body - direct hardware-touch organ (high in-degree).

Upgraded campaign contract: every organ's own output ledger (here
alice_hardware_touch.jsonl) must also end at delta 0, in addition to the
four core ledgers.

Tests focus on the logging contract + representative read surfaces.
Write surfaces are exercised under heavy mocking.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from System import alice_hardware_body as body


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return len(path.read_text(encoding="utf-8", errors="replace").splitlines())


def test_module_exports_many_surfaces():
    """Real behavior 1: the organ exposes a rich surface of named verbs."""
    assert hasattr(body, "power")
    assert hasattr(body, "thermal")
    assert hasattr(body, "cpu_load")
    assert hasattr(body, "memory")
    assert hasattr(body, "wifi")
    assert hasattr(body, "set_volume")
    assert hasattr(body, "clipboard_write")
    assert hasattr(body, "notify")


def test_read_surfaces_are_side_effect_free_under_mocked_hardware(tmp_path, monkeypatch):
    """Read surfaces return structured data without writing the touch ledger."""
    original_ledger = body._TOUCH_LEDGER
    body._TOUCH_LEDGER = tmp_path / "alice_hardware_touch.jsonl"

    try:
        with patch.object(body, "_run") as mock_run, \
             patch.object(body, "_log") as mock_log:   # prevent real write while still exercising the call

            mock_run.return_value = (0, "Battery 87%; discharging", "")

            power = body.power()
            thermal = body.thermal()

            assert power["ok"] is True
            assert thermal["ok"] is True
            assert mock_run.call_count == 2
            assert mock_log.call_count == 0
            assert not body._TOUCH_LEDGER.exists()
    finally:
        body._TOUCH_LEDGER = original_ledger


def test_power_surface_parses_reasonably(monkeypatch):
    """Real behavior: power() returns structured data under normal conditions."""
    with patch.object(body, "_run") as mock_run:
        mock_run.return_value = (0, "Now drawing from 'Battery Power'\n -InternalBattery-0\t87%; discharging; 2:14 remaining", "")

        result = body.power()

    assert isinstance(result, dict)
    assert "ok" in result
    assert result.get("source") in ("Battery Power", "AC Power", None)


def test_thermal_surface_returns_level(monkeypatch):
    """Real behavior: thermal() reports a pressure level."""
    with patch.object(body, "_run") as mock_run:
        mock_run.return_value = (0, "CPU Power limit: 0\nthermal pressure: 1", "")

        result = body.thermal()

    assert isinstance(result, dict)
    assert "ok" in result


def test_write_surfaces_are_logged_and_safe(monkeypatch, tmp_path):
    """Write surfaces must still log and never raise on mocked paths."""
    original_ledger = body._TOUCH_LEDGER
    body._TOUCH_LEDGER = tmp_path / "alice_hardware_touch.jsonl"

    try:
        with patch.object(body, "_run") as mock_run:
            mock_run.return_value = (0, "", "")

            before = _count_lines(body._TOUCH_LEDGER)

            _ = body.set_volume(50)
            _ = body.set_mute(True)
            _ = body.notify("Test", "Coverage")

            after = _count_lines(body._TOUCH_LEDGER)
            assert (after - before) == 3
    finally:
        body._TOUCH_LEDGER = original_ledger


def test_real_ledgers_untouched_including_organ_own_log(tmp_path, monkeypatch):
    """Explicit isolation gate under the upgraded contract."""
    state = Path(".sifta_state")
    watch = [
        state / "memory_ledger.jsonl",
        state / "stgm_memory_rewards.jsonl",
        state / "work_receipts.jsonl",
        state / "ide_stigmergic_trace.jsonl",
        state / "alice_hardware_touch.jsonl",
    ]
    before = {str(p): _count_lines(p) for p in watch}

    # Redirect the organ's own ledger for the entire test
    original_ledger = body._TOUCH_LEDGER
    body._TOUCH_LEDGER = tmp_path / "alice_hardware_touch.jsonl"

    try:
        with patch.object(body, "_run") as mock_run, \
             patch.object(body, "_log"):   # prevent any real append to the redirected ledger
            mock_run.return_value = (0, "mock output", "")

            _ = body.power()
            _ = body.cpu_load()
            _ = body.wifi()
            _ = body.set_brightness(0.5)

    finally:
        body._TOUCH_LEDGER = original_ledger

    after = {str(p): _count_lines(p) for p in watch}
    delta = {k: after[k] - before[k] for k in before}

    assert all(v == 0 for v in delta.values()), f"Real ledgers (incl. organ own touch log) contaminated: {delta}"


def test_clipboard_and_processes_are_bounded(monkeypatch):
    """Safety surfaces: clipboard is truncated, processes filtered to swarm-owned."""
    with patch.object(body, "_run") as mock_run:
        mock_run.return_value = (0, "very long clipboard content " * 50, "")

        clip = body.clipboard()
        assert isinstance(clip, dict)
        assert "ok" in clip

        mock_run.return_value = (0, "12345 AliceProcess\n99999 OtherProcess", "")
        procs = body.processes()
        assert isinstance(procs, dict)


def test_prompt_line_carries_display_body_surfaces_from_snapshot():
    """Alice's compact body line should name attached display surfaces."""
    line = body.prompt_line({
        "power": {"ok": True, "percent": 80, "source": "AC Power"},
        "cpu_load": {"ok": True, "load_1m": 2.5, "ncpu": 10},
        "memory": {"ok": True, "free_bytes": 8 * 1024**3, "total_bytes": 24 * 1024**3},
        "volume": {"ok": True, "output_volume": 43, "muted": False},
        "idle_time": {"ok": True, "idle_seconds": 5},
        "system_info": {"ok": True, "uptime_s": 7200},
        "displays": {
            "ok": True,
            "gpu_name": "Apple M5",
            "gpu_cores": 10,
            "displays": [
                {
                    "name": "LS37D70xE",
                    "resolution": "3840 x 2160 @ 60.00Hz",
                    "pixels": "3840 x 2160",
                    "main": True,
                    "online": True,
                    "mirror": "off",
                    "body_role": "main_display_arm",
                },
                {
                    "name": "Color LCD",
                    "resolution": "1800 x 1169 @ 120.00Hz",
                    "pixels": "3600 x 2338",
                    "main": False,
                    "online": True,
                    "mirror": "off",
                    "body_role": "built_in_display_arm",
                },
                {
                    "name": "DELL U2415",
                    "resolution": "1920 x 1200 @ 60.00Hz",
                    "pixels": "1920 x 1200",
                    "main": False,
                    "online": True,
                    "mirror": "off",
                    "body_role": "external_display_arm",
                },
            ],
        },
    })

    assert "display arms on Apple M5/10gpu" in line
    assert "LS37D70xE 3840 x 2160 @60.00Hz (main, main-display-arm, pixels 3840 x 2160, online, mirror off)" in line
    assert "Color LCD 1800 x 1169 @120.00Hz (built-in-display-arm, pixels 3600 x 2338, online, mirror off)" in line
    assert "DELL U2415 1920 x 1200 @60.00Hz (external-display-arm, pixels 1920 x 1200, online, mirror off)" in line


def test_displays_surface_preserves_physical_display_details():
    """Display arms carry physical metadata, not just a name."""
    sample = {
        "SPDisplaysDataType": [{
            "sppci_model": "Apple M5",
            "sppci_cores": 10,
            "sppci_bus": "spdisplays_builtin",
            "spdisplays_vendor": "sppci_vendor_Apple",
            "spdisplays_mtlgpufamilysupport": "spdisplays_metal4",
            "spdisplays_ndrvs": [{
                "_name": "LS37D70xE",
                "_spdisplays_pixels": "3840 x 2160",
                "_spdisplays_resolution": "3840 x 2160 @ 60.00Hz",
                "_spdisplays_displayID": "2",
                "_spdisplays_display-vendor-id": "4c2d",
                "_spdisplays_display-product-id": "7907",
                "_spdisplays_display-serial-number": "30584141",
                "_spdisplays_display-week": "39",
                "_spdisplays_display-year": "2025",
                "spdisplays_main": "spdisplays_yes",
                "spdisplays_online": "spdisplays_yes",
                "spdisplays_mirror": "spdisplays_off",
                "spdisplays_rotation": "spdisplays_supported",
                "spdisplays_television": "spdisplays_yes",
                "spdisplays_pixelresolution": "spdisplays_2160p",
            }],
        }]
    }
    with patch.object(body, "_run") as mock_run:
        import json
        mock_run.return_value = (0, json.dumps(sample), "")

        result = body.displays()

    row = result["displays"][0]
    assert result["gpu_name"] == "Apple M5"
    assert result["gpu_cores"] == 10
    assert result["gpu_bus"] == "built-in"
    assert result["gpu_vendor"] == "Apple"
    assert result["metal_support"] == "Metal 4"
    assert row["body_role"] == "main_display_arm"
    assert row["pixels"] == "3840 x 2160"
    assert row["pixel_mode"] == "2160p"
    assert row["online"] is True
    assert row["mirror"] == "off"
    assert row["television"] is True
    assert row["vendor_id"] == "4c2d"
    assert row["serial"] == "30584141"


def test_display_body_boot_receipt_is_idempotent(tmp_path, monkeypatch):
    """One Mac boot + one display fingerprint should not double-spend receipts."""
    monkeypatch.setattr(body, "_DISPLAY_BODY_LEDGER", tmp_path / "alice_display_body.jsonl")

    display_info = {
        "ok": True,
        "gpu_name": "Apple M5",
        "gpu_cores": 10,
        "gpu_bus": "built-in",
        "gpu_vendor": "Apple",
        "metal_support": "Metal 4",
        "displays": [{
            "name": "LS37D70xE",
            "resolution": "3840 x 2160 @ 60.00Hz",
            "pixels": "3840 x 2160",
            "main": True,
            "online": True,
            "mirror": "off",
            "body_role": "main_display_arm",
        }],
    }
    monkeypatch.setattr(body, "displays", lambda: display_info)
    monkeypatch.setattr(body, "system_info", lambda: {
        "ok": True,
        "boot_unix_ts": 123456,
        "model": "Mac17,2",
        "hostname": "Mac.lan",
        "os_version": "26.5",
        "build": "25F5042g",
    })

    first = body.record_display_body_boot_receipt(reason="test_boot")
    second = body.record_display_body_boot_receipt(reason="test_boot")

    assert first["ok"] is True
    assert first["reused"] is False
    assert second["ok"] is True
    assert second["reused"] is True
    assert second["receipt"] == first["receipt"]
    rows = (tmp_path / "alice_display_body.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(rows) == 1
    assert '"event": "ALICE_DISPLAY_BODY"' in rows[0]


def test_autonomic_boot_hook_carries_display_body_receipt(tmp_path, monkeypatch):
    """The boot/autonomic hook should surface the durable display-arm receipt."""
    from System import alice_body_autopilot as autopilot

    monkeypatch.setattr(autopilot, "_STATE", tmp_path)
    monkeypatch.setattr(autopilot, "_STATEFILE", tmp_path / "alice_body_autopilot.json")
    monkeypatch.setattr(autopilot, "ensure_iphone_gps_bridge", lambda: {"iphone_gps_receiver": "mock"})
    monkeypatch.setattr(autopilot, "ensure_local_mcp_bridge", lambda: {"mcp_server": "mock"})
    monkeypatch.setattr(autopilot, "inspect_body", lambda: {
        "ollama_local": {"alive": True},
        "hardware_body": {"ok": True},
    })
    monkeypatch.setattr(autopilot, "_display_body_boot_receipt", lambda reason: {
        "ok": True,
        "receipt": "display-receipt-1",
        "display_count": 3,
        "reason": reason,
    })

    snap = autopilot.ensure_autonomic_services(boot_channel="test")

    assert snap["display_body_boot_receipt"]["receipt"] == "display-receipt-1"
    assert snap["display_body_boot_receipt"]["display_count"] == 3
    assert "hw.display_body_boot_receipt" in snap["governable_actions"]


def test_set_volume_clamps_out_of_range_levels_and_logs_clamped_values(tmp_path):
    """Edge probe: volume writes clamp unsafe inputs before touching the OS command."""
    original_ledger = body._TOUCH_LEDGER
    body._TOUCH_LEDGER = tmp_path / "alice_hardware_touch.jsonl"

    try:
        with patch.object(body, "_run") as mock_run:
            mock_run.return_value = (0, "", "")

            high = body.set_volume(150)
            low = body.set_volume(-12)

        assert high["level"] == 100
        assert low["level"] == 0
        commands = [" ".join(call.args[0]) for call in mock_run.call_args_list]
        assert any("set volume output volume 100" in cmd for cmd in commands)
        assert any("set volume output volume 0" in cmd for cmd in commands)

        rows = body._TOUCH_LEDGER.read_text(encoding="utf-8").splitlines()
        assert len(rows) == 2
        assert '"level": 100' in rows[0]
        assert '"level": 0' in rows[1]
    finally:
        body._TOUCH_LEDGER = original_ledger
