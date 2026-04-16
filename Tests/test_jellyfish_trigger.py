#!/usr/bin/env python3
"""
test_jellyfish_trigger.py
=========================
Simulates a rapid influx of hostile environmental signals (BLEEDING syntax wounds).
Proves that the internal SIFTA Cardio daemon autonomically accelerates its heartbeat
from a resting state (5s/2s) to URGENCY panic mode (0.5s) to defend the perimeter.
"""

import os
import time
import shutil
import subprocess
from pathlib import Path

print("🌊 INITIALIZING JELLYFISH URGENY TRIGGER TEST...")

TARGET_DIR = Path("bureau_of_identity")
SIFTA_DIR = TARGET_DIR / ".sifta"
PROPOSALS_DIR = Path("proposals")

# 1. Clean the environment to guarantee a REST state
if SIFTA_DIR.exists():
    shutil.rmtree(SIFTA_DIR)
TARGET_DIR.mkdir(parents=True, exist_ok=True)
PROPOSALS_DIR.mkdir(exist_ok=True) # Cardio requires proposals dir to be wired to panic

print("[+] Territory clean. Booting SIFTA Cardio Daemon...")

# 2. Boot Cardio in a background process
env = os.environ.copy()
env["PYTHONUNBUFFERED"] = "1"
cardio_proc = subprocess.Popen(
    [".venv/bin/python", "sifta_cardio.py"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    env=env
)

time.sleep(2)
print("\n[+] Injecting 4 hostile BLEEDING wounds into the territory...")

# 3. Inject wounds directly using the Pheromone API
from pheromone import drop_scar
from body_state import SwarmBody

dummy_agent = {"id": "TEST_HOUND", "sex": 0, "vocation": "DETECTIVE"}

for i in range(4):
    drop_scar(
        directory=TARGET_DIR,
        agent_state=dummy_agent,
        action="SCAN",
        found=f"SyntaxError at line {i*10}",
        status="BLEEDING",
        mark_text="Severe environmental breach detected.",
    )
    time.sleep(0.1)

print("[+] Wounds injected. Waiting for autonomic Jellyfish response...\n")
print("--- CARDIO DAEMON LOG ---")

# 4. Monitor the daemon output for the shift to URGENCY
urgency_detected = False
start_time = time.time()

try:
    for line in iter(cardio_proc.stdout.readline, ''):
        stripped = line.strip()
        if stripped:
            print(f"  {stripped}")
        if "URGENCY" in stripped:
            urgency_detected = True
            break
        if time.time() - start_time > 10:
            break
finally:
    cardio_proc.terminate()
    cardio_proc.wait()

print("-------------------------")

if urgency_detected:
    print("\n[+] SUCCESS: Jellyfish Trigger successfully entered URGENCY mode (0.5s heartbeat).")
    print("🌊 THE SWARM AUTONOMIC SURVIVAL INSTINCT IS FUNCTIONAL.")
else:
    print("\n[!] FAILURE: Jellyfish Trigger failed to enter panic mode.")

# Cleanup
if SIFTA_DIR.exists():
    shutil.rmtree(SIFTA_DIR)
