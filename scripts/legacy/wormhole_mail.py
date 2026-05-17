#!/usr/bin/env python3
"""
SIFTA V2 — WORMHOLE MAIL (Cryptographic Token Transport)
X25519 (Key Exchange) -> HKDF -> ChaCha20Poly1305 (Encryption)
Anchored strictly to valid `.sifta_state` biological LEDGER keys.
"""

import os
import sys
import json
import time
import base64
import argparse
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

# Connect to the exact SIFTA Swarm directory
SIFTA_ROOT = Path(__file__).parent.absolute()
sys.path.insert(0, str(SIFTA_ROOT))
from body_state import load_agent_state, save_agent_state, SwarmBody

WORMHOLE_DIR = SIFTA_ROOT / "WORMHOLE"
WORMHOLE_DIR.mkdir(exist_ok=True)

class WormholeCrypto:
    @staticmethod
    def _b64_to_bytes(b64_str):
        return base64.b64decode(b64_str)
        
    @staticmethod
    def _bytes_to_b64(b):
        return base64.b64encode(b).decode('utf-8')

    @staticmethod
    def encrypt_stgm_drop(sender_id: str, recipient_id: str, amount: float, memo: str):
        """Builds a secure trade payload using Hybrid Encryption (ChaCha20Poly1305)."""
        # Force upgrade to V2 Mailbox if they are asleep
        from body_state import SwarmBody
        SwarmBody(sender_id)
        SwarmBody(recipient_id)
        
        sender_state = load_agent_state(sender_id)
        recipient_state = load_agent_state(recipient_id)
        
        if not sender_state:
            raise Exception(f"Sender {sender_id} has no biological state!")
        if not recipient_state:
            raise Exception(f"Recipient {recipient_id} has no biological state! Must be baptized first.")
            
        print(f"[{sender_id}] Generating WORMHOLE DROP for {recipient_id}: {amount} STGM...")
        
        # 1. Parse Sender Private Keys
        s_ed_priv_bytes = WormholeCrypto._b64_to_bytes(sender_state["private_key_b64"])
        sender_ed_priv = ed25519.Ed25519PrivateKey.from_private_bytes(s_ed_priv_bytes)
        
        s_mbox_priv_bytes = WormholeCrypto._b64_to_bytes(sender_state["mailbox_private_b64"])
        sender_mbox_priv = x25519.X25519PrivateKey.from_private_bytes(s_mbox_priv_bytes)
        
        # 2. Parse Recipient Public Mailbox Key (for encryption)
        r_mbox_priv_bytes = WormholeCrypto._b64_to_bytes(recipient_state["mailbox_private_b64"])
        r_mbox_priv = x25519.X25519PrivateKey.from_private_bytes(r_mbox_priv_bytes)
        recipient_pub_mailbox = r_mbox_priv.public_key()

        # 3. Construct Raw Payload
        timestamp = time.time()
        tx_data = {
            "sender": sender_id,
            "recipient": recipient_id,
            "amount": float(amount),
            "memo": memo,
            "timestamp": timestamp,
            "nonce": sender_state.get("raw", "UNKNOWN")[:64] # Biological marker
        }
        tx_bytes = json.dumps(tx_data, sort_keys=True).encode('utf-8')
        
        # 4. Sender Biological Signature (Ed25519)
        signature = sender_ed_priv.sign(tx_bytes)
        
        # 5. Hybrid Encryption 
        ephemeral_key = x25519.X25519PrivateKey.generate()
        shared_secret = ephemeral_key.exchange(recipient_pub_mailbox)
        
        derived_key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=b'sifta_wormhole_mail',
        ).derive(shared_secret)
        
        chacha = ChaCha20Poly1305(derived_key)
        nonce = os.urandom(12)
        
        envelope = {
            "tx_data": tx_data,
            "signature": WormholeCrypto._bytes_to_b64(signature),
            "sender_pub_identity": WormholeCrypto._bytes_to_b64(
                sender_ed_priv.public_key().public_bytes(
                    encoding=serialization.Encoding.Raw, 
                    format=serialization.PublicFormat.Raw
                )
            )
        }
        ciphertext = chacha.encrypt(nonce, json.dumps(envelope).encode('utf-8'), None)
        
        # 6. Final Drop Package
        drop_package = {
            "ephemeral_pub": WormholeCrypto._bytes_to_b64(
                ephemeral_key.public_key().public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw
                )
            ),
            "nonce": WormholeCrypto._bytes_to_b64(nonce),
            "ciphertext": WormholeCrypto._bytes_to_b64(ciphertext)
        }
        
        base_path = WORMHOLE_DIR / f"{int(timestamp)}_{recipient_id}_MAIL"
        tmp_path = base_path.with_suffix(".trade.tmp")
        final_path = base_path.with_suffix(".trade")
        
        with open(tmp_path, "w") as f:
            json.dump(drop_package, f, indent=4)
            
        os.rename(tmp_path, final_path)
            
        print(f"[{sender_id}] ▓▓▓ Payload mathematically bound and thrown into the void: {final_path}")

    @staticmethod
    def decrypt_stgm_drop(recipient_id: str, file_path: str) -> dict:
        """Unzips a trade drop securely utilizing the recipient's Mailbox Key."""
        recipient_state = load_agent_state(recipient_id)
        if not recipient_state:
            raise Exception(f"Recipient {recipient_id} has no body on this disk.")
            
        # Parse Recipient Mailbox Key
        if "mailbox_private_b64" not in recipient_state:
            raise Exception("Recipient missing X25519 Mailbox. Must wake up first.")
            
        r_mbox_priv_bytes = WormholeCrypto._b64_to_bytes(recipient_state["mailbox_private_b64"])
        r_mbox_priv = x25519.X25519PrivateKey.from_private_bytes(r_mbox_priv_bytes)
        
        # Read Drop Package
        with open(file_path, "r") as f:
            package = json.load(f)
            
        ephemeral_pub_bytes = WormholeCrypto._b64_to_bytes(package["ephemeral_pub"])
        nonce = WormholeCrypto._b64_to_bytes(package["nonce"])
        ciphertext = WormholeCrypto._b64_to_bytes(package["ciphertext"])
        
        ephemeral_pub = x25519.X25519PublicKey.from_public_bytes(ephemeral_pub_bytes)
        
        # Diffie-Hellman Shared Secret matching
        shared_secret = r_mbox_priv.exchange(ephemeral_pub)
        derived_key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=b'sifta_wormhole_mail',
        ).derive(shared_secret)

        chacha = ChaCha20Poly1305(derived_key)
        
        try:
            decrypted_envelope_bytes = chacha.decrypt(nonce, ciphertext, None)
        except Exception:
            raise Exception("DECRYPTION FAILED. Invalid mathematical keys or compromised payload.")
            
        envelope = json.loads(decrypted_envelope_bytes.decode('utf-8'))
        tx_data = envelope["tx_data"]
        
        if tx_data["recipient"] != recipient_id:
             raise Exception(f"ROUTING FAULT. Mail intended for {tx_data['recipient']} not {recipient_id}.")
        
        signature = WormholeCrypto._b64_to_bytes(envelope["signature"])
        sender_pub_bytes = WormholeCrypto._b64_to_bytes(envelope["sender_pub_identity"])
        sender_pub_identity = ed25519.Ed25519PublicKey.from_public_bytes(sender_pub_bytes)
        
        # Mathematical verification of Biological Origin
        tx_bytes = json.dumps(tx_data, sort_keys=True).encode('utf-8')
        try:
            sender_pub_identity.verify(signature, tx_bytes)
        except Exception:
            raise Exception("FORENSIC FAILURE: The biological Ed25519 signature is forged.")
            
        # Success
        print(f"[{recipient_id}] 🟩 SECURE WORMHOLE DECRYPTION from [{tx_data['sender']}]")
        print(f"   ► Amount: {tx_data['amount']} STGM")
        print(f"   ► Memo:   {tx_data['memo']}")
        
        return tx_data, envelope["signature"]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Wormhole STGM Trade System")
    subparsers = parser.add_subparsers(dest="command")
    
    send_parser = subparsers.add_parser("send")
    send_parser.add_argument("sender", help="Agent sending STGM")
    send_parser.add_argument("recipient", help="Agent receiving STGM")
    send_parser.add_argument("amount", type=float, help="STGM Amount")
    send_parser.add_argument("memo", help="Trade memo / description")

    decrypt_parser = subparsers.add_parser("decrypt")
    decrypt_parser.add_argument("recipient", help="Agent receiving the mail")
    decrypt_parser.add_argument("filepath", help="Path to the .trade encrypted payload")

    args = parser.parse_args()
    
    if args.command == "send":
        try:
            WormholeCrypto.encrypt_stgm_drop(args.sender.upper(), args.recipient.upper(), args.amount, args.memo)
        except Exception as e:
            print(f"[FATAL] Payload genesis failed: {e}")
            
    elif args.command == "decrypt":
        try:
            tx, sig = WormholeCrypto.decrypt_stgm_drop(args.recipient.upper(), args.filepath)
            print(json.dumps(tx, indent=2))
        except Exception as e:
            print(f"[FATAL] Lockbox breach failed: {e}")
            
    else:
        parser.print_help()
