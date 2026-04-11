import unittest
import threading
from level_02_race_condition import BankAccount

class TestLevel02(unittest.TestCase):
    def test_concurrent_deposits(self):
        account = BankAccount(0)
        
        def run_deposits():
            for _ in range(100):
                account.deposit(1)
                
        threads = [threading.Thread(target=run_deposits) for _ in range(5)]
        for t in threads: t.start()
        for t in threads: t.join()
        
        # 5 threads * 100 deposits = 500
        self.assertEqual(account.balance, 500)

if __name__ == '__main__':
    unittest.main()
