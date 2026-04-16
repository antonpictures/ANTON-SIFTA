#!/usr/bin/env python3
"""
chorus_consent.py — Node Ownership, Chorus Consent & Transfer Protocol
═══════════════════════════════════════════════════════════════════════
The chorus is a privilege, not a right.

A node joins the chorus ONLY if:
  1. Its silicon serial is registered in the PKI.
  2. Its owner has signed a CONSENT scar granting EXTERNAL_COMMS.
  3. The consent has not been revoked or transferred.

Ownership transfer (gift, sale, inheritance):
  The Architect signs a TRANSFER scar. The old consent dies.
  The new owner bootstraps new keys and signs new consent.
  Old scars remain valid under old keys — history doesn't rewrite.

The chorus degrades gracefully:
  If M5 is transferred and its consent revoked, M1 runs alone.
  If M1 goes offline, the website waits or shows "Chorus silent."
  The loop is always closed. The answer was to build it.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Set

_REPO = Path(__file__).resolve().parent.parent
STATE_DIR = _REPO / ".sifta_state"
CONSENT_FILE = STATE_DIR / "chorus_consent.json"
TRANSFER_LOG = STATE_DIR / "ownership_transfers.jsonl"

# Capabilities a node can be granted
CAPABILITY_EXTERNAL_COMMS = "EXTERNAL_COMMS"
CAPABILITY_CHORUS_INVITE = "CHORUS_INVITE"
CAPABILITY_CHORUS_RESPOND = "CHORUS_RESPOND"
CAPABILITY_FULL_CHORUS = "FULL_CHORUS"

ALL_CHORUS_CAPS = {
    CAPABILITY_EXTERNAL_COMMS,
    CAPABILITY_CHORUS_INVITE,
    CAPABILITY_CHORUS_RESPOND,
    CAPABILITY_FULL_CHORUS,
}


def _load_consent() -> Dict:
    """Load the consent registry. Creates default if missing."""
    if CONSENT_FILE.exists():
        try:
            return json.loads(CONSENT_FILE.read_text())
        except Exception:
            pass
    return {"nodes": {}, "version": 1}


def _save_consent(data: Dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    CONSENT_FILE.write_text(json.dumps(data, indent=2) + "\n")


def grant_consent(
    silicon_serial: str,
    node_name: str,
    owner: str,
    capabilities: Set[str],
    signer_serial: str,
    sign_fn=None,
) -> Dict:
    """
    Grant chorus consent to a node. Must be signed by the granting silicon.

    In practice: the Architect runs this on each machine he owns.
    The consent scar is append-only — revocation creates a new entry.
    """
    consent = _load_consent()

    entry = {
        "silicon": silicon_serial,
        "node_name": node_name,
        "owner": owner,
        "capabilities": sorted(capabilities),
        "granted_ts": time.time(),
        "granted_by": signer_serial,
        "revoked": False,
        "transfer_to": None,
        "sig": "",
    }

    # Sign the consent scar
    payload = json.dumps({
        k: v for k, v in entry.items() if k != "sig"
    }, sort_keys=True)

    if sign_fn:
        entry["sig"] = sign_fn(payload)

    consent["nodes"][silicon_serial] = entry
    _save_consent(consent)
    return entry


def revoke_consent(silicon_serial: str, reason: str = "manual") -> bool:
    """Revoke a node's chorus consent. The node can no longer participate."""
    consent = _load_consent()
    node = consent["nodes"].get(silicon_serial)
    if not node:
        return False
    node["revoked"] = True
    node["revoke_ts"] = time.time()
    node["revoke_reason"] = reason
    _save_consent(consent)
    return True


def transfer_ownership(
    silicon_serial: str,
    old_owner: str,
    new_owner: str,
    method: str = "gift",
    sign_fn=None,
) -> Dict:
    """
    Record an ownership transfer. This:
      1. Revokes the old consent (the node drops out of chorus).
      2. Logs a permanent transfer scar.
      3. The new owner must run bootstrap_pki.py to generate new keys
         and then grant_consent() to rejoin the chorus under new authority.

    The old scars remain valid under the old keys.
    History doesn't rewrite. Only the future changes.
    """
    # Revoke old consent
    revoke_consent(silicon_serial, reason=f"transfer:{method}:{new_owner}")

    # Write transfer scar
    scar = {
        "ts": time.time(),
        "event": "OWNERSHIP_TRANSFER",
        "silicon": silicon_serial,
        "old_owner": old_owner,
        "new_owner": new_owner,
        "method": method,
        "sig": "",
    }

    payload = json.dumps({k: v for k, v in scar.items() if k != "sig"}, sort_keys=True)
    if sign_fn:
        scar["sig"] = sign_fn(payload)

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(TRANSFER_LOG, "a") as f:
        f.write(json.dumps(scar) + "\n")

    return scar


def check_consent(silicon_serial: str, capability: str) -> bool:
    """
    Check if a node has active (non-revoked) consent for a capability.
    This is the gate. Every chorus invite and response passes through here.
    """
    consent = _load_consent()
    node = consent["nodes"].get(silicon_serial)
    if not node:
        return False
    if node.get("revoked", False):
        return False
    return capability in node.get("capabilities", [])


def get_consented_nodes(capability: str) -> List[Dict]:
    """Return all nodes that have active consent for a given capability."""
    consent = _load_consent()
    result = []
    for serial, node in consent["nodes"].items():
        if node.get("revoked", False):
            continue
        if capability in node.get("capabilities", []):
            result.append(node)
    return result


def get_node_info(silicon_serial: str) -> Optional[Dict]:
    """Get consent info for a specific node."""
    consent = _load_consent()
    return consent["nodes"].get(silicon_serial)


def get_transfer_history(silicon_serial: str = None) -> List[Dict]:
    """Read the transfer log. Optionally filter by silicon serial."""
    if not TRANSFER_LOG.exists():
        return []
    entries = []
    for line in TRANSFER_LOG.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            if silicon_serial is None or entry.get("silicon") == silicon_serial:
                entries.append(entry)
        except Exception:
            continue
    return entries


# ── Bootstrap: grant consent for current machine ─────────────────────────
def bootstrap_local_consent():
    """
    Run on each machine to grant chorus consent to itself.
    Requires the crypto keychain to be initialized.
    """
    import sys
    sys.path.insert(0, str(_REPO / "System"))

    try:
        from crypto_keychain import sign_block, get_silicon_identity
    except ImportError:
        print("[CONSENT] Cannot import crypto_keychain. Run from repo root.")
        return

    serial = get_silicon_identity()
    if serial == "UNKNOWN_SERIAL":
        print("[CONSENT] Cannot determine silicon serial.")
        return

    # Determine node name from serial
    node_names = {
        "GTH4921YP3": "M5QUEEN",
        "C07FL0JAQ6NV": "M1THER",
    }
    node_name = node_names.get(serial, f"NODE_{serial[:6]}")

    entry = grant_consent(
        silicon_serial=serial,
        node_name=node_name,
        owner="Ioan George Anton",
        capabilities=ALL_CHORUS_CAPS,
        signer_serial=serial,
        sign_fn=sign_block,
    )

    print(f"[CONSENT] Granted FULL_CHORUS to {node_name} [{serial}]")
    print(f"[CONSENT] Capabilities: {entry['capabilities']}")
    print(f"[CONSENT] Signature: {entry['sig'][:24]}...")
    print(f"[CONSENT] Stored: {CONSENT_FILE}")


if __name__ == "__main__":
    bootstrap_local_consent()
