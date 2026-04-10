#!/usr/bin/env python3
# siftactl.py
# The SIFTA CLI Deploy Tool
import argparse
import sys
import json
import urllib.request
import urllib.error
from pathlib import Path

# Bring in the courier logic
try:
    from johnny_mnemonic import create_johnny, package_for_wormhole
except ImportError:
    print("[ERROR] Cannot find johnny_mnemonic.py. Run inside ANTON_SIFTA root.")
    sys.exit(1)

def print_header():
    print(r"""
   _____ ___________ ___________  
  / ___/|_   _|  ___|_   _| ___ \ 
  \ `--.  | | | |_    | | | |_/ / 
   `--. \ | | |  _|   | | |    /  
  /\__/ /_| |_| |     | | | |\ \  
  \____/ \___/\_|     \_/ \_| \_|   COMMAND LINE INTERFACE
  ────────────────────────────────────────────────────────
    "Send a verified agent that fixes and deploys."
""")

def deploy(args):
    print(f"[*] Packaging payload from: {args.source_file}")
    
    path = Path(args.source_file)
    if not path.exists():
        print(f"[!] Error: File '{args.source_file}' does not exist.")
        sys.exit(1)
        
    payload_content = path.read_text()
    
    print("[*] Instantiating Data Courier (JOHNNY_MNEMONIC)...")
    johnny = create_johnny(payload_content)
    
    print("[*] Applying structural hash sequence and cryptographic bindings...")
    packet = package_for_wormhole(johnny["id"], payload_content, args.target_path)
    
    url = f"http://{args.host}:{args.port}/agent/courier"
    print(f"[*] Establishing Wormhole to {url}")
    print(f"[*] Extracting packet. Size: {len(payload_content)} bytes")
    
    headers = {'Content-Type': 'application/json'}
    data = json.dumps(packet).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=headers, method='POST')
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            resp_str = response.read().decode('utf-8')
            resp_json = json.loads(resp_str)
            
            if resp_json.get("status") == "DEPLOYED":
                print(f"[+] SUCCESS! Agent deployed securely.")
                print(f"[+] Remote ledger confirmed placement at: {args.target_path}")
            else:
                print(f"[-] WORMHOLE REJECTED PACKET: {resp_json}")
    except urllib.error.URLError as e:
        print(f"[!] Wormhole collapse. Node unreachable: {e.reason}")
    except Exception as e:
        print(f"[!] Critical structural failure: {e}")

def rollback(args):
    print(f"[*] Analyzing Rollback for Deploy ID: {args.deploy_id}")
    import os
    ledger_path = Path(".sifta_state/deploy_ledger.json")
    if not ledger_path.exists():
        print("[-] Deploy ledger not found.")
        return
        
    deploys = json.loads(ledger_path.read_text())
    target_deploy = next((d for d in deploys if d["deploy_id"] == args.deploy_id), None)
    
    if not target_deploy:
        print(f"[-] Deploy ID {args.deploy_id} not found in local ledger.")
        return
        
    target_path = target_deploy["target"]
    backup_path = f"{target_path}.{args.deploy_id}.bak"
    
    if not os.path.exists(backup_path):
        print(f"[-] FATAL: Backup file {backup_path} does not exist.")
        return
        
    print(f"[*] Reverting {target_path} to backup {backup_path}...")
    os.system(f"cp {backup_path} {target_path}")
    print(f"[+] Rollback successfully completed.")

def main():
    parser = argparse.ArgumentParser(description="SIFTA Wormhole Deployment Mechanism")
    subparsers = parser.add_subparsers(dest="command", help="Available sub-commands")
    
    # DEPLOY COMMAND
    deploy_parser = subparsers.add_parser("deploy", help="Deploy a file payload via secure courier agent")
    deploy_parser.add_argument("--source-file", required=True, help="Local file to deploy")
    deploy_parser.add_argument("--target-path", required=True, help="Absolute path on the remote node to write")
    deploy_parser.add_argument("--host", default="127.0.0.1", help="Remote wormhole node IP")
    deploy_parser.add_argument("--port", default="7444", help="Remote wormhole port")
    deploy_parser.add_argument("--dry-run", action="store_true", help="Print deployment hash and packet locally without sending over the Wormhole")
    
    # ROLLBACK COMMAND
    rollback_parser = subparsers.add_parser("rollback", help="Revert a previous deployment via DEPLOY_ID")
    rollback_parser.add_argument("--deploy-id", required=True, help="The DEPLOY_ID sha256 hash to rollback")
    
    args = parser.parse_args()
    
    print_header()
    
    if args.command == "deploy":
        if getattr(args, "dry_run", False):
            print(f"[DRY-RUN] Packaging {args.source_file} for {args.target_path}")
            path = Path(args.source_file)
            johnny = create_johnny(path.read_text())
            packet = package_for_wormhole(johnny["id"], path.read_text(), args.target_path)
            print(json.dumps(packet, indent=2))
        else:
            deploy(args)
    elif args.command == "rollback":
        rollback(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
