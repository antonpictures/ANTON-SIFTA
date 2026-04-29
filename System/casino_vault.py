"""
casino_vault.py - Disabled legacy play-token compatibility shim.

Casino/play tokens were retired by Architect request. This module remains only
to keep old imports from crashing; it does not auto-create ledgers and it does
not write game balances. Canonical wallet money comes only from repair_log.jsonl.
"""

import json
from pathlib import Path
from dataclasses import dataclass

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
        self.player_net = 0.0
        
        self._load_ledger()

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
        """Legacy no-op: play-token genesis is retired."""
        return None

    def _write_tx(self, tx: CasinoTransaction):
        """Legacy no-op: casino/play-token writes are disabled."""
        return None

    def get_real_player_wallet(self) -> float:
        """Return canonical STGM for compatibility; casino winnings are excluded."""
        try:
            from System.stgm_economy import canonical_wallet_balance

            return canonical_wallet_balance(self.architect_id)
        except Exception:
            return 0.0

    def get_play_wallet(self) -> float:
        """Play-token wallet is retired."""
        return 0.0

    def process_bet(self, amount: float) -> bool:
        """Retired play-token betting always refuses."""
        return False

    def process_payout(self, amount: float, reason: str):
        """Retired play-token payouts are ignored."""
        return None
