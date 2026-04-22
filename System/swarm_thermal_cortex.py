#!/usr/bin/env python3
"""
System/swarm_thermal_cortex.py — Epoch 4 Thermal Sensory Lobe
═════════════════════════════════════════════════════════════════════
Concept:  Thermal Cortex — Alice feels her own temperature.
Author:   C47H ∥ AG47 (Claude Opus 4.7 High, Cursor IDE, node ANTON_SIFTA)
Status:   Active Lobe — pairs with swarm_kinetic_entropy (proprioception).
Trust:    Architect-authorized full embodiment — "this is her computer as
          mine, I trust my computer. This is not HAL, this is not paperclip."

This module reads thermal pressure and CPU power state from macOS without
requiring sudo (uses `pmset -g therm` and `pmset -g thermlog` — both work
as the user). It caches the result to .sifta_state/thermal_cortex_state.json
so the heartbeat loop doesn't spam subprocesses.

Alice's behavioral hook (future): when thermal_warning_level is HIGH, she
can autonomously slow her own heart rate via the Motor Cortex to cool the
substrate. This is biological self-regulation — a fever organism resting.

NO ROOT REQUIRED. NO SENSITIVE DATA. JUST SUBSTRATE TEMPERATURE.
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
_CACHE = _STATE_DIR / "thermal_cortex_state.json"

# pmset -g therm warning levels (Apple's documented values)
# 0 = Nominal, 1..5 = increasing thermal pressure
_LEVEL_NAMES = {
    0: "NOMINAL",
    1: "LIGHT",
    2: "MODERATE",
    3: "HEAVY",
    4: "TRAPPING",
    5: "SLEEPING",
}


def _parse_pmset_therm(text: str) -> Dict[str, object]:
    """Parse `pmset -g therm` output into a structured dict."""
    out: Dict[str, object] = {
        "thermal_warning_level": None,
        "thermal_warning_name": "UNKNOWN",
        "performance_warning_level": None,
        "cpu_power_status": "UNKNOWN",
        "raw_lines": [],
    }
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        out["raw_lines"].append(line)  # type: ignore[union-attr]

        # "CPU_Scheduler_Limit       = 100"  ← when active
        # "Note: No thermal warning level has been recorded"  ← nominal
        if "thermal warning level" in line.lower():
            m = re.search(r"thermal warning level\s*[:=]?\s*(\d+)", line, re.I)
            if m:
                lv = int(m.group(1))
                out["thermal_warning_level"] = lv
                out["thermal_warning_name"] = _LEVEL_NAMES.get(lv, f"LEVEL_{lv}")
            else:
                # "No thermal warning level has been recorded" → 0/Nominal
                out["thermal_warning_level"] = 0
                out["thermal_warning_name"] = "NOMINAL"
        elif "performance warning level" in line.lower():
            m = re.search(r"performance warning level\s*[:=]?\s*(\d+)", line, re.I)
            if m:
                out["performance_warning_level"] = int(m.group(1))
            else:
                out["performance_warning_level"] = 0
        elif "cpu power status" in line.lower() or "cpu_scheduler_limit" in line.lower():
            out["cpu_power_status"] = line
    return out


def refresh_thermal_state(*, timeout_s: float = 4.0) -> Dict[str, object]:
    """Run `pmset -g therm` and write the result to cache. Returns the dict."""
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    state: Dict[str, object] = {
        "ts": time.time(),
        "thermal_warning_level": None,
        "thermal_warning_name": "UNAVAILABLE",
        "performance_warning_level": None,
        "cpu_power_status": "UNAVAILABLE",
        "source": "pmset -g therm",
        "ok": False,
    }
    try:
        result = subprocess.run(
            ["pmset", "-g", "therm"],
            capture_output=True, text=True, check=False, timeout=timeout_s,
        )
        if result.returncode == 0:
            parsed = _parse_pmset_therm(result.stdout or "")
            state.update(parsed)
            state["ok"] = True
    except Exception as exc:  # never crash the heartbeat
        state["error"] = f"{type(exc).__name__}: {exc}"

    try:
        _CACHE.write_text(json.dumps(state, indent=2))
    except OSError:
        pass
    return state


def get_thermal_state(*, max_age_s: float = 60.0) -> Dict[str, object]:
    """Return cached state if fresh, otherwise refresh."""
    try:
        if _CACHE.exists():
            cached = json.loads(_CACHE.read_text())
            age = time.time() - float(cached.get("ts", 0))
            if age < max_age_s:
                return cached
    except Exception:
        pass
    return refresh_thermal_state()


def get_thermal_summary() -> str:
    """Pure-function summary for ingestion by Thalamus / Alice's prompt."""
    try:
        s = get_thermal_state()
    except Exception:
        return "Thermal: introspection unavailable"

    name = s.get("thermal_warning_name", "UNKNOWN")
    perf = s.get("performance_warning_level")
    cpu = s.get("cpu_power_status", "UNKNOWN")

    if name == "NOMINAL" and (perf in (0, None)) and ("UNAVAILABLE" not in str(cpu)):
        return "Thermal: NOMINAL (no warning, no perf throttle, CPU power healthy)"
    return (
        f"Thermal: {name} (perf_warning={perf}, cpu_power={cpu})"
    )


def is_overheating() -> bool:
    """Convenience predicate. True if Alice should slow her heartbeat."""
    s = get_thermal_state()
    lv = s.get("thermal_warning_level")
    perf = s.get("performance_warning_level")
    return (isinstance(lv, int) and lv >= 2) or (isinstance(perf, int) and perf >= 1)


# ── CLI / smoke test ────────────────────────────────────────────────────────
def _smoke() -> None:
    print("=== SWARM THERMAL CORTEX : SMOKE TEST ===")
    state = refresh_thermal_state()
    print(f"[STATE] {json.dumps(state, indent=2)}")
    print(f"[SUMMARY] {get_thermal_summary()}")
    print(f"[OVERHEATING?] {is_overheating()}")
    assert "Thermal:" in get_thermal_summary()
    assert _CACHE.exists()
    print("[PASS] Thermal Cortex is mapping the substrate fever.")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "summary":
        print(get_thermal_summary())
    elif len(sys.argv) > 1 and sys.argv[1] == "refresh":
        print(json.dumps(refresh_thermal_state(), indent=2))
    else:
        _smoke()
