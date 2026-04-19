#!/usr/bin/env python3
"""
System/swarm_electromagnetic_lobe.py
═══════════════════════════════════════════════════════════════════════════════
The Wi-Fi Sensory Organ.

1. Autodiscovery (Cortical Mapping): Continuously parses ARP table (`arp -a`) 
   and automatically catalogs MAC/IP addresses into `iot_devices.json`.
2. RF Motion Sensing (Jitter Variance): Rapidly micro-pings stationary anchors
   (Router, NAS) to calculate rolling latency standard deviation. 
   Sudden violent latency spikes (caused by human water absorption traversing 
   Wi-Fi beams) are logged as a physical disturbance in `rf_stigmergy.jsonl`.
"""
import sys
import os
import time
import json
import subprocess
import threading
from collections import deque
import statistics
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_STATE_DIR.mkdir(parents=True, exist_ok=True)

IOT_REGISTRY_FILE = _STATE_DIR / "iot_devices.json"
RF_STIGMERGY_LOG = _STATE_DIR / "rf_stigmergy.jsonl"

ANCHORS = ["192.168.1.1", "192.168.1.178"] # Router and WD NAS (known static nodes)
ROLLING_WINDOW_SIZE = 10
VARIANCE_THRESHOLD_MS = 6.0 # Threshold for latency deviation spike

def parse_arp_table():
    """Autodiscover devices on the LAN and inject them into SIFTA's awareness."""
    try:
        output = subprocess.check_output(["arp", "-a"], universal_newlines=True)
        discovered = {}
        for line in output.splitlines():
            line = line.strip()
            if not line: continue
            
            # Format usually: hostname (192.168.1.X) at mac_addr on en0 ...
            # Extract IP
            try:
                ip_part = line.split("(")[1].split(")")[0]
                host_part = line.split("(")[0].strip()
                if "192.168" not in ip_part:
                    continue  # Ignore multicast masks
                    
                discovered[ip_part] = {
                    "alias": f"Auto-Detected: {host_part}" if host_part != "?" else f"Unknown Node ({ip_part})",
                    "ip": ip_part,
                    "port": 80,
                    "protocol": "ARP"
                }
            except Exception:
                continue

        # Merge with existing IoT map
        existing = {"devices": []}
        if IOT_REGISTRY_FILE.exists():
            try:
                with open(IOT_REGISTRY_FILE, "r") as f:
                    existing = json.load(f)
            except Exception:
                pass
        
        # Merge by IP to avoid duplicates
        ip_map = {d["ip"]: d for d in existing.get("devices", [])}
        for ip, dev in discovered.items():
            if ip not in ip_map:
                ip_map[ip] = dev
        
        existing["devices"] = list(ip_map.values())
        
        with open(IOT_REGISTRY_FILE, "w") as f:
            json.dump(existing, f, indent=2)

    except Exception as e:
        print(f"[ARP Lobe Error] {e}")


def ping_node(ip_address: str) -> float:
    """Send a micro-ping to capture raw latency in milliseconds. Returns -1 if timeout."""
    try:
        # Ping exactly 1 packet, wait max 1000ms
        out = subprocess.check_output(["ping", "-c", "1", "-W", "1000", ip_address], universal_newlines=True)
        # Parse macOS ping output -> "time=3.14 ms"
        for line in out.splitlines():
            if "time=" in line:
                ms_val = line.split("time=")[1].split(" ")[0]
                return float(ms_val)
        return -1.0
    except Exception:
        return -1.0


def rf_sensory_loop():
    """Continuously measure Wi-Fi beam jitter to detect physical movement."""
    latency_histories = {ip: deque(maxlen=ROLLING_WINDOW_SIZE) for ip in ANCHORS}

    while True:
        try:
            for anchor in ANCHORS:
                ms = ping_node(anchor)
                if ms < 0:
                    continue  # packet lost

                history = latency_histories[anchor]
                history.append(ms)

                if len(history) == ROLLING_WINDOW_SIZE:
                    base_median = statistics.median(list(history)[:-1])
                    current = history[-1]
                    
                    # If latency spikes violently compared to recent median, the RF wave was disturbed
                    if abs(current - base_median) > VARIANCE_THRESHOLD_MS:
                        # Write Stigmergic disturbance
                        with open(RF_STIGMERGY_LOG, "a", encoding="utf-8") as f:
                            json.dump({
                                "ts": time.time(),
                                "anchor_ip": anchor,
                                "latency_spike_ms": round(current, 2),
                                "base_median_ms": round(base_median, 2),
                                "event": "WIFI_BEAM_BROKEN"
                            }, f)
                            f.write("\n")
                        
                        # Clear history window post-spike to avoid cascading triggers
                        history.clear()
            
            # Sub-second sensory loop to feel immediate physics
            time.sleep(0.8)
        except Exception as e:
            time.sleep(2)

def arp_loop():
    while True:
        parse_arp_table()
        time.sleep(60)

if __name__ == "__main__":
    print("📡 [Electromagnetic Lobe] Booting organic Wi-Fi sensory arrays...")
    parse_arp_table() # Initial map
    
    t1 = threading.Thread(target=arp_loop, daemon=True)
    t1.start()
    
    # Run RF sense on main thread
    rf_sensory_loop()
