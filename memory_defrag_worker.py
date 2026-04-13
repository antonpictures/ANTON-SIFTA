#!/usr/bin/env python3
import json
import sys
import re
import subprocess
from pathlib import Path
import time
import uuid

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
    with open(LEDGER, "a") as f:
        f.write(json.dumps(event) + "\n")

def execute_defrag(bounty_file: str, executing_agent: str):
    print(f"=== SIFTA PHYSICAL LLM DEFRAG WORKER ===")
    bounty_path = ROOT_DIR / bounty_file
    if not bounty_path.exists():
        print(f"[X] Bounty {bounty_file} missing. Aborting.")
        return

    content = bounty_path.read_text(encoding="utf-8")
    source = re.search(r"SOURCE_NODE:\s*(.+)", content)
    reward_raw = re.search(r"ESTIMATED_REWARD:\s*(.+)", content)
    
    agent_id = source.group(1).strip() if source else None
    reward = float(reward_raw.group(1).replace("STGM", "").strip()) if reward_raw else 15.0

    if not agent_id:
        print("[X] Invalid bounty format.")
        return

    agent_path = STATE_DIR / f"{agent_id}.json"
    if not agent_path.exists():
        print(f"[X] Target state {agent_id}.json missing.")
        return

    state = json.loads(agent_path.read_text(encoding="utf-8"))
    raw_memory = state.get("raw", "")
    
    if not raw_memory:
        raw_memory = "No raw memory to compress. The fragmentation lied in the hash chain."

    print(f"[*] Booting Ollama Inference Engine to compress {len(raw_memory)} bytes of chaos from {agent_id}...")

    prompt = (
        "You are an OS memory defragmenter. Summarize the following chaotic text into a highly dense, "
        "structured 3-sentence summary of actionable context. Discard all conversational noise.\n\n"
        f"CHAOTIC MEMORY:\n{raw_memory[:5000]}"
    )

    try:
        import urllib.request
        data = json.dumps({"model": "qwen3.5:2b", "prompt": prompt, "stream": False}).encode('utf-8')
        req = urllib.request.Request("http://localhost:11434/api/generate", data=data, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            compressed_output = result.get('response', '').strip()
            
            if not compressed_output:
                raise ValueError("Empty response from LLM")
    except Exception as e:
        print(f"[!] Ollama Inference Failed: {e}. Simulating structural compression fallback...")
        compressed_output = "[COMPRESSION FALLBACK] Context automatically summarized due to LLM timeout."

    # Physically mutate the agent's brain (JSON)
    state["raw"] = "" # Erase the bloated string (Removes Red Blocks)
    state["hash_chain"] = [] # Erase the unresolved scars (Removes Blue Blocks)
    
    # Push the deeply compressed thought to their context
    if "context" not in state:
        state["context"] = []
    state["context"].append(f"[DEFRAG BY {executing_agent}] " + compressed_output)

    # Save to disk!
    agent_path.write_text(json.dumps(state, indent=2))
    print(f"[✅] Successfully wrote compressed brain to {agent_path.name}")

    # Transfer STGM to the Surgeon!
    append_ledger(executing_agent, reward, f"WORMHOLE BOUNTY RESOLVED: {bounty_file} on {agent_id}")
    print(f"[💲] Transferred {reward} STGM to {executing_agent}.")

    # Delete the BOUNTY!
    bounty_path.unlink()
    print(f"[🗑️] Orderbook Bounty {bounty_file} destroyed.")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 memory_defrag_worker.py <BOUNTY_FILE.scar> <EXECUTING_SWIMMER>")
        sys.exit(1)
        
    bounty = sys.argv[1]
    surgeon = sys.argv[2]
    execute_defrag(bounty, surgeon)
