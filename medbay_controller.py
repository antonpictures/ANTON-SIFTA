import asyncio
from state_bus import get_state, set_state

async def medbay_monitor_loop():
    """
    Biological safe-state suspension monitor.
    If system constraints break under severe anomaly (Volatility >= 0.80),
    the OS freezes all execution endpoints to prevent Context Damage and
    Muscle Memory Contamination until the Parasympathetic Reflex has bled
    system stress down to <= 0.15.
    """
    # Ensure MEDBAY_ACTIVE exists
    if get_state("MEDBAY_ACTIVE", "MISSING") == "MISSING":
        set_state("MEDBAY_ACTIVE", False)

    while True:
        await asyncio.sleep(2.0) # Check every 2 biological ticks
        
        current_vol = get_state("volatility_score", 0.10)
        is_medbay = get_state("MEDBAY_ACTIVE", False)

        if not is_medbay and current_vol >= 0.80:
            set_state("MEDBAY_ACTIVE", True)
            print("\n[🚨 MEDBAY TRIGGERED] Volatility Critical. Freezing Execution across Swarm.")
        
        elif is_medbay and current_vol <= 0.15:
            set_state("MEDBAY_ACTIVE", False)
            print("\n[⚕️ MEDBAY LIFTED] Stability Restored. Normal execution resumed.")
