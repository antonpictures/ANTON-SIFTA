import os
import json
import time
import sys
from pathlib import Path

# AG31 explicitly loads the canonical lock scripts.
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

try:
    from System.jsonl_file_lock import read_text_locked, rewrite_text_locked
except ImportError:
    print("[FATAL] Spinal cord severed. Run with PYTHONPATH=.")
    exit(1)

class SwarmMacrophage:
    def __init__(self):
        """
        The Tumor Excision Daemon (Heavy Immune Response).
        Reads the Oncology ledger and physically deletes hallucinated schemas 
        (malignant tumors) from the biological substrate.
        """
        self.state_dir = Path(".sifta_state")
        self.oncology_ledger = self.state_dir / "oncology_tumors.jsonl"

    def execute_targeted_apoptosis(self):
        """
        Scans the Oncology trace, excises the target files, and clears the ledger.
        """
        if not self.oncology_ledger.exists():
            return 0
            
        tumors_excised = 0
        surviving_traces = []
        
        try:
            # AG31 Fix: Apply the canonical POSIX lock reading instead of raw bare `open`
            raw_text = read_text_locked(self.oncology_ledger)
            if not raw_text.strip():
                return 0
                
            lines = raw_text.strip().split("\n")
                
            for line in lines:
                if not line.strip(): continue
                try:
                    trace = json.loads(line)
                    if trace.get("transaction_type") == "MALIGNANT_HALLUCINATION":
                        filename = trace.get("hallucinated_file")
                        if filename:
                            target_path = self.state_dir / filename
                            if target_path.exists() and target_path.is_file():
                                target_path.unlink()  # PHYSICAL EXCISION
                                tumors_excised += 1
                                print(f"[-] MACROPHAGE: Excised malignant tumor -> {filename}")
                    else:
                        # Preserve non-tumor traces if any exist in this ledger
                        surviving_traces.append(line)
                except json.JSONDecodeError:
                    continue
                    
            # Wipe the excised tumors from the ledger cleanly via the exclusive lock rewrite
            rewrite_text_locked(self.oncology_ledger, "".join(s + "\n" for s in surviving_traces))
                
            return tumors_excised
            
        except Exception as e:
            print(f"[!] Macrophage failure: {e}")
            return 0

if __name__ == "__main__":
    print("\n=== SIFTA MACROPHAGE (TUMOR EXCISION) ===")
    
    macrophage = SwarmMacrophage()
    excised_count = macrophage.execute_targeted_apoptosis()
    
    if excised_count > 0:
        print(f"\n[+] EXCISION COMPLETE. {excised_count} tumors violently removed from the substrate.")
        print("[+] Organism homeostasis restored. Thermodynamic bleeding stopped.")
    else:
        print("\n[+] Scan complete. No tumors found. Substrate is clean.")
