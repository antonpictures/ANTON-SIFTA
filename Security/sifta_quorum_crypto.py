# sifta_quorum_crypto.py

import json
import time
import base64
import os
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization

KEY_PATH = Path.home() / ".sifta" / "identity.pem"
PUBKEY_PATH = Path.home() / ".sifta" / "identity.pub.pem"


def _load_private_key():
    with open(KEY_PATH, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)


def sign_vote(agent_id: str, proposal_id: str, vote: str) -> dict:
    """
    vote: "APPROVE" or "REJECT"
    """
    payload = {
        "agent_id": agent_id,
        "proposal_id": proposal_id,
        "vote": vote,
        "timestamp": time.time()
    }

    raw = json.dumps(payload, sort_keys=True).encode()
    priv = _load_private_key()
    sig = priv.sign(raw)

    return {
        "payload": payload,
        "signature": base64.b64encode(sig).decode()
    }


def get_pubkey(agent_id: str) -> bytes:
    """In a true distributed network, we would lookup agent_id's registered pubkey.
    For this monolithic node simulation, we load the singular node identity."""
    with open(PUBKEY_PATH, "rb") as f:
        return f.read()


def verify_vote(signed_vote: dict, pubkey_bytes: bytes) -> bool:
    try:
        # Load the public key
        pub = serialization.load_pem_public_key(pubkey_bytes)
        if not isinstance(pub, Ed25519PublicKey):
            return False

        # Sort the keys exactly as signed
        raw = json.dumps(signed_vote["payload"], sort_keys=True).encode()
        sig = base64.b64decode(signed_vote["signature"])
        
        pub.verify(sig, raw)
        return True
    except Exception:
        return False
