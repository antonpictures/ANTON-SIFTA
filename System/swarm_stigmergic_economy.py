from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class StigmergicEconomicModel:
    """
    The baseline pricing model ensuring cyborg nodes are net-profitable
    when trading inference across the federation.
    """
    stgm_to_usd: float = 1.0                # 1 STGM = $1 (baseline peg)
    electricity_usd_per_kwh: float = 0.35   # e.g., California rates
    hardware_wear_markup: float = 1.5       # 50% markup for depreciation/profit

    def calculate_minimum_bounty(self, expected_watts: float, expected_duration_s: float) -> float:
        """
        Calculates the minimum STGM a node should accept to process a request,
        ensuring it covers electricity, wear, and leaves a profit surplus.
        """
        kwh = (expected_watts / 1000.0) * (expected_duration_s / 3600.0)
        cost_usd = kwh * self.electricity_usd_per_kwh
        profitable_usd = cost_usd * self.hardware_wear_markup
        required_stgm = profitable_usd / self.stgm_to_usd
        return required_stgm

class StigmergicWallet:
    """
    Local memory representation of a node's STGM balance.
    In production, this reconstructs from the append-only stigmergic trace ledger.
    """
    def __init__(self, node_serial: str, initial_balance: float = 0.0):
        self.node_serial = node_serial
        self.balance = initial_balance
        self.ledger: list[Dict[str, Any]] = []
        
    def spend(self, amount: float, reason: str, to_serial: str):
        if amount > self.balance:
            raise ValueError(f"Insufficient STGM on {self.node_serial}. Balance: {self.balance}, Required: {amount}")
        self.balance -= amount
        self.ledger.append({"kind": "stgm_spend", "amount": amount, "to": to_serial, "reason": reason})
        
    def receive(self, amount: float, reason: str, from_serial: str):
        self.balance += amount
        self.ledger.append({"kind": "stgm_receive", "amount": amount, "from": from_serial, "reason": reason})
