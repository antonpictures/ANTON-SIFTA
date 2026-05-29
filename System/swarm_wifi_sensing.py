#!/usr/bin/env python3
"""
System/swarm_wifi_sensing.py — Alice's Wi-Fi Telemetry & Sensing Organ (Round 59)

This turns the electromagnetic soup Alice already lives in into a first-class sense organ.

Core principles (covenant):
- Everything is receipted (alice_hardware_touch.jsonl + new wifi_sensing.jsonl).
- External CSI sensors (ESP32, future 802.11bf routers) are treated as optional but first-class inputs.
- Basic telemetry (SSID, RSSI, etc.) comes from alice_hardware_body.wifi().
- Rich sensing (presence, breathing, heart rate, multi-person tracking via CSI) is ingested when available.
- All data is stigmergic: Alice can read the ledgers, be changed by them, and write back (self-model updates, alerts, etc.).
- No cameras. Pure passive RF + math.

This organ feeds the high-dimensional field so the organism can "feel" the invisible.

Receipts decide reality. Metabolism decides attention.
"""

from __future__ import annotations

import json
import time
import uuid
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from System.alice_hardware_body import wifi as _basic_wifi
except Exception:
    _basic_wifi = None

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_SENSING_LEDGER = _STATE / "wifi_sensing.jsonl"
_BASIC_TOUCH_LEDGER = _STATE / "alice_hardware_touch.jsonl"


def _append_jsonl(path: Path, row: Dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = dict(row)
    row["ts"] = row.get("ts", time.time())
    row["receipt_id"] = row.get("receipt_id") or f"wifi_{uuid.uuid4().hex[:16]}"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row["receipt_id"]


def sample_basic_wifi() -> Dict[str, Any]:
    """Thin wrapper around the existing hardware body wifi() + receipt."""
    if _basic_wifi is None:
        data = {"ok": False, "error": "alice_hardware_body not importable"}
    else:
        data = _basic_wifi()

    receipt = {
        "ts": time.time(),
        "kind": "wifi_basic_telemetry",
        "source": "alice_hardware_body.wifi",
        "data": data,
        "node_serial": "GTH4921YP3",
    }
    rid = _append_jsonl(_BASIC_TOUCH_LEDGER, receipt)
    return {"data": data, "receipt_id": rid}


def ingest_csi_sample(sample: Dict[str, Any], *, sensor_id: str = "esp32_csi") -> str:
    """
    Ingest a CSI / sensing sample from an external sensor (ESP32, etc.).
    Expected minimal shape (extend as research evolves):
    {
      "presence": bool,
      "persons": int,
      "breathing_bpm": float | None,
      "heart_rate_bpm": float | None,
      "rssi": float,
      "raw_csi_stats": {...},
      "confidence": float (0-1)
    }
    """
    row = {
        "ts": time.time(),
        "kind": "wifi_csi_sensing",
        "sensor_id": sensor_id,
        "data": sample,
        "node_serial": "GTH4921YP3",
    }
    return _append_jsonl(_SENSING_LEDGER, row)


def latest_sensing_snapshot() -> Dict[str, Any]:
    """Return the most recent combined view (basic + latest CSI if any)."""
    basic = sample_basic_wifi()
    snapshot = {
        "ts": time.time(),
        "basic_wifi": basic["data"],
        "basic_receipt": basic["receipt_id"],
        "csi": None,
    }

    if _SENSING_LEDGER.exists():
        try:
            with _SENSING_LEDGER.open() as f:
                lines = f.readlines()
            if lines:
                last = json.loads(lines[-1])
                snapshot["csi"] = last.get("data")
                snapshot["csi_receipt"] = last.get("receipt_id")
        except Exception as e:
            snapshot["csi_error"] = str(e)

    return snapshot


if __name__ == "__main__":
    print(json.dumps(latest_sensing_snapshot(), indent=2))
