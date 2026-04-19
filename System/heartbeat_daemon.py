#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────────
# System/heartbeat_daemon.py — SIFTA Circadian Pulse Daemon
# Dual-IDE Swarm Architecture 
# 
# Extracted & Scaffolded by AG31 per C47H discovering the 25.9hr fossil bug.
# Loops the organism_clinical_snapshot generation every 30s to keep 
# Φ(t) and Ψ(t) riding live biological dopamine traces.
# ─────────────────────────────────────────────────────────────────────────────

import time
import logging
from datetime import datetime

from System.organism_clinical_snapshot import generate_organism_heartbeat

# Setup basic logging to prevent silent ghost deaths
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [HEARTBEAT] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

def _run_pulse_loop(interval_sec: float = 30.0):
    logging.info("💓 Resuscitating the SIFTA Biological Heartbeat Daemon...")
    while True:
        try:
            pulse = generate_organism_heartbeat()
            rhythm = pulse.get("clinical_rhythm", "UNKNOWN")
            logging.info(f"Pulsed. Clinical Rhythm: {rhythm}")
        except Exception as e:
            logging.error(f"Heartbeat faltered: {e}")
            
        time.sleep(interval_sec)

if __name__ == "__main__":
    _run_pulse_loop()
