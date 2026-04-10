#!/usr/bin/env python3
"""
sifta_relay.py  —  MacBook Control Surface
Type here. Mac Mini acts.

Usage:
    python sifta_relay.py --target mac_mini --intent system.ping
    python sifta_relay.py --target mac_mini --intent swarm.medic
    python sifta_relay.py --target mac_mini --intent fs.organize --payload '{"path":"/Downloads"}'
    python sifta_relay.py --keygen          # First-time: generate your identity keypair
"""
import argparse
import base64
import json
import time
import uuid
import sys
from pathlib import Path

# ─── Key Management ──────────────────────────────────────────────────────────
KEY_DIR  = Path.home() / ".sifta"
PRIV_KEY = KEY_DIR / "identity.pem"
PUB_KEY  = KEY_DIR / "identity.pub.pem"

# ─── Wormhole Targets ─────────────────────────────────────────────────────────
TARGETS = {
    "mac_mini":  "http://192.168.1.100:7444/agent/ingest",  # ← change to your Mac Mini IP
    "localhost": "http://127.0.0.1:7444/agent/ingest",
}

REGISTRY_VERSION = "v1.0"

def keygen():
    """First-time setup: generate the Ed25519 identity keypair."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    
    KEY_DIR.mkdir(mode=0o700, exist_ok=True)
    
    private_key = Ed25519PrivateKey.generate()
    public_key  = private_key.public_key()
    
    with open(PRIV_KEY, "wb") as f:
        f.write(private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption()
        ))
    PRIV_KEY.chmod(0o600)
    
    with open(PUB_KEY, "wb") as f:
        f.write(public_key.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo
        ))
    
    print(f"[+] Identity keypair generated.")
    print(f"    Private: {PRIV_KEY}")
    print(f"    Public:  {PUB_KEY}")
    print(f"\n[!] Copy the public key to your Mac Mini:")
    print(f"    scp {PUB_KEY} mac-mini:~/.sifta/authorized_keys/macbook.pub.pem")

def load_private_key():
    from cryptography.hazmat.primitives import serialization
    if not PRIV_KEY.exists():
        print("[-] No identity keypair found. Run:  python sifta_relay.py --keygen")
        sys.exit(1)
    return serialization.load_pem_private_key(PRIV_KEY.read_bytes(), password=None)

def build_envelope(intent: str, target: str, payload: dict, ttl: int = 60) -> dict:
    """Constructs and signs the canonical command envelope."""
    private_key = load_private_key()
    
    nonce     = str(uuid.uuid4())
    timestamp = time.time()
    
    # Strict canonical JSON — attack-proof whitespace
    canonical_obj = {
        "nonce":    nonce,
        "timestamp": timestamp,
        "intent":   intent,
        "target":   target,
        "payload":  payload,
    }
    canonical_string = json.dumps(canonical_obj, sort_keys=True, separators=(",", ":"))
    
    signature = private_key.sign(canonical_string.encode("utf-8"))
    
    return {
        "version":          REGISTRY_VERSION,
        "source":           "macbook",
        "nonce":            nonce,
        "timestamp":        timestamp,
        "intent":           intent,
        "target":           target,
        "payload":          payload,
        "ttl":              ttl,
        "signature":        base64.b64encode(signature).decode(),
    }

def ship(envelope: dict, gateway_url: str):
    """Sends the signed envelope to the Mac Mini's Wormhole Gateway."""
    import urllib.request
    import urllib.error
    
    body = json.dumps(envelope).encode("utf-8")
    req  = urllib.request.Request(
        gateway_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            print(f"[+] Mac Mini confirmed: {result}")
    except urllib.error.URLError as e:
        print(f"[-] Wormhole unreachable: {e.reason}")
        print(f"    Is the Mac Mini running?  ssh mac-mini 'python sifta_gateway.py'")

def main():
    print("""
  ╔═══════════════════════════════════════╗
  ║   SIFTA RELAY — MacBook Control Plane ║
  ║   "Type here. Mac Mini acts."         ║
  ╚═══════════════════════════════════════╝""")
    
    parser = argparse.ArgumentParser(description="SIFTA MacBook Relay")
    parser.add_argument("--keygen", action="store_true", help="Generate identity keypair (first time) — DEPRECATED: use --keygen-mnemonic")
    parser.add_argument("--keygen-mnemonic", action="store_true", help="Generate mnemonic-derived identity keypair (recoverable)")
    parser.add_argument("--recover-keys", metavar="MNEMONIC", help="Recover identity keypair from a 12-word mnemonic phrase")
    parser.add_argument("--queen-id", default="QUEEN", help="Queen identifier for mnemonic keygen")
    parser.add_argument("--sign-override", metavar="BINARY", help="Generate edit-override token for a specific binary")
    parser.add_argument("--target", default="localhost", choices=list(TARGETS.keys()), help="Target node")
    parser.add_argument("--intent", help="Intent to dispatch (e.g. system.ping, swarm.medic)")
    parser.add_argument("--payload", default="{}", help="JSON payload string")
    parser.add_argument("--ttl", type=int, default=60, help="Packet TTL in seconds")
    args = parser.parse_args()
    
    if args.keygen_mnemonic:
        import sifta_keyvault
        sifta_keyvault.provision_queen(queen_id=args.queen_id)
        return

    if args.recover_keys:
        import sifta_keyvault
        sifta_keyvault.recover_queen(mnemonic=args.recover_keys, queen_id=args.queen_id)
        return

    if args.keygen:
        print("[⚠️  DEPRECATION] --keygen generates random (non-recoverable) keys.")
        print("[⚠️  DEPRECATION] Use --keygen-mnemonic for recoverable mnemonic-derived keys.")
        keygen()
        return
        
    if args.sign_override:
        print(f"[*] Generating cryptographically signed override for [{args.sign_override}]...")
        private_key = load_private_key()
        canonical_payload = {
            "action": "POLICY_BYPASS",
            "target_binary": args.sign_override,
            "timestamp": time.time(),
            "ttl_seconds": args.ttl
        }
        canonical_str = json.dumps(canonical_payload, sort_keys=True, separators=(",", ":"))
        signature = private_key.sign(canonical_str.encode("utf-8"))
        
        envelope = canonical_payload.copy()
        envelope["signature"] = base64.b64encode(signature).decode()
        
        token = base64.b64encode(json.dumps(envelope).encode()).decode()
        print(f"\n[+] Override Token Generated:")
        print(f"--auth-token={token}")
        print(f"\n[+] Usage:")
        print(f"python {args.sign_override} --auth-token={token}")
        return
    
    if not args.intent:
        parser.print_help()
        return
    
    try:
        payload = json.loads(args.payload)
    except json.JSONDecodeError:
        print("[-] --payload must be valid JSON string, e.g. '{\"path\":\"/Downloads\"}'")
        sys.exit(1)
    
    print(f"[*] Building envelope → intent=[{args.intent}] target=[{args.target}]")
    
    envelope = build_envelope(args.intent, args.target, payload, args.ttl)
    gateway  = TARGETS[args.target]
    
    print(f"[*] Shipping to Wormhole Gateway [{gateway}]...")
    ship(envelope, gateway)

if __name__ == "__main__":
    main()
