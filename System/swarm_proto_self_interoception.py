"""
Q4 — Proto-Self Interoception
Damasio, A. (1999). The Feeling of What Happens. Harcourt Brace. Ch.7–8.
Damasio, A. (2010). Self Comes to Mind. Pantheon. Ch.4.

Maps macOS system calls to the interoceptive signals Damasio identifies
as necessary for proto-self formation (body-state representation,
moment-to-moment):

    CPU temperature  ≈  metabolic heat / fever
    Thermal pressure ≈  allostatic load
    Battery state    ≈  energy reserve / hunger
    Disk I/O latency ≈  visceral processing load
    Uptime           ≈  wakefulness duration

Writes to proto_self_interoception.jsonl (append-only).
Kill-switch: SIFTA_INTEROCEPTION_DISABLE=1.

Integration point: call read_proto_self_interoception() from
body_brain_tick or temporal self-model update.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from System.swarm_persistent_owner_history import state_dir
except ImportError:
    def state_dir(root=None):  # type: ignore
        return Path(root) if root else Path(".sifta_state")

try:
    from System.jsonl_file_lock import append_line_locked
except ImportError:
    def append_line_locked(path: Path, line: str, **kw) -> None:  # type: ignore
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", **kw) as f:
            f.write(line)

_DISABLE_ENV = "SIFTA_INTEROCEPTION_DISABLE"
LOG_NAME = "proto_self_interoception.jsonl"


def _sysctl(key: str) -> Optional[str]:
    try:
        result = subprocess.run(
            ["sysctl", "-n", key],
            capture_output=True, text=True, timeout=2
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


def _powermetrics_thermal() -> Optional[str]:
    """Read Apple Silicon thermal pressure via sysctl."""
    # macOS 12+ exposes kern.thermald.mode or similar
    for key in ("kern.thermald.mode", "machdep.xcpm.cpu_thermal_level",
                "kern.thermal_level"):
        v = _sysctl(key)
        if v:
            return v
    return None


def _battery_state() -> Dict[str, Any]:
    """Read battery state via pmset or sysctl."""
    result: Dict[str, Any] = {"source": "unknown", "percent": None, "charging": None}
    try:
        out = subprocess.run(
            ["pmset", "-g", "batt"],
            capture_output=True, text=True, timeout=3
        ).stdout
        if "InternalBattery" in out:
            import re
            pct = re.search(r"(\d+)%", out)
            if pct:
                result["percent"] = int(pct.group(1))
            result["charging"] = "charging" in out.lower() or "ac power" in out.lower()
            result["source"] = "battery" if "Battery Power" in out else "ac"
    except Exception:
        pass
    return result


def _uptime_seconds() -> float:
    try:
        v = _sysctl("kern.boottime")
        if v and "sec = " in v:
            import re
            m = re.search(r"sec = (\d+)", v)
            if m:
                return time.time() - float(m.group(1))
    except Exception:
        pass
    # Fallback: parse uptime command
    try:
        out = subprocess.run(["uptime"], capture_output=True, text=True, timeout=2).stdout
        # "up X days, Y:ZZ" or "up Y:ZZ"
        import re
        m = re.search(r"up\s+(?:(\d+)\s+days?,\s*)?(\d+):(\d+)", out)
        if m:
            days = int(m.group(1) or 0)
            hours = int(m.group(2))
            mins = int(m.group(3))
            return (days * 86400 + hours * 3600 + mins * 60)
    except Exception:
        pass
    return 0.0


def _cpu_load_percent() -> float:
    """Rough CPU load from sysctl (macOS)."""
    try:
        v = _sysctl("vm.loadavg")  # e.g. "{ 0.52 0.48 0.41 }"
        if v:
            nums = [float(x) for x in v.strip("{}").split() if x.replace(".", "").isdigit()]
            if nums:
                # 1-min load average normalised to 0-1 (assumes ≤8 cores typical)
                return min(1.0, nums[0] / 8.0)
    except Exception:
        pass
    return 0.0


def read_proto_self_interoception(
    *,
    root: Optional[Path] = None,
    write_ledger: bool = True,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Q4 — Read macOS interoceptive signals and map them to Damasio proto-self.

    Returns a dict (and optionally writes to proto_self_interoception.jsonl):
        cpu_load_norm         — 0–1 proxy for metabolic heat
        thermal_pressure      — string or None
        battery_percent       — 0–100 or None
        battery_source        — "battery" | "ac" | "unknown"
        battery_charging      — bool
        uptime_hours          — float (wakefulness duration)
        allostatic_load_norm  — composite 0–1 (high = organism is stressed)
        truth_label           — "PROTO_SELF_INTEROCEPTION"

    Damasio (1999) mapping:
        metabolic heat → cpu_load_norm
        allostatic load → allostatic_load_norm (composite)
        energy reserve → battery_percent / 100
        wakefulness → uptime_hours
    """
    if os.environ.get(_DISABLE_ENV, "").strip() == "1":
        return {"disabled": True, "truth_label": "PROTO_SELF_INTEROCEPTION"}

    batt = _battery_state()
    cpu_load = _cpu_load_percent()
    uptime_s = _uptime_seconds()
    thermal  = _powermetrics_thermal()

    # energy reserve (1.0 = full, 0.0 = empty or AC unknown)
    batt_pct = batt.get("percent")
    energy_reserve = (batt_pct / 100.0) if batt_pct is not None else 0.8

    # Allostatic load: composite of CPU heat + battery depletion rate + uptime
    # High uptime = more fatigue proxy, low battery = resource stress
    uptime_norm = min(1.0, uptime_s / (24.0 * 3600.0))  # 0 to 1 over 24h
    allostatic_load = round(0.4 * cpu_load + 0.3 * (1.0 - energy_reserve) + 0.3 * uptime_norm, 4)

    row: Dict[str, Any] = {
        "ts":                 now or time.time(),
        "trace_id":           str(uuid.uuid4()),
        "kind":               "PROTO_SELF_INTEROCEPTION",
        "truth_label":        "PROTO_SELF_INTEROCEPTION",
        "cpu_load_norm":      round(cpu_load, 4),
        "thermal_pressure":   thermal,
        "battery_percent":    batt_pct,
        "battery_source":     batt.get("source", "unknown"),
        "battery_charging":   bool(batt.get("charging")),
        "uptime_seconds":     round(uptime_s, 1),
        "uptime_hours":       round(uptime_s / 3600.0, 3),
        "energy_reserve_norm": round(energy_reserve, 4),
        "allostatic_load_norm": allostatic_load,
        "damasio_mapping": {
            "metabolic_heat":    round(cpu_load, 4),
            "allostatic_load":   allostatic_load,
            "energy_reserve":    round(energy_reserve, 4),
            "wakefulness_hours": round(uptime_s / 3600.0, 3),
        },
        "provenance": "Damasio1999Ch7-8; Damasio2010Ch4",
    }

    if write_ledger:
        append_line_locked(
            state_dir(root) / LOG_NAME,
            json.dumps(row, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return row


def summary_for_prompt(*, root: Optional[Path] = None) -> str:
    sd = state_dir(root)
    log = sd / LOG_NAME
    if not log.exists():
        return ""
    try:
        lines = [l for l in log.read_text(errors="ignore").splitlines() if l.strip()]
        if not lines:
            return ""
        row = json.loads(lines[-1])
    except Exception:
        return ""
    allo = row.get("allostatic_load_norm", "?")
    batt = row.get("battery_percent", "?")
    uptime = row.get("uptime_hours", "?")
    return (
        f"PROTO-SELF INTEROCEPTION (Q4 — Damasio 1999):\n"
        f"- allostatic_load={allo} | battery={batt}% | uptime={uptime}h"
    )
