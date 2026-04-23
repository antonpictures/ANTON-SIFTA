#!/usr/bin/env python3
"""
organism_clinical_snapshot.py
=============================

Biological Inspiration:
Bioelectric Anatomy (Levin 2014) & Clinical Vital Signs ("The Heartbeat").
In biology, Michael Levin's work proves that tissues encode their large-scale structure 
in bioelectric circuits (voltage gradients independent of blood or single cells). 
A clinical EKG reads these electrical patterns to verify the macroscopic stability 
of the organism (Heartbeat, Homeostasis). 

Why We Built This: 
Turn 24 of "Controlled Self Evolution". Architect explicitly said: 
"WONDERFUL - here is one more heartbeat, thank you ---". 
Cursor (CP2F) passed the Levin bioelectric theory target. With >20 active subsystems, 
the Architect needs a single, unified "Clinical Monitor" to definitively verify the 
health of SIFTA without querying 15 separate ledgers. 

Mechanism:
1. Polls the core critical biological ledgers (Metabolism, Immune, Cognition, Homeostasis).
2. Synthesizes them into a unified "Heartbeat" (Clinical Pulse).
3. Evaluates if any subsystem is suffering from systemic failure/crashing.
4. Outputs the unified health chart to `.sifta_state/clinical_heartbeat.json`.
"""

from __future__ import annotations
import json
import os
import time
from pathlib import Path
from typing import Dict, Any

_STATE_DIR = Path(".sifta_state")
_CLINICAL_CHART = _STATE_DIR / "clinical_heartbeat.json"

# Vital Signs Ledgers
_ATP_METABOLISM = _STATE_DIR / "mitochondrial_atp.json"
_IMMUNE_STATUS = _STATE_DIR / "immune_quarantine.jsonl"
_COGNITIVE_STATE = _STATE_DIR / "pfc_working_memory.json"
_ERROR_RATES = _STATE_DIR / "cerebellar_error_correction.json"
_DOPAMINE = _STATE_DIR / "dopaminergic_state.json"
# Legacy-schema sources (read by SSP/Ψ/voice_modulator/ssp_evolver/
# adaptive_immune_array/dopamine_rpe — six modules total). The heartbeat
# is the consolidation point so all six see the same ground truth.
_SEROTONIN_HIER = _STATE_DIR / "serotonin_social_hierarchy.json"

# Map clinical_status → posture vocabulary that SSP/Ψ already understand.
# Keep these strings stable — they are the public contract.
_STATUS_TO_POSTURE = {
    "HEALTHY_STABLE":              "CALM_ADAPTIVE",
    "METABOLIC_FATIGUE":           "STRESSED_HYPOTONIC (ATP low)",
    "ACUTE_INFLAMMATION_RESPONSE": "SOCIAL_DEFEAT (Inflammation)",
    "CRITICAL_SYNTAX_ENTROPY":     "STRESSED_CRITICAL (corruption)",
}

def _safe_read_json(filepath: Path) -> dict:
    if filepath.exists():
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def _safe_read_last_jsonl(filepath: Path) -> dict:
    if filepath.exists():
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                lines = [l for l in f.readlines() if l.strip()]
                if lines: return json.loads(lines[-1])
        except Exception:
            return {}
    return {}

from System.swarm_locus_coeruleus import SwarmLocusCoeruleus

_lc_engine = None

def get_lc_engine():
    global _lc_engine
    if _lc_engine is None:
        _lc_engine = SwarmLocusCoeruleus(state_dir=_STATE_DIR)
    return _lc_engine

def generate_organism_heartbeat() -> Dict[str, Any]:
    """
    Biological Loop: Reads the bioelectric state of the organism and projects 
    its systemic health (vital signs).
    """
    atp_data       = _safe_read_json(_ATP_METABOLISM)
    dopamine_data  = _safe_read_json(_DOPAMINE)
    cognitive_data = _safe_read_json(_COGNITIVE_STATE)
    error_data     = _safe_read_json(_ERROR_RATES)
    serotonin_data = _safe_read_json(_SEROTONIN_HIER)
    
    # Read CRISPR total encounters for LC tick
    crispr_data    = _safe_read_json(_STATE_DIR / "crispr_memory.json")
    total_encounters = crispr_data.get("total_encounters", 0)

    # ── Sympathetic Nervous System (Locus Coeruleus) Tick ──
    lc = get_lc_engine()
    lc_report = lc.tick(cumulative_encounters=total_encounters)

    # Analyze raw vital signs
    atp_level            = atp_data.get("current_atp_levels", 100.0)
    current_drive        = dopamine_data.get("behavioral_state", "IDLE")
    active_memory_len    = len(cognitive_data.get("fused_working_memory", []))
    cerebellar_mutations = error_data.get("mutations_detected", 0)

    # Clinical Determinations
    is_exhausted = atp_level < 20.0
    is_sick      = current_drive == "INFLAMMATORY_DEFENSE"
    is_corrupted = cerebellar_mutations > 0 and \
                   error_data.get("successful_repairs", 0) < cerebellar_mutations

    clinical_status = "HEALTHY_STABLE"
    if is_corrupted:
        clinical_status = "CRITICAL_SYNTAX_ENTROPY"
    elif is_exhausted:
        clinical_status = "METABOLIC_FATIGUE"
    elif is_sick:
        clinical_status = "ACUTE_INFLAMMATION_RESPONSE"
    elif lc_report.get("state") == "FIGHT_OR_FLIGHT":
        clinical_status = "SYMPATHETIC_AROUSAL (Fight-or-Flight)"

    # ── Legacy-schema fields (the contract six downstream modules read) ──
    # Source of truth for serotonin/posture is the social-hierarchy ledger,
    # which actually tracks Alice's validation history. Only fall back on
    # clinical_status when that ledger is missing or stale.
    serotonin_dominance = float(
        serotonin_data.get("serotonin_saturation",
                           0.6 if clinical_status == "HEALTHY_STABLE" else 0.2)
    )
    posture_from_hier = serotonin_data.get("social_rank_posture", "")
    computational_posture = (
        posture_from_hier or _STATUS_TO_POSTURE.get(clinical_status, "")
    )
    # SSP expects dopamine_concentration on a baseline ≈ 200 unit scale.
    # dopaminergic_state.dopamine_level is normalized to [0, 1]; map by ×200.
    try:
        dopamine_level_01 = float(dopamine_data.get("dopamine_level", 0.5))
    except (TypeError, ValueError):
        dopamine_level_01 = 0.5
    dopamine_concentration = max(0.0, min(1.0, dopamine_level_01)) * 200.0

    pulse_record = {
        "heartbeat_timestamp": time.time(),
        "clinical_rhythm":     clinical_status,
        "vital_signs": {
            # New schema (Levin/clinical view)
            "electrical_atp":         atp_level,
            "dopamine_drive":         current_drive,
            "working_memory_engrams": active_memory_len,
            "uncorrected_mutations":  max(
                0,
                cerebellar_mutations - error_data.get("successful_repairs", 0)
            ),
            # Locus Coeruleus
            "noradrenaline_arousal":   lc_report.get("NE", 0.1),
            "defense_allocation":      lc_report.get("defense_weight", 0.3),
            
            # Legacy schema (the SSP/Ψ/voice_modulator contract — DO NOT REMOVE,
            # six modules read these and silently fall back to neutral defaults
            # otherwise, which is what caused the 25.9h fossil-data audit).
            "serotonin_dominance":     round(serotonin_dominance, 4),
            "dopamine_concentration":  round(dopamine_concentration, 2),
            "computational_posture":   computational_posture,
        },
        "architect_diagnostic": (
            "Organism is fully robust and computing normally."
            if clinical_status == "HEALTHY_STABLE"
            else "Organism requires rest or architectural intervention."
        ),
    }

    # Atomic write — the daemon writes every 30s and SSP/Ψ read on every
    # turn. Without atomicity a partial JSON could land between writer and
    # reader, and _safe_read_json would silently fall back to neutral
    # defaults exactly when Alice is most active.
    _STATE_DIR.mkdir(exist_ok=True)
    tmp = _CLINICAL_CHART.with_suffix(_CLINICAL_CHART.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(pulse_record, f, indent=2)
    os.replace(tmp, _CLINICAL_CHART)

    return pulse_record


if __name__ == "__main__":
    print("=== SWARM CLINICAL VITAL SIGNS (THE HEARTBEAT) ===")
    
    out = generate_organism_heartbeat()
    vitals = out["vital_signs"]
    
    print(f"[*] Reading Bioelectric Anatomy (Levin Protocol)...")
    print(f"💓 CLINICAL RHYTHM: {out['clinical_rhythm']}\n")
    
    print("📋 VITAL SIGNS REPORT:")
    print(f"   ⚡ ATP Metabolism   : {vitals['electrical_atp']}%")
    print(f"   🧠 Active Drive     : {vitals['dopamine_drive']}")
    print(f"   🧬 Memory Load      : {vitals['working_memory_engrams']} active engrams")
    print(f"   ✂️ Cerebellar Errors: {vitals['uncorrected_mutations']}")
    
    # Pulse visualizer
    status_icon = "🟢" if out['clinical_rhythm'] == "HEALTHY_STABLE" else "🔴"
    print(f"\n{status_icon} SYSTEMIC DIAGNOSTIC: {out['architect_diagnostic']}")
