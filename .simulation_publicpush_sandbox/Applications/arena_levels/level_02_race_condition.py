import threading
import time

class BankAccount:
    def __init__(self, balance=0):
        self.balance = balance
        # BUG: Missing lock for thread-safe operations

    def deposit(self, amount):
        # Simulate delay to force race condition
        current = self.balance
        time.sleep(0.001)
        self.balance = current + amount

    def withdraw(self, amount):
        current = self.balance
        time.sleep(0.001)
        self.balance = current - amount
