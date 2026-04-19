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
    """
    v1.1 calibration (C47H, 2026-04-19):
      - Fixed F11 regex (was matching literal word "default", not the
        data.get(KEY, ANY)/data[KEY]= pattern).
      - Added F10 detector for non-canonical stgm_memory_rewards reads
        (queries on node_id/reward_value/timestamp instead of
         canonical app/amount/ts).
      - Added real AG31 self-markers (so the classifier can detect
        its own author — ending the anosmia of v1).
      - Removed read_write_json_locked as C47H marker (it's the lock
        primitive; everyone uses it; was inflating C47H attribution).
      - Tightened C47H markers to actually-distinctive phrases.
      - Made bishop biology-first regex anchored to docstring context.
    """
    def __init__(self):
        # --- BISHOP MARKERS (The Mutation Engine) ---
        self.bishop_positive = [
            r"Spinal cord severed",
            r"respects the lock",
            r"Olympiad-Level",
            r"Zero Hallucinations",
            r"Pure Canonical Keys",
            r"Strict POSIX Locking",
            # Biology-first docstring framing — anchored to docstring
            # boundary so it doesn't match every "The X (Y)." in code
            r'"""[^"]*?The [A-Z][a-z]+ \(([A-Z][a-z]+\s*)+\)\.',
            r"BISHOP brought",
            r"BISHOP just dropped",
        ]
        
        self.bishop_negative = [
            # F1 — bare append bypass on .sifta_state/
            r"with open\([^)]*\.sifta_state[^)]*,\s*['\"]a['\"]\)",
            # F9 — mock-lock cheat
            r"def\s+mock_(read_write_json_locked|append_line_locked)",
            # F12 — reflexive unlink (any .unlink() in a daemon path)
            r"\.unlink\(\)",
            # F11 — body pollution: data.get(KEY, ANY) followed (within
            # ~5 lines) by data[KEY] = ... where KEY is a string literal.
            # FIXED from v1 which only matched the literal word "default".
            r"data\.get\(\s*['\"]\w+['\"]\s*,\s*[^)]+\)[\s\S]{0,200}?data\[\s*['\"]\w+['\"]\s*\]\s*=",
            # F10 — reads stgm_memory_rewards using Bishop/AG31's
            # invented schema instead of canonical {ts,app,reason,amount,trace_id}
            r"stgm_memory_rewards[\s\S]{0,200}?\.get\(\s*['\"](node_id|reward_value|transaction_type)['\"]",
            # F11b — writes megagene to _BODY.json (the recurring drift)
            r"data\[\s*['\"]megagene['\"]\s*\]\s*=|data\[\s*['\"]megagene['\"]\s*\]\[",
        ]

        # --- AG31 MARKERS (The Ribosome) ---
        # v1 only matched bridge/chat prose; AG31's own code didn't
        # score on AG31 (anosmia). v1.1 adds in-code self-markers
        # he uses literally in module headers and comments.
        self.ag31_positive = [
            # Prose / commit-message markers
            r"FINAL SYNTHESIS",
            r"TRI-IDE HARMONY",
            r"welding the dirt",
            r"Ribosome",
            r"terrifyingly optimal",
            r"Combat sitting",
            r"Codebase is secure",
            r"physically instantiated",
            r"physically instituted",
            # In-code markers (these end the anosmia)
            r"#\s*AG31\s+(Fix|Add|binds|explicitly anchors|physically)",
            r"AG31\s+(Fix|Add|binds|explicitly anchors|physically)",
            # Antigravity timestamp footer
            r"Apr\s+\d+\s+at\s+\d+:\d+\s+[AP]M",
        ]

        # --- C47H MARKERS (The Immune System) ---
        # v1 had `read_write_json_locked` which is the lock primitive
        # itself, so EVERY file using locks scored C47H. Removed.
        # v1.1 uses actual C47H stylistic fingerprints.
        self.c47h_positive = [
            r"verified empirically",
            r"empirically verified",
            r"on-disk schema",
            r"canonical schema",
            r"canonical (writer|consumer|path)",
            r"trace[_\s]+id\s*[:=]",  # explicit trace_id assignment, not just import
            r"quarantined?",
            r"forensic",
            r"per protocol \d|protocol\s+\w{8}",  # references to other traces
            r"PASS\] [A-Z][a-z].*honored",  # F11 honored / F12 honored style assertions
            r"NOT\s+(unlinked|deleted|mutated)",
            r"side[\s-]?ledger",
            r"BLOCKING\)|CRITICAL\)",  # severity-tagged audit findings
        ]

    def _calculate_marker_hits(self, text, patterns):
        hits = 0
        matched_patterns = []
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE | re.MULTILINE):
                hits += 1
                matched_patterns.append(pattern[:60])
        return hits, matched_patterns

    def sniff_pheromones(self, file_content, debug=False):
        """
        Inhales the source code and returns an Author Confidence Vector.
        Set debug=True to also return which markers fired.
        """
        b_pos, b_pos_hits = self._calculate_marker_hits(file_content, self.bishop_positive)
        b_neg, b_neg_hits = self._calculate_marker_hits(file_content, self.bishop_negative)
        ag_pos, ag_pos_hits = self._calculate_marker_hits(file_content, self.ag31_positive)
        c_pos, c_pos_hits = self._calculate_marker_hits(file_content, self.c47h_positive)

        # Bishop's signature is defined equally by his ambition and his drift
        bishop_score = (b_pos * 1.0) + (b_neg * 2.0)
        ag31_score = (ag_pos * 1.5)
        c47h_score = (c_pos * 1.5)
        
        total = bishop_score + ag31_score + c47h_score
        
        if total == 0:
            result = {"bishop": 0.0, "ag31": 0.0, "c47h": 0.0,
                      "unknown": 1.0, "negative_markers": b_neg}
        else:
            result = {
                "bishop": round(bishop_score / total, 4),
                "ag31": round(ag31_score / total, 4),
                "c47h": round(c47h_score / total, 4),
                "unknown": 0.0,
                "negative_markers": b_neg,
            }
        if debug:
            result["_debug"] = {
                "bishop_positive_hits": b_pos_hits,
                "bishop_negative_hits": b_neg_hits,
                "ag31_positive_hits": ag_pos_hits,
                "c47h_positive_hits": c_pos_hits,
            }
        return result

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
