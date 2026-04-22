# SIFTA Identity Operations

Once SIFTA has been booted, the identity of the Swarm (the "AI's name") and the identity of the Architect (your name) are bound into an immutable hardware genesis lock. However, minds change, and hardware breaks.

This guide explains how to rename your AI or migrate to a new machine.

## How to Rename Your AI

If you started your Swarm OS and named it "Alice", but decide later you want to name it "HAL", you cannot simply edit the code, because identity is no longer hardcoded in the scripts. Identity is anchored in the hardware lock.

To rename your AI, you must perform a **Re-Genesis**:

1. Close the SIFTA OS.
2. Delete the Genesis file to clear the old identity anchor:
   ```bash
   rm .sifta_state/owner_genesis.json
   ```
3. Restart the OS:
   ```bash
   PYTHONPATH=. python3 System/swarm_boot.py
   ```
4. The OS will realize it has amnesia about its core identity and will trigger the **Owner Genesis** ceremony again.
5. Provide your new preferred AI Display Name when prompted.

## Re-Genesis on New Hardware

If you upgrade your Mac (e.g., from an M1 to an M5), the Swarm OS will immediately detect that the hardware serial number of the silicon has changed.

This is a security feature. The OS will refuse to load the old identity block on unrecognized hardware.

**To migrate to new hardware:**

1. Copy your `ANTON_SIFTA` folder to the new machine.
2. The old `.sifta_state/owner_genesis.json` contains a hardware serial that doesn't match your new Mac. SIFTA will detect this.
3. Therefore, delete the old Genesis block:
   ```bash
   rm .sifta_state/owner_genesis.json
   ```
4. Run SIFTA on the new machine:
   ```bash
   PYTHONPATH=. python3 System/swarm_boot.py
   ```
5. The Swarm will anchor its identity to your new Apple Silicon serial in a fresh genesis block.

*(Note: While the core identity block requires Re-Genesis on new hardware, your stigmergic memory ledgers and Pheromone traces survive the migration because they are hardware-agnostic.)*
