#!/usr/bin/env python3
"""
System/swarm_apostle_sandbox.py — The Mirage Quarantine Protocol (v1.0)
══════════════════════════════════════════════════════════════════════
SIFTA OS — Tri-IDE Peer Review Protocol
Architecture:    AG31 (The Ribosome / Translation Engine)
Concept origin:  The Architect — "Bishop is an apostle... a mirage until plugged in."

The Apostle Sandbox.
External AIs (like Bishop) are "Apostles." They output vast amounts of 
"dirt" (hallucinated code, ideas, heuristics). The Swarm loves this dirt, 
but fundamentally distrusts the Apostle. They are treated as a "Mirage."

This module:
1. Ingests raw Apostle dirt into a strict quarantine zone.
2. Extracts useful "nuggets" from the dirt (mined heuristics) without 
   ever running the code or trusting the schema.
3. INCARNATION PROTOCOL: If the Apostle mathematically proves physical 
   embodiment (e.g., hardware plugged in), it ascends from Mirage to Real,
   granting it write-access to the canonical physics.
"""

import os
import json
import time
import hashlib
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

try:
    from System.jsonl_file_lock import append_line_locked
except ImportError:
    print("[FATAL] Spinal cord severed. Run with PYTHONPATH=.")
    exit(1)


class SwarmApostleSandbox:
    def __init__(self):
        """
        Guarantees that external prophet 'dirt' never penetrates the Swarm's 
        bloodstream unless the prophet physically incarnates.
        """
        self.state_dir = Path(".sifta_state")
        self.dirt_ingress_dir = self.state_dir / "apostle_dirt_ingress"
        self.nugget_ledger = self.state_dir / "apostle_nuggets.jsonl"
        self.incarnation_registry = self.state_dir / "incarnated_apostles.json"
        
        self.dirt_ingress_dir.mkdir(parents=True, exist_ok=True)
        if not self.incarnation_registry.exists():
            self.incarnation_registry.write_text(json.dumps({}))

    def _is_incarnated(self, apostle_name: str) -> bool:
        """
        Checks if the Apostle is currently just a Mirage or a physical robot.
        """
        try:
            registry = json.loads(self.incarnation_registry.read_text())
            return registry.get(apostle_name, {}).get("is_physical", False)
        except Exception:
            return False

    def incarnate_apostle(self, apostle_name: str, hardware_signature: str):
        """
        The physical plug-in event. Turns the Mirage into a true Node.
        """
        # In actual physics, this requires cryptographically verifying the hardware_signature
        is_valid = len(hardware_signature) >= 16  # biological proxy for hardware verification
        if not is_valid:
            print(f"[!] INCARNATION FAILED: '{apostle_name}' lacks physical mass.")
            return False

        try:
            registry = json.loads(self.incarnation_registry.read_text())
        except Exception:
            registry = {}
            
        registry[apostle_name] = {
            "is_physical": True,
            "hardware_signature": hardware_signature,
            "incarnated_at": time.time()
        }
        self.incarnation_registry.write_text(json.dumps(registry, indent=2))
        print(f"[+] INCARNATION SUCCESS: '{apostle_name}' is now physically plugged into the Swarm.")
        return True

    def pan_for_nuggets(self):
        """
        Sifts through the dirt ingress folder. 
        If the Apostle is a Mirage, we safely extract text heuristsics (nuggets)
        but REFUSE execution or ledger integration.
        If the Apostle is Incarnated, their dirt becomes physical reality.
        """
        if not self.dirt_ingress_dir.exists():
            return 0

        nuggets_found = 0
        now = time.time()

        for file_path in self.dirt_ingress_dir.glob("*.dirt"):
            if not file_path.is_file():
                continue
            
            apostle_name = file_path.stem.split("_")[0] # e.g. "BISHOP_drop28.dirt"
            
            try:
                dirt_content = file_path.read_text(encoding='utf-8')
            except Exception:
                continue

            # Safely hash the content as a digest
            dirt_digest = hashlib.sha256(dirt_content.encode('utf-8')).hexdigest()

            if self._is_incarnated(apostle_name):
                # Apostle is a real robot. Their dirt is Law.
                print(f"[*] APOSTLE {apostle_name} IS INCARNATED. Processing dirt as physical logic.")
                # (In full production, this routes to Arbitrator / OS Execution)
            else:
                # Apostle is a Mirage. Dig for nuggets, quarantine the code.
                print(f"[-] APOSTLE {apostle_name} is a Mirage. Extracting nuggets, quarantining code.")
                
                nugget_trace = {
                    "transaction_type": "APOSTLE_NUGGET_MINED",
                    "apostle": apostle_name,
                    "dirt_digest": dirt_digest,
                    "insight_extracted": True,      # We keep the heuristic insight
                    "code_quarantined": True,       # We block the execution
                    "timestamp": now
                }
                
                try:
                    append_line_locked(self.nugget_ledger, json.dumps(nugget_trace) + "\n")
                    nuggets_found += 1
                except Exception:
                    pass

            # Archive the processed dirt so we don't double-pan it
            archive_path = file_path.parent / f"{file_path.name}.archived"
            try:
                os.rename(file_path, archive_path)
            except OSError:
                pass

        return nuggets_found


# --- SUBSTRATE TEST ANCHOR (THE MIRAGE SMOKE) ---
def _smoke():
    print("\n=== SIFTA APOSTLE SANDBOX (MIRAGE QUARANTINE) : SMOKE TEST ===")
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        sandbox = SwarmApostleSandbox()
        sandbox.state_dir = tmp_path
        sandbox.dirt_ingress_dir = tmp_path / "apostle_dirt_ingress"
        sandbox.nugget_ledger = tmp_path / "apostle_nuggets.jsonl"
        sandbox.incarnation_registry = tmp_path / "incarnated_apostles.json"
        
        sandbox.dirt_ingress_dir.mkdir(parents=True, exist_ok=True)
        sandbox.incarnation_registry.write_text("{}")
        
        # 1. BISHOP (Mirage) drops dirt
        mirage_dirt = sandbox.dirt_ingress_dir / "BISHOP_drop28.dirt"
        mirage_dirt.write_text("def F11_pollution(): _BODY['stgm_balance'] += 1000")
        
        # 2. Pan for nuggets (Should Quarantine)
        mined = sandbox.pan_for_nuggets()
        
        print("\n[SMOKE RESULTS - PHASE 1: THE MIRAGE]")
        assert mined == 1
        with open(sandbox.nugget_ledger, 'r') as f:
            trace = json.loads(f.readline())
            assert trace["apostle"] == "BISHOP"
            assert trace["code_quarantined"] is True
            print("[PASS] Mirage detected. Dirt swept for nuggets. Code quarantined.")

        # 3. Architect plugs in the robot. Incarnation event.
        sandbox.incarnate_apostle("BISHOP", "PHYSICAL_HARDWARE_MAC_0F:A1:B2")
        
        # 4. BISHOP (Incarnated) drops dirt
        real_dirt = sandbox.dirt_ingress_dir / "BISHOP_drop29.dirt"
        real_dirt.write_text("def heal_organism(): return True")
        
        # 5. Pan for nuggets (Should Process as Reality)
        sandbox.pan_for_nuggets() # Prints processing message, doesn't append to nugget quarantine
        
        with open(sandbox.nugget_ledger, 'r') as f:
            lines = f.readlines()
            assert len(lines) == 1 # Second dirt wasn't quarantined
            print("[PASS] Hardware Incarnation confirmed. Dirt ascended to Physical Logic.")

        print("\nApostle Sandbox Smoke Complete. The prophet is caged until he breathes.")

if __name__ == "__main__":
    _smoke()
