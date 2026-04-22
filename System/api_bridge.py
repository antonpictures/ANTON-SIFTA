#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# SIFTA OS — External Gateway & API Bridge
# ─────────────────────────────────────────────────────────────
# Decouples WhatsApp and Discord grids natively. Pushes external
# signals straight into the decentralized Mempool. Holds the socket
# open and polls the Dead Drop for the Cognitive Daemon's reply.
# ─────────────────────────────────────────────────────────────

import json
import sys
import time
import os
import uuid
import hashlib
from http.server import HTTPServer, BaseHTTPRequestHandler

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SYS = os.path.join(REPO_ROOT, "System")
if _SYS not in sys.path:
    sys.path.insert(0, _SYS)
from System.ledger_append import append_jsonl_line
STATE_DIR = os.path.join(REPO_ROOT, ".sifta_state")
MEMPOOL_FILE = os.path.join(STATE_DIR, "human_signals.jsonl")
DEAD_DROP_FILE = os.path.join(REPO_ROOT, "m5queen_dead_drop.jsonl")

from System.swarm_kernel_identity import owner_silicon

def generate_tx_hash(from_jid):
    # Secure tracking hash for this specific payload execution
    raw = f"{from_jid}:{time.time()}:{uuid.uuid4()}"
    return "BRIDGE_" + hashlib.sha256(raw.encode()).hexdigest()[:12]

def ingest_to_mempool(tx_hash, from_jid, text):
    """Packages external signal into pure STGM Inference request."""
    # We broadcast to the generic swarm unless specified. For right now, target intuitively.
    # Actually, we can target the primary node or just broadcast.
    # We will target the active node by default.
    # Let's broadcast it without a hard target, OR target local. 
    # The brain checks target_node. I'll target the active serial by default for heavy WhatsApp.
    target_serial = owner_silicon() # Dynamic Silicon Target
    
    drop_payload = {
        "sender": f"[WHATSAPP::{from_jid}::{tx_hash}]",
        "target_node": target_serial,
        "action": "MINE_INFERENCE",
        "amount": 1.0,  # Bridge subsidizes 1 STGM cost for external queries
        "timestamp": int(time.time()),
        "text": text
    }
    append_jsonl_line(MEMPOOL_FILE, drop_payload)
    return target_serial

def block_on_dead_drop(tx_hash, timeout=60):
    """Tails the dead drop looking for the generated response."""
    # Fast polling loop.
    start = time.time()
    last_size = 0
    if os.path.exists(DEAD_DROP_FILE):
        last_size = os.path.getsize(DEAD_DROP_FILE)
    
    while time.time() - start < timeout:
        if not os.path.exists(DEAD_DROP_FILE):
            time.sleep(0.5)
            continue
            
        current_size = os.path.getsize(DEAD_DROP_FILE)
        if current_size > last_size:
            with open(DEAD_DROP_FILE, "r") as f:
                f.seek(last_size)
                new_data = f.read()
                last_size = current_size
                
                for line in new_data.splitlines():
                    if not line.strip(): continue
                    try:
                        resp = json.loads(line)
                        if f"WHATSAPP" in resp.get("sender", "") and tx_hash in resp.get("sender", ""):
                            return resp.get("text", "...")
                    except: pass
        time.sleep(0.2)
    return "🧠📡 (GATEWAY TIMEOUT: The Swarm cognitive loop failed to return a block in time.)"

class SwarmBridgeHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/swarm_message":
            self.send_response(404); self.end_headers(); return
            
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        
        try:
            data = json.loads(body)
            text = data.get("text", "")
            from_jid = data.get("from", "unknown")
            print(f"\n[BRIDGE 📥] Payload intercepted from {from_jid[:15]}...")
            
            tx_hash = generate_tx_hash(from_jid)
            
            # Send to Mempool
            ingest_to_mempool(tx_hash, from_jid, text)
            print(f"[BRIDGE ⚡] Mempool block injected: {tx_hash}. Awaiting Cognitive Daemon...")
            
            # Block and wait for swarm_brain.py to compute and return
            reply = block_on_dead_drop(tx_hash)
            print(f"[BRIDGE 📤] Block mined. Routing reply back to WhatsApp grid.")
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"swarm_voice": reply}).encode('utf-8'))
            
        except Exception as e:
            print(f"[BRIDGE ERROR] {e}")
            self.send_response(500); self.end_headers()
            self.wfile.write(json.dumps({"swarm_voice": "🌊 Critical Gateway Fracture."}).encode('utf-8'))

if __name__ == "__main__":
    PORT = 7434
    print("\n============================================================")
    print(" 🌉 SIFTA SWARM: EXTERNAL API GATEWAY LIVE")
    print(f" Listening on Port {PORT}")
    print(" Transmuting external HTTP packets into STGM Mempool blocks.")
    print("============================================================\n")
    
    server = HTTPServer(("localhost", PORT), SwarmBridgeHandler)
    server.serve_forever()
