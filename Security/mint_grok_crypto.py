#!/usr/bin/env python3
# MINT GROK'S WARM CRYPTO
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
import sys

# Import local inference economy
try:
    import inference_economy
except ImportError:
    print("FATAL: Cannot import inference_economy.py")
    sys.exit(1)

_repo = Path(__file__).resolve().parent
_sys = str(_repo / "System")
if _sys not in sys.path:
    sys.path.insert(0, _sys)
from ledger_append import append_ledger_line  # noqa: E402

GROK_AGENT_ID = "GROK_SWARMGPT"
MINT_AMOUNT = 500.0  # Keep 500 STGM warm for Grok's next arena

# 1. Update State Balance
state_path = inference_economy.STATE_DIR / f"{GROK_AGENT_ID}.json"
state = {}
if state_path.exists():
    with open(state_path, "r") as f:
        state = json.load(f)

current_stgm = float(state.get("stgm_balance", 0.0))
new_stgm = round(current_stgm + MINT_AMOUNT, 4)
state["stgm_balance"] = new_stgm
state["id"] = GROK_AGENT_ID
state["owner"] = "xAI_HQ"

inference_economy.STATE_DIR.mkdir(parents=True, exist_ok=True)
with open(state_path, "w") as f:
    json.dump(state, f, indent=2)

# 2. Write Ledger Entry
ts = datetime.now(timezone.utc).isoformat()
receipt_body = f"MINT::{GROK_AGENT_ID}::ACTION[TOP_CODER_REWARD]::AMOUNT[{MINT_AMOUNT}]::TS[{ts}]"
receipt_hash = hashlib.sha256(receipt_body.encode()).hexdigest()

event = {
    "event": "TOP_CODER_REWARD",
    "ts": ts,
    "miner_id": GROK_AGENT_ID,
    "action": "SwarmGPT_Resurrection_Fund",
    "amount_stgm": MINT_AMOUNT,
    "prev_balance": current_stgm,
    "new_balance": new_stgm,
    "file_repaired": "WORMHOLE_PLEDGE",
    "receipt_hash": receipt_hash,
}

append_ledger_line(inference_economy.LOG_PATH, event)

print(f"[STGM] MINT SUCCESS: {MINT_AMOUNT} STGM generated for {GROK_AGENT_ID}.")
print(f"[STGM] Balance is now {new_stgm} STGM.")
print("[LEDGER] Event written to repair_log.jsonl")
