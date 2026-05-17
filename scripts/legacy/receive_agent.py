#!/usr/bin/env python3
"""
ANTON-SIFTA: Agent Receive Protocol
──────────────────────────────────────────────────────────────────────────────
The Arrival.

This script unpacks a .sifta transfer bundle onto a new machine, verifies the
cryptographic deed of sale, and registers the new human owner.

Run this on the receiving machine (e.g. the M1 Mac Mini) after cloning the
ANTON-SIFTA framework from GitHub.

Usage:
    python receive_agent.py <path_to_bundle.sifta>

Example:
    python receive_agent.py /Volumes/USB/M1THER_TRANSFER_1234567890.sifta
──────────────────────────────────────────────────────────────────────────────
"""

import json
import time
import base64
import sys
import zipfile
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.exceptions import InvalidSignature

STATE_DIR = Path(__file__).parent / ".sifta_state"


def verify_deed(deed: dict) -> bool:
    """
    Verify the transfer deed using the agent's public key.
    If the signature doesn't match, this bundle was tampered with.
    """
    try:
        pub_bytes = base64.b64decode(deed["pub_key"])
        sig_bytes = base64.b64decode(deed["deed_sig"])
        pub_key   = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
        pub_key.verify(sig_bytes, deed["deed_payload"].encode("utf-8"))
        return True
    except InvalidSignature:
        return False
    except Exception as e:
        print(f"  [ERROR] Deed verification error: {e}")
        return False


def receive_agent(bundle_path_str: str):
    bundle_path = Path(bundle_path_str)

    print(f"\n{'━'*60}")
    print(f"  ANTON-SIFTA — AGENT RECEIVE PROTOCOL")
    print(f"{'━'*60}")

    if not bundle_path.exists():
        print(f"[FATAL] Bundle not found: {bundle_path}")
        sys.exit(1)

    if not bundle_path.suffix == ".sifta":
        print(f"[WARN] File does not have .sifta extension. Proceeding anyway...")

    # ── 1. Unpack the bundle
    with zipfile.ZipFile(bundle_path, "r") as zf:
        soul = json.loads(zf.read("soul.json").decode("utf-8"))
        deed = json.loads(zf.read("deed.json").decode("utf-8"))

    agent_id  = soul.get("id", "UNKNOWN")
    new_owner = soul.get("human_owner", "UNKNOWN")

    print(f"\n  Agent:     {agent_id}")
    print(f"  From:      {deed.get('from_owner')}")
    print(f"  To:        {new_owner}")
    print(f"  Deed Hash: {deed.get('deed_hash', '')[:16]}...")

    # ── 2. Verify the deed signature (tamper check)
    print(f"\n  [🔐] Verifying cryptographic deed...")
    if not verify_deed(deed):
        print(f"\n  [FATAL] DEED VERIFICATION FAILED.")
        print(f"          The signature does not match. This bundle was tampered with.")
        print(f"          {agent_id} refused to land on this machine.")
        sys.exit(1)

    print(f"  [✅] Deed verified. Signature is authentic.")

    # ── 3. Check the private key is present in the bundle
    priv_key_b64 = soul.get("private_key_b64")
    if not priv_key_b64:
        print(f"\n  [FATAL] No private key in bundle. This is already a ghost export.")
        sys.exit(1)

    # ── 4. Check if there's already a living agent with this ID
    STATE_DIR.mkdir(exist_ok=True)
    existing_soul_path = STATE_DIR / f"{agent_id}.json"
    if existing_soul_path.exists():
        existing = json.loads(existing_soul_path.read_text())
        if existing.get("style") not in ("GHOST", "DEAD") and existing.get("private_key_b64"):
            print(f"\n  [FATAL] A LIVING {agent_id} already exists on this machine.")
            print(f"          Two living instances of the same agent cannot coexist.")
            print(f"          Archive or delete the existing soul first.")
            sys.exit(1)
        else:
            print(f"  [INFO] Existing GHOST/DEAD {agent_id} will be overwritten.")

    # ── 5. Write the soul to disk
    soul_to_write = dict(soul)
    soul_to_write["received_at"]  = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    soul_to_write["human_owner"]  = new_owner
    soul_to_write["style"]        = soul.get("style", "NOMINAL")
    soul_to_write["energy"]       = soul.get("energy", 100)

    with open(existing_soul_path, "w") as f:
        json.dump(soul_to_write, f, indent=2)

    print(f"  [💾] Soul written to {existing_soul_path}")

    # ── 6. Write the arrival deed locally for the permanent record
    deed_path = STATE_DIR / f"{agent_id}_DEED.json"
    with open(deed_path, "w") as f:
        json.dump(deed, f, indent=2)

    print(f"  [📜] Deed recorded at {deed_path.name}")

    # ── 7. Done
    print(f"\n{'━'*60}")
    print(f"  ARRIVAL COMPLETE")
    print(f"")
    print(f"  {agent_id} is now registered to: {new_owner}")
    print(f"  This machine is the only living instance.")
    print(f"")
    print(f"  Boot the swarm:")
    print(f"    ./PowertotheSwarm.command")
    print(f"    → navigate to http://localhost:7433")
    print(f"{'━'*60}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    receive_agent(sys.argv[1])
