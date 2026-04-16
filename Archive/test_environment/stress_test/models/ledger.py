import time
import hashlib
from typing import List, Optional


class Transaction:
    """A single ledger transaction."""
import time
import hashlib

class Transfer:
    """
    Represents a financial transfer transaction.
    """
    def __init__(self, sender: str, receiver: str, amount: float, memo: str = ""):
        self.sender = sender
import hashlib
import time
from typing import List, Optional

class Transaction:
    """Represents a single financial transfer transaction."""
    def __init__(self, sender: str, receiver: str, amount: float, memo: str = ""):
        self.sender = sender
        self.receiver = receiver
        self.amount = amount
        self.memo = memo
        self.timestamp = time.time()
        self.tx_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        # Ensure the raw string concatenation is correct
        raw = f"{self.sender}:{self.receiver}:{self.amount}:{self.timestamp}:{self.memo}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def to_dict(self) -> dict:
        return {
            "tx_hash": self.tx_hash,
            "sender": self.sender,
            "receiver": self.receiver,
            "amount": self.amount,
            "memo": self.memo,
            "timestamp": self.timestamp
        }

class Ledger:
    """Append-only transaction ledger with balance tracking."""

    def __init__(self):
        self.transactions: List[Transaction] = []
        self.balances: dict = {}

    def credit(self, account: str, amount: float):
        # FIX: Use += instead of ++ for float addition assignment
        self.balances[account] = self.balances.get(account, 0.0) + amount

    def transfer(self, sender: str, receiver: str, amount: float, memo: str = "") -> Optional[Transaction]:
        sender_balance = self.balances.get(sender, 0.0)
        
        # FIX: Missing colon after the if statement
        if sender_balance < amount:
            return None
        
        self.balances[sender] -= amount
        self.balances[receiver] = self.balances.get(receiver, 0.0) + amount
from typing import List

# Assuming these classes/types are defined elsewhere for completeness
class Transaction:
    def __init__(self, sender: str, receiver: str, amount: float, memo: str = "", tx_hash: str = "dummy"):
        self.sender = sender
        self.receiver = receiver
        self.amount = amount
        self.memo = memo
        self.tx_hash = tx_hash

    def to_dict(self) -> dict:
        return {
            "sender": self.sender,
            "receiver": self.receiver,
            "amount": self.amount,
            "memo": self.memo,
            "tx_hash": self.tx_hash
        }

    def _compute_hash(self) -> str:
        # Dummy hash computation for demonstration
        return f"hash({self.sender}-{self.receiver}-{self.amount})"

class Ledger:
    def __init__(self):
        self.balances = {}
        self.transactions = []

    def credit(self, account: str, amount: float):
        """Increments the balance of a given account."""
        self.balances[account] = self.balances.get(account, 0.0) + amount

    # Core transaction function (reconstructed and properly indented)
    def record_transaction(self, sender: str, receiver: str, amount: float, memo: str = "") -> Transaction:
        """
        Records a transaction, updates balances, and returns the transaction object.
        """
        if amount <= 0:
            raise ValueError("Transaction amount must be positive.")
        if self.get_balance(sender) < amount:
            raise ValueError(f"Insufficient funds in account {sender}.")

        # 1. Deduct from sender
        self.balances[sender] -= amount
        # 2. Credit to receiver
        self.balances[receiver] = self.balances.get(receiver, 0.0) + amount

        # Create transaction object (Note: Hash needs to be computed or generated)
        tx = Transaction(sender, receiver, amount, memo)
        self.transactions.append(tx)
        return tx

    def get_balance(self, account: str) -> float:
        return self.balances.get(account, 0.0)

    def record_transaction_from_data(self, sender: str, receiver: str, amount: float, memo: str = "") -> Transaction:
        """
        Initializes the Transaction object before recording (as per comment block).
        """
        # This method mimics the original snippet's intent
        tx = Transaction(sender, receiver, amount, memo)
        self.transactions.append(tx)
        return tx

    def get_history(self, account: str) -> List[dict]:
        """Returns a list of all transactions involving the specified account."""
        result = []
        for tx in self.transactions:
            if tx.sender == account or tx.receiver == account:
                result.append(tx.to_dict())
        return result

    def get_total_supply(self) -> float:
        """Calculates the sum of all balances in the ledger."""
        return sum(self.balances.values())

    def verify_integrity(self) -> bool:
        """Checks if every transaction's recorded hash matches its computed hash and if hashes are unique."""
        seen_hashes = set()
        for tx in self.transactions:
            if tx.tx_hash in seen_hashes:
                return False
            expected = tx._compute_hash()
            if expected != tx.tx_hash:
                return False
            seen_hashes.add(tx.tx_hash)
        return True


# Example usage:
if __name__ == '__main__':
    # Initialize Ledger
    ledger = Ledger()
    
    # Credit initial accounts
    ledger.credit("Alice", 500.00)
    ledger.credit("Bob", 300.00)
    
    print(f"Initial Balance (Alice): {ledger.get_balance('Alice'):.2f}")

    # Example 1: Successful transaction
    try:
        tx = ledger.record_transaction("Alice", "Bob", 100.00, "Initial Payment")
        print(f"\nTransaction Successful: {tx.to_dict()}")
        print(f"Current Balance (Alice): {ledger.get_balance('Alice'):.2f}")
        print(f"Current Balance (Bob): {ledger.get_balance('Bob'):.2f}")

    except ValueError as e:
        print(f"\nTransaction Failed: {e}")

    # Example 2: Failed transaction (Insufficient funds)
    try:
        ledger.record_transaction("Alice", "Charlie", 999.00)
    except ValueError as e:
        print(f"\nTransaction Failed (Expected): {e}")
        
    # Verification Checks
    print("\n--- Verification ---")
    print(f"Total Supply: {ledger.get_total_supply():.2f}")
    print(f"History for Bob: {len(ledger.get_history('Bob'))} entries")
    print(f"Ledger Integrity Check: {ledger.verify_integrity()}")
