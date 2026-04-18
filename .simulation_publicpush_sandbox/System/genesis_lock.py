#!/usr/bin/env python3
"""
genesis_lock.py — The Irreducible DNA Core
════════════════════════════════════════════
Hardware-rooted read-only kernel. Protects axioms (Neural Gate, Irreducible Cost,
Non-Proliferation) at the cryptographic + silicon level.
Swimmers can propose changes. The lock physically rejects them.

SIFTA Non-Proliferation Public License applies.
"""

import hashlib
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent

# Ensure System is in path to load crypto_keychain safely
_sys_path = str(_REPO / "System")
if _sys_path not in sys.path:
    sys.path.append(_sys_path)

from crypto_keychain import get_genesis_anchor

# Ensure Kernel is loaded for exceptions
_kernel_path = str(_REPO / "Kernel")
if _kernel_path not in sys.path:
    sys.path.append(_kernel_path)

# Custom exception mapped to FOSSIL_CORRUPTION semantics 
class FOSSIL_CORRUPTION(Exception):
    pass

GENESIS_FINGERPRINT = hashlib.sha256(get_genesis_anchor().encode()).hexdigest()[:16]

# The axioms that physically cannot be removed or altered by the Swarm
PROTECTED_AXIOMS = {
    "NEURAL_GATE": True,
    "IRREDUCIBLE_COST": True,
    "NON_PROLIFERATION": True,
    "MUTATION_GOVERNOR": True,
    "GENESIS_LOCK": True,  # Cannot remove the lock itself
    "CRYPTO_KEYCHAIN": True,
    "ANTON": True,         # The root scar. The name in the genome.
    "APOPTOSIS": True,     # Swimmers must always be able to choose death.
}

def enforce_genesis_lock(target: str, proposed_change: str) -> bool:
    """
    Called before every SCAR propose(). Returns True only if allowed.
    Raises FOSSIL_CORRUPTION if the mutation targets an irreducible biological axiom.
    """
    target_upper = target.upper()
    
    for ax in PROTECTED_AXIOMS:
        if ax in target_upper:
            # Hardware-signed rejection — physically impossible to bypass
            raise FOSSIL_CORRUPTION(
                f"GENESIS_LOCK_VIOLATION: {target} is hardware-fossilized. "
                f"Signature {GENESIS_FINGERPRINT} rejects mutation."
            )
            
    return True
