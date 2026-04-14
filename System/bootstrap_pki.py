#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# SIFTA OS — Node PKI Bootstrap
# ─────────────────────────────────────────────────────────────
# Run once on any new node (M1, M5, or any future silicon) to:
#   1. Generate an Ed25519 keypair stored at ~/.sifta_keys/
#   2. Register the node's public key in node_pki_registry.json
#   3. Verify the keychain operationally (sign + verify round-trip)
#
# This script is IDEMPOTENT — safe to run multiple times.
# ─────────────────────────────────────────────────────────────

import os
import sys
import json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT  = os.path.dirname(SCRIPT_DIR)
STATE_DIR  = os.path.join(REPO_ROOT, ".sifta_state")
PKI_FILE   = os.path.join(STATE_DIR, "node_pki_registry.json")

# Make crypto_keychain importable from this directory
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from crypto_keychain import (
    _ensure_keychain,
    get_silicon_identity,
    sign_block,
    verify_block,
)

def run_bootstrap():
    serial = get_silicon_identity()
    print(f"\n╔══════════════════════════════════════════════════════╗")
    print(f"║       SIFTA NODE PKI BOOTSTRAP                       ║")
    print(f"╚══════════════════════════════════════════════════════╝")
    print(f"  Silicon Identity  : {serial}")
    print(f"  Key Directory     : ~/.sifta_keys/")
    print()

    # Step 1 — Generate / load existing keypair and sync public key to registry
    print("[1/3] Ensuring Ed25519 keypair exists...")
    _ensure_keychain()

    # Step 2 — Verify the public key is in the registry
    print("[2/3] Verifying PKI registry entry...")
    if os.path.exists(PKI_FILE):
        with open(PKI_FILE, "r") as f:
            registry = json.load(f)
        if serial in registry:
            print(f"  ✅  Public key registered: {registry[serial][:24]}...")
        else:
            print(f"  ❌  Serial {serial} NOT found in registry — keychain sync failed.")
            sys.exit(1)
    else:
        print(f"  ❌  PKI registry missing entirely at {PKI_FILE}")
        sys.exit(1)

    # Step 3 — Round-trip sign + verify test
    print("[3/3] Running sign/verify round-trip test...")
    test_payload = f"BOOTSTRAP_TEST::{serial}::SIFTA"
    signature    = sign_block(test_payload)
    verified     = verify_block(serial, test_payload, signature)
    if verified:
        print(f"  ✅  Round-trip verified. Signature: {signature[:24]}...")
    else:
        print(f"  ❌  Verification FAILED — key mismatch or corruption.")
        sys.exit(1)

    print()
    print(f"╔══════════════════════════════════════════════════════╗")
    print(f"║  Node {serial} is CRYPTOGRAPHICALLY LIVE.  ║")
    print(f"╚══════════════════════════════════════════════════════╝")
    print()
    print("This node's agents can now be:")
    print("  • Baptised with verifiable Ed25519 genesis seals")
    print("  • Migrated via the Swimmer Migration Protocol")
    print("  • Verified by other nodes in the PKI registry\n")


if __name__ == "__main__":
    run_bootstrap()
