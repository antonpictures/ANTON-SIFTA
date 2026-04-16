import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from System.casino_vault import CasinoVault
cv = CasinoVault(architect_id="IOAN_M5")
player = cv.get_real_player_wallet()
casino = cv.casino_balance
print(f"Architect Wallet: {player}")
print(f"Casino Vault: {casino}")
