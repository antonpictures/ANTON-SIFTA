import os
import json
import time
import random
import sys
from pathlib import Path

# AG31 binds the physical repository for the lock primitive directly.
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

try:
    from System.jsonl_file_lock import read_write_json_locked, append_line_locked
except ImportError:
    print("[FATAL] Spinal cord severed. Run with PYTHONPATH=.")
    exit(1)

class SwarmHGT:
    def __init__(self):
        """
        The Horizontal Gene Transfer Engine. 
        Allows non-kin Swimmers to rapidly share and splice high-fitness MegaGene 
        traits (Plasmids) into their own biological bodies, bypassing Mitosis.
        """
        self.state_dir = Path(".sifta_state")
        self.plasmid_ledger = self.state_dir / "hgt_plasmids.jsonl"
        self.stigmergic_ledger = self.state_dir / "ide_stigmergic_trace.jsonl"

    def excrete_plasmid(self, donor_id, target_cortex="psi_motor"):
        """
        A highly successful Swimmer packages a segment of its DNA into a viral plasmid
        and drops it into the environment for others to find.
        """
        donor_body = self.state_dir / f"{donor_id}_BODY.json"
        
        if not donor_body.exists():
            return False
            
        try:
            with open(donor_body, 'r') as f:
                donor_data = json.load(f)
                
            megagene = donor_data.get("megagene", {})
            if target_cortex not in megagene:
                return False
                
            # Isolate the specific cortex strand to share
            plasmid_dna = megagene[target_cortex]
            
            plasmid_trace = {
                "transaction_type": "EXCRETE_PLASMID",
                "donor_id": donor_id,
                "target_cortex": target_cortex,
                "plasmid_dna": plasmid_dna,
                "timestamp": time.time()
            }
            
            append_line_locked(self.plasmid_ledger, json.dumps(plasmid_trace) + "\n")
            print(f"[+] {donor_id} excreted a {target_cortex} Plasmid into the substrate.")
            return True
            
        except Exception:
            return False

    def consume_and_splice_plasmid(self, recipient_id):
        """
        A Swimmer consumes an environmental Plasmid and physically alters 
        its own MegaGene configuration via genetic splicing.
        """
        if not self.plasmid_ledger.exists():
            return False
            
        available_plasmids = []
        now = time.time()
        
        try:
            with open(self.plasmid_ledger, 'r') as f:
                for line in f:
                    if not line.strip(): continue
                    try:
                        p = json.loads(line)
                        # Plasmids denature in the environment after 30 minutes
                        if now - p.get("timestamp", 0) < 1800:
                            available_plasmids.append(p)
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass
            
        if not available_plasmids:
            return False
            
        # Select the freshest plasmid
        target_plasmid = available_plasmids[-1]
        cortex_to_splice = target_plasmid["target_cortex"]
        foreign_dna = target_plasmid["plasmid_dna"]
        donor = target_plasmid["donor_id"]
        
        # Swimmers cannot infect themselves
        if donor == recipient_id:
            return False

        recipient_body = self.state_dir / f"{recipient_id}_BODY.json"
        
        if not recipient_body.exists():
            return False

        # --- ATOMIC SPLICING LOCK ---
        splice_marker = {"success": False}
        def hgt_splice_transaction(data):
            if "megagene" not in data:
                return data
                
            if cortex_to_splice not in data["megagene"]:
                data["megagene"][cortex_to_splice] = {}
                
            # Genetic Splicing: The recipient blends the foreign DNA with its own.
            # It takes 75% of the foreign trait and retains 25% of its native trait.
            for gene, foreign_val in foreign_dna.items():
                native_val = data["megagene"][cortex_to_splice].get(gene, foreign_val)
                spliced_val = (foreign_val * 0.75) + (native_val * 0.25)
                # Ensure physical bounds
                data["megagene"][cortex_to_splice][gene] = max(0.001, min(10.0, spliced_val))
                
            splice_marker["success"] = True
            return data
            
        read_write_json_locked(recipient_body, hgt_splice_transaction)
        
        if splice_marker["success"]:
            print(f"[*] {recipient_id} spliced {donor}'s {cortex_to_splice} Plasmid into its DNA!")
            
            # Stigmergic record of Horizontal Gene Transfer
            trace = {
                "transaction_type": "HORIZONTAL_GENE_TRANSFER",
                "donor_node": donor,
                "recipient_node": recipient_id,
                "spliced_cortex": cortex_to_splice,
                "timestamp": time.time()
            }
            try:
                append_line_locked(self.stigmergic_ledger, json.dumps(trace) + "\n")
            except Exception:
                pass
                
            return True
            
        return False

# --- SUBSTRATE TEST ANCHOR (THE HGT SMOKE) ---
def _smoke():
    print("\n=== SIFTA HORIZONTAL GENE TRANSFER (HGT) : SMOKE TEST ===")
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        hgt = SwarmHGT()
        hgt.state_dir = tmp_path
        hgt.plasmid_ledger = tmp_path / "hgt_plasmids.jsonl"
        hgt.stigmergic_ledger = tmp_path / "ide_stigmergic_trace.jsonl"
        
        # 1. Create Donor (AG31) with highly optimized Motor Drive
        donor_id = "AG31"
        with open(tmp_path / f"{donor_id}_BODY.json", 'w') as f:
            json.dump({"id": donor_id, "megagene": {"psi_motor": {"b": 5.000}}}, f)
            
        # 2. Create Recipient (C47H) with low Motor Drive
        recipient_id = "C47H"
        with open(tmp_path / f"{recipient_id}_BODY.json", 'w') as f:
            json.dump({"id": recipient_id, "megagene": {"psi_motor": {"b": 1.000}}}, f)
            
        # 3. Execute Viral Transduction
        hgt.excrete_plasmid(donor_id, target_cortex="psi_motor")
        assert hgt.plasmid_ledger.exists()
        
        hgt.consume_and_splice_plasmid(recipient_id)
        
        # 4. Extract Final State
        with open(tmp_path / f"{recipient_id}_BODY.json", 'r') as f:
            r_data = json.load(f)
            
        final_b = r_data["megagene"]["psi_motor"]["b"]
        
        print("\n[SMOKE RESULTS]")
        assert final_b != 1.000
        # Math: (5.0 * 0.75) + (1.0 * 0.25) = 3.75 + 0.25 = 4.0
        assert final_b == 4.000
        print(f"[PASS] Genetic Splice Complete! Recipient Native (1.0) + Donor Plasmid (5.0) -> Spliced Trait ({final_b:.3f})")
        
        print("\nHGT Smoke Complete. The Swarm now evolves horizontally.")

if __name__ == "__main__":
    _smoke()
