#!/usr/bin/env python3
"""
homeostasis_engine.py — Continuous Self-Regulation of the Body
===============================================================
SWARM GPT + Architect — April 2026

A living organism doesn't just act — it maintains internal stability
while acting. This engine monitors the PHYSICAL HARDWARE the swarm
runs on and enforces biological self-regulation:

  - Measure body state (CPU load, memory, disk, responsiveness)
  - Compute stability index (1.0 = perfect, 0.0 = collapse)
  - Pre-failure repair trigger (fix BEFORE breaking)
  - Hard physical constraint (the body can say NO)

ZERO EXTERNAL DEPENDENCIES. Uses only os, shutil, time.
No psutil. No pip install. Body checks via the kernel itself.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_STATE_DIR.mkdir(parents=True, exist_ok=True)
_HOMEOSTASIS_LOG = _STATE_DIR / "homeostasis.log"

# ─── THRESHOLDS ─────────────────────────────────────────────────────────────────

STABILITY_REPAIR_THRESHOLD = 0.60   # Below this → auto-trigger INFRA_FORAGER
STABILITY_REST_THRESHOLD   = 0.40   # Below this → FORCE REST, halt all swimmers
DISK_CRITICAL_PERCENT      = 90.0   # Above this → refuse all writes
LOAD_CRITICAL              = 8.0    # 1-min load avg above this → overloaded


# ─── BODY MEASUREMENT (zero dependencies) ──────────────────────────────────────

def _get_cpu_load() -> float:
    """
    1-minute load average, normalized to number of cores.
    On macOS/Linux: os.getloadavg() is a syscall, not a library.
    Returns 0.0-1.0+ (>1.0 means overloaded).
    """
    try:
        load_1min, _, _ = os.getloadavg()
        cores = os.cpu_count() or 1
        return round(load_1min / cores, 4)
    except (OSError, AttributeError):
        return 0.0


def _get_memory_pressure() -> float:
    """
    Memory pressure as 0.0-1.0.
    macOS: read vm_stat. Linux: read /proc/meminfo.
    Fallback: 0.5 (unknown).
    """
    # Try /proc/meminfo (Linux)
    try:
        with open("/proc/meminfo", "r") as f:
            lines = f.readlines()
        mem_total = 0
        mem_available = 0
        for line in lines:
            if line.startswith("MemTotal:"):
                mem_total = int(line.split()[1])
            elif line.startswith("MemAvailable:"):
                mem_available = int(line.split()[1])
        if mem_total > 0:
            return round(1.0 - (mem_available / mem_total), 4)
    except Exception:
        pass

    # macOS fallback: vm_stat
    try:
        import subprocess
        result = subprocess.run(
            ["vm_stat"], capture_output=True, text=True, timeout=2
        )
        lines = result.stdout.splitlines()
        free = 0
        active = 0
        inactive = 0
        wired = 0
        for line in lines:
            if "Pages free" in line:
                free = int(line.split(":")[1].strip().rstrip("."))
            elif "Pages active" in line:
                active = int(line.split(":")[1].strip().rstrip("."))
            elif "Pages inactive" in line:
                inactive = int(line.split(":")[1].strip().rstrip("."))
            elif "Pages wired" in line:
                wired = int(line.split(":")[1].strip().rstrip("."))
        total = free + active + inactive + wired
        if total > 0:
            used = active + wired
            return round(used / total, 4)
    except Exception:
        pass

    return 0.5  # Unknown


def _get_disk_usage() -> float:
    """Disk usage as 0.0-100.0 percent."""
    try:
        usage = shutil.disk_usage("/")
        return round((usage.used / usage.total) * 100, 2)
    except Exception:
        return 50.0


def _get_responsiveness() -> float:
    """
    Disk I/O latency in seconds.
    Write a tiny temp file and read it back.
    This is the REAL pulse check — not abstract.
    """
    test_path = _STATE_DIR / ".pulse_check"
    try:
        start = time.time()
        test_path.write_text("♥")
        _ = test_path.read_text()
        test_path.unlink(missing_ok=True)
        return round(time.time() - start, 6)
    except Exception:
        return 99.0  # Catastrophic


# ─── BODY STATE ─────────────────────────────────────────────────────────────────

def measure_body_state() -> dict:
    """
    Full physical measurement of the hardware body.
    No abstraction. No libraries. Just the machine.
    """
    return {
        "cpu_load": _get_cpu_load(),           # 0.0-1.0+ (normalized to cores)
        "memory_pressure": _get_memory_pressure(),  # 0.0-1.0
        "disk_percent": _get_disk_usage(),     # 0.0-100.0
        "io_latency": _get_responsiveness(),   # seconds
        "timestamp": time.time()
    }


def compute_stability_index(state: dict) -> float:
    """
    Body stability: 1.0 = perfect, 0.0 = collapse.
    
    Weighted penalties:
    - CPU load:    25% (sustained compute)
    - Memory:      25% (working set pressure)
    - Disk:        25% (storage runway)
    - I/O latency: 25% (responsiveness / the "pulse")
    """
    cpu_penalty = min(state["cpu_load"], 1.0)
    mem_penalty = state["memory_pressure"]
    disk_penalty = state["disk_percent"] / 100.0
    
    # I/O latency: 0.001s = perfect, 0.1s = bad, 1.0s+ = catastrophic
    io_lat = state["io_latency"]
    if io_lat < 0.01:
        io_penalty = 0.0
    elif io_lat < 0.1:
        io_penalty = io_lat * 5     # 0.0 to 0.5
    else:
        io_penalty = min(1.0, io_lat)

    stability = 1.0 - (
        0.25 * cpu_penalty +
        0.25 * mem_penalty +
        0.25 * disk_penalty +
        0.25 * io_penalty
    )

    return round(max(0.0, min(1.0, stability)), 4)


# ─── HOMEOSTASIS CYCLE ──────────────────────────────────────────────────────────

def homeostasis_cycle() -> dict:
    """
    One heartbeat of the body.
    Returns the state, stability, and recommended action.
    
    Actions:
    - STABLE:         System healthy. Continue.
    - TRIGGER_REPAIR: Instability detected. Spawn INFRA_FORAGER.
    - FORCE_REST:     Critical instability. Halt all swimmers.
    - DISK_CRITICAL:  Disk nearly full. Refuse writes.
    """
    state = measure_body_state()
    stability = compute_stability_index(state)
    
    # Determine action
    if state["disk_percent"] >= DISK_CRITICAL_PERCENT:
        action = "DISK_CRITICAL"
    elif stability < STABILITY_REST_THRESHOLD:
        action = "FORCE_REST"
    elif stability < STABILITY_REPAIR_THRESHOLD:
        action = "TRIGGER_REPAIR"
    else:
        action = "STABLE"
    
    # Log
    _log_heartbeat(state, stability, action)
    
    result = {
        "state": state,
        "stability": stability,
        "action": action
    }
    
    return result


def _log_heartbeat(state: dict, stability: float, action: str):
    """Append one line to the homeostasis log."""
    ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(state["timestamp"]))
    line = (
        f"{ts} | stability={stability:.3f} | action={action} | "
        f"cpu={state['cpu_load']:.2f} mem={state['memory_pressure']:.2f} "
        f"disk={state['disk_percent']:.1f}% io={state['io_latency']*1000:.1f}ms\n"
    )
    with open(_HOMEOSTASIS_LOG, "a") as f:
        f.write(line)


# ─── SWIM LOOP GATE ────────────────────────────────────────────────────────────

def body_allows_swim() -> tuple:
    """
    Gate function for the swim loop.
    Call this BEFORE any agent does any work.
    
    Returns (allowed: bool, reason: str, stability: float)
    """
    result = homeostasis_cycle()
    stability = result["stability"]
    action = result["action"]
    
    if action == "FORCE_REST":
        print(f"  [🛑 BODY] Critical instability (stability={stability:.3f}). "
              f"Halting swimmer. The body says NO.")
        return False, "BODY_CRITICAL", stability
    
    if action == "DISK_CRITICAL":
        print(f"  [🛑 BODY] Disk critical ({result['state']['disk_percent']:.1f}%). "
              f"Refusing writes.")
        return False, "DISK_FULL", stability
    
    if action == "TRIGGER_REPAIR":
        print(f"  [⚠️ BODY] Instability detected (stability={stability:.3f}). "
              f"Swimmer may proceed but INFRA_FORAGER should be dispatched.")
        return True, "BODY_DEGRADING", stability
    
    return True, "BODY_STABLE", stability


# ─── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  SIFTA HOMEOSTASIS ENGINE — Body Status")
    print("=" * 60)
    
    state = measure_body_state()
    stability = compute_stability_index(state)
    
    print(f"\n  CPU Load (normalized):  {state['cpu_load']:.2f}")
    print(f"  Memory Pressure:       {state['memory_pressure']:.2f}")
    print(f"  Disk Usage:            {state['disk_percent']:.1f}%")
    print(f"  I/O Latency (pulse):   {state['io_latency']*1000:.2f}ms")
    print(f"\n  ═══ STABILITY INDEX: {stability:.3f} ═══")
    
    if stability >= 0.8:
        print(f"  Status: 🟢 HEALTHY")
    elif stability >= STABILITY_REPAIR_THRESHOLD:
        print(f"  Status: 🟡 NOMINAL")
    elif stability >= STABILITY_REST_THRESHOLD:
        print(f"  Status: 🟠 DEGRADING — repair agents should be dispatched")
    else:
        print(f"  Status: 🔴 CRITICAL — all swimmers must halt")
    
    result = homeostasis_cycle()
    print(f"  Action: {result['action']}")
    print(f"\n  Logged to: {_HOMEOSTASIS_LOG}")
    print("=" * 60)
