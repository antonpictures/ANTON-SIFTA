#!/usr/bin/env python3
"""
launchd/stig_thermal_helper.py
Privileged helper to read raw thermal sensors (die temps, SMC fan RPM, ANE wattage)
Crosses the sudo boundary intentionally. Supervised by a root-level LaunchDaemon.
"""
import sys
import time
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LEDGER = _STATE / "thermal_state.jsonl"
sys.path.insert(0, str(_REPO))

def _parse_and_deposit(lines):
    text = "\n".join(lines)
    fan_rpm = None
    die_temp = None
    ane_power = None
    
    m_fan = re.search(r"Fan:\s*(\d+)\s*rpm", text, re.IGNORECASE)
    if m_fan: fan_rpm = int(m_fan.group(1))
    
    m_ane = re.search(r"ANE Power:\s*(\d+)\s*mW", text, re.IGNORECASE)
    if m_ane: ane_power = int(m_ane.group(1))
    
    # Powermetrics has various temp formats
    m_temp = re.search(r"(SOC|DIE).*?(temp|temperature):\s*([0-9.]+)\s*C", text, re.IGNORECASE)
    if m_temp: 
        die_temp = float(m_temp.group(3))
        
    snap = {
        "ts": time.time(),
        "iso": datetime.now(tz=timezone.utc).isoformat(),
        "fan_rpm": fan_rpm,
        "die_temp_c": die_temp,
        "ane_power_mw": ane_power
    }
    
    _STATE.mkdir(parents=True, exist_ok=True)
    with _LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(snap) + "\n")
        
    # Pheromone intensity proportional to thermal pressure
    intensity = 0.5
    if die_temp and die_temp > 60.0:
        intensity += (die_temp - 60.0) * 0.5
    if fan_rpm and fan_rpm > 1500:
        intensity += (fan_rpm - 1500) / 1000.0
    
    intensity = min(15.0, intensity)
    
    try:
        from System.swarm_pheromone import deposit_pheromone # type: ignore
        deposit_pheromone("stig_thermal_probe", intensity)
    except Exception as exc:
        pass

def main():
    if os.geteuid() != 0:
        sys.exit("stig_thermal_helper.py must be run as root.")
        
    while True:
        try:
            p = subprocess.run(["powermetrics", "--samplers", "smc", "-n", "1"], capture_output=True, text=True, check=False)
            _parse_and_deposit(p.stdout.splitlines())
        except Exception as e:
            pass
        time.sleep(5)

if __name__ == "__main__":
    import os
    main()
