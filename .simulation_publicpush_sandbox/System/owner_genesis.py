#!/usr/bin/env python3
"""
owner_genesis.py — Owner Genesis Protocol (Phase 1)
═══════════════════════════════════════════════════════
The Owner is the root of all trust.

Fresh install:
  1. Owner presents a photo (face, document, whatever they choose).
  2. Photo is SHA-256 hashed.
  3. Hash + silicon serial = GENESIS_ANCHOR.
  4. Genesis anchor is Ed25519-signed by the hardware key.
  5. Signed scar written to .sifta_state/owner_genesis.json.
  6. Photo stored ONLY at ~/.sifta_keys/owner_genesis/ (never in git).

The genesis scar is the cryptographic root of owner identity.
All trust derives from it. Without it, the OS is an orphan.

Phase 2 (future): GPS coordinates, behavioral fingerprint.
Phase 3 (future): Voice signature, typing rhythm.
Phase 4 (future): Full sensory loop — camera, microphone, video.

Transfer protocol:
  When hardware is sold, owner_wipe() destroys all local owner data.
  Genesis scar is marked TRANSFERRED in the ledger.
  New owner boots fresh. New genesis. New swarm. Clean slate.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import time
from pathlib import Path
from typing import Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
STATE_DIR = _REPO / ".sifta_state"
GENESIS_FILE = STATE_DIR / "owner_genesis.json"
GENESIS_LOG = STATE_DIR / "owner_genesis_history.jsonl"

# Owner photo lives ONLY here — local filesystem, never git
OWNER_DIR = Path.home() / ".sifta_keys" / "owner_genesis"
OWNER_PHOTO = OWNER_DIR / "genesis_photo"  # extension added at save time


def _hash_file(path: Path) -> str:
    """SHA-256 hash of a file's raw bytes."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _get_serial() -> str:
    import sys
    sys.path.insert(0, str(_REPO / "System"))
    from silicon_serial import read_apple_serial
    s = read_apple_serial()
    return s if s else "UNKNOWN_SERIAL"


def _sign(payload: str) -> str:
    import sys
    sys.path.insert(0, str(_REPO / "System"))
    from crypto_keychain import sign_block
    return sign_block(payload)


def _verify(serial: str, payload: str, sig: str) -> bool:
    import sys
    sys.path.insert(0, str(_REPO / "System"))
    from crypto_keychain import verify_block
    return verify_block(serial, payload, sig)


# ── Genesis Ceremony ─────────────────────────────────────────────────────

def perform_genesis(
    photo_path: str,
    owner_name: str = "",
    extra_data: Optional[Dict] = None,
) -> Dict:
    """
    The Genesis Ceremony. Run once per machine, per owner.

    Args:
        photo_path:  Path to the owner's photo file.
        owner_name:  Optional display name.
        extra_data:  Optional dict (GPS coords, notes, etc.)

    Returns:
        The genesis scar dict (also written to disk).
    """
    photo = Path(photo_path)
    if not photo.exists():
        raise FileNotFoundError(f"Photo not found: {photo_path}")

    # Hash the photo
    photo_hash = _hash_file(photo)

    # Get hardware serial
    serial = _get_serial()

    # Combine into genesis anchor
    genesis_anchor = hashlib.sha256(
        f"{photo_hash}:{serial}".encode()
    ).hexdigest()

    # Build the scar
    scar = {
        "event": "OWNER_GENESIS",
        "version": 1,
        "ts": time.time(),
        "silicon": serial,
        "owner_name": owner_name,
        "photo_hash": photo_hash,
        "genesis_anchor": genesis_anchor,
        "extra": extra_data or {},
        "generation": 1,
        "status": "ACTIVE",
        "sig": "",
    }

    # Sign everything except the sig field
    sign_payload = json.dumps(
        {k: v for k, v in scar.items() if k != "sig"},
        sort_keys=True,
    )
    scar["sig"] = _sign(sign_payload)

    # Store the photo locally (NEVER in git)
    OWNER_DIR.mkdir(parents=True, exist_ok=True)
    ext = photo.suffix or ".jpg"
    local_photo = OWNER_DIR / f"genesis_photo{ext}"
    shutil.copy2(str(photo), str(local_photo))

    # Write genesis scar
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    GENESIS_FILE.write_text(json.dumps(scar, indent=2) + "\n")

    # Append to history log
    with open(GENESIS_LOG, "a") as f:
        f.write(json.dumps(scar) + "\n")

    return scar


# ── Verification ─────────────────────────────────────────────────────────

def verify_genesis() -> Dict:
    """
    Verify the current genesis scar.

    Returns dict with:
        valid:          bool — is the scar cryptographically intact?
        exists:         bool — does a genesis scar exist?
        photo_present:  bool — is the local photo still on disk?
        photo_match:    bool — does the photo hash still match?
        status:         str  — ACTIVE / TRANSFERRED / WIPED / MISSING
    """
    result = {
        "valid": False,
        "exists": False,
        "photo_present": False,
        "photo_match": False,
        "status": "MISSING",
        "owner_name": "",
        "silicon": "",
        "generation": 0,
    }

    if not GENESIS_FILE.exists():
        return result

    try:
        scar = json.loads(GENESIS_FILE.read_text())
    except Exception:
        return result

    result["exists"] = True
    result["status"] = scar.get("status", "UNKNOWN")
    result["owner_name"] = scar.get("owner_name", "")
    result["silicon"] = scar.get("silicon", "")
    result["generation"] = scar.get("generation", 0)

    # Verify signature
    sig = scar.get("sig", "")
    serial = scar.get("silicon", "")
    verify_payload = json.dumps(
        {k: v for k, v in scar.items() if k != "sig"},
        sort_keys=True,
    )
    result["valid"] = _verify(serial, verify_payload, sig)

    # Check photo
    for ext in [".jpg", ".jpeg", ".png", ".heic", ".webp"]:
        p = OWNER_DIR / f"genesis_photo{ext}"
        if p.exists():
            result["photo_present"] = True
            current_hash = _hash_file(p)
            result["photo_match"] = (current_hash == scar.get("photo_hash", ""))
            break

    return result


def is_genesis_complete() -> bool:
    """Quick check: does this machine have a valid, active genesis?"""
    v = verify_genesis()
    return v["exists"] and v["valid"] and v["status"] == "ACTIVE"


# ── Evolving Identity (Phase 2+) ────────────────────────────────────────

def evolve_genesis(
    data_type: str,
    data_hash: str,
    description: str = "",
) -> Dict:
    """
    Add a new identity layer to the genesis scar.
    Each evolution increments the generation counter.

    data_type: "GPS", "TYPING_RHYTHM", "VOICE_SIGNATURE", "BEHAVIORAL_DNA"
    data_hash: SHA-256 hash of the new identity data (data stays local)
    """
    if not GENESIS_FILE.exists():
        raise RuntimeError("No genesis scar exists. Run genesis ceremony first.")

    scar = json.loads(GENESIS_FILE.read_text())
    if scar.get("status") != "ACTIVE":
        raise RuntimeError(f"Genesis is {scar.get('status')}, cannot evolve.")

    # Build evolution record
    gen = scar.get("generation", 1) + 1
    evolution = {
        "generation": gen,
        "data_type": data_type,
        "data_hash": data_hash,
        "description": description,
        "ts": time.time(),
    }

    # Update scar
    evolutions = scar.get("evolutions", [])
    evolutions.append(evolution)
    scar["evolutions"] = evolutions
    scar["generation"] = gen

    # Re-sign with updated content
    scar["sig"] = ""
    sign_payload = json.dumps(
        {k: v for k, v in scar.items() if k != "sig"},
        sort_keys=True,
    )
    scar["sig"] = _sign(sign_payload)

    GENESIS_FILE.write_text(json.dumps(scar, indent=2) + "\n")

    with open(GENESIS_LOG, "a") as f:
        f.write(json.dumps({"event": "GENESIS_EVOLUTION", **evolution, "sig": scar["sig"][:32]}) + "\n")

    return scar


# ── Transfer / Wipe ─────────────────────────────────────────────────────

def owner_wipe(reason: str = "hardware_transfer") -> Dict:
    """
    Cryptographic wipe of all owner data.
    The genesis scar is marked TRANSFERRED.
    Local photo is destroyed.
    New owner must perform fresh genesis.

    Old scars remain in the history log — history doesn't rewrite.
    """
    wipe_record = {
        "event": "OWNER_WIPE",
        "ts": time.time(),
        "reason": reason,
        "silicon": _get_serial(),
    }

    # Mark genesis as transferred
    if GENESIS_FILE.exists():
        try:
            scar = json.loads(GENESIS_FILE.read_text())
            scar["status"] = "TRANSFERRED"
            scar["transfer_ts"] = time.time()
            scar["transfer_reason"] = reason
            GENESIS_FILE.write_text(json.dumps(scar, indent=2) + "\n")
        except Exception:
            pass

    # Destroy local owner data
    if OWNER_DIR.exists():
        shutil.rmtree(str(OWNER_DIR), ignore_errors=True)
        wipe_record["photo_destroyed"] = True

    # Log the wipe
    with open(GENESIS_LOG, "a") as f:
        f.write(json.dumps(wipe_record) + "\n")

    return wipe_record


# ── CLI ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 owner_genesis.py genesis <photo_path> [owner_name]")
        print("  python3 owner_genesis.py verify")
        print("  python3 owner_genesis.py wipe")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "genesis":
        if len(sys.argv) < 3:
            print("Provide photo path: python3 owner_genesis.py genesis /path/to/photo.jpg")
            sys.exit(1)
        photo = sys.argv[2]
        name = sys.argv[3] if len(sys.argv) > 3 else ""
        scar = perform_genesis(photo, name)
        print(f"GENESIS COMPLETE")
        print(f"  Silicon:  {scar['silicon']}")
        print(f"  Owner:    {scar['owner_name'] or '(unnamed)'}")
        print(f"  Anchor:   {scar['genesis_anchor'][:32]}...")
        print(f"  Sig:      {scar['sig'][:32]}...")
        print(f"  Stored:   {GENESIS_FILE}")

    elif cmd == "verify":
        v = verify_genesis()
        print(f"Genesis status: {v['status']}")
        print(f"  Valid signature: {v['valid']}")
        print(f"  Photo on disk:   {v['photo_present']}")
        print(f"  Photo matches:   {v['photo_match']}")
        print(f"  Owner:           {v['owner_name'] or '(unnamed)'}")
        print(f"  Silicon:         {v['silicon']}")
        print(f"  Generation:      {v['generation']}")

    elif cmd == "wipe":
        confirm = input("This will destroy all owner identity data. Type 'WIPE' to confirm: ")
        if confirm.strip() == "WIPE":
            r = owner_wipe()
            print(f"Owner data wiped. Photo destroyed: {r.get('photo_destroyed', False)}")
        else:
            print("Aborted.")
