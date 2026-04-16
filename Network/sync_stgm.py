#!/usr/bin/env python3
"""
sync_stgm.py — Quorum Wallet Re-Entanglement

Delegates balance calculation to ledger_balance() (inference_economy.py),
which is the single canonical parser for repair_log.jsonl. This ensures
sync_wallets() and the Finance GUI share identical STGM accounting,
including all ledger dialects (MINING_REWARD, STGM_MINT, STGM_SPEND,
INFERENCE_BORROW, UTILITY_MINT, FOUNDATION_GRANT, compute-drip rows).

WARNING: This script writes agent JSON files from ledger truth.
         It does NOT extend the ledger — it re-hydrates JSON wallets
         from it. If wallet JSON disagrees with the ledger, the ledger wins.
"""
import json
import sys
from pathlib import Path

ROOT_DIR  = Path(__file__).resolve().parent
STATE_DIR = ROOT_DIR / ".sifta_state"

# Make System/ importable
sys.path.insert(0, str(ROOT_DIR / "System"))


def sync_wallets() -> None:
    print("=== SIFTA STGM Quorum Sync ===")

    try:
        from inference_economy import ledger_balance, LOG_PATH
    except ImportError as e:
        print(f"[ERROR] Cannot import inference_economy: {e}")
        return

    if not Path(LOG_PATH).exists():
        print(f"[ERROR] Quorum Ledger not found at {LOG_PATH}. Cannot sync.")
        return

    # ── Collect every agent_id that has any row in the ledger ─────────────────
    import re
    agent_ids: set[str] = set()
    id_pattern = re.compile(r'"(?:agent_id|miner_id|borrower_id|lender_ip)"\s*:\s*"([^"]+)"')

    with open(LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            for match in id_pattern.finditer(line):
                raw_id = match.group(1).strip().upper()
                if raw_id:
                    agent_ids.add(raw_id)

    if not agent_ids:
        print("[WARN] No agent IDs found in ledger. Nothing to sync.")
        return

    STATE_DIR.mkdir(exist_ok=True)

    print("\n[SYNC] Quorum Balances Resolved (via ledger_balance):")
    for agent_id in sorted(agent_ids):
        try:
            bal = round(float(ledger_balance(agent_id)), 2)
        except Exception as e:
            print(f"  -> {agent_id}: ERROR ({e})")
            continue

        print(f"  -> {agent_id}: {bal} STGM")

        state_file = STATE_DIR / f"{agent_id}.json"
        existing: dict = {}
        if state_file.exists():
            try:
                existing = json.loads(state_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        if not isinstance(existing, dict):
            print(f"     [SKIP] Corrupt state file for {agent_id}")
            continue

        existing["id"] = agent_id
        existing["stgm_balance"] = bal
        try:
            state_file.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"     [WARN] Could not write {state_file.name}: {e}")

    print("\n=== Wallet Physics Re-Entangled ===")


if __name__ == "__main__":
    sync_wallets()
