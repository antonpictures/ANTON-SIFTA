#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# SIFTA OS — Biological Cryptography (Ed25519 Keychain)
# ─────────────────────────────────────────────────────────────
# Associates a node identifier with an Ed25519 key held by this OS account.
# Signatures prove key possession, not exclusive execution on physical hardware.
# ─────────────────────────────────────────────────────────────

import os
import json
import fcntl
import stat
import tempfile
from contextlib import contextmanager

try:
    from silicon_serial import read_apple_serial
except ImportError:  # Package import path, e.g. `from System.crypto_keychain`.
    from System.silicon_serial import read_apple_serial
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_DIR = os.path.join(REPO_ROOT, ".sifta_state")
PKI_REGISTRY = os.path.join(STATE_DIR, "node_pki_registry.json")

KEY_DIR = os.path.expanduser("~/.sifta_keys")
PRIV_KEY_FILE = os.path.join(KEY_DIR, "private.pem")

def get_silicon_identity():
    """Extract hardware-bound identity directly from macOS (delegates to silicon_serial)."""
    s = read_apple_serial()
    return s if s else "UNKNOWN_SERIAL"

def get_genesis_anchor() -> str:
    """Combines hardware serial with the root biological anchor (Lana's picture hash)."""
    hw_id = get_silicon_identity()
    anchor_path = os.path.join(REPO_ROOT, "lana_kernel_pic.PNG")
    if os.path.exists(anchor_path):
        import hashlib
        with open(anchor_path, "rb") as f:
            h = hashlib.sha256(f.read()).hexdigest()
        return f"{hw_id}::ANCHOR::{h}"
    return f"{hw_id}::NO_ANCHOR"

@contextmanager
def _private_file(path, flags):
    fd = os.open(path, flags | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1:
            raise PermissionError("Keychain file must be a regular, singly linked file owned by this user")
        os.fchmod(fd, 0o600)
        yield fd
    finally:
        os.close(fd)


def _load_private_key():
    with _private_file(PRIV_KEY_FILE, os.O_RDONLY) as fd:
        with os.fdopen(os.dup(fd), "rb") as stream:
            key = serialization.load_pem_private_key(stream.read(), password=None)
    if not isinstance(key, ed25519.Ed25519PrivateKey):
        raise ValueError("Expected an Ed25519 private key")
    return key


def _atomic_write(path, content):
    pending = None
    try:
        with tempfile.NamedTemporaryFile(dir=os.path.dirname(path), delete=False) as stream:
            pending = stream.name
            os.fchmod(stream.fileno(), 0o600)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(pending, path)
    finally:
        if pending and os.path.exists(pending):
            os.unlink(pending)


def _ensure_keychain():
    """Preserve the account key; serialize creation and fail closed on trust mismatch."""
    os.makedirs(KEY_DIR, mode=0o700, exist_ok=True)
    info = os.lstat(KEY_DIR)
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
        raise PermissionError("Key directory must be owned by this user and cannot be a symlink")
    os.chmod(KEY_DIR, 0o700)
    with _private_file(os.path.join(KEY_DIR, ".keychain.lock"), os.O_RDWR | os.O_CREAT) as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not os.path.lexists(PRIV_KEY_FILE):
            key = ed25519.Ed25519PrivateKey.generate()
            _atomic_write(PRIV_KEY_FILE, key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ))
        key = _load_private_key()
        _sync_public_key(key.public_key())

def _sync_public_key(pub_key):
    hw_serial = get_silicon_identity()
    pub_hex = pub_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    ).hex()

    registry = {}
    if os.path.exists(PKI_REGISTRY):
        with open(PKI_REGISTRY, "r") as f:
            registry = json.load(f)
        if not isinstance(registry, dict):
            raise ValueError("Invalid PKI registry; refusing to replace trust records")

    if hw_serial in registry and registry[hw_serial] != pub_hex:
        raise ValueError("Local key differs from trusted node key; explicit key recovery is required")
    if hw_serial not in registry:
        registry[hw_serial] = pub_hex
        os.makedirs(os.path.dirname(PKI_REGISTRY), exist_ok=True)
        _atomic_write(PKI_REGISTRY, json.dumps(registry, indent=2).encode("utf-8"))

def sign_block(payload: str) -> str:
    """Sign with this OS account's key, without claiming hardware attestation."""
    _ensure_keychain()
    private_key = _load_private_key()
    
    signature = private_key.sign(payload.encode('utf-8'))
    return signature.hex()

def verify_block(hardware_serial: str, payload: str, signature_hex: str) -> bool:
    """Verify payload integrity against the locally trusted public key for a node."""
    if not os.path.exists(PKI_REGISTRY):
        return False
        
    try:
        with open(PKI_REGISTRY, "r") as f:
            registry = json.load(f)
    except Exception:
        return False

    if not isinstance(registry, dict):
        return False
    pub_hex = registry.get(hardware_serial)
    if not pub_hex:
        return False

    try:
        # ── Pre-validate hex format silently ──────────────────────
        # Legacy signatures (SEAL_, NO_KEYCHAIN_, MARKET_, etc.)
        # are not valid hex and must never spam the console.
        if not signature_hex or not isinstance(signature_hex, str):
            return False
        hex_chars = set("0123456789abcdefABCDEF")
        if not all(c in hex_chars for c in signature_hex):
            return False  # silent reject — not a hex signature
        if not all(c in hex_chars for c in pub_hex):
            return False

        # Reconstruct public key
        pub_bytes = bytes.fromhex(pub_hex)
        public_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)

        # Reconstruct sig bytes
        sig_bytes = bytes.fromhex(signature_hex)

        # Verify
        public_key.verify(sig_bytes, payload.encode('utf-8'))
        return True
    except InvalidSignature:
        return False
    except Exception as e:
        # Only print truly unexpected errors (not hex noise)
        print(f"[CRYPTO] Unexpected verify error for {hardware_serial}: {e}")
        return False

if __name__ == "__main__":
    _ensure_keychain()
    print("Biological Cryptography Layer Active.")
