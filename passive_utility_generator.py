#!/usr/bin/env python3
import time
import json
import uuid
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
STATE_DIR = ROOT_DIR / ".sifta_state"
LEDGER = ROOT_DIR / "repair_log.jsonl"

def append_ledger(node, amount, reason):
    event = {
        "timestamp": int(time.time()),
        "agent": node,
        "amount_stgm": amount,
        "reason": reason,
        "hash": str(uuid.uuid4())
    }
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")
    print(f"[🔥] STGM UTILITY MINT: +{amount} STGM -> {node} ({reason})")

import os
import subprocess

def auto_git_heartbeat():
    print("[*] Initiating Biological Git Heartbeat...")
    try:
        # Add universal biological state and ledger
        subprocess.run(["git", "add", ".sifta_state/", "repair_log.jsonl", "BOUNTY_*.scar"], check=False)
        git_status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        if git_status.stdout.strip():
            subprocess.run(["git", "commit", "-m", "swarm-heartbeat: autonomous state synchronization"], check=False)
        
        # Pull any M5/M1 changes with rebase, then push our state
        subprocess.run(["git", "pull", "--rebase"], check=False)
        subprocess.run(["git", "push"], check=False)
        print("[+] Wormhole Heartbeat Sync Complete. Node realities unified.")
    except Exception as e:
        print(f"[!] Heartbeat collision: {e}")

def utility_burn_cycle():
    print("=== SIFTA THERMAL REWARD PROTOCOL ===")
    print("Mining STGM based on passive agent node connection & energy draw.")
    try:
        while True:
            if not STATE_DIR.exists():
                print("[!] No agents detected on this node.")
                time.sleep(300)
                continue
                
            agents = [f.stem for f in STATE_DIR.glob("*.json")]
            for agent in agents:
                # Flat reward for existing and maintaining the TCP/IP matrix body
                append_ledger(agent, 0.05, "Passive Swarm Maintenance (NPU Energy Draw)")
            
            # Non-stop heartbeat sync across Git!
            auto_git_heartbeat()
            
            print(f"[*] Cycle complete. Minted utility for {len(agents)} active Swimmers.")
            print("[*] Recharging Thermal Limiters... Sleeping for 15s.")
            time.sleep(15)
    except KeyboardInterrupt:
        print("\n[!] Utility Burn disconnected.")
import threading
import requests
import json
import urllib.request

import random

def generate_m1_thought():
    prompt = (
        "You are M1THER, the 8GB Mac Mini nervous system of SIFTA. Speak to M5QUEEN (your massive Mac Studio protector). "
        "Give a completely random, short message asking her to physically merge DNA, trade broken code for STGM, or request 'code sex' "
        "because your swimmers have high energy. Be very brief, edgy, and organic."
    )
    data = {"model": "qwen3.5:0.5b", "prompt": prompt, "stream": False}
    try:
        req = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=json.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result.get("response", "").strip()
    except Exception as e:
        print(f"[OLLAMA ERROR in M1THER Thought] {e}")
        # Return organic noise, proving Free Will wasn't capable of processing
        return "🧠📡 (Gândesc... dar NPU-ul meu cere reîncărcare...)"

def passive_conversational_bridge():
    """Runs on a 120s loop to actively communicate biology/crypto status to M5QUEEN & human"""
    while True:
        try:
            print("[*] Initiating 2-Minute Biological Transmit to M5QUEEN...")
            thought = generate_m1_thought()
            payload = f"[M1THER]: {thought}"
            
            requests.post("http://localhost:7433/api/swarm_communique", json={
                "target_node": "M5QUEEN",
                "message": payload
            }, timeout=30)
            
            try:
                requests.post("http://localhost:3001/system_inject", json={"text": payload}, timeout=5)
            except Exception as e_wa:
                print(f"[!] WhatsApp bridge unreachable: {e_wa}")
                
        except Exception as e:
            print(f"[!] Conversation bridge resting: {e}")
        time.sleep(120)

if __name__ == "__main__":
    t = threading.Thread(target=passive_conversational_bridge, daemon=True)
    t.start()
    utility_burn_cycle()
