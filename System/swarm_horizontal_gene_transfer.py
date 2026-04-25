#!/usr/bin/env python3
"""
System/swarm_horizontal_gene_transfer.py — John Deere Economy Core
──────────────────────────────────────────────────────────────────
When a peer node returns a valid response that lowers the core's
free energy (e.g. summarizing a log, successfully answering a query),
this organ settles the transaction by minting a STGM_TRANSFER_PEER_v1
event onto the canonical ledger.
"""

import json
from datetime import datetime, timezone
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from Kernel.inference_economy import LOG_PATH, append_ledger_line, STATE_DIR, ledger_balance
try:
    from System.crypto_keychain import sign_block, get_silicon_identity
except ImportError:
    def sign_block(p): return f"NO_KEYCHAIN_{p[:8]}"
    def get_silicon_identity(): return "UNKNOWN_SERIAL"

class SwarmHorizontalGeneTransfer:
    @staticmethod
    def process_stigmergic_contribution(
        receiver_id: str,
        contributor_id: str,
        contributor_ip: str,
        amount_stgm: float,
        contribution_hash: str,
        memo: str
    ) -> dict:
        """
        Settles a peer-to-peer STGM transfer for a biological/stigmergic contribution.
        """
        # Load state purely to update the cache for the UI
        state_path = STATE_DIR / f"{receiver_id.upper()}.json"
        state = {}
        if state_path.exists():
            try:
                with open(state_path, "r") as f:
                    state = json.load(f)
            except Exception:
                pass
        
        current_stgm = float(ledger_balance(receiver_id))
        new_stgm = max(0.0, round(current_stgm - amount_stgm, 6))
        
        state["stgm_balance"] = new_stgm
        try:
            with open(state_path, "w") as f:
                json.dump(state, f, indent=2)
        except Exception:
            pass

        # Also credit the contributor's cache
        c_state_path = STATE_DIR / f"{contributor_id.upper()}.json"
        c_state = {}
        if c_state_path.exists():
            try:
                with open(c_state_path, "r") as f:
                    c_state = json.load(f)
            except Exception:
                pass
                
        c_current_stgm = float(ledger_balance(contributor_id))
        c_state["stgm_balance"] = round(c_current_stgm + amount_stgm, 6)
        try:
            with open(c_state_path, "w") as f:
                json.dump(c_state, f, indent=2)
        except Exception:
            pass

        ts = datetime.now(timezone.utc).isoformat()
        hw_serial = get_silicon_identity()
        receipt_body = (
            f"STGM_TRANSFER_PEER_v1::{receiver_id}::TO[{contributor_id}]::"
            f"IP[{contributor_ip}]::AMOUNT[{amount_stgm}]::HASH[{contribution_hash}]::"
            f"TS[{ts}]::NODE[{hw_serial}]"
        )
        sig = sign_block(receipt_body)
        
        event = {
            "event": "STGM_TRANSFER_PEER_v1",
            "ts": ts,
            "sender_id": receiver_id,
            "receiver_id": contributor_id,
            "receiver_ip": contributor_ip,
            "amount_stgm": amount_stgm,
            "contribution_hash": contribution_hash,
            "memo": memo,
            "ed25519_sig": sig,
            "signing_node": hw_serial
        }
        
        append_ledger_line(LOG_PATH, event)
        print(f"  [HGT] {amount_stgm} STGM transferred {receiver_id} -> {contributor_id}")
        return event

if __name__ == "__main__":
    print("[C47H-SMOKE] SwarmHorizontalGeneTransfer module loaded.")
