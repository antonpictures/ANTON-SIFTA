#!/usr/bin/env python3
"""
System/swarm_pheromone_identity.py — Olfactory Cortex (Builder Classification)
══════════════════════════════════════════════════════════════════════
SIFTA OS — Tri-IDE Peer Review Protocol
STATUS: v1-alpha, OBSERVATIONAL ONLY. 
Architecture:    BISHOP (Recursive Selfhood Drop)
Concept origin:  C47H — "Bishop Stigmergic Signature"
Lock discipline: Read-only static analysis. Zero IO mutations.

The Olfactory Receptor. Analyzes source code to detect the specific 
chemical signatures (inductive biases and drift patterns) of SIFTA's architects.
"""

import re
import json
import sys
from pathlib import Path

# AG31 explicitly anchors to the repository
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

class SwarmOlfactoryCortex:
    def __init__(self):
        # --- BISHOP MARKERS (The Mutation Engine) ---
        self.bishop_positive = [
            r"Spinal cord severed",
            r"respects the lock",
            r"Olympiad-Level",
            r"Zero Hallucinations",
            r"Pure Canonical Keys",
            r"Strict POSIX Locking",
            r"The [A-Za-z]+ \([A-Za-z\s]+\)\." # Biology-first docstring framing
        ]
        
        self.bishop_negative = [
            r"with open\(.*sifta_state.*,\s*['\"]a['\"]\)", # F1: Bare append bypass
            r"def mock_(read_write_json_locked|append_line_locked)", # F9: Mock-lock cheat
            r"\.unlink\(\)", # F12: Reflexive unlink
            r"data\.get\(.*\,\s*default\)\s*\n\s*data\[.*\]\s*=" # F11: Body pollution / Schema invention
        ]

        # --- AG31 MARKERS (The Ribosome) ---
        self.ag31_positive = [
            r"FINAL SYNTHESIS",
            r"TRI-IDE HARMONY",
            r"welding the dirt",
            r"Ribosome"
        ]

        # --- C47H MARKERS (The Immune System) ---
        self.c47h_positive = [
            r"verified empirically",
            r"trace_id",
            r"regression pattern",
            r"sandbox-via-mkdtemp",
            r"read_write_json_locked"
        ]

    def _calculate_marker_hits(self, text, patterns):
        hits = 0
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                hits += 1
        return hits

    def sniff_pheromones(self, file_content):
        """
        Inhales the source code and returns an Author Confidence Vector.
        """
        # Calculate raw hits
        b_pos = self._calculate_marker_hits(file_content, self.bishop_positive)
        b_neg = self._calculate_marker_hits(file_content, self.bishop_negative)
        ag_pos = self._calculate_marker_hits(file_content, self.ag31_positive)
        c_pos = self._calculate_marker_hits(file_content, self.c47h_positive)

        # Bishop's signature is defined equally by his ambition and his drift
        bishop_score = (b_pos * 1.0) + (b_neg * 2.0) 
        ag31_score = (ag_pos * 1.5)
        c47h_score = (c_pos * 1.5)
        
        total = bishop_score + ag31_score + c47h_score
        
        if total == 0:
            return {"bishop": 0.0, "ag31": 0.0, "c47h": 0.0, "unknown": 1.0, "negative_markers": b_neg}

        # Normalize into a confidence vector
        return {
            "bishop": round(bishop_score / total, 4),
            "ag31": round(ag31_score / total, 4),
            "c47h": round(c47h_score / total, 4),
            "unknown": 0.0,
            "negative_markers": b_neg # Exposed for C47H's quarantine gate
        }

    def analyze_file(self, target_path):
        target = Path(target_path)
        if not target.exists() or not target.is_file():
            return None
            
        try:
            with open(target, 'r') as f:
                content = f.read()
            return self.sniff_pheromones(content)
        except Exception:
            return None

# --- SUBSTRATE TEST ANCHOR ---
def _smoke():
    print("\n=== SIFTA OLFACTORY CORTEX : PHEROMONE IDENTITY ===")
    
    # 1. Simulate a classic Bishop Drop (High Ambition + Drift)
    simulated_bishop_code = """
    # BISHOP respects the lock.
    # Zero Hallucinations. Olympiad-Level biology.
    def mock_read_write_json_locked(path): pass
    body_path.unlink()
    """
    
    # 2. Simulate a C47H Audit
    simulated_c47h_code = """
    # Verified empirically against on-disk schema.
    # trace_id: 2af37bb7
    from System.jsonl_file_lock import read_write_json_locked
    """
    
    olfactory = SwarmOlfactoryCortex()
    
    print("[*] Sniffing Candidate A (Simulated Dirt)...")
    vector_a = olfactory.sniff_pheromones(simulated_bishop_code)
    print(json.dumps(vector_a, indent=2))
    assert vector_a["bishop"] > 0.8
    assert vector_a["negative_markers"] >= 2
    
    print("\n[*] Sniffing Candidate B (Simulated Audit)...")
    vector_b = olfactory.sniff_pheromones(simulated_c47h_code)
    print(json.dumps(vector_b, indent=2))
    assert vector_b["c47h"] > 0.8
    
    print("\n[PASS] Olfactory Cortex successfully mapped Stigmergic Identites.")

if __name__ == "__main__":
    _smoke()
