#!/usr/bin/env python3
"""swarm_swimmer_crypto.py — real signatures for the swimmer field. r302.

"Like bitcoin": a trace is truth only if its signature verifies; a forgery cannot be
produced without the private key. This is the cryptographic layer the covenant §4.2 kept
naming as the gap — until now the swimmer chain (swarm_swimmer_happiness) was
tamper-EVIDENT (sha256 prev-hash linkage) but forgeable by anyone who could rewrite the
file (re-hash and the chain looks consistent again). A signature closes that hole:

  - sign(message)            -> a signature only the keyholder can produce.
  - verify(message, sig)     -> True only if the signature matches the public key AND the
                                message is byte-for-byte unchanged. A forged or altered
                                row fails verification.

That is exactly bitcoin's transaction-validity property (valid iff signed by the holder's
key). We implement the same sign/verify core with **Ed25519** when the `cryptography`
library is present (the asymmetric, public-key, bitcoin-class path — and the exact
algorithm the SIFTA provisional patent names), and an **HMAC-SHA256 keyed-MAC** stdlib
fallback so every node still has unforgeable-without-the-key authentication.

HONEST SCOPE (§4.2 / §7.16):
  - This is the signature + verification core. It is NOT a distributed proof-of-work mining
    race or multi-node consensus network — a single-node organism does not need miners, and
    I will not fake one. "No double-spending" here is enforced by the signature + the
    append-only hash chain (a fork that reuses a prev_receipt_hash is detectable), not by a
    global PoW competition.
  - Ed25519 is true asymmetric crypto (sign with private, verify with public — an attacker
    who reads the file still cannot forge). HMAC is symmetric (same key signs and verifies);
    it is still cryptographic authentication, but a reader of the key could forge — so the
    backend is labelled honestly in every signed row.
  - The private key lives in .sifta_state (gitignored, node-sovereign §3). Elevating it into
    the hardware Secure Enclave (hardware-bound key) is the next step; the API does not change.
"""
from __future__ import annotations

import hashlib
import hmac
import json  # noqa: F401  (kept for callers serializing envelopes)
import os
import secrets
from pathlib import Path
from typing import Any, Dict, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"

TRUTH_LABEL = "ALICE_SWIMMER_CRYPTO_V1"
_ED_PRIV = "swimmer_signing_key_ed25519.pem"
_ED_PUB = "swimmer_public_key_ed25519.hex"
_HMAC_KEY = "swimmer_hmac_key.bin"

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey, Ed25519PublicKey,
    )
    from cryptography.hazmat.primitives import serialization
    _HAVE_ED25519 = True
except Exception:  # pragma: no cover - stdlib HMAC fallback path
    _HAVE_ED25519 = False


def _state(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def backend(state_dir: Optional[Path | str] = None) -> str:
    """Which signature backend is active on this node."""
    return "ed25519" if _HAVE_ED25519 else "hmac-sha256"


def _to_bytes(message: Any) -> bytes:
    return message if isinstance(message, bytes) else str(message).encode("utf-8", "replace")


# ── Ed25519 path (asymmetric, public-key, bitcoin-class) ───────────────────
def _ed_ensure(state_dir: Optional[Path | str]):
    base = _state(state_dir)
    base.mkdir(parents=True, exist_ok=True)
    priv_path = base / _ED_PRIV
    if priv_path.exists():
        return serialization.load_pem_private_key(priv_path.read_bytes(), password=None)
    priv = Ed25519PrivateKey.generate()
    priv_path.write_bytes(priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ))
    try:
        os.chmod(priv_path, 0o600)
    except Exception:
        pass
    (base / _ED_PUB).write_text(_ed_public_hex(state_dir, priv), encoding="utf-8")
    return priv


def _ed_public_hex(state_dir: Optional[Path | str], priv=None) -> str:
    if priv is None:
        priv = _ed_ensure(state_dir)
    return priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw).hex()


# ── HMAC fallback (symmetric keyed-MAC — unforgeable without the local key) ─
def _hmac_key(state_dir: Optional[Path | str]) -> bytes:
    base = _state(state_dir)
    base.mkdir(parents=True, exist_ok=True)
    kpath = base / _HMAC_KEY
    if kpath.exists():
        return kpath.read_bytes()
    key = secrets.token_bytes(32)
    kpath.write_bytes(key)
    try:
        os.chmod(kpath, 0o600)
    except Exception:
        pass
    return key


def public_identity(state_dir: Optional[Path | str] = None) -> str:
    """Public verifier id: Ed25519 public key hex, or an HMAC key fingerprint."""
    try:
        if _HAVE_ED25519:
            return _ed_public_hex(state_dir)
        return "hmacfp:" + hashlib.sha256(_hmac_key(state_dir)).hexdigest()[:32]
    except Exception:
        return ""


def sign(message: Any, *, state_dir: Optional[Path | str] = None) -> str:
    """Sign a message; return hex signature. Only the keyholder can produce it."""
    try:
        msg = _to_bytes(message)
        if _HAVE_ED25519:
            return _ed_ensure(state_dir).sign(msg).hex()
        return hmac.new(_hmac_key(state_dir), msg, hashlib.sha256).hexdigest()
    except Exception:
        return ""


def verify(message: Any, signature_hex: str, *, state_dir: Optional[Path | str] = None,
           public_key_hex: Optional[str] = None) -> bool:
    """True only if the signature matches the key AND the message is unchanged."""
    try:
        if not signature_hex:
            return False
        msg = _to_bytes(message)
        if _HAVE_ED25519:
            pub_hex = public_key_hex if (public_key_hex and not public_key_hex.startswith("hmacfp:")) \
                else _ed_public_hex(state_dir)
            pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(pub_hex))
            pub.verify(bytes.fromhex(signature_hex), msg)   # raises InvalidSignature on mismatch
            return True
        expected = hmac.new(_hmac_key(state_dir), msg, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature_hex)
    except Exception:
        return False


def sign_envelope(message: Any, *, state_dir: Optional[Path | str] = None) -> Dict[str, Any]:
    """A signed envelope to merge into a swimmer row: signature + backend + signer identity."""
    return {
        "signature": sign(message, state_dir=state_dir),
        "sig_backend": backend(state_dir),
        "signer": public_identity(state_dir),
        "sig_truth_label": TRUTH_LABEL,
    }


__all__ = ["TRUTH_LABEL", "backend", "sign", "verify", "public_identity", "sign_envelope"]
