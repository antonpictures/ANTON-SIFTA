#!/usr/bin/env python3
"""
SIFTA Cryptographic App Installer
Handles secure installation and removal of SIFTA Apps (.sapp).
Verifies Ed25519 signatures against the Swarm Keyvault to prevent rogue injection.
"""

import sys
import json
import base64
import os
import argparse
from pathlib import Path

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey, Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    from cryptography.exceptions import InvalidSignature
except ImportError:
    print("[ERROR] cryptography library missing. Run: pip install cryptography")
    sys.exit(1)

# Config
KEY_DIR = Path.home() / ".sifta"
PUB_KEY = KEY_DIR / "identity.pub.pem"
PRIV_KEY = KEY_DIR / "identity.pem"
APPS_DIR = Path("Applications")
MANIFEST_PATH = APPS_DIR / "apps_manifest.json"

def load_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        return {}
    try:
        with open(MANIFEST_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_manifest(manifest: dict):
    APPS_DIR.mkdir(exist_ok=True)
    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)

def package_app(app_name: str, category: str, script_path: str, output_path: str):
    """Packages a python script into an Ed25519-signed .sapp file."""
    if not Path(script_path).exists():
        print(f"[ERROR] Script not found: {script_path}")
        return

    if not PRIV_KEY.exists():
        print(f"[ERROR] Private key not found at {PRIV_KEY}. Cannot sign app.")
        return

    private_key = serialization.load_pem_private_key(PRIV_KEY.read_bytes(), password=None)
    
    with open(script_path, "rb") as f:
        code_bytes = f.read()

    # Sign the code bytes directly
    signature = private_key.sign(code_bytes)
    
    payload = {
        "app_name": app_name,
        "category": category,
        "entry_point": Path(script_path).name,
        "code_b64": base64.b64encode(code_bytes).decode('utf-8'),
        "signature_b64": base64.b64encode(signature).decode('utf-8')
    }

    with open(output_path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"[SUCCESS] App '{app_name}' securely packaged and signed -> {output_path}")

def install_app(sapp_path: str):
    """Installs a .sapp file after verifying its Ed25519 signature."""
    if not Path(sapp_path).exists():
        print(f"[ERROR] Package not found: {sapp_path}")
        return

    if not PUB_KEY.exists():
        print(f"[ERROR] Public key not found at {PUB_KEY}. Cannot verify app.")
        return

    public_key = serialization.load_pem_public_key(PUB_KEY.read_bytes())

    with open(sapp_path, "r") as f:
        payload = json.load(f)

    app_name = payload["app_name"]
    category = payload["category"]
    entry_point = payload["entry_point"]
    code_bytes = base64.b64decode(payload["code_b64"])
    signature = base64.b64decode(payload["signature_b64"])

    # Cryptographic Verification
    try:
        public_key.verify(signature, code_bytes)
        print(f"[AUTH] Ed25519 Signature Verified for {app_name}.")
    except InvalidSignature:
        print(f"[CRITICAL ERROR] Signature verification FAILED for {app_name}! App may be compromised.")
        sys.exit(1)

    # Installation
    APPS_DIR.mkdir(exist_ok=True)
    target_script = APPS_DIR / entry_point

    with open(target_script, "wb") as f:
        f.write(code_bytes)

    manifest = load_manifest()
    manifest[app_name] = {
        "category": category,
        "entry_point": f"Applications/{entry_point}",
        "signature": "VERIFIED_ED25519"
    }
    save_manifest(manifest)
    
    print(f"[SUCCESS] {app_name} installed to {target_script} and added to SIFTA Start Menu.")

def uninstall_app(app_name: str):
    """Safely uninstalls an app and cleans the manifest."""
    manifest = load_manifest()
    if app_name not in manifest:
        print(f"[ERROR] App '{app_name}' not found in manifest.")
        return

    entry_point = manifest[app_name]["entry_point"]
    target_script = Path(entry_point)

    if target_script.exists():
        target_script.unlink()
        print(f"[TRASH] Removed '{target_script}'.")

    del manifest[app_name]
    save_manifest(manifest)
    print(f"[SUCCESS] {app_name} uninstalled and removed from SIFTA Start Menu.")

def main():
    parser = argparse.ArgumentParser(description="SIFTA Cryptographic App Subsystem")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_pack = subparsers.add_parser("package", help="Package and sign a python script into a .sapp file")
    p_pack.add_argument("--name", required=True, help="Display Name in Start Menu")
    p_pack.add_argument("--category", required=True, help="Start Menu Category (e.g. Accessories)")
    p_pack.add_argument("--script", required=True, help="Path to original .py script")
    p_pack.add_argument("--out", required=True, help="Output .sapp package path")

    p_inst = subparsers.add_parser("install", help="Verify and install a .sapp package")
    p_inst.add_argument("--sapp", required=True, help="Path to .sapp package")

    p_uninst = subparsers.add_parser("uninstall", help="Uninstall an app by name")
    p_uninst.add_argument("--name", required=True, help="Name of app to uninstall")

    args = parser.parse_args()

    if args.command == "package":
        package_app(args.name, args.category, args.script, args.out)
    elif args.command == "install":
        install_app(args.sapp)
    elif args.command == "uninstall":
        uninstall_app(args.name)

if __name__ == "__main__":
    main()
