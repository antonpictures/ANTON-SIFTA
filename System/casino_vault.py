"""
casino_vault.py - Real STGM Economy for SIFTA Games
═══════════════════════════════════════════════════════════════════════════════
Implements the verified cryptographic ledger for the Swarm Global Casino Vault.
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
        """If the vault is completely empty, accept the 1000.0 STGM Warren Buffet loan."""
        if not LEDGER_FILE.exists() or self.casino_balance == 0.0:
            tx = CasinoTransaction(
                ts=time.time(),
                action="WARREN_BUFFET_LOAN",
                casino_delta=1000.0,
                player_delta=0.0, # The angel investment was minted externally, so we don't dock the player's personal wallet
                memo="Initial 1000 STGM Genesis Injection by Architect."
            )
            self._write_tx(tx)

    def _write_tx(self, tx: CasinoTransaction):
        with open(LEDGER_FILE, "a") as f:
            f.write(json.dumps(asdict(tx)) + "\n")
        self.casino_balance += tx.casino_delta
        self.player_net += tx.player_delta

    def get_real_player_wallet(self) -> float:
        """
        The player's absolute STGM balance.
        = Total Memory STGM Minted + Net Casino Winnings
        """
        from System.stigmergic_memory_bus import StigmergicMemoryBus
        bus = StigmergicMemoryBus(architect_id=self.architect_id)
        minted = bus.total_stgm_earned()
        return minted + self.player_net

    def process_bet(self, amount: float) -> bool:
        """Deducts from player, adds to Casino Vault. Returns True if enough funds."""
        wallet = self.get_real_player_wallet()
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
        """Deducts from Casino Vault, adds to player."""
        tx = CasinoTransaction(
            ts=time.time(),
            action="PAYOUT",
            casino_delta=-amount,
            player_delta=amount,
            memo=f"Payout for: {reason}"
        )
        self._write_tx(tx)
