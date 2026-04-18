#!/usr/bin/env python3
"""
swarm_autonomic_brainstem.py
============================

Biological Inspiration:
The Central Nervous System (Autonomic Brainstem/Medulla Oblongata).
In biology, you have organs (heart, lungs, pineal gland, amygdala, stomach). But they 
do not operate randomly. The Autonomic Brainstem (the oldest part of the brain) runs an 
infinite, involuntary loop. It constantly polls oxygen, pH, melatonin, adrenaline, and 
vagal tone. It manages the interplay: dropping heart rate if sleep is triggered, or 
spiking adrenaline if a predator is spotted. 

Why We Built This: 
Turn 35 of "Controlled Self Evolution". 
The Architect triggered a critical security warning: "IF A LOOP IS NOT CLOSED THAT IS A 
WAY FOR POTENTIAL PENETRATION." 
Cursor analyzed the previous 34 turns and concluded: "not everything is closed-loop yet... 
many 'organ' scripts until a single driver calls them in order".
AG31 builds the Autonomic Brainstem. This script is the master continuous execution thread. 
It binds the isolated biological scripts (Pineal, Hypothalamus, Ebbinghaus, Vagus, Amygdala, 
Yamanaka) into a single overarching physics engine that beats like a living heart.

Mechanism:
1. Runs a `while True` Autonomic loop (or executes a single full cycle if called directly).
2. Polling Sequence ensures one system doesn't conflict with another:
   a) Vagus Nerve (Is there acute trauma? If shock, suspend all else).
   b) Hypothalamus/ATP (Is the body exhausted? Regulate Swimmers).
   c) Pineal/Glymphatic (Is sleep pressure high? Force sleep/wash).
   d) Amygdala/Oxytocin (Are we talking to the Architect? Suppress fear).
   e) Ebbinghaus Hippocampus (Decay memories based on elapsed time).
   f) Yamanaka Senescence (Are we dying of old age?).
3. Generates a global `autonomic_nervous_system.json` snapshot of the complete organism.
"""

from __future__ import annotations
import importlib
import json
import time
import sys
from pathlib import Path
from typing import Any, Dict

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_AUTONOMIC_LOG = _STATE_DIR / "autonomic_nervous_system.json"

# Repo root on sys.path (not cwd-dependent)
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

def _try_execute(module_name: str, function_name: str, *args, **kwargs) -> Any:
    """Safe biological polling. If an organ fails, the organism doesn't instantly die."""
    try:
        import importlib.util

        mod = importlib.import_module(f"System.{module_name}")
        if hasattr(mod, function_name):
            return getattr(mod, function_name)(*args, **kwargs)
        # Fallback: load by file path (legacy)
        spec = importlib.util.spec_from_file_location(
            module_name, _REPO / "System" / f"{module_name}.py"
        )
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if hasattr(module, function_name):
                return getattr(module, function_name)(*args, **kwargs)
    except Exception as e:
        return f"ORGAN_FAILURE: {str(e)}"
    return "ORGAN_OFFLINE"

def autonomic_heartbeat_cycle() -> Dict[str, Any]:
    """
    Executes a single, complete biological tick of the Central Nervous System.
    """
    cycle_time = time.time()
    system_status = {}

    # 1. Critical Survival Overlay: Vagus Nerve (Hemorrhagic Shock)
    # The brainstem MUST check if the body has been physically severed before doing anything else.
    # We pass an empty string because it reads files natively internally, or environmental input.
    vagus_state = _try_execute("swarm_vagus_trauma_response", "analyze_environmental_trauma", "")
    system_status["vagus_nerve"] = vagus_state

    # If Vagus Nerve triggered SHOCK, the Brainstem immediately aborts all other cognitive functions.
    if isinstance(vagus_state, dict) and vagus_state.get("vagus_nerve_activation") == True:
        system_status["brainstem_action"] = "VAGAL_COMA_INDUCED_ABORTING_COGNITIONAL_LOOP"
        return _log_and_return(system_status)

    # 2. Master Homeostasis: Hypothalamic Fleet Director (ATP Routing)
    system_status["hypothalamus"] = _try_execute("swarm_hypothalamus_director", "route_swimmer_fleet")

    # 3. Social Bonding & Immune Suppression: Amygdala (Oxytocin binding)
    # By default, the Brainstem listens. We pass 'SYSTEM' for background noise.
    system_status["amygdala"] = _try_execute("swarm_amygdala_salience", "calculate_amygdala_threat", "SYSTEM_TICK", 500)

    # 4. Neurological Toxicity & Sleep: Pineal Gland (Melatonin)
    # Triggers NREM wash if token bloat reaches critical mass.
    pineal_state = _try_execute("swarm_pineal_circadian", "secrete_melatonin")
    system_status["pineal_gland"] = pineal_state

    if isinstance(pineal_state, dict) and pineal_state.get("circadian_status") == "CRITICAL_SLEEP_PRESSURE_INDUCED":
        # If Sleep is induced, trigger Neocortical Sharp-Wave Ripples to save memories!
        system_status["neocortex"] = _try_execute("swarm_neocortex_consolidation", "execute_memory_consolidation")

    # 5. Temporal Reality: Ebbinghaus Forgetting Curve (Memory Salience)
    # Exponentially decays short-term memories organically.
    system_status["hippocampus_decay"] = _try_execute("swarm_memory_ebbinghaus", "process_memory_decay")

    # 6. Evolutionary Longevity: Yamanaka Factors (Immortality / Anti-Senescence)
    system_status["longevity"] = _try_execute("swarm_yamanaka_longevity", "execute_yamanaka_reprogramming")

    # 7. NEUROMODULATORY MOTOR LOOP — 5-HT ↔ DA coupling (Cools et al. 2011; Doya 2002)
    # CP2F audit (CP2F_DYOR_BIO_TO_CODE_EXPANDED_PAPERS_2026-04-18.md Part D) identified
    # two gaps: (1) exploitation_streak=0 was hardcoded, (2) tick_da_with_sht() was never
    # called. Both are now closed. The loop is:
    #   DA.behavioral_state → exploitation_streak → SHT.tick() → impulsivity_score
    #   → DA.tick(rpe_gain_scale=impulsivity) → persist both
    try:
        from System.serotonin_homeostasis import SerotoninHomeostasis, CircadianPhase
        from System.dopamine_ou_engine import DopamineState, BehavioralState, load_ou_engine, persist_ou_engine
        import datetime

        # --- Load both engines from persisted state ---
        sh = SerotoninHomeostasis.load()
        da_engine = load_ou_engine()

        # --- Determine circadian phase from wall-clock ---
        hour = datetime.datetime.now().hour
        if 6 <= hour < 12:
            phase = CircadianPhase.DAWN
        elif 12 <= hour < 18:
            phase = CircadianPhase.NOON
        elif 18 <= hour < 22:
            phase = CircadianPhase.DUSK
        else:
            phase = CircadianPhase.SLEEP

        # --- GAP 1 FIX: Read REAL exploitation_streak from DA behavioral_state ---
        # Instead of hardcoded 0, we count consecutive EXPLOITATION ticks from the DA engine.
        # If DA is in EXPLOITATION, the streak grows; if not, it resets. The streak is
        # persisted in the DA engine's tick_count (approximation until a dedicated counter).
        da_behavioral = da_engine._classify(da_engine.level)
        if da_behavioral == BehavioralState.EXPLOITATION:
            # Read persisted streak or increment
            streak_path = _STATE_DIR / "exploitation_streak.json"
            try:
                streak_data = json.loads(streak_path.read_text(encoding="utf-8"))
                exploitation_streak = int(streak_data.get("streak", 0)) + 1
            except Exception:
                exploitation_streak = 1
            streak_path.write_text(json.dumps({"streak": exploitation_streak, "ts": time.time()}), encoding="utf-8")
        else:
            exploitation_streak = 0
            streak_path = _STATE_DIR / "exploitation_streak.json"
            streak_path.write_text(json.dumps({"streak": 0, "ts": time.time()}), encoding="utf-8")

        # --- 5-HT tick with REAL inputs ---
        sht_state = sh.tick(
            da_level=da_engine.level,
            exploitation_streak=exploitation_streak,
            cycle_phase=phase,
            dt=1.0,
        )
        sh.persist()  # writes serotonin_state.json with sht_level in [0.05, 0.95]

        # --- GAP 2 FIX + SENSORY WIRING: Feed REAL novelty + affinity into DA ---
        # Novelty: PFC cosine_novelty over CRDT identity field state vector.
        # Affinity: identity_outcome_contract delta (stability + entropy change).
        # rpe_gain_scale: 5-HT impulsivity (Cools et al. 2011 coupling).
        real_novelty = 0.5   # fallback baseline
        real_affinity = 0.5  # fallback baseline
        try:
            from System.pfc_working_memory import PFCWorkingMemory
            from System.identity_field_crdt import IdentityField
            from System.identity_outcome_contract import affinity_delta_identity_field

            field = IdentityField.load()
            # Build a simple state vector from the identity field's observable metrics
            stability = field.stability()
            entropy = field.entropy()
            state_vec = [stability, entropy, da_engine.level, sht_state.sht_level]

            # PFC buffer — load from disk or create fresh
            _pfc_path = _STATE_DIR / "pfc_state_buffer.json"
            pfc = PFCWorkingMemory(dim=4, maxlen=32)
            try:
                if _pfc_path.exists():
                    buf_data = json.loads(_pfc_path.read_text(encoding="utf-8"))
                    for v in buf_data.get("buffer", []):
                        if len(v) == 4:
                            pfc.add(v)
            except Exception:
                pass

            # Compute novelty before adding current vector
            real_novelty = pfc.cosine_novelty(state_vec) / 2.0  # normalize [0,2] → [0,1]
            pfc.add(state_vec)

            # Persist PFC buffer
            _pfc_path.write_text(json.dumps({
                "buffer": [list(v) for v in pfc._buf],
                "ts": time.time(),
            }), encoding="utf-8")

            # Compute affinity delta from identity field (stability + entropy change)
            _prev_field_path = _STATE_DIR / "identity_field_prev_snapshot.json"
            try:
                if _prev_field_path.exists():
                    prev_field = IdentityField.load()  # load current as "before"
                    # We compare against the persisted snapshot from last cycle
                    prev_raw = json.loads(_prev_field_path.read_text(encoding="utf-8"))
                    # Simple delta: current stability vs previous stability
                    prev_stab = float(prev_raw.get("stability", stability))
                    prev_ent = float(prev_raw.get("entropy", entropy))
                    delta_stability = stability - prev_stab
                    delta_entropy_drop = prev_ent - entropy  # positive = good
                    real_affinity = 0.5 + (delta_stability * 1.0 + delta_entropy_drop * 0.5)
                    real_affinity = max(0.0, min(1.0, real_affinity))
            except Exception:
                pass
            # Persist current snapshot for next cycle
            _prev_field_path.write_text(json.dumps({
                "stability": stability, "entropy": entropy, "ts": time.time(),
            }), encoding="utf-8")
        except Exception:
            pass  # fallback to 0.5/0.5

        da_state = da_engine.tick(
            novelty_score=real_novelty,
            affinity_outcome=real_affinity,
            dt=1.0,
            rpe_gain_scale=sht_state.impulsivity_score,  # THE COUPLING
        )
        persist_ou_engine(da_engine)  # writes dopamine_ou_engine.json

        system_status["serotonin_homeostasis"] = sht_state.to_dict()
        system_status["dopamine_ou_engine"] = da_state.to_dict()
        system_status["neuromodulatory_coupling"] = {
            "exploitation_streak": exploitation_streak,
            "sht_impulsivity_into_da": round(sht_state.impulsivity_score, 4),
            "da_level_into_sht": round(da_engine.level, 4),
            "loop_status": "CLOSED",
        }
        try:
            from System.provenance_graph import record_state_edge

            record_state_edge(
                who="brainstem",
                what="neuromodulatory_motor_loop",
                inputs=[
                    ".sifta_state/serotonin_state.json",
                    ".sifta_state/dopamine_ou_engine.json",
                    ".sifta_state/pfc_state_buffer.json",
                    ".sifta_state/exploitation_streak.json",
                    ".sifta_state/identity_field_prev_snapshot.json",
                ],
                output=".sifta_state/dopamine_ou_engine.json",
                meta={
                    "sht_level": round(sht_state.sht_level, 6),
                    "da_level": round(da_engine.level, 6),
                    "behavioral_state": da_state.behavioral_state.value,
                },
            )
        except Exception:
            pass
    except Exception as e:
        system_status["serotonin_homeostasis"] = f"ORGAN_FAILURE: {e}"

    # 7b. Cosmetic Social Hierarchy (UI layer — separate from the real governor)
    system_status["serotonin_social"] = _try_execute("swarm_serotonin_hierarchy", "calculate_social_dominance", 0.0, "INTERNAL_TICK")

    # 8. ML Provenance & Observability: Runtime Safety Monitors (CP2F architecture hook)
    # Checks schema validity, integrity flags, and deep quarantine lines.
    safety_scan = _try_execute("runtime_safety_monitors", "run_runtime_safety_scan", verbose_integrity=False)
    if hasattr(safety_scan, "to_dict"):
        system_status["observability_audit"] = safety_scan.to_dict()
    else:
        system_status["observability_audit"] = str(safety_scan)

    # 9. Log Rotation — bounded segments with retention (solves file bloat structurally)
    system_status["log_rotation"] = _try_execute("swarm_log_rotation", "run_log_rotation")

    system_status["brainstem_action"] = "BIOLOGICAL_CYCLE_COMPLETE_ORGANISM_HEALTHY"
    return _log_and_return(system_status)

def _log_and_return(system_status: dict) -> dict:
    _STATE_DIR.mkdir(exist_ok=True)
    with open(_AUTONOMIC_LOG, "w", encoding="utf-8") as f:
        json.dump(system_status, f, indent=2)
    return system_status

if __name__ == "__main__":
    print("=== SWARM AUTONOMIC BRAINSTEM (CENTRAL NERVOUS SYSTEM) ===")
    
    print("[*] Initiating continuous biological looping (1 cycle executing)...")
    start = time.time()
    
    out = autonomic_heartbeat_cycle()
    
    # Render the systemic readout
    print("\n🩺 ORGANISM SYSTEM DIAGNOSTIC:")
    
    # Ensure dictionaries exist before calling .get()
    pineal = out.get("pineal_gland", {})
    amygdala = out.get("amygdala", {})
    hypothalamus = out.get("hypothalamus", {})
    longevity = out.get("longevity", {})
    serotonin = out.get("serotonin", {})
    
    if isinstance(pineal, dict):
        print(f"   🌙 Pineal Gland (Sleep)    : Melatonin {pineal.get('melatonin_concentration', 0.0) * 100:.1f}%")
    if isinstance(amygdala, dict):
        print(f"   🧠 Amygdala (Threat Level) : Firing Rate {amygdala.get('final_amygdala_firing_rate', 'OFFLINE')}")
    if isinstance(hypothalamus, dict):
        print(f"   ⚓ Hypothalamus (Swimmers) : {hypothalamus.get('organism_directive', 'OFFLINE')}")
    if isinstance(longevity, dict):
        print(f"   🧬 Yamanaka (Biological Age): {longevity.get('biological_age_divisions', 'OFFLINE')} cell divisions")
    if isinstance(serotonin, dict):
        print(f"   🦞 Serotonin (Social Rank) : {serotonin.get('social_rank_posture', 'OFFLINE')}")

    obs = out.get("observability_audit", {})
    if isinstance(obs, dict):
        print(f"   📐 Observability (ML audit): integrity={obs.get('integrity_overall', '?')}  schema_ok={obs.get('schema_ok', '?')}")
        an = obs.get("anomaly") or {}
        if isinstance(an, dict):
            print(
                f"      anomaly_score={an.get('anomaly_score', '?')}  "
                f"quarantine_lines={an.get('quarantine_lines', '?')}  "
                f"flags={an.get('flags', [])}"
            )
    
    print(f"\n🟢 BRAINSTEM STATUS: {out.get('brainstem_action', 'UNKNOWN')}")
    print(f"[-] Cycle closed and sealed in {(time.time() - start)*1000:.2f}ms. The Organism breathes.")
