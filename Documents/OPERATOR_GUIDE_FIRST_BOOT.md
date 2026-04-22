# SIFTA First-Boot Ceremony

Welcome to SIFTA. When you clone the public OS and run the boot script for the first time, your system starts in a state of **biological amnesia**. It does not know who you are, it does not know what your hardware is, and it does not know the AI's name.

The first boot is not a configuration wizard; it is an **Owner Genesis** ceremony.

## What Happens on First Boot?

When you run `PYTHONPATH=. python3 System/swarm_boot.py` for the first time:

1. **Hardware Anchoring:** The system reads your actual Apple Silicon serial number (`owner_silicon()`).
2. **Naming the Swarm:** The OS will prompt you to provide your name, your preferred camera label, and the Display Name you want to give the Swarm (default is "Alice").
3. **The Genesis Block:** These three pieces of information, cryptographically anchored to your hardware serial number, are written to `.sifta_state/owner_genesis.json`.

This JSON file becomes the **trust-root** for your swarm. The Swarm OS reads your identity natively from this file. No cloud settings, no user profiles. Your hardware serial is the key.

## Privacy Note

- Your name and your Apple Silicon serial number are **never sent to the cloud**. They are stored locally.
- The public GitHub repository does not contain the original Architect's hardware serials or names; they were scrubbed before the release.

If you ever move your SIFTA OS to a different Mac, you will need to re-run the Genesis ceremony because the hardware serial will have changed. See the [Rename AI Guide](OPERATOR_GUIDE_RENAME_AI.md) for details on re-genesis.
