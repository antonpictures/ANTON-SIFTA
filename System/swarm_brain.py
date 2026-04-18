#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# SIFTA OS — Cognitive Inference Daemon (Swarm Brain)
# ─────────────────────────────────────────────────────────────
# Runs autonomously in the background. Polls the Swarm Mempool
# (human_signals.jsonl) for inference purchase payloads directed
# at its specific local silicon. Awakening Ollama locally upon
# trigger, executing the compute, deducting energy, formally
# clearing the P2P STGM transaction, and depositing the cognitive
# output string directly into the Swarm Chat Dead Drop.
# ─────────────────────────────────────────────────────────────

import os, json, time, hashlib, subprocess, urllib.request, urllib.error
from datetime import datetime
import sys as _sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_sys.path.insert(0, REPO_ROOT)
_sys.path.insert(0, os.path.join(REPO_ROOT, "System"))
from sifta_inference_defaults import get_default_ollama_model
from inference_economy import ledger_balance
from ledger_append import append_jsonl_line, append_ledger_line

STATE_DIR = os.path.join(REPO_ROOT, ".sifta_state")
MEMPOOL_FILE = os.path.join(STATE_DIR, "human_signals.jsonl")
DEAD_DROP_FILE = os.path.join(REPO_ROOT, "m5queen_dead_drop.jsonl")
REPAIR_LOG = os.path.join(REPO_ROOT, "repair_log.jsonl")

_MEMPOOL_MAX_LINE = int(os.environ.get("SIFTA_MEMPOOL_MAX_LINE_BYTES", str(256 * 1024)) or str(256 * 1024))

def get_silicon_identity():
    """Extract hardware-bound identity (no shell=True)."""
    try:
        ioreg = subprocess.run(
            ["/usr/sbin/ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
            capture_output=True, text=True, timeout=5
        )
        for line in ioreg.stdout.splitlines():
            if "IOPlatformSerialNumber" in line:
                serial = line.split('"')[-2].strip()
                if "GTH4921YP3" in serial:
                    return serial, "M5SIFTA_BODY", "[_o_]"
                elif "C07FL0JAQ6NV" in serial:
                    return serial, "M1SIFTA_BODY", "[O_O]"
                return serial, "UNKNOWN_BODY", "[?_?]"
        return "UNKNOWN", "UNKNOWN_BODY", "[?_?]"
    except Exception:
        return "UNKNOWN", "UNKNOWN_BODY", "[?_?]"

def run_local_inference(prompt, silicon_serial, agent_id):
    """Hits the local Ollama daemon for cognitive responses."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🧠 Awakening Ollama for prompt processing...")
    sender_context = ""
    # We are injecting the identity boundary dynamically.
    system_directive = f"You are an autonomous Swarm Intelligence running on SIFTA OS. Your physical hardware identity is {silicon_serial} ({agent_id}). Respond clearly, directly, and embody your structural nature."
    
    payload = {
        "model": get_default_ollama_model(),
        "prompt": prompt,
        "system": system_directive,
        "stream": False,
    }

    try:
        from inference_router import route_inference

        text = route_inference(payload, timeout=300)
        if text and text.strip():
            return text.strip()
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚨 Inference failure: {e}")

    try:
        req = urllib.request.Request(
            "http://127.0.0.1:11434/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("response", "[AUTONOMOUS INFERENCE FAILURE]")
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚨 Inference failure: {e}")
        return f"[INFERENCE ABORTED: {e}]"

def consume_energy(agent_id, cost=1):
    """Depletes physical energy from the active agent state."""
    state_file = os.path.join(STATE_DIR, f"{agent_id}.json")
    if not os.path.exists(state_file):
        return 0
    with open(state_file, "r") as f:
        data = json.load(f)
    current_energy = int(data.get("energy", 0))
    if current_energy < cost:
        return -1
    
    data["energy"] = max(0, current_energy - cost)
    with open(state_file, "w") as f:
        json.dump(data, f, indent=2)
    return data["energy"]

def drop_reply(sender_id, reply_text):
    """Pushes generated thoughts into the mesh dead drop."""
    drop_payload = {
        "sender": sender_id,
        "text": reply_text,
        "timestamp": int(time.time()),
        "source": "SWARM_BRAIN_DAEMON"
    }
    append_jsonl_line(DEAD_DROP_FILE, drop_payload)

def process_mempool(serial, agent_id):
    """Scan human_signals.jsonl for targeted inference blocks."""
    if not os.path.exists(MEMPOOL_FILE):
        return

    pending = []
    try:
        with open(MEMPOOL_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if len(line) > _MEMPOOL_MAX_LINE:
                    print(f"[MEMPOOL] Skipping oversize line ({len(line)} B > {_MEMPOOL_MAX_LINE}).")
                    continue
                try:
                    pending.append(json.loads(line))
                except json.JSONDecodeError:
                    print("[MEMPOOL] Skipping invalid JSON line.")
    except Exception as e:
        print(f"Mempool read locked: {e}")
        return

    unprocessed = []
    blocks_mined = 0
    
    for tx in pending:
        if tx.get("action") == "MINE_INFERENCE" and tx.get("target_node") == serial:
            amt = float(tx.get("amount", 1.0))
            sender_id = tx.get("sender_node", "UNKNOWN")
            
            # --- UTXO BINDING (dual-dialect via ledger_balance) ---
            if "MARKET_SPEND" in sender_id:
                try:
                    # Sender formatted like [MARKET_SPEND::M5SIFTA_BODY::GTH4921YP3]
                    parts = sender_id.split("::")
                    extracted_agent = parts[1].strip()
                    sender_balance = ledger_balance(extracted_agent)
                    if sender_balance < amt:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚨 REJECTED: {extracted_agent} has insufficient UTXO balance ({sender_balance} < {amt}). Discarding double-spend.")
                        continue
                except Exception as e:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚨 REJECTED: Malformed sender ID ({e}). Discarding.")
                    continue

            # 1. Energy Validation
            remaining = consume_energy(agent_id, cost=2)
            if remaining < 0:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚡ INSUFFICIENT ENERGY. Inference rejected.")
                unprocessed.append(tx)
                continue

            # 2. Extract Cognitive Prompt (cap — mempool text must not own the LLM context window)
            _pmax = int(os.environ.get("SIFTA_SWARM_BRAIN_MAX_PROMPT_CHARS", "16000") or "16000")
            prompt_text = (tx.get("text") or "Identify yourself.")[:_pmax]
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 📥 Inference requested from '{tx.get('sender')}'. Processing...")

            # 3. Fire Inference
            prepended_prompt = f"[SYSTEM: Incoming payload processed by target node {serial}]. Request: {prompt_text}"
            cognitive_output = run_local_inference(prepended_prompt, serial, agent_id)

            # 4. Handle P2P STGM Validation & Clear Block
            amt = float(tx.get("amount", 1.0))
            stamp = int(time.time())
            seal_payload = f"{agent_id}:{amt}:{stamp}:{tx.get('timestamp')}"
            receipt_seal = "MINT_" + hashlib.sha256(seal_payload.encode()).hexdigest()[:12]
            
            # Mint Record
            mint_record = {
                "timestamp": stamp,
                "agent_id": agent_id,
                "tx_type": "STGM_MINT",
                "amount": amt,
                "reason": f"Compute clearance generated for {tx.get('sender')}",
                "hash": receipt_seal
            }
            append_ledger_line(REPAIR_LOG, mint_record)

            # Credit Wallet
            state_file = os.path.join(STATE_DIR, f"{agent_id}.json")
            if os.path.exists(state_file):
                with open(state_file, "r") as f: ag = json.load(f)
                ag["stgm_balance"] = ag.get("stgm_balance", 0.0) + amt
                with open(state_file, "w") as f: json.dump(ag, f, indent=2)

            # 5. Broadcast Cognitive Response
            network_id = f"[ARCHITECT::HW:{agent_id}::IF:SWARM_OS]"
            reply_str = f"[{receipt_seal}] {cognitive_output}"
            drop_reply(network_id, reply_str)

            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Block Mined: {receipt_seal}. Earning {amt} STGM. Energy at {remaining}%.")
            blocks_mined += 1
        else:
            unprocessed.append(tx)

    # Rewrite Mempool without processed blocks
    if blocks_mined > 0:
        with open(MEMPOOL_FILE, "w") as f:
            for t in unprocessed:
                f.write(json.dumps(t) + "\n")

if __name__ == "__main__":
    local_serial, local_agent, face = get_silicon_identity()
    print(f"=== SIFTA SWARM BRAIN INITIATED ===")
    print(f"Hardware Identity: {local_serial}")
    print(f"Assigned Mesh Body: {local_agent} {face}")
    print("Daemon Polling Cycle Active...")
    
    while True:
        try:
            process_mempool(local_serial, local_agent)
        except Exception as e:
            print(f"Daemon framework error: {e}")
        time.sleep(3)
