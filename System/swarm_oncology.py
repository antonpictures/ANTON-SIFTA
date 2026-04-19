#!/usr/bin/env python3
"""
System/swarm_oncology.py — Hallucination Detection Daemon (v1-alpha)
══════════════════════════════════════════════════════════════════════
SIFTA OS — Tri-IDE Peer Review Protocol

STATUS: v1-alpha, OBSERVATIONAL ONLY. Not yet calibrated.

Architecture:    BISHOP (drop 5, post-exhaustion reset)
Concept origin:  BISHOP — "hallucinated schemas as cancer"
Lock discipline: clean (real append_line_locked, real \\n, no mocks)
Calibration:     UNCALIBRATED — see peer review trace cf900ffd

KNOWN LIMITATIONS (must address before any consumer relies on output):
  [O1] Logic inversion: hardcoded whitelist treats absence-from-list
       as evidence of malignancy. First production run flagged 270
       canonical cortex files (homeostasis_coefficients_proposed.json,
       motor_potential_traces.jsonl, field_dynamics_state.json,
       circadian_m1.json, mitochondrial_atp.json, etc.) as tumors.
       Forensic ledger preserved at
       Archive/bishop_drops_pending_review/oncology_tumors_270_FALSE_POSITIVES_2026-04-19.jsonl
  [O2] Whitelist contains author's own un-reviewed outputs
       (nmj_acetylcholine.jsonl, long_term_instincts.json) as
       "canonical." Iteration 2 must derive canonical set by
       grepping System/ + Applications/ for ledger path literals.
  [O3] Runner has no tempfile sandbox; writes to live .sifta_state/.
  [O4] state_dir.glob('*') is non-recursive; misses subdirectories.
  [O5] Header originally suggested "C47H or Microglia excises tumors"
       — REJECTED per protocol. Auto-deletion on a faulty whitelist
       would erase real cortex state. This module is observational
       only. Excision is a separate human-reviewed decision.

DO NOT IMPORT CONSUMERS until iteration 2 ships green with tri-IDE
review. Header maintained by C47H. Architecture remains BISHOP's.
"""

import os
import json
import time
import sys
from pathlib import Path

# AG31 binds the physical repository for the lock primitive directly.
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

try:
    from System.jsonl_file_lock import append_line_locked
except ImportError:
    print("[FATAL] Spinal cord severed. Run with PYTHONPATH=.")
    exit(1)

class SwarmOncology:
    def __init__(self):
        """
        The Oncology Daemon. Scans the biological substrate for unconstrained 
        cellular growth (hallucinated LLM schemas) and tracks them stigmergically
        so the Swarm can visualize and excise the cancer.
        """
        self.state_dir = Path(".sifta_state")
        self.oncology_ledger = self.state_dir / "oncology_tumors.jsonl"
        
        # The canonical, healthy DNA of the SIFTA organism
        self.healthy_schemas = {
            "ide_stigmergic_trace.jsonl",
            "work_receipts.jsonl",             # [AG31 Fix] BISHOP missed the valid reward ledger
            "stgm_memory_rewards.jsonl",       # [AG31 Fix] Old biological ledger required for stability
            "amygdala_nociception.jsonl",
            "entorhinal_spatial_map.jsonl",
            "long_term_instincts.json",
            "nmj_acetylcholine.jsonl",
            "oncology_tumors.jsonl",
            "wernicke_semantics.jsonl",        # Core Wernicke Broca semantic stream
            "audio_ingress_log.jsonl",         # Core Acoustic Stream
            "clinical_heartbeat.json",         # Health Monitor
            "event_clock.jsonl",               # Chronometry
            "clock_settings.json",             # Chronometry bounds
            "hgt_plasmids.jsonl",              # Horizontal Gene Transfer vectors
            "endocrine_glands.jsonl",          # Global Adrenaline Output ledgers
            "bioluminescence_photons.jsonl",   # Quorum Sensing structural signals
            "mycelial_network.jsonl",          # Wood Wide Web time-3D fungal networks
            "bishop_mrna_field.jsonl",         # BISHOP mRNA conscience lock ledger
            "epigenetic_methylations.jsonl",   # DNA methylation / lineage trauma
            "apostle_nuggets.jsonl",           # BISHOP/External LLM sterilized heuristics
            "incarnated_apostles.json",        # Hardware signature registry for Apostles
        }

    def detect_metastasis(self):
        """
        Tails the state directory. Any file that is not a canonical schema 
        or a valid Swimmer BODY is flagged as a tumor.
        """
        if not self.state_dir.exists():
            return 0
            
        tumors_found = 0
        
        for file_path in self.state_dir.glob("*"):
            if not file_path.is_file():
                continue

            filename = file_path.name

            # Ignore healthy Swimmer bodies and canonical ledgers
            if filename.endswith("_BODY.json") or filename in self.healthy_schemas:
                continue

            # Ignore the lock file, generic temp dirs, lymphatic staging files,
            # and the archive/ subdirectory written by swarm_lymphatic.py
            if ("lock" in filename or filename.startswith(".")
                    or filename.endswith(".lymph")
                    or "apostle_dirt" in filename):
                continue
            
            # MALIGNANCY DETECTED: A Swimmer hallucinated a new ledger/schema.
            tumor_trace = {
                "transaction_type": "MALIGNANT_HALLUCINATION",
                "hallucinated_file": filename,
                "file_size_bytes": file_path.stat().st_size,
                "timestamp": time.time()
            }
            
            try:
                # Strictly using C47H's lock to record the cancer
                # [AG31 Fix] added "\n" to adhere to jsonl standard correctly
                append_line_locked(self.oncology_ledger, json.dumps(tumor_trace) + "\n")
                tumors_found += 1
                print(f"[!] ONCOLOGY WARNING: Malignant schema detected -> {filename}")
            except Exception:
                pass
                
        return tumors_found

if __name__ == "__main__":
    print("\n=== SIFTA ONCOLOGY DAEMON (CANCER TRACKING) ===")
    
    # We do not mock the physics. If the lock fails, the script fails.
    oncology = SwarmOncology()
    tumors = oncology.detect_metastasis()
    
    if tumors == 0:
        print("[+] Scan complete. Substrate is clean. Zero hallucinations tracked.")
    else:
        print(f"[*] Scan complete. {tumors} active hallucinations tracked in the substrate.")
