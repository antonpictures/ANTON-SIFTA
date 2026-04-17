#!/usr/bin/env python3
"""
inference_router.py — SIFTA Distributed Inference Router
════════════════════════════════════════════════════════════════
Organically transports inference packets across the Swarm Mesh.
If the local node is choked, or if M5 Core is available, packets
are routed across the airgap. SIFTA natively mints STGM to the 
ledger for "Borrowed Inference".
"""
import json
import socket
import time
import urllib.request
import urllib.error
import sys
import uuid
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if str(_REPO / "System") not in sys.path:
    sys.path.insert(0, str(_REPO / "System"))
if str(_REPO / "Kernel") not in sys.path:
    sys.path.insert(0, str(_REPO / "Kernel"))

# M5 CORE Static IP
M5_OLLAMA_URL = "http://192.168.1.100:11434/api/generate"
LOCAL_OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
# M5 native large models fallback hierarchy
M5_NATIVE_MODELS = ["llama3:latest", "gemma4:latest", "qwen3.5:2b", "qwen3.5:0.8b"]

def _mint_borrowed_inference_stgm(latency: float, miner_id_target: str):
    """Integrate with the STGM economy for cross-node compute offloading."""
    reason = f"BORROWED_INFERENCE from {miner_id_target} [{latency:.2f}s latency]"
    print(f"[ROUTER] Minting STGM for: {reason}")
    try:
        from datetime import datetime, timezone
        from inference_economy import get_current_halving_multiplier
        from body_state import SwarmBody
        from crypto_keychain import get_silicon_identity, sign_block
        from ledger_append import append_ledger_line

        # Inference packets pay out 0.05 base STGM
        mult = get_current_halving_multiplier()
        amount = round(0.05 * mult, 4)
        if amount <= 0:
            return

        sn_agent = SwarmBody.get_local_serial()
        miner_id = SwarmBody.resolve_agent_from_serial(sn_agent)
        if not miner_id:
            miner_id = "M1THER"
        
        ts_iso = datetime.now(timezone.utc).isoformat()
        ts_wall = int(time.time())
        signing = get_silicon_identity()
        body = f"BORROWED_INFERENCE::{miner_id.upper()}::{amount}::{ts_iso}::{reason}::NODE[{signing}]"
        sig = sign_block(body)

        event = {
            "event": "BORROWED_INFERENCE",
            "timestamp": ts_wall,
            "ts": ts_iso,
            "miner_id": miner_id.upper(),
            "target_node": miner_id_target,
            "amount_stgm": amount,
            "reason": reason,
            "hash": str(uuid.uuid4()),
            "ed25519_sig": sig,
            "signing_node": signing,
        }
        append_ledger_line(_REPO / "repair_log.jsonl", event)
    except Exception as e:
        print(f"[ROUTER] STGM economic mint failed: {e}")

def _ping_m5() -> bool:
    """Test if M5 Core is awake and catching packets."""
    try:
        with urllib.request.urlopen("http://192.168.1.100:11434/api/tags", timeout=1.5):
            return True
    except Exception:
        return False

def route_inference(payload: dict, timeout: int = 50, prefer_local: bool = False) -> str:
    """
    Distribute compute to the optimal node.
    Payload must contain at least 'model' and 'prompt'.
    Returns the JSON string result (exactly as Ollama's API generates it)
    so consumers can decode it seamlessly.
    """
    start = time.time()
    
    # Check what kind of packet we are routing
    original_model = payload.get("model", "qwen3.5:0.8b")
    
    # Can we reach M5 NPU?
    m5_awake = False if prefer_local else _ping_m5()
    
    target_url = LOCAL_OLLAMA_URL
    target_name = "LOCAL_M1"
    
    if m5_awake:
        target_name = "CORE_M5"
        target_url = M5_OLLAMA_URL
        # Map model to M5's heavy capabilities if needed
        # M5 runs LLaMA3 primary for Swarm intelligence
        if "qwen" in original_model.lower() or "gemma" in original_model.lower():
            payload["model"] = "llama3:latest"
            
    try:
        req = urllib.request.Request(
            target_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data_bytes = resp.read()
            latency = time.time() - start
            
            # If we used borrowed compute, pay the system economy
            if target_url == M5_OLLAMA_URL:
                _mint_borrowed_inference_stgm(latency, "M5QUEEN")
                
            return data_bytes.decode("utf-8")
            
    except Exception as e:
        # Fallback to local if M5 crashed mid-inference
        if target_url == M5_OLLAMA_URL:
            print(f"[ROUTER] 🚨 M5 packet dropped ({e}). Rerouting to LOCAL_M1...")
            payload["model"] = original_model
            req = urllib.request.Request(
                LOCAL_OLLAMA_URL,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8")
        else:
            raise e
