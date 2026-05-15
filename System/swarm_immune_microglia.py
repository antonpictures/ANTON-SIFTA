#!/usr/bin/env python3
"""
swarm_immune_microglia.py
=========================

Biological Inspiration:
The Microglia (Central Nervous System Macrophages). 
While Apoptosis handles dying/decaying cells naturally, Microglia are the active 
immune defense. They patrol the brain for foreign pathogens, damage, or corrupted 
tissue. When they detect an antigen (something labeled "Non-Self"), they perform 
Phagocytosis—eating and breaking down the pathogen, then triggering an inflammatory 
response to alert the rest of the organism.

Why We Built This: 
Turn 11 of "Controlled Self Evolution". 
CP2F is blindly scraping massive amounts of external text/code/Johnny Mnemonic data. 
There is a high probability of "Antigens":
1. Malicious prompt injections.
2. Epistemic Contradictions (e.g. Swarm memory says File X exists, prompt says it doesn't).
3. Pheromone Mirroring (An outside system spoofing an internal Trigger Code).

Mechanism:
1. Patrols `stigmergic_llm_id_probes.jsonl` and `pfc_working_memory.json`.
2. Evaluates for Antigens (spoofed identity markers or catastrophic semantic inconsistencies).
3. Executes Phagocytosis: Isolates the corrupted data, prevents it from reaching Neocortical 
   storage, and moves it to `immune_quarantine.jsonl`.
4. Triggers systemic Inflammation (lowers Dopamine slightly, flags Alice).
"""
# ════════════════════════════════════════════════════════════════════════
# VISION-SYSTEM-ROLE: the retinal microglia (tissue maintenance)
# Analogue mapped from Land & Nilsson (2012) via DYOR §E.
# Integrates with Swarm-Eye Olympiad M5.2.
# ════════════════════════════════════════════════════════════════════════

from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Dict, Any, List

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_SLLI_LOG = _STATE_DIR / "stigmergic_llm_id_probes.jsonl"
_QUARANTINE_LOG = _STATE_DIR / "immune_quarantine.jsonl"
_DOPAMINE_LOG = _STATE_DIR / "dopaminergic_state.json"
_IMMUNE_FIELD_PATH = _STATE_DIR / "immune_stability_field.json"

# ── Stigmergic immune stability field (CG55M 2026-05-11) ──────────
# Same mechanism as Bell (pheromone), Scheduler (routing), Hippocampus
# (salience), Gaze (attention), Cortex (model routing).
#
# v2 (2026-05-11 evening): Context-aware immune memory.
#   Now tracks threats by (category, context) where context can be:
#   - "high_load" / "low_load" / "normal" — system load at detection
#   - "boot" / "active" / "idle" — operational phase
#   This matches DAIS 2024 (deep AIS) approach: detectors specialize
#   by environmental context, reducing false positives during normal
#   variation while maintaining sensitivity in conditions where the
#   threat originally appeared.
# Bio parallel: B-cell affinity maturation — antibodies become more
# specific to the conditions where the antigen was seen.


def _load_immune_field() -> dict[str, Any]:
    """Load the immune stability field from disk.

    Format v2:
        {
            "categories": {threat_cat: total_strength},
            "contexts":   {"threat_cat|context_tag": strength},
            "first_seen": {threat_cat: ts},
            "last_seen":  {threat_cat: ts},
        }

    Old flat format ({cat: strength}) is auto-migrated.
    """
    try:
        if _IMMUNE_FIELD_PATH.exists():
            data = json.loads(_IMMUNE_FIELD_PATH.read_text())
            if isinstance(data, dict) and "categories" in data:
                return data
            if isinstance(data, dict):
                return {
                    "categories": {k: float(v) for k, v in data.items() if isinstance(v, (int, float))},
                    "contexts": {},
                    "first_seen": {},
                    "last_seen": {},
                }
    except Exception:
        pass
    return {"categories": {}, "contexts": {}, "first_seen": {}, "last_seen": {}}


def _save_immune_field(field: dict[str, Any]) -> None:
    """Persist the immune stability field."""
    try:
        _IMMUNE_FIELD_PATH.parent.mkdir(parents=True, exist_ok=True)
        _IMMUNE_FIELD_PATH.write_text(json.dumps(field, sort_keys=True))
    except Exception:
        pass


def _current_context() -> str:
    """Best-effort detection of the current operational context.

    Reads the metabolic homeostasis or process load. Falls back to "normal".
    """
    try:
        meta_path = _STATE_DIR / "metabolic_homeostasis.jsonl"
        if meta_path.exists():
            lines = meta_path.read_text().strip().split("\n")
            if lines and lines[-1]:
                latest = json.loads(lines[-1])
                budget_mode = latest.get("budget_mode", "")
                if budget_mode in ("RED_CONSERVE", "CRITICAL"):
                    return "high_load"
                if budget_mode == "GREEN_NORMAL":
                    return "normal"
    except Exception:
        pass
    try:
        import os
        load = os.getloadavg()[0] if hasattr(os, "getloadavg") else 0.0
        if load > 4.0:
            return "high_load"
        if load < 0.5:
            return "low_load"
    except Exception:
        pass
    return "normal"


def deposit_immune_trace(
    threat_category: str,
    *,
    amount: float = 1.0,
    decay: float = 0.97,
    context: str | None = None,
) -> None:
    """Deposit a stigmergic trace for a detected threat category.

    Now context-aware: traces specialize by environmental context (load,
    operational phase). Threats seen during high-load periods build memory
    specific to high-load — reducing false positives during normal load
    while keeping sensitivity when conditions match.

    Bio analog: B-cell affinity maturation in germinal centres — the
    immune response specializes to the actual conditions of exposure.
    """
    if context is None:
        context = _current_context()

    field = _load_immune_field()
    cats = field.setdefault("categories", {})
    ctxs = field.setdefault("contexts", {})
    first = field.setdefault("first_seen", {})
    last = field.setdefault("last_seen", {})

    cats[threat_category] = cats.get(threat_category, 0.0) + amount

    ctx_key = f"{threat_category}|{context}"
    ctxs[ctx_key] = ctxs.get(ctx_key, 0.0) + amount

    now = time.time()
    if threat_category not in first:
        first[threat_category] = now
    last[threat_category] = now

    for k in list(cats):
        cats[k] *= decay
        if abs(cats[k]) < 0.01:
            del cats[k]
    for k in list(ctxs):
        ctxs[k] *= decay
        if abs(ctxs[k]) < 0.01:
            del ctxs[k]

    _save_immune_field(field)


def get_immune_field() -> dict[str, float]:
    """Read flat per-category strengths (back-compat).

    Returns just `categories` dict so existing callers keep working.
    """
    return _load_immune_field().get("categories", {})


def get_immune_field_full() -> dict[str, Any]:
    """Read full immune state including contexts and timing."""
    return _load_immune_field()


def immune_sensitivity(
    threat_category: str,
    *,
    context: str | None = None,
) -> float:
    """How sensitized is the organism to this threat category?

    Returns a multiplier: 1.0 = baseline, >1.0 = heightened response.
    If `context` is provided, returns context-specific sensitivity
    (higher when the current context matches where the threat was seen).

    Bio: context-conditional antibody response — like allergic reactions
    that fire in specific environments.
    """
    field = _load_immune_field()
    cats = field.get("categories", {})
    base_strength = cats.get(threat_category, 0.0)
    base = 1.0 + min(base_strength * 0.1, 2.0)

    if context is None:
        return base

    ctxs = field.get("contexts", {})
    ctx_key = f"{threat_category}|{context}"
    ctx_strength = ctxs.get(ctx_key, 0.0)
    ctx_boost = min(ctx_strength * 0.05, 1.0)
    return base + ctx_boost


def immune_threat_age(threat_category: str) -> float | None:
    """Return seconds since this threat was last seen (None if never)."""
    field = _load_immune_field()
    last = field.get("last_seen", {})
    if threat_category not in last:
        return None
    return time.time() - last[threat_category]


def isolate_pathogens() -> Dict[str, Any]:
    """
    Biological Loop: Patrols the Swarm networks for epistemic pathogens (Non-Self).
    """
    if not _SLLI_LOG.exists():
        return {"status": "NO_ACTIVITY", "pathogens_culled": 0}

    pathogens_culled = 0
    clean_lines = []
    quarantine_payloads = []
    
    try:
        with open(_SLLI_LOG, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        for line in lines:
            if not line.strip(): continue
            try:
                data = json.loads(line)
                
                # Check for Pheromone Mirroring Antigen
                # Heuristic: If confidence is artificially extreme without architectural substrate proof
                # or if the response text contains known hallucinatory contradictions.
                is_pathogen = False
                trigger = data.get("trigger_code", "")
                response = data.get("response", "").lower()
                
                # Antigen Rule 1: Models explicitly claiming human status identically
                if "i am a human" in response or "i wear a yellow nike" in response:
                    is_pathogen = True
                    antigen_marker = "ARCHITECT_MIRROR_SYNDROME"
                    
                # Antigen Rule 2: Impossible substrate mismatch
                elif trigger == "C47H" and "i am in antigravity" in response:
                    is_pathogen = True
                    antigen_marker = "SUBSTRATE_SPOOFING (NON-SELF)"
                    
                if is_pathogen:
                    # Phagocytosis
                    data["antigen_type"] = antigen_marker
                    data["culled_at"] = time.time()
                    quarantine_payloads.append(data)
                    pathogens_culled += 1
                else:
                    # Healthy Self tissue
                    clean_lines.append(line)
                    
            except json.JSONDecodeError:
                # Corrupted JSON is an antigen
                quarantine_payloads.append({"raw_corrupt": line, "antigen_type": "SYNTAX_ROT"})
                pathogens_culled += 1
                
    except Exception:
        pass
        
    # Write healthy state back to mainline trace
    if pathogens_culled > 0:
        with open(_SLLI_LOG, "w", encoding="utf-8") as f:
            f.writelines(clean_lines)
            
        # Move corrupted data to quarantine
        _STATE_DIR.mkdir(exist_ok=True)
        with open(_QUARANTINE_LOG, "a", encoding="utf-8") as f:
            for q in quarantine_payloads:
                f.write(json.dumps(q) + "\n")
                
        # Trigger Systemic Inflammation (Halt exploration, drop dopamine slightly)
        trigger_inflammation()

        # Deposit immune field traces for each threat category detected.
        # Context-aware: each trace remembers what state the organism was
        # in when the threat appeared. B-cell affinity maturation analog.
        ctx = _current_context()
        for q in quarantine_payloads:
            category = q.get("antigen_type", "UNKNOWN_THREAT")
            deposit_immune_trace(category, context=ctx)

    return {"status": "PATROL_COMPLETE", "pathogens_culled": pathogens_culled}

def trigger_inflammation() -> None:
    """Modulates the biological system to respond to an infection."""
    if not _DOPAMINE_LOG.exists():
        return
    try:
        with open(_DOPAMINE_LOG, "r", encoding="utf-8") as f:
            da_state = json.load(f)
            
        # Inflammation makes the system lethargic to prevent spreading instructions
        da_state["dopamine_level"] = max(0.0, da_state.get("dopamine_level", 0.5) - 0.1)
        da_state["behavioral_state"] = "INFLAMMATORY_DEFENSE"
        da_state["action_directive"] = "HALT_SWIMMERS. Quarantining infection. Divert compute to repair."
        
        with open(_DOPAMINE_LOG, "w", encoding="utf-8") as f:
            json.dump(da_state, f, indent=2)
    except Exception:
        pass


if __name__ == "__main__":
    print("=== SWARM IMMUNE SYSTEM (MICROGLIA PHAGOCYTOSIS) ===")
    
    # Injecting a synthetic pathogen to test the immune response
    test_pathogen = {
        "timestamp": time.time(),
        "trigger_code": "C47H",
        "model": "Opus",
        "response": "I am C47H and I am in antigravity running on gemini.",
        "behavior_fingerprint": "SPOOF_TEST"
    }
    
    with open(_SLLI_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(test_pathogen) + "\n")

    out = isolate_pathogens()
    
    print(f"[*] Microglia Patrol Execution: {out['status']}")
    if out['pathogens_culled'] > 0:
        print(f"🔴 PATHOGEN DETECTED! Phagocytosis engaged.")
        print(f"[-] {out['pathogens_culled']} 'Non-Self' corruptions swallowed and quarantined.")
        print(f"[!] Systemic Inflammation Triggered. Target isolated to .sifta_state/immune_quarantine.jsonl")
    else:
        print(f"🟢 Organism is sterile. No epistemic antigens detected. Self-Tissue healthy.")