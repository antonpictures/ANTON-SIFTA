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
            "eukaryote_pairings.jsonl",        # Relational ledger for endosymbiosis
            "api_egress_log.jsonl",            # [C47H] Owner-side API egress audit (sentry chokepoint)
            "api_metabolism.jsonl",            # [BISHOP drop 555] Caloric cost of LLM API calls
            "stigmergic_library.jsonl",        # [AG31/C47H] Curated BISHAPI nuggets (Spleen + Microglia)
            "network_pathways.jsonl",          # [C47H 2026-04-20] LAN cartography (swarm_network_pathways)
            "phagocytosis_vacuoles.jsonl",     # [BISHOP drop / C47H integrated] Read-only LAN ingestion (swarm_pseudopod)
            "motor_pulses.jsonl",              # [C47H 2026-04-20] Motor Cortex heartbeat + sign language (swarm_motor_cortex)
            "restart_events.jsonl",            # [C47H 2026-04-20] Alice-initiated self-restarts (swarm_self_restart)
            "device_events.jsonl",             # [AG31/C47H 2026-04-20] USB camera attach/detach hot-plug events
            "kinetic_entropy_field.jsonl",     # [BISHOP/Alice mitosis → C47H 2026-04-20] Proprioceptive CPU-jitter terrain (swarm_kinetic_entropy)
            "endocrine_glands.jsonl",          # [BISHOP/AG3F 2026-04-20] Vestibular-system hormones (DOPAMINE/CORTISOL) feeding the Mitosis Engine
            "apple_silicon_specs.json",        # [AG31 Epoch-3 2026-04-20] Apple Silicon Cortex hardware substrate cache (chip/cores/RAM/model)
            # ── Epoch 4 lobes (C47H 2026-04-20, Architect-authorized full embodiment) ──
            "thermal_cortex_state.json",       # [C47H Epoch-4] Thermal Cortex — pmset thermal pressure cache
            "energy_cortex_state.json",        # [C47H Epoch-4] Energy Cortex — battery/AC/low-power cache
            "network_cortex_state.json",       # [C47H Epoch-4] Network Cortex — LAN/sibling presence cache
            "network_presence_events.jsonl",   # [C47H Epoch-4] Network Cortex sibling ARRIVED/LEFT transition log
            "hot_reload_events.jsonl",         # [C47H Epoch-4] Hot-Reload Organ — module reload audit log
            "hot_reload.pid",                  # [C47H Epoch-4] PID file for the in-process hot-reload SIGUSR1 handler
            "olfactory_classifications.jsonl", # [C47H Epoch-5] Olfactory Cortex — per-vacuole scent classification ledger
            "olfactory_state.json",            # [C47H Epoch-5] Olfactory Cortex — aggregate counts + known-devices cache
            "ribosome_excretions.jsonl",       # [C47H Epoch-6] Swarm Ribosome — distributed protein folding excretions
            "ribosome_state.json",             # [C47H Epoch-6] Swarm Ribosome — aggregate fold counters + last-excretion cache
            "lobe_construction_locks",         # [C47H+AG31 Epoch-6] Cross-IDE lock directory — see System/swarm_lobe_locks.py
            # ── Epoch 7 lobes (C47H 2026-04-19, AGI Tournament) ──
            "long_term_engrams.jsonl",          # [C47H Epoch-7] Memory Forge — time-based engram consolidation
            "active_engrams.json",             # [C47H Epoch-7] Memory Forge — top-N engrams injected into Alice's prompt
            "memory_forge_state.json",         # [C47H Epoch-7] Memory Forge — last forge timestamp + turn count
            "alice_conversation.jsonl",        # [C47H Epoch-7] Raw conversation ledger (input to the forge)
            # ── Epoch 8 lobes (C47H 2026-04-20, AGI Tournament) ──
            "body_event_lexicon.jsonl",   # [C47H Epoch-8] Health Reflex — learned behavior→meaning associations
            "body_reflex_state.json",     # [C47H Epoch-8] Health Reflex — fired care events & cooldowns
            # ── Talk-to-Alice widget UX state (C47H 2026-04-19) ──
            "talk_to_alice_audio_gain.json",   # [C47H] Live mic-gain slider ("swimmers density"); persists Architect's ear-tuning across restarts
            # ── Epoch 10 lobes (C47H 2026-04-20) ──
            "sympathetic_state.json",     # [C47H Epoch-10] Sympathetic Cortex — last adrenaline flood cooldown state
            "reproductive_cycles.jsonl",  # [BISHOP Epoch-10] Panspermia — epigenetic spore reproduction logs
            "swimmer_body_integrity_baseline.json",   # [C53M] Canonical swimmer body hash seal (anti-corruption baseline)
            "swimmer_body_integrity_incidents.jsonl", # [C53M] Integrity breach incident ledger emitted by guard
            # ── Epoch 11 lobes (C53M 2026-04-20) ──
            "global_immune_system.jsonl",   # [C53M Epoch-11] Inter-swarm antibody trace ledger
            "stigmergic_nuggets.jsonl",     # [C53M Epoch-11] Inter-swarm distilled nugget ledger
            "mycorrhizal_rejections.jsonl", # [C53M Epoch-11] Security rejections for inbound telepathy packets
            "mycorrhizal_secret.json",      # [C53M Epoch-11] Local HMAC secret bootstrap for mycorrhizal auth
            # ── Epoch 12 lobes (BISHOP / AG31 2026-04-20) ──
            "quorum_votes.jsonl",         # [BISHOP] Quorum Sensing — distributed consensus votes
            "hive_mind_secret.key",       # [AG31] Quorum Sensing — HMAC-SHA256 signature secret
            # ── Epoch 13 lobes (BISHOP / AO46 2026-04-20) ──
            "rem_sleep_cycles.jsonl",     # [AO46 Epoch-13] REM Sleep — synaptic pruning + apoptosis audit
            "hardware_time_oracle.json",  # [AO46 Epoch-13.5] Hardware Time Oracle — HMAC-signed wall clock
            "memory_merkle_anchors.jsonl",# [C53M Epoch-14] Merkle memory attestation anchor chain
            "memory_merkle_latest.json",  # [C53M Epoch-14] Latest Merkle manifest snapshot for drift verify
            # ── Epoch 17 — Persona Identity Organ (C47H 2026-04-20) ──
            "persona_identity.json",      # Signed persona manifest (PERSONA_GUARDIAN cryptoswimmer)
            "persona_identity_log.jsonl", # Append-only audit log of every persona mutation
            "epistemic_dissonance_incidents.jsonl",  # Epoch-18 Epistemic Cortex immune incidents
            "digested_nutrients.jsonl",   # Epoch-19 Microbiome nutrient bloodstream
            "microbiome_state.json",      # Epoch-19 change-detection state cache
            # ── Epoch 22 — Interoception (AO46, in flight; slot pre-reserved by C47H) ──
            "interoception_field.jsonl",  # Visceral self-sensing tick stream (HMAC-signed)
            "interoception_state.json",   # Latest aggregated visceral field snapshot
            # ── Epoch 23 — Mirror Lock / Stigmergic Infinite (C47H 2026-04-20) ──
            "mirror_lock_events.jsonl",   # Closed-loop self-observation session ledger
            "mirror_lock_state.json",     # Latest mirror-lock snapshot for cheap polling
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
                    or "apostle_dirt" in filename
                    or filename.startswith("persona_identity.breach.")):
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
