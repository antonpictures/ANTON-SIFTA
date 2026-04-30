import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from Kernel.inference_economy import ledger_balance
try:
    print(ledger_balance('M5SIFTA_BODY'))
except Exception as e:
    print("Error:", e)
