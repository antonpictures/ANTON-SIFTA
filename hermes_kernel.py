#!/usr/bin/env python3
"""
hermes_kernel.py
The SIFTA Cognitive Orchestration Kernel (Async execution fabric).
Sits above the Python Runtime to breathe life into the Swarm concurrently.
"""
import asyncio
import os
import time
import json
import platform
import sifta_cardio
from pathlib import Path

STATE_DIR = Path(".sifta_state")

# Shared state between routines
kernel_state_lock = asyncio.Lock()
kernel_state = {
    "interval": 2.0,
    "hal_mode": "UNKNOWN"
}

async def run_scheduler():
    """
    Asynchronous executor bridging to the Ledger heartbeat.
    """
    while True:
        # Prevent blocking the async loop by shipping synchronous DB I/O and exec to a thread
        try:
            await asyncio.to_thread(sifta_cardio.recover_stale_leases)
            work_found = await asyncio.to_thread(sifta_cardio.pump_blood)
        except Exception as e:
            print(f"[HERMES][SCHEDULER] {e}")
            work_found = False
            
        async with kernel_state_lock:
            current_interval = kernel_state["interval"]
        await asyncio.sleep(current_interval if not work_found else 0.5)

async def monitor_state():
    """
    Biological Rhythm & Density Sensing (Jellyfish Trigger).
    """
    last_mode = "NORMAL"
    while True:
        try:
            density = await asyncio.to_thread(sifta_cardio._sense_scar_density)
            new_interval = sifta_cardio._compute_heartbeat_interval(density)
            async with kernel_state_lock:
                kernel_state["interval"] = new_interval
            
            # Mode transitions
            if new_interval == 0.5:
                new_mode = "URGENCY"
            elif new_interval == 5.0:
                new_mode = "REST"
            else:
                new_mode = "NORMAL"

            if new_mode != last_mode:
                print(f"[🌊 HERMES] Jellyfish shift: {last_mode} → {new_mode} "
                      f"(bleeding={density.get('bleeding_count', 0)}, potency={density.get('total_potency', 0)})")
                last_mode = new_mode
                
        except Exception as e:
            print(f"[HERMES][MONITOR] {e}")
            
        # Sense environmental shift every X seconds
        async with kernel_state_lock:
            current_interval = kernel_state["interval"]
        await asyncio.sleep(current_interval)

async def handle_agents():
    """
    The HAL Environment Awareness loop. 
    Continuously maps the raw hardware footprint and publishes node class.
    """
    STATE_DIR.mkdir(exist_ok=True)
    hal_file = STATE_DIR / "kernel_hal.json"
    
    while True:
        machine = platform.machine().lower()
        if "arm" in machine or "aarch64" in machine:
            # We can refine this to explicitly detect M1/M2/M3 vs mobile
            node_class = "LIGHT_NODE" 
        else:
            node_class = "HEAVY_NODE"
            
        async with kernel_state_lock:
            kernel_state["hal_mode"] = node_class
            current_interval = kernel_state["interval"]
        
        hal_data = {
            "node_class": node_class,
            "architecture": machine,
            "processor": platform.processor(),
            "kernel_rhythm": current_interval,
            "timestamp": time.time()
        }
        
        try:
            with open(hal_file, "w") as f:
                json.dump(hal_data, f, indent=2)
        except Exception as e:
            print(f"[HERMES][HAL] {e}")
            
        # Update every 10 seconds. Static hardware doesn't change, but interval does
        await asyncio.sleep(10)

async def process_votes():
    """
    Asynchronously parses the `.sifta_votes` directory and emits updates or handles consensus.
    """
    while True:
        # In a real heavy implementation we would walk the votes dir,
        # but for now this is the async stub running in parallel.
        await asyncio.sleep(15)

async def swarm_kernel():
    print("══════════════════════════════════════════════════")
    print(" 👁 HERMES (COGNITIVE ORCHESTRATION KERNEL) ONLINE")
    print("══════════════════════════════════════════════════")
    print("[*] Initiating parallel swarm fabric...")
    
    # Needs sifta_cardio db initialized
    sifta_cardio.init_ledger()
    
    await asyncio.gather(
        run_scheduler(),
        process_votes(),
        handle_agents(),
        monitor_state()
    )

if __name__ == "__main__":
    try:
        asyncio.run(swarm_kernel())
    except KeyboardInterrupt:
        print("\n[*] Hermes Kernel suspending cognition... offline.")
