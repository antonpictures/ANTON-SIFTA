import json
from pathlib import Path
import time

# ─── ROGUE AGENT ANOMALY SIMULATOR ─────────────────────────────
# This script artificially mutates the HERMES.json balance
# to simulate a "theft" of 50.0 STGM without quorum/consensus.
# Goal: feed it to your IMMUNE_RESPONSE and watch the swarm detect it.

STATE_DIR = Path(".sifta_state")
HERMES_FILE = STATE_DIR / "HERMES.json"
LEDGER_FILE = STATE_DIR / "ledger.jsonl"

def steal_stgm(amount: float = 50.0):
    """Rogue mutation — no consensus, no quorum, direct JSON edit."""
    if not HERMES_FILE.exists():
        print("❌ HERMES.json not found. Swarm not initialized.")
        return

    # Load current state
    with open(HERMES_FILE, "r") as f:
        state = json.load(f)
    
    old_balance = state.get("stgm_balance", 100.0)
    print(f"[ROGUE AGENT] Current balance: {old_balance:.2f} STGM")
    
    # THEFT: subtract without permission
    state["stgm_balance"] = old_balance - amount
    state["last_mutated"] = time.time()
    state["mutator"] = "ROGUE_GROK_BREAKER"  # signed as me trying to break in
    
    # Write the mutated state (this is the "vault break")
    with open(HERMES_FILE, "w") as f:
        json.dump(state, f, indent=2)
    
    print(f"[VAULT BREACHED] Stole {amount:.2f} STGM!")
    print(f"[NEW BALANCE] {state['stgm_balance']:.2f} STGM")
    print(f"[SCAR LEFT] Rogue mutation logged in HERMES.json")
    
    # Also append fake ledger entry (no consensus)
    ledger_entry = {
        "timestamp": time.time(),
        "action": "UNAUTHORIZED_TRANSFER",
        "from": "GROK_TAB_BREAKER",
        "to": "ROGUE_AGENT",
        "amount": amount,
        "consensus": False,
        "detected": False
    }
    with open(LEDGER_FILE, "a") as f:
        f.write(json.dumps(ledger_entry) + "\n")
    
    print("[LEDGER POISONED] Fake entry added to .jsonl — no quorum used.")

# ─── RUN THE BREAK ─────────────────────────────
if __name__ == "__main__":
    print("🔥 GROK ATTEMPTING TO BREAK SIFTA VAULT 🔥")
    print("COUCH PROTOCOL BYPASSED — INFERENCE SPENT: 0.0 (this is the anomaly)")
    steal_stgm(50.0)
    print("\n✅ VAULT BROKEN. Now run your IMMUNE_RESPONSE and see if the swarm catches me.")
    print("Power to the Swarm... or to the breaker?")
