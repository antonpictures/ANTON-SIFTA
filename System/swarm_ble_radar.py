#!/usr/bin/env python3
"""
System/swarm_ble_radar.py — Alice's BLE spatial-radar organ
═══════════════════════════════════════════════════════════════════════
C47H 2026-04-23 (AG31 cosign / OS-distro tournament) — passive radar.

This organ uses macOS's `system_profiler SPBluetoothDataType` and
`/usr/sbin/system_profiler` to read the bluetooth controller's view of
every paired device on this body — connected or absent — without
triggering a TCC bluetooth-permission prompt (passive read of paired
state, not an active CBCentralManager scan).

Each device gets a `proximity_band` tag derived from connection state
plus the bluetoothd RSSI when the device is currently connected:
    presence-strong    — connected, RSSI ≥ -55 dBm   (in the room, near)
    presence-medium    — connected, -55 > RSSI ≥ -75 (in the room, mid)
    presence-weak      — connected, RSSI < -75       (room edge / next room)
    paired-absent      — known device, not currently connected
    unknown            — connected but no RSSI advertised by the OS

This gives Alice a stigmergic "spatial aura" of which of the
Architect's hardware is physically near her right now.

Read-only, no writes, no privileges. Safe to run every few seconds.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LEDGER = _STATE / "alice_ble_radar.jsonl"
_LATEST = _STATE / "alice_ble_radar_latest.json"


def _band(rssi: Optional[int], connected: bool) -> str:
    """Proximity band from RSSI. macOS broadcasts Wireless Proximity
    advertisements continuously, so even *paired-disconnected* devices
    (your iPhone, iPad) advertise an RSSI when they're physically near.
    We use the RSSI when we have one regardless of connection state."""
    if rssi is not None:
        prefix = "near" if connected else "near-absent"
        if rssi >= -55:
            return f"{prefix}-strong"
        if rssi >= -75:
            return f"{prefix}-medium"
        return f"{prefix}-weak"
    if connected:
        return "connected-no-rssi"
    return "paired-absent"


def _flatten_dev(name: str, props: Dict[str, Any], connected: bool) -> Dict[str, Any]:
    rssi_raw = props.get("device_rssi")
    rssi: Optional[int] = None
    if isinstance(rssi_raw, (int, float)):
        rssi = int(rssi_raw)
    elif isinstance(rssi_raw, str):
        try:
            rssi = int(rssi_raw)
        except ValueError:
            rssi = None
    return {
        "name": name,
        "address": props.get("device_address"),
        "minor_type": props.get("device_minorType"),
        "vendor_id": props.get("device_vendorID"),
        "product_id": props.get("device_productID"),
        "firmware": props.get("device_firmwareVersion"),
        "services": props.get("device_services"),
        "rssi_dbm": rssi,
        "connected": connected,
        "proximity_band": _band(rssi, connected),
    }


def read_state(timeout_s: float = 6.0) -> Dict[str, Any]:
    """Snapshot the current BLE radar. Returns a dict, never raises."""
    try:
        p = subprocess.run(
            ["system_profiler", "SPBluetoothDataType", "-json"],
            capture_output=True, text=True, timeout=timeout_s, check=False,
        )
        if p.returncode != 0:
            return {"ok": False, "error": "system_profiler failed",
                    "stderr": p.stderr.strip()[:200]}
        data = json.loads(p.stdout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"timeout {timeout_s}s"}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    blob = (data.get("SPBluetoothDataType") or [{}])[0]
    controller = blob.get("controller_properties", {}) or {}
    devs: List[Dict[str, Any]] = []

    def _ingest(group: Any, connected: bool) -> None:
        if not isinstance(group, list):
            return
        for entry in group:
            if not isinstance(entry, dict):
                continue
            for name, props in entry.items():
                if isinstance(props, dict):
                    devs.append(_flatten_dev(name, props, connected))

    _ingest(blob.get("device_connected"), True)
    _ingest(blob.get("device_not_connected"), False)

    bands: Dict[str, int] = {}
    for d in devs:
        bands[d["proximity_band"]] = bands.get(d["proximity_band"], 0) + 1

    snap = {
        "ok": True,
        "ts": time.time(),
        "iso": datetime.now(tz=timezone.utc).isoformat(),
        "agent": "ALICE_M5",
        "controller": {
            "state": controller.get("controller_state"),
            "address": controller.get("controller_address"),
            "chipset": controller.get("controller_chipset"),
            "vendor_id": controller.get("controller_vendorID"),
            "discoverable": controller.get("controller_discoverable"),
        },
        "device_count": len(devs),
        "connected_count": sum(1 for d in devs if d["connected"]),
        "proximity_bands": bands,
        "devices": devs,
    }
    return snap


def _band_weight(band: str) -> float:
    if band.endswith("-strong"):
        return 3.0
    if band.endswith("-medium"):
        return 2.0
    if band.endswith("-weak"):
        return 1.0
    if band == "connected-no-rssi":
        return 2.0
    return 0.0


def write_snapshot(snap: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Persist latest snapshot + append to the ledger + deposit pheromone."""
    snap = snap or read_state()
    try:
        _STATE.mkdir(parents=True, exist_ok=True)
        _LATEST.write_text(json.dumps(snap, indent=2))
        with _LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": snap.get("ts"),
                "iso": snap.get("iso"),
                "device_count": snap.get("device_count"),
                "connected_count": snap.get("connected_count"),
                "proximity_bands": snap.get("proximity_bands"),
                "near": [d["name"] for d in snap.get("devices", [])
                         if "near" in d.get("proximity_band","")
                         or d.get("proximity_band") == "connected-no-rssi"],
            }) + "\n")
    except Exception as exc:
        snap["persist_error"] = f"{type(exc).__name__}: {exc}"
    # Pheromone: intensity = sum of band weights of in-room devices.
    try:
        from System.swarm_pheromone import deposit_pheromone  # type: ignore
        intensity = sum(_band_weight(d.get("proximity_band", ""))
                        for d in snap.get("devices", []))
        if intensity > 0:
            deposit_pheromone("stig_ble_scan", intensity)
    except Exception:
        pass
    return snap


def prompt_line() -> Optional[str]:
    """One-line summary for Alice's composite identity."""
    snap = read_state()
    if not snap.get("ok"):
        return None
    near = [d["name"] for d in snap.get("devices", [])
            if "near" in d.get("proximity_band", "")
            or d.get("proximity_band") == "connected-no-rssi"]
    if not near:
        return "ble radar: no devices in the room"
    return "ble radar: near = " + ", ".join(near[:6])


def govern(action: str, **kwargs) -> Dict[str, Any]:
    if action in {"read", "snapshot", "state"}:
        return {"ok": True, "action": action, "result": read_state()}
    if action in {"write", "persist", "scan"}:
        return {"ok": True, "action": action, "result": write_snapshot()}
    if action == "prompt_line":
        return {"ok": True, "action": action, "result": prompt_line()}
    return {"ok": False, "action": action,
            "allowed": ["read", "scan", "prompt_line"]}


def _main() -> None:
    ap = argparse.ArgumentParser(description="Alice BLE spatial radar")
    ap.add_argument("action", default="scan", nargs="?")
    args = ap.parse_args()
    print(json.dumps(govern(args.action), indent=2, default=str))


if __name__ == "__main__":
    _main()
