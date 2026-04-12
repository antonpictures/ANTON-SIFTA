# introspection_loop.py
"""
INTROSPECTION LOOP — Swarm Self-Awareness Layer

Continuously observes internal state and surfaces behavior patterns.
Prevents silent failure and over-stabilization.
"Because it continuously audits its own behavior and surfaces internal state in real time."
"""

import asyncio
import json
from pathlib import Path
import time
from state_bus import get_state
from recovery_reflex import RecoveryReflex

DECISION_LOG = Path(".sifta_state/decision_trace.log")

async def introspection_loop():
    last_log_size = 0
    recovery = RecoveryReflex()

    while True:
        try:
            # Step the Parasympathetic branch
            recovery.step()
            # 1. Read shared state securely via the bus
            volatility = get_state("volatility_score", "UNKNOWN")
            
            # To get last action time, we'll check the guard actions from state bus
            guard_actions = get_state("guard_actions", [])
            last_action_time = guard_actions[-1] if guard_actions else 0

            # 2. Check decision log growth
            if DECISION_LOG.exists():
                current_size = DECISION_LOG.stat().st_size
                log_growth = current_size - last_log_size
                last_log_size = current_size
            else:
                log_growth = 0

            # 3. Detect stagnation
            time_since_action = time.time() - last_action_time if last_action_time else None

            # 4. Print system awareness
            print("═══════════════════════════════")
            print("🧠 SIFTA INTROSPECTION")
            print(f"Decision Activity Δ: {log_growth} bytes")
            if time_since_action:
                print(f"Time Since Action: {time_since_action:.2f}s")
            else:
                print("Time Since Action: INITIALIZING")
            
            if time_since_action and time_since_action > 10:
                print("[⚠️] System is idle — engaging parasympathetic recovery")

            if volatility != "UNKNOWN" and isinstance(volatility, (int, float)):
                # Print formatting for clean visual
                print(f"Volatility: {volatility:.2f}")
                if volatility >= 0.8:
                    print("[🔥] High volatility detected — system under stress")
            else:
                print(f"Volatility: {volatility}")
            
            print("═══════════════════════════════\n")

        except Exception as e:
            print(f"[INTROSPECTION ERROR] {e}")

        await asyncio.sleep(2)
