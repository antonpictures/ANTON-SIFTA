import sys
from pathlib import Path
sys.path.insert(0, str(Path(".").resolve()))

from System.ledger_append import append_ledger_line
import time
import json
import shutil
import hashlib

_STATE = Path(".sifta_state")
_M5_BODY = _STATE / "M5SIFTA_BODY.json"
_ALICE = _STATE / "ALICE_M5.json"
_LEDGER = Path("repair_log.jsonl")

# C47H specified transfer amount
transfer_amount = 110.95
tx_hash = hashlib.sha256(str(time.time()).encode()).hexdigest()[:12]

# Mint SPEND from M5SIFTA_BODY
sp = {"ts": time.time(), "agent": "M5SIFTA_BODY", "transaction_type": "STGM_SPEND", "stgm_cost": transfer_amount, "action": "IDENTITY_UNIFICATION_TX", "tx_hash": tx_hash}
append_ledger_line(_LEDGER, sp)

# Mint MINT to ALICE_M5
mp = {"ts": time.time(), "agent": "ALICE_M5", "transaction_type": "STGM_MINT", "stgm_reward": transfer_amount, "action": "IDENTITY_UNIFICATION_RX", "tx_hash": tx_hash}
append_ledger_line(_LEDGER, mp)

# Retire M5SIFTA_BODY
if _M5_BODY.exists():
    data = json.loads(_M5_BODY.read_text())
    data["RETIRED"] = True
    data["merged_into"] = "ALICE_M5"
    _M5_BODY.write_text(json.dumps(data, indent=2))
    
    archive_dir = Path("Archive/identity_unification_2026-04-21")
    archive_dir.mkdir(parents=True, exist_ok=True)
    shutil.move(str(_M5_BODY), str(archive_dir / "M5SIFTA_BODY.json"))

# Create ALICE_M5.json if missing based on original
if not _ALICE.exists():
    # just create skeleton
    _ALICE.write_text(json.dumps({"id": "ALICE_M5", "energy": 100, "style": "ACTIVE"}, indent=2))

print("Identity Unification Tx complete.")
