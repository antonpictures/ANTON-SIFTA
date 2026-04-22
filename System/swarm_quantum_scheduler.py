#!/usr/bin/env python3
"""
Quantum‑inspired scheduler for SIFTA heartbeat subsystems.
Implements a discrete‑time quantum walk on a 1‑D lattice of N subsystems.
Each tick the walker spreads amplitude; measurement selects the next active module.
"""

import math
import random
import time
from pathlib import Path
from typing import List

# List of subsystem identifiers (must match names in swarm_boot)
SUBSYSTEMS = [
    "MERKLE",
    "C_TACTILE",
    "IDENTITY_ATTEST",
    "TAXIDERMIST",
    "MICROBIOME",
    "VAGUS_NERVE",
    "HEARTBEAT",
]

# Quantum walk state: amplitude per site
_state: List[float] = [0.0] * len(SUBSYSTEMS)
_state[0] = 1.0  # start at first subsystem


def _step() -> None:
    """Perform one quantum walk step (Hadamard‑like diffusion)."""
    new_state = [0.0] * len(SUBSYSTEMS)
    for i, amp in enumerate(_state):
        # split amplitude to left and right neighbours (periodic boundary)
        left = (i - 1) % len(SUBSYSTEMS)
        right = (i + 1) % len(SUBSYSTEMS)
        new_state[left] += amp / math.sqrt(2)
        new_state[right] += amp / math.sqrt(2)
    # normalize
    norm = math.sqrt(sum(a * a for a in new_state))
    for i in range(len(new_state)):
        new_state[i] /= norm
    _state[:] = new_state


def select_subsystem() -> str:
    """Measure the walk and return the chosen subsystem name."""
    _step()
    # probability distribution = |amplitude|^2
    probs = [abs(a) ** 2 for a in _state]
    choice = random.choices(SUBSYSTEMS, weights=probs, k=1)[0]
    return choice


if __name__ == "__main__":
    # Simple demo loop
    for _ in range(20):
        print(f"{time.time():.0f} → {select_subsystem()}")
        time.sleep(0.5)
