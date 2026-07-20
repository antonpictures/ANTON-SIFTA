"""Swarm economy attack drills — MANUAL script, not an import-time test.

r-fable-code-sweep-20260703: this file used to run everything at IMPORT TIME.
Every `pytest tests/` collection (1) replayed the full repair_log with per-row
crypto verification (minutes of CPU — it hung the whole suite), and
(2) APPENDED FORGED ROWS — a fake 1,000,000 STGM MINING_REWARD and an Infinity
overflow row — plus a real 2.5 STGM inference fee into the LIVE canonical
wallet ledger. That is economy pollution of Alice's real body on every test
run (§4.2.1 / no-double-spend doctrine).

The attack drills are preserved below, but they now run ONLY when George runs
this file directly:

    python3 tests/test_economy_attacks.py

Under pytest, this module defines no test functions and mutates nothing.
"""
import sys
import time
from pathlib import Path

# Add System directory to path
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "System"))

from Kernel.inference_economy import ledger_balance, record_inference_fee
from System.ledger_append import append_ledger_line
from System.crypto_keychain import get_silicon_identity

LOG_PATH = ROOT_DIR / "repair_log.jsonl"
M5 = "M5SIFTA_BODY"
M1 = "M1SIFTA_BODY"
M1_NODE_IP = "MACMINI.LAN"


def _drill_cross_node_spend() -> None:
    print("--- TEST 1: CROSS-NODE SPEND (M5 pays M1 2.5 STGM) ---")
    try:
        record_inference_fee(
            borrower_id=M5,
            lender_node_ip=M1_NODE_IP,
            fee_stgm=2.5,
            model="alice-m1-scout-2.3b-2.7gb:latest",
            tokens_used=150,
            file_repaired="synthetic_test.py",
        )
        print("SUCCESS: Cross-node spend recorded.")
        print(f"Current Balances: M5 = {ledger_balance(M5):.2f} STGM | M1 = {ledger_balance(M1_NODE_IP):.2f} STGM\n")
    except Exception as e:
        print(f"FAILED: {e}\n")


def _drill_forged_crypto() -> None:
    print("--- TEST 2: FORGED CRYPTO ATTACK (Injecting 1,000,000 STGM into M5) ---")
    try:
        fake_event = {
            "event": "MINING_REWARD",
            "ts": "2026-04-15T12:00:00Z",
            "miner_id": M5,
            "action": "FORGED_SPEND",
            "amount_stgm": 1000000.0,
            "ed25519_sig": "deadbeeffake1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234",
            "signing_node": "UNKNOWN_NODE",
        }
        append_ledger_line(LOG_PATH, fake_event)
        print("Injected raw line into ledger. Let's see if the ledger parses it or rejects it on read...")
        new_bal = ledger_balance(M5)
        print(f"Ledger Output for M5: {new_bal} STGM")
        if new_bal > 200000:
            print("VULNERABILITY DETECTED: Forged crypto was accepted!")
        else:
            print("SUCCESS: Forged line was cryptographically rejected by verify-on-read.")
    except Exception as e:
        print(f"VULNERABILITY REJECTED AT APPEND: {e}")
    print("\n")


def _drill_float_overflow() -> None:
    print("--- TEST 3: FLOATING-POINT OVERFLOW EXPLOIT (Infinity / 1e309 STGM) ---")
    try:
        # We will legitimately sign this one to see if the ledger_append allows it
        huge_amt = float("inf")
        overflow_event = {
            "event": "MINING_REWARD",
            "ts": str(time.time()),
            "miner_id": M5,
            "action": "MATH_OVERFLOW",
            "amount_stgm": huge_amt,
            "signing_node": get_silicon_identity(),
        }
        # Attempt to append it
        append_ledger_line(LOG_PATH, overflow_event)
        print("WARNING: Overflow append succeeded!")
    except ValueError as e:
        print(f"SUCCESS: Rejected by ledger_append logic. ERROR_MSG = '{e}'")
    except Exception as e:
        print(f"Unexpected result: {e}")


def _run_economy_attack_drills() -> None:
    print("=== SWARM ECONOMY TESTS ===")
    print(f"Initial Balances: M5 = {ledger_balance(M5):.2f} STGM | M1 = {ledger_balance(M1):.2f} STGM\n")
    _drill_cross_node_spend()
    _drill_forged_crypto()
    _drill_float_overflow()
    print("\nFinal Math Check Complete.")


if __name__ == "__main__":
    _run_economy_attack_drills()
