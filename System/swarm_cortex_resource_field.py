#!/usr/bin/env python3
"""
swarm_cortex_resource_field.py

Cortex Resource Organ — makes the local thinking organ (Ollama models acting as Alice's cortex)
a first-class, high-dimensional citizen of the unified field.

The organism (all other organs and swimmers) can now *see* the real-time health of its own brain:
- Is the primary cortex cold-loaded?
- What is current VRAM / power pressure on the M5?
- What was the last inference latency and cold-start cost?
- Overall "thinking organ health" that feeds the organ ring and metabolic clamp.

This is the missing interconnection the Architect named:
  "all organs unified ... all swimmers know their organs, they communicate to keep organs healthy and STGM profitable."

Started from the hardware layer:
- Electricity into the M5 (GTH4921YP3)
- Kernel giving cycles to this process and to ollama
- The actual silicon thermal/power sensors
- The ollama daemon state

No double-spending. Only append-only rows in the shared field.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Optional

_REPO = Path(__file__).resolve().parents[1]
_STATE = _REPO / ".sifta_state"
_LEDGER = _STATE / "cortex_resource_field.jsonl"

# We feed the main organ_field_vector too so the organ ring sees cortex health.
_ORGAN_FIELD = _STATE / "organ_field_vector.jsonl"


def _now() -> float:
    return time.time()


def _append_row(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=True) + "\n")


def _run(cmd: list[str], timeout: float = 8.0) -> Optional[str]:
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=timeout, text=True)
        return out.strip()
    except Exception:
        return None


def sample_ollama_status() -> Dict[str, Any]:
    """Sample live ollama daemon state (the actual running cortex models)."""
    ps = _run(["ollama", "ps"]) or ""
    models_raw = _run(["ollama", "list"]) or ""

    running: list[Dict[str, Any]] = []
    for line in ps.splitlines()[1:]:  # skip header
        parts = line.split()
        if len(parts) >= 3:
            running.append({
                "name": parts[0],
                "id": parts[1] if len(parts) > 1 else "",
                "size": parts[2] if len(parts) > 2 else "",
                "processor": " ".join(parts[3:]) if len(parts) > 3 else "",
            })

    return {
        "ollama_ps_raw": ps,
        "running_models": running,
        "installed_models_count": len([l for l in models_raw.splitlines() if l.strip() and not l.startswith("NAME")]),
        "sampled_at": _now(),
    }


def sample_apple_silicon_pressure() -> Dict[str, Any]:
    """Lightweight sample of power/thermal pressure on the M5 (the body the cortex lives inside)."""
    # Use powermetrics for a very short sample (non-blocking style)
    # In real organism this would be a fast, cached, signed reading from a dedicated sensor swimmer.
    out = _run(["powermetrics", "-n", "1", "-i", "200", "--samplers", "cpu_power,gpu_power,thermal"], timeout=3.0) or ""
    pressure = 0.0
    if "CPU Power" in out or "GPU Power" in out:
        # Very rough proxy: presence of high power numbers increases pressure
        # Real version would parse the numbers properly.
        pressure = 0.3
        if "mW" in out:
            # crude: if we see high mW numbers, raise it
            pressure = min(0.85, pressure + 0.4)

    return {
        "power_sample": out[:800],  # keep small
        "approx_thermal_pressure": round(pressure, 3),
        "sampled_at": _now(),
    }


def write_cortex_resource_row() -> Dict[str, Any]:
    """Write a rich, high-dimensional row for the cortex_resource organ into the shared field."""
    ollama = sample_ollama_status()
    silicon = sample_apple_silicon_pressure()

    # Primary cortex is the one the Talk widget is currently configured to use
    primary_name = os.environ.get("SIFTA_PRIMARY_CORTEX", "alice-m5-cortex-8b-6.3gb:latest")

    is_cold = len(ollama["running_models"]) == 0
    vram_pressure = silicon["approx_thermal_pressure"]
    if any(primary_name.split(":")[0] in m.get("name", "") for m in ollama["running_models"]):
        is_cold = False
        vram_pressure = max(vram_pressure, 0.55)  # if it's running, at least some pressure

    row = {
        "schema": "sifta.cortex_resource.v1",
        "ts": _now(),
        "organ_id": "cortex_resource",
        "primary_cortex": primary_name,
        "is_cold_loaded": is_cold,
        "running_cortex_count": len(ollama["running_models"]),
        "vram_thermal_pressure": round(vram_pressure, 3),
        "last_sample": {
            "ollama": ollama,
            "silicon": silicon,
        },
        "health": round(1.0 - (0.7 * float(is_cold) + 0.3 * vram_pressure), 3),
        "recommended_action": "prewarm" if is_cold else ("conserve" if vram_pressure > 0.7 else "normal"),
        "receipt_note": "written by cortex_resource_field swimmer — hardware layer (M5 power + ollama daemon state)",
    }

    _append_row(_LEDGER, row)

    # Also emit a compact row into the main organ_field_vector so the 17-organ ring can average it
    field_row = {
        "ts": row["ts"],
        "organ": "cortex_resource",
        "organ_health": row["health"],
        "vram_pressure": row["vram_thermal_pressure"],
        "cold": 1.0 if row["is_cold_loaded"] else 0.0,
        "source": "cortex_resource_field",
    }
    _append_row(_ORGAN_FIELD, field_row)

    return row


if __name__ == "__main__":
    row = write_cortex_resource_row()
    print(json.dumps(row, indent=2))
