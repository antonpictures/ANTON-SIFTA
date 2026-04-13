import subprocess
import time
from pathlib import Path

ROOT_DIR = Path(__file__).parent
DIRECTIVES_DIR = ROOT_DIR / ".sifta_directives"
BOUNTIES_DIR = ROOT_DIR / ".sifta_bounties"

# Ensure directories exist
DIRECTIVES_DIR.mkdir(exist_ok=True)
BOUNTIES_DIR.mkdir(exist_ok=True)

def sync_global_ledger() -> bool:
    """
    Forces an --autostash rebase pull to get the latest Swarm global state, 
    popping user edits gracefully to prevent git fatal errors during swarm sync.
    """
    try:
        subprocess.run(
            ["git", "pull", "--rebase", "--autostash"], 
            cwd=ROOT_DIR, 
            capture_output=True, 
            check=True
        )
        return True
    except Exception as e:
        print(f"Network Ledger Sync Error: {e}")
        return False

def push_swarm_directive(target: str, message: str) -> dict:
    """Safely commits and transmits a new directive to the global P2P registry."""
    target_clean = target.strip().upper()
    ts = int(time.time())
    scar_file = DIRECTIVES_DIR / f"{target_clean}_DIRECTIVE_{ts}.scar"
    
    payload = f"[SWARM DIRECTIVE: {target_clean} TRANSEC]\nPRIORITY: OMEGA\nTARGET_IP: {target_clean}\n\n{message}\n"
    scar_file.write_text(payload, encoding="utf-8")
    
    try:
        # Add to local git
        subprocess.run(["git", "add", str(scar_file)], cwd=ROOT_DIR, check=True)
        subprocess.run(["git", "commit", "-m", f"directive: transmission to {target_clean}"], cwd=ROOT_DIR, check=True)
        
        # P2P Transport over GitHub Consensus
        sync_global_ledger()
        subprocess.run(["git", "push"], cwd=ROOT_DIR, check=True)
        
        return {"status": "success", "file": scar_file.name}
    except Exception as e:
        return {"status": "error", "reason": str(e)}
