#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# SIFTA OS — Biological Cryptography (Ed25519 Keychain)
# ─────────────────────────────────────────────────────────────
# Anchors raw cryptographic sovereignty to the physical Mac architecture.
# Prevents node 51% forgery by enforcing mathematically verifiable
# payload signatures tied to isolated user-root private keys.
# ─────────────────────────────────────────────────────────────

import os
import json
import subprocess
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_DIR = os.path.join(REPO_ROOT, ".sifta_state")
PKI_REGISTRY = os.path.join(STATE_DIR, "node_pki_registry.json")

KEY_DIR = os.path.expanduser("~/.sifta_keys")
PRIV_KEY_FILE = os.path.join(KEY_DIR, "private.pem")

def get_silicon_identity():
    """Extract hardware-bound identity directly from MacOS."""
    try:
        raw = subprocess.check_output("/usr/sbin/ioreg -l | grep IOPlatformSerialNumber", shell=True)
        return raw.decode().split('"')[-2].strip()
    except Exception:
        return "UNKNOWN_SERIAL"

def _ensure_keychain():
    """Generates the off-mesh Private Key if the biological node natively lacks one."""
    if not os.path.exists(KEY_DIR):
        os.makedirs(KEY_DIR, exist_ok=True)
    
    if not os.path.exists(PRIV_KEY_FILE):
        print(f"[CRYPTO] Generating bare-metal Ed25519 Keys for {get_silicon_identity()}...")
        private_key = ed25519.Ed25519PrivateKey.generate()
        
        # Serialize and freeze to hidden user directory
        priv_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        with open(PRIV_KEY_FILE, "wb") as f:
            f.write(priv_bytes)
        
        # We must sync the public key to the Swarm Mesh Registry
        _sync_public_key(private_key.public_key())
    
    # Check if PKI dict needs our public key updated
    try:
        with open(PRIV_KEY_FILE, "rb") as f:
            private_key = serialization.load_pem_private_key(f.read(), password=None)
            _sync_public_key(private_key.public_key())
    except Exception as e:
        print(f"Keychain load error: {e}")

def _sync_public_key(pub_key):
    hw_serial = get_silicon_identity()
    pub_hex = pub_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    ).hex()

    registry = {}
    if os.path.exists(PKI_REGISTRY):
        try:
            with open(PKI_REGISTRY, "r") as f:
                registry = json.load(f)
        except: pass

    if registry.get(hw_serial) != pub_hex:
        registry[hw_serial] = pub_hex
        with open(PKI_REGISTRY, "w") as f:
            json.dump(registry, f, indent=2)
        print(f"[CRYPTO] Synchronized Public Key {pub_hex[:12]}... to {hw_serial} in PKI.")

def sign_block(payload: str) -> str:
    """Signs a given string payload using the physical hardware's private key."""
    _ensure_keychain()
    with open(PRIV_KEY_FILE, "rb") as f:
        private_key = serialization.load_pem_private_key(f.read(), password=None)
    
    signature = private_key.sign(payload.encode('utf-8'))
    return signature.hex()

def verify_block(hardware_serial: str, payload: str, signature_hex: str) -> bool:
    """Mathematically evaluates if the genesis payload was signed by the genuine hardware."""
    if not os.path.exists(PKI_REGISTRY):
        return False
        
    try:
        with open(PKI_REGISTRY, "r") as f:
            registry = json.load(f)
    except:
        return False

    pub_hex = registry.get(hardware_serial)
    if not pub_hex:
        return False

    try:
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
        print(f"Crypto evaluate error: {e}")
        return False

if __name__ == "__main__":
    _ensure_keychain()
    print("Biological Cryptography Layer Active.")
