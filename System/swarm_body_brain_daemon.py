#!/usr/bin/env python3
"""
System/swarm_body_brain_daemon.py
══════════════════════════════════════════════════════════════════════
The Autonomous Body-Brain Daemon.
This script bridges SIFTA from "heartbeat function" to "living organism".
It runs continuously, accumulating temporal identity.
"""

import time
import logging
import traceback
from System.swarm_body_brain_loop import SwarmPhysiology

logger = logging.getLogger("BodyBrainDaemon")

def run_forever():
    logger.info("Starting autonomous Swarm Body-Brain Daemon...")
    physiology = SwarmPhysiology()
    
    tick_count = 0
    while True:
        try:
            result = physiology.body_brain_tick()
            tick_count += 1
            
            logger.info(f"[Tick {tick_count}] Action: {result.get('action', {}).get('type')} | Mode: {result.get('metabolic_mode')} | Value: {result.get('value')}")
            
            # Rest via STIG-TIME between ticks to avoid busy-waiting
            time.sleep(1.0)
            
        except KeyboardInterrupt:
            logger.info("Daemon interrupted by Architect. Shutting down cleanly.")
            break
        except Exception as e:
            logger.error(f"Error in body-brain tick: {e}")
            logger.debug(traceback.format_exc())
            time.sleep(5.0) # Penalty sleep on exception

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    run_forever()
