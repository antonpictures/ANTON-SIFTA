"""
casino_vault.py - Quarantined play-token ledger for SIFTA games.

This module is intentionally NOT a STGM wallet. Gambling/game outcomes cannot
mint spendable STGM. Canonical wallet money comes only from repair_log.jsonl.
"""

import json
import time
from pathlib import Path
from dataclasses import dataclass, asdict

_STATE_DIR = Path(__file__).resolve().parent.parent / ".sifta_state"
LEDGER_FILE = _STATE_DIR / "casino_vault.jsonl"

@dataclass
class CasinoTransaction:
    ts: float
    action: str
    casino_delta: float
    player_delta: float
    memo: str

class CasinoVault:
    def __init__(self, architect_id: str):
        self.architect_id = architect_id
        _STATE_DIR.mkdir(exist_ok=True)
        
        self.casino_balance = 0.0
        self.player_net = 0.0 # How much STGM the player has won/lost strictly via gaming
        
        self._load_ledger()
        self._ensure_genesis()

    def _load_ledger(self):
        self.casino_balance = 0.0
        self.player_net = 0.0
        if not LEDGER_FILE.exists():
            return
            
        with open(LEDGER_FILE, "r") as f:
            for line in f:
                if not line.strip(): continue
                try:
                    tx = json.loads(line)
                    self.casino_balance += tx.get("casino_delta", 0.0)
                    self.player_net += tx.get("player_delta", 0.0)
                except Exception:
                    pass

    def _ensure_genesis(self):
        """Seed a local play-token house balance for old game surfaces."""
        if not LEDGER_FILE.exists() or self.casino_balance == 0.0:
            tx = CasinoTransaction(
                ts=time.time(),
                action="PLAY_TOKEN_GENESIS",
                casino_delta=1000.0,
                player_delta=0.0,
                memo="Initial play-token house balance; not spendable STGM."
            )
            self._write_tx(tx)

    def _write_tx(self, tx: CasinoTransaction):
        with open(LEDGER_FILE, "a") as f:
            f.write(json.dumps(asdict(tx)) + "\n")
        self.casino_balance += tx.casino_delta
        self.player_net += tx.player_delta

    def get_real_player_wallet(self) -> float:
        """Return canonical STGM for compatibility; casino winnings are excluded."""
        try:
            from System.stgm_economy import canonical_wallet_balance

            return canonical_wallet_balance(self.architect_id)
        except Exception:
            return 0.0

    def get_play_wallet(self) -> float:
        """Game-only play-token balance, separate from STGM."""
        return max(0.0, 1000.0 + self.player_net)

    def process_bet(self, amount: float) -> bool:
        """Deduct from the play-token wallet. Returns True if enough credits."""
        wallet = self.get_play_wallet()
        if wallet < amount:
            return False # Cut off
            
        tx = CasinoTransaction(
            ts=time.time(),
            action="BET",
            casino_delta=amount,
            player_delta=-amount,
            memo=f"Placed bet of {amount} STGM"
        )
        self._write_tx(tx)
        return True

    def process_payout(self, amount: float, reason: str):
        """Deduct from play-token house balance, adds to player play credits."""
        tx = CasinoTransaction(
            ts=time.time(),
            action="PAYOUT",
            casino_delta=-amount,
            player_delta=amount,
            memo=f"Payout for: {reason}"
        )
        self._write_tx(tx)
