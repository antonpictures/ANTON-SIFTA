#!/usr/bin/env python3
import json
from pathlib import Path
from inference_economy import record_inference_fee, get_stgm_balance, STATE_DIR

def setup_dummy_nodes():
    # Make sure we have our 2 dummy nodes heavily funded for the test
    m1_state = {"id": "M1THER", "stgm_balance": 1000.0}
    m5_state = {"id": "ALICE_M5", "stgm_balance": 5000.0}
    
    STATE_DIR.mkdir(exist_ok=True)
    with open(STATE_DIR / "M1THER.json", "w") as f:
        json.dump(m1_state, f)
    with open(STATE_DIR / "ALICE_M5.json", "w") as f:
        json.dump(m5_state, f)

if __name__ == "__main__":
    print("\n[SIMULATION] Booting STGM Trading Economy Test")
    setup_dummy_nodes()
    
    print(f"Initial M1THER: {get_stgm_balance('M1THER')} STGM")
    print(f"Initial ALICE_M5: {get_stgm_balance('ALICE_M5')} STGM")
    
    print("\n[TRADE] M1THER borrows 5000 inference tokens from ALICE_M5...")
    
    fee = 50.0  # Just a hardcoded simulation fee
    
    record_inference_fee(
        borrower_id="M1THER",
        lender_node_ip="ALICE_M5",
        fee_stgm=fee,
        model="llama4-maverick:17b",
        tokens_used=5000,
        file_repaired="test.py"
    )
    
    print("\n[VERIFICATION] Reading post-trade balances:")
    print(f"Final M1THER: {get_stgm_balance('M1THER')} STGM")
    print(f"Final ALICE_M5: {get_stgm_balance('ALICE_M5')} STGM")
