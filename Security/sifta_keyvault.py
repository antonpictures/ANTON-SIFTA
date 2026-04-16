#!/usr/bin/env python3
"""
sifta_keyvault.py — Persistent, Mnemonic-Derived Ed25519 Identity

Generates deterministic Ed25519 keypairs from BIP-39-style mnemonic phrases.
The same 12 words always produce the same key. Lose the words, lose the Queen.

Properties:
  - Deterministic: mnemonic → HKDF-SHA256 → Ed25519 seed (32 bytes)
  - Recoverable: same mnemonic on any machine → same keypair
  - No external deps beyond `cryptography` (already in requirements)

Usage:
  python sifta_keyvault.py --generate         # Create new mnemonic + provision keys
  python sifta_keyvault.py --recover "word1 word2 ... word12"  # Re-derive keys
  python sifta_keyvault.py --verify           # Show current pubkey fingerprint
"""
import hashlib
import os
import sys
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

# ─── Key Paths ────────────────────────────────────────────────────────────────
KEY_DIR  = Path.home() / ".sifta"
PRIV_KEY = KEY_DIR / "identity.pem"
PUB_KEY  = KEY_DIR / "identity.pub.pem"

# ─── BIP-39 English Wordlist (2048 words, truncated to essential set) ─────────
# We use a minimal but sufficient set. For full BIP-39 compatibility,
# replace with the full 2048-word list.
# This uses os.urandom(16) → 128 bits → mapped to 12 words from the list.
WORDLIST_URL = "https://raw.githubusercontent.com/bitcoin/bips/master/bip-0039/english.txt"
_WORDLIST_CACHE = None


def _load_wordlist() -> list[str]:
    """Load or generate a deterministic 2048-word list for mnemonic encoding."""
    global _WORDLIST_CACHE
    if _WORDLIST_CACHE:
        return _WORDLIST_CACHE

    # Try to load from bundled file first
    bundled = KEY_DIR / "wordlist.txt"
    if bundled.exists():
        words = bundled.read_text().strip().splitlines()
        if len(words) >= 2048:
            _WORDLIST_CACHE = words[:2048]
            return _WORDLIST_CACHE

    # Generate a deterministic wordlist from SHA-256 hashing
    # This is reproducible: same algorithm = same words on any machine
    words = []
    for i in range(2048):
        h = hashlib.sha256(f"SIFTA_WORD_{i}".encode()).hexdigest()
        # Take first 4-8 chars as a pronounceable word seed
        syllables = [
            h[0:2], h[2:4], h[4:6]
        ]
        # Map hex pairs to consonant+vowel pairs for pronounceability
        vowels = "aeiou"
        consonants = "bcdfghjklmnprstvwxyz"
        word = ""
        for s in syllables:
            c_idx = int(s[0], 16) % len(consonants)
            v_idx = int(s[1], 16) % len(vowels)
            word += consonants[c_idx] + vowels[v_idx]
        words.append(word)

    _WORDLIST_CACHE = words

    # Cache for future use
    KEY_DIR.mkdir(mode=0o700, exist_ok=True)
    bundled.write_text("\n".join(words))

    return _WORDLIST_CACHE


def generate_mnemonic() -> str:
    """Generate a 12-word mnemonic from 128 bits of entropy."""
    entropy = os.urandom(16)  # 128 bits
    wordlist = _load_wordlist()

    # Convert 128 bits to 12 indices (11 bits each, with 4-bit checksum)
    # Simplified: we split the entropy into 12 chunks and map to words
    bits = int.from_bytes(entropy, "big")
    checksum = hashlib.sha256(entropy).digest()[0] >> 4  # 4-bit checksum
    bits = (bits << 4) | checksum  # 132 bits total

    words = []
    for _ in range(12):
        idx = bits & 0x7FF  # 11 bits = 0-2047
        words.append(wordlist[idx])
        bits >>= 11

    words.reverse()  # MSB first
    return " ".join(words)


def derive_keypair_from_mnemonic(mnemonic: str) -> tuple[Ed25519PrivateKey, bytes]:
    """
    Derive a deterministic Ed25519 keypair from a mnemonic phrase.
    Uses HKDF-SHA256 to stretch the mnemonic into a 32-byte seed.

    Returns (private_key, public_key_bytes)
    """
    mnemonic_bytes = mnemonic.strip().lower().encode("utf-8")

    # HKDF: mnemonic → 32-byte Ed25519 seed
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"SIFTA_QUEEN_IDENTITY_V1",
        info=b"ed25519_seed",
    )
    seed = hkdf.derive(mnemonic_bytes)

    # Ed25519 from seed
    private_key = Ed25519PrivateKey.from_private_bytes(seed)
    public_key = private_key.public_key()
    pub_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )

    return private_key, pub_bytes


def _write_keypair(private_key: Ed25519PrivateKey):
    """Write the keypair to the standard SIFTA key locations."""
    KEY_DIR.mkdir(mode=0o700, exist_ok=True)

    # Write private key (PEM)
    with open(PRIV_KEY, "wb") as f:
        f.write(private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ))
    PRIV_KEY.chmod(0o600)

    # Write public key (PEM)
    public_key = private_key.public_key()
    with open(PUB_KEY, "wb") as f:
        f.write(public_key.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ))

    # Fingerprint for display
    pub_raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    fingerprint = hashlib.sha256(pub_raw).hexdigest()[:16]
    return fingerprint


def provision_queen(queen_id: str = "QUEEN", mnemonic: str = None) -> dict:
    """
    Provision a Queen identity from a mnemonic.
    If no mnemonic provided, generates one and displays it ONCE.

    Returns dict with fingerprint and mnemonic (if newly generated).
    """
    newly_generated = False
    if not mnemonic:
        mnemonic = generate_mnemonic()
        newly_generated = True

    private_key, pub_bytes = derive_keypair_from_mnemonic(mnemonic)
    fingerprint = _write_keypair(private_key)

    result = {
        "queen_id": queen_id,
        "fingerprint": fingerprint,
        "pub_key_path": str(PUB_KEY),
        "priv_key_path": str(PRIV_KEY),
    }

    print("═" * 60)
    print(f"  SIFTA KEYVAULT — {queen_id} IDENTITY PROVISIONED")
    print("═" * 60)
    print(f"  Fingerprint:  {fingerprint}")
    print(f"  Private Key:  {PRIV_KEY}")
    print(f"  Public Key:   {PUB_KEY}")

    if newly_generated:
        result["mnemonic"] = mnemonic
        print()
        print("  ┌─────────────────────────────────────────────┐")
        print("  │  ⚠️  WRITE DOWN YOUR RECOVERY PHRASE NOW  ⚠️  │")
        print("  │  This is the ONLY time it will be shown.    │")
        print("  └─────────────────────────────────────────────┘")
        print()
        words = mnemonic.split()
        for i, word in enumerate(words, 1):
            print(f"    {i:2d}. {word}")
        print()
        print("  These 12 words can recover this exact identity")
        print("  on any machine: python sifta_keyvault.py --recover \"...\"")
    else:
        print()
        print("  ✓ Keypair recovered from provided mnemonic.")

    print("═" * 60)
    return result


def recover_queen(mnemonic: str, queen_id: str = "QUEEN") -> dict:
    """Recover a Queen identity from a mnemonic phrase."""
    return provision_queen(queen_id=queen_id, mnemonic=mnemonic)


def verify_current_key() -> dict:
    """Display the fingerprint of the currently installed key."""
    if not PUB_KEY.exists():
        print("[KEYVAULT] No identity key found. Run --generate first.")
        return {"installed": False}

    from cryptography.hazmat.primitives import serialization
    pub_key = serialization.load_pem_public_key(PUB_KEY.read_bytes())
    pub_raw = pub_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    fingerprint = hashlib.sha256(pub_raw).hexdigest()[:16]

    print("═" * 60)
    print("  SIFTA KEYVAULT — CURRENT IDENTITY")
    print("═" * 60)
    print(f"  Fingerprint:  {fingerprint}")
    print(f"  Public Key:   {PUB_KEY}")
    print(f"  Private Key:  {PRIV_KEY} ({'exists' if PRIV_KEY.exists() else 'MISSING'})")
    print("═" * 60)

    return {"installed": True, "fingerprint": fingerprint}


# ─── CLI ──────────────────────────────────────────────────────────────────────
def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="SIFTA Keyvault — Mnemonic-Derived Ed25519 Identity",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python sifta_keyvault.py --generate                    # New mnemonic + keys
  python sifta_keyvault.py --generate --queen-id M5IDE   # Named queen
  python sifta_keyvault.py --recover "word1 word2 ..."   # Recover from mnemonic
  python sifta_keyvault.py --verify                      # Show current fingerprint
        """
    )
    parser.add_argument("--generate", action="store_true",
                        help="Generate new mnemonic and provision keys")
    parser.add_argument("--recover", metavar="MNEMONIC",
                        help="Recover keys from a 12-word mnemonic phrase")
    parser.add_argument("--verify", action="store_true",
                        help="Show current key fingerprint")
    parser.add_argument("--queen-id", default="QUEEN",
                        help="Queen identifier (default: QUEEN)")

    args = parser.parse_args()

    if args.generate:
        if PRIV_KEY.exists():
            print("[⚠️  WARNING] Existing key will be OVERWRITTEN.")
            confirm = input("Type 'YES' to proceed: ").strip()
            if confirm != "YES":
                print("Aborted.")
                return
        provision_queen(queen_id=args.queen_id)
    elif args.recover:
        recover_queen(mnemonic=args.recover, queen_id=args.queen_id)
    elif args.verify:
        verify_current_key()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
