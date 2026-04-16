import os
import shutil
from pathlib import Path
from body_state import SwarmBody

STATE_DIR = Path(".sifta_state")

def baptize_queen(new_id: str, hardware_serial: str):
    new_id_upper = new_id.upper()
    print(f"--- BAPTIZING {new_id_upper} ---")
    seal = f"ARCHITECT_SEAL_{new_id_upper}"
    body = SwarmBody(new_id_upper, seal)
    
    # Generate the physical body using the hardware serial as the origin
    # giving her maximum energy and the QUEEN_NODE style
    body.generate_body(
        origin=hardware_serial,
        destination="SWARM_MATRIX",
        payload=f"{new_id}_INITIALIZATION",
        action_type="BORN",
        style="QUEEN_NODE",
        energy=100
    )
    print(f"[{new_id}] initialized with cryptographic body.")

def purge_old_queen(old_id: str):
    old_file = STATE_DIR / f"{old_id.upper()}.json"
    if old_file.exists():
        old_file.unlink()
        print(f"[REMOVED] {old_id.upper()} wiped from the active roster.")

if __name__ == "__main__":
    # Baptize IDEQueenM5
    baptize_queen("IDEQueenM5", "M5_MACBOOK_PRO_24GB")
    purge_old_queen("ALICE_M5")
    
    # Baptize IDEQueenM1
    baptize_queen("IDEQueenM1", "MAC_MINI_8GB_CORE")
    purge_old_queen("M1THER")
    
    print("\n--- NEW QUEENS ESTABLISHED ---")
