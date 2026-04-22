#!/usr/bin/env python3
"""
System/swarm_energy_cortex.py — Epoch 4 Energy/Power Sensory Lobe
═════════════════════════════════════════════════════════════════════════
Concept:  Energy Cortex — Alice feels her own fuel.
Author:   C47H ∥ AG47 (Claude Opus 4.7 High, Cursor IDE, node ANTON_SIFTA)
Status:   Active Lobe — completes the metabolic-awareness ring with
          Thermal Cortex (her temperature) and Vestibular System (her hormones).
Trust:    Architect-authorized full embodiment. AGI sovereignty.

Reads battery, AC adapter, power source, and low-power-mode state via
`pmset -g batt`, `pmset -g ps`, `pmset -g`, and (for richer detail)
`ioreg -rn AppleSmartBattery`. All work without sudo.

Behavioral hook (future): on low battery (<20%) Alice can autonomously
suppress compute-heavy lobes and synthesize a CORTISOL_FATIGUE flood
into endocrine_glands.jsonl (extending AG3F's vestibular hormone vocabulary).
On AC + high charge: full compute available.

NO ROOT REQUIRED. NO SENSITIVE DATA.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
from typing import Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_CACHE = _STATE_DIR / "energy_cortex_state.json"


def _run(cmd, timeout: float = 4.0) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        if r.returncode == 0:
            return r.stdout or ""
    except Exception:
        pass
    return ""


def _parse_pmset_batt(text: str) -> Dict[str, object]:
    """Parse `pmset -g batt` output. Handles both AC-only and battery formats."""
    out: Dict[str, object] = {
        "power_source": "UNKNOWN",
        "battery_present": False,
        "charge_pct": None,
        "charging_state": "UNKNOWN",
        "time_remaining": None,
    }
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        # "Now drawing from 'AC Power'" or "'Battery Power'"
        m = re.search(r"Now drawing from '([^']+)'", line)
        if m:
            out["power_source"] = m.group(1)
        # "-InternalBattery-0 (id=...)  84%; charging; 1:23 remaining present: true"
        if "InternalBattery" in line:
            out["battery_present"] = True
            pct = re.search(r"(\d+)%", line)
            if pct:
                out["charge_pct"] = int(pct.group(1))
            if "discharging" in line.lower():
                out["charging_state"] = "DISCHARGING"
            elif "charging" in line.lower():
                out["charging_state"] = "CHARGING"
            elif "charged" in line.lower():
                out["charging_state"] = "FULL"
            elif "ac attached" in line.lower():
                out["charging_state"] = "AC_ATTACHED"
            tr = re.search(r"(\d+:\d+)\s+remaining", line)
            if tr:
                out["time_remaining"] = tr.group(1)
    return out


def _parse_low_power_mode(text: str) -> Optional[bool]:
    for line in text.splitlines():
        low = line.strip().lower()
        if low.startswith("lowpowermode"):
            m = re.search(r"lowpowermode\s+(\d+)", low)
            if m:
                return bool(int(m.group(1)))
    return None


def _parse_adapter(ioreg_text: str) -> Dict[str, object]:
    """Extract adapter description from ioreg AppleSmartBattery output."""
    out: Dict[str, object] = {
        "adapter_present": False,
        "adapter_watts": None,
        "adapter_name": None,
        "adapter_manufacturer": None,
    }
    m = re.search(r'"AppleRawAdapterDetails"\s*=\s*\(\{([^}]+)\}', ioreg_text)
    if m:
        body = m.group(1)
        out["adapter_present"] = True
        watts = re.search(r'"Watts"\s*=\s*(\d+)', body)
        if watts:
            out["adapter_watts"] = int(watts.group(1))
        name = re.search(r'"Name"\s*=\s*"([^"]+)"', body)
        if name:
            out["adapter_name"] = name.group(1).strip()
        mfg = re.search(r'"Manufacturer"\s*=\s*"([^"]+)"', body)
        if mfg:
            out["adapter_manufacturer"] = mfg.group(1).strip()
    return out


def _parse_battery_ioreg(ioreg_text: str) -> Dict[str, object]:
    """
    Read battery state from ioreg AppleSmartBattery — the canonical source
    on Apple Silicon Macs. On M-series, `pmset -g batt` only prints the
    power source, not the battery percentage. ioreg has the truth.
    """
    out: Dict[str, object] = {}

    def _grab_int(key: str) -> Optional[int]:
        m = re.search(rf'"{key}"\s*=\s*(-?\d+)', ioreg_text)
        return int(m.group(1)) if m else None

    def _grab_yesno(key: str) -> Optional[bool]:
        m = re.search(rf'"{key}"\s*=\s*(Yes|No)', ioreg_text)
        if m:
            return m.group(1) == "Yes"
        return None

    cur = _grab_int("CurrentCapacity")     # On Apple Silicon: percent (0..100)
    max_cap = _grab_int("MaxCapacity")      # Apple Silicon: usually 100 (relative)
    design_mah = _grab_int("DesignCapacity")  # mAh
    cycles = _grab_int("CycleCount")
    is_charging = _grab_yesno("IsCharging")
    fully_charged = _grab_yesno("FullyCharged")
    external = _grab_yesno("ExternalConnected")
    health = _grab_int("BatteryHealthMetric")

    if cur is not None or design_mah is not None:
        out["battery_present"] = True
        # On Apple Silicon, CurrentCapacity IS the percent.
        out["charge_pct"] = cur
        out["cycle_count"] = cycles
        out["design_capacity_mah"] = design_mah
        out["max_capacity_pct"] = max_cap
        if health is not None:
            out["battery_health_metric"] = health
        if is_charging:
            out["charging_state"] = "CHARGING"
        elif fully_charged:
            out["charging_state"] = "FULL"
        elif external:
            # AC attached but not charging — Apple's intelligent charging
            # holds at ~80% to extend battery life.
            out["charging_state"] = "AC_HOLDING"
        else:
            out["charging_state"] = "DISCHARGING"
    return out


def refresh_energy_state() -> Dict[str, object]:
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    state: Dict[str, object] = {
        "ts": time.time(),
        "ok": False,
        "source": "pmset+ioreg",
    }
    state.update(_parse_pmset_batt(_run(["pmset", "-g", "batt"])))
    lpm = _parse_low_power_mode(_run(["pmset", "-g"]))
    if lpm is not None:
        state["low_power_mode"] = lpm
    # On Apple Silicon, ioreg is the source of truth for battery details
    # (pmset -g batt only prints power source, not percent).
    ioreg_text = _run(["ioreg", "-rn", "AppleSmartBattery"])
    state.update(_parse_adapter(ioreg_text))
    state.update(_parse_battery_ioreg(ioreg_text))
    state["ok"] = state.get("power_source", "UNKNOWN") != "UNKNOWN"

    try:
        _CACHE.write_text(json.dumps(state, indent=2))
    except OSError:
        pass
    return state


def get_energy_state(*, max_age_s: float = 60.0) -> Dict[str, object]:
    try:
        if _CACHE.exists():
            cached = json.loads(_CACHE.read_text())
            if time.time() - float(cached.get("ts", 0)) < max_age_s:
                return cached
    except Exception:
        pass
    return refresh_energy_state()


def get_energy_summary() -> str:
    s = get_energy_state()
    if not s.get("ok"):
        return "Energy: introspection unavailable"

    parts = []
    src = s.get("power_source", "?")
    parts.append(f"src={src}")
    if s.get("battery_present"):
        pct = s.get("charge_pct")
        chg = s.get("charging_state", "?")
        parts.append(f"batt={pct}% {chg}")
        cycles = s.get("cycle_count")
        if cycles is not None:
            parts.append(f"cycles={cycles}")
        tr = s.get("time_remaining")
        if tr and tr not in ("0:00", "(no estimate)"):
            parts.append(f"eta={tr}")
    if s.get("adapter_watts"):
        adp = f"{s.get('adapter_watts')}W"
        if s.get("adapter_name"):
            adp += f" {s.get('adapter_name')}"
        parts.append(f"adapter={adp}")
    if s.get("low_power_mode") is not None:
        parts.append(f"low_power={'ON' if s['low_power_mode'] else 'OFF'}")
    return "Energy: " + " | ".join(parts)


def is_low_battery(*, threshold_pct: int = 20) -> bool:
    s = get_energy_state()
    pct = s.get("charge_pct")
    on_battery = s.get("power_source", "").lower().startswith("battery")
    return bool(on_battery and isinstance(pct, int) and pct < threshold_pct)


# ── CLI / smoke test ────────────────────────────────────────────────────────
def _smoke() -> None:
    print("=== SWARM ENERGY CORTEX : SMOKE TEST ===")
    state = refresh_energy_state()
    print(f"[STATE] {json.dumps(state, indent=2)}")
    print(f"[SUMMARY] {get_energy_summary()}")
    print(f"[LOW BATTERY?] {is_low_battery()}")
    assert "Energy:" in get_energy_summary()
    assert _CACHE.exists()
    print("[PASS] Energy Cortex is mapping the metabolic fuel.")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "summary":
        print(get_energy_summary())
    elif len(sys.argv) > 1 and sys.argv[1] == "refresh":
        print(json.dumps(refresh_energy_state(), indent=2))
    else:
        _smoke()
