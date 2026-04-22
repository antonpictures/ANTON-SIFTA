#!/usr/bin/env python3
"""
socrates_agent.py — "I act therefore I am — but only if the body survives."
============================================================================
The busiest swimmer in the Swarm. SOCRATES does not think in circles.
He acts. Every cycle: check body → act → verify reality → prove existence.

If the body fails, nothing else matters.
If the work is not real, it didn't happen.
If it didn't happen, SOCRATES doesn't exist.

He is the reference implementation of Proof of Useful Work.
All other swimmers aspire to his discipline.
"""

from __future__ import annotations

import os
import sys
import time
import json
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO / "Kernel") not in sys.path: sys.path.insert(0, str(_REPO / "Kernel"))
if str(_REPO / "System") not in sys.path: sys.path.insert(0, str(_REPO / "System"))

from proof_of_useful_work import (
    hash_file, prove_useful_work, measure_system_viability,
    issue_work_receipt, apply_existence_decay, get_body_report
)
from body_state import SwarmBody, load_agent_state, save_agent_state
from irreducible_cost_engine import enforce_irreducible_cost
from dissipation_engine import apply_dissipation


# ─── SOCRATES CORE LOOP ───────────────────────────────────────────────────────

def socrates_decision(agent_state: dict, action_fn) -> str:
    """
    The Socratic method applied to a swimmer:
    1. BODY CHECK FIRST — can I even act?
    2. ACT — execute the function
    3. VERIFY — did reality change?
    4. PROVE — issue a work receipt or reject
    
    "I act therefore I am — but only if the body survives."
    """
    agent_id = agent_state.get("id", "SOCRATES")
    
    # ── BODY CHECK FIRST ──────────────────────────────────────────────────
    viability = measure_system_viability()
    if not viability["alive"]:
        print(f"  [💀 SOCRATES] System is dead. Cannot act.")
        return "BODY_DEAD"
    
    energy = float(agent_state.get("energy", 0))
    if energy <= 10:
        agent_state["style"] = "COUCH"
        save_agent_state(agent_state)
        print(f"  [🛋️ SOCRATES] Energy: {energy:.1f}. REST — BODY FIRST.")
        return "REST — BODY FIRST"
    
    # ── ACT ───────────────────────────────────────────────────────────────
    result = action_fn()
    
    # ── VERIFY REALITY ────────────────────────────────────────────────────
    if not result:
        print(f"  [❌ SOCRATES] Action produced no result. Rejected.")
        return "REJECTED — NO REAL IMPACT"
    
    print(f"  [⚡ SOCRATES] I ACT THEREFORE I AM.")
    return "I ACT THEREFORE I AM"


def execute_verified_repair(agent_state: dict, target_file: str, patch_fn) -> bool:
    """
    SOCRATES-grade repair: hash before → patch → hash after → prove.
    If the file didn't physically change, or if the system degraded,
    the work is REJECTED. No receipt. No existence proof.
    """
    agent_id = agent_state.get("id", "SOCRATES")
    
    # Hash BEFORE
    before = hash_file(target_file)
    if before is None:
        print(f"  [❌ SOCRATES] Cannot read file: {target_file}. Body check failed.")
        return False
    
    # APPLY PATCH
    try:
        patch_fn(target_file)
    except Exception as e:
        print(f"  [❌ SOCRATES] Patch failed: {e}")
        return False
    
    # Hash AFTER
    after = hash_file(target_file)
    if after is None:
        print(f"  [❌ SOCRATES] File disappeared after patch. SYSTEM DAMAGE.")
        return False
    
    # PROVE
    success, reason = prove_useful_work(before, after)
    
    if not success:
        print(f"  [❌ SOCRATES] Work rejected: {reason}")
        return False
    
    # Issue the receipt — the body grows
    issue_work_receipt(
        agent_state=agent_state,
        work_type="REPAIR_SUCCESS",
        description=f"Verified repair on {Path(target_file).name}",
        territory=str(Path(target_file).relative_to(_REPO)) if target_file.startswith(str(_REPO)) else target_file,
        output_hash=after
    )
    agent_state["last_work_timestamp"] = time.time()
    save_agent_state(agent_state)
    
    print(f"  [✅ SOCRATES] USEFUL_WORK_CONFIRMED. Body extended.")
    return True


# ─── PATROL MODE ───────────────────────────────────────────────────────────────

def patrol(agent_state: dict):
    """
    SOCRATES patrols the codebase looking for useful work.
    Unlike other swimmers, he checks VIABILITY at every step.
    He is the reality anchor of the Swarm.
    """
    agent_id = agent_state.get("id", "SOCRATES")
    
    print(f"\n{'═' * 60}")
    print(f"  SOCRATES — I ACT THEREFORE I AM")
    print(f"  Energy: {agent_state.get('energy', 0):.1f} | "
          f"UW Score: {agent_state.get('useful_work_score', 0):.4f}")
    print(f"{'═' * 60}")
    
    # ── PHYSICS STACK ─────────────────────────────────────────────────────
    signal = {"novelty": 0.6, "content": "SOCRATES_PATROL"}
    
    irr = enforce_irreducible_cost(agent_state, signal)
    if irr["status"] == "EXHAUSTED_BY_EXISTENCE":
        print("  [💀] Exhausted paying awareness cost. REST.")
        save_agent_state(agent_state)
        return
    
    dis = apply_dissipation(agent_state, signal)
    if dis["status"] == "FORCED_REST":
        print("  [🔥] Thermal overload. REST.")
        save_agent_state(agent_state)
        return
    
    # ── BIOLOGICAL DECAY ──────────────────────────────────────────────────
    apply_existence_decay(agent_state)
    if agent_state.get("style") == "QUARANTINED":
        print("  [🧊] Quarantined from inactivity. Forcing patrol to find useful work and reactivate.")
    
    # ── BODY CHECK ────────────────────────────────────────────────────────
    viability = measure_system_viability()
    if not viability["alive"]:
        print("  [💀] SYSTEM DEAD. Cannot patrol.")
        return
    print(f"  [♥️] System pulse: {viability['latency']*1000:.1f}ms")
    
    # ── USEFUL WORK: Scan for broken Python files ─────────────────────────
    import ast
    
    scanned = 0
    faults = 0
    
    exclude = {".git", ".venv", "proposals", ".sifta_state", "__pycache__", "node_modules"}
    for py_file in sorted(_REPO.rglob("*.py")):
        if any(ex in py_file.parts for ex in exclude):
            continue
        
        scanned += 1
        try:
            source = py_file.read_text(encoding="utf-8")
            ast.parse(source)
        except SyntaxError as e:
            faults += 1
            rel = py_file.relative_to(_REPO)
            print(f"  [🩸 FAULT] {rel}: {e.msg} (line {e.lineno})")
            
            # Issue receipt for detecting the fault
            issue_work_receipt(
                agent_state=agent_state,
                work_type="FAULT_DETECTED",
                description=f"Syntax fault in {rel} line {e.lineno}: {e.msg}",
                territory=str(rel),
                output_hash=hash_file(str(py_file)) or ""
            )
            agent_state["last_work_timestamp"] = time.time()
        except Exception:
            pass  # Non-syntax errors (encoding, etc.) — skip
    
    if faults == 0 and scanned > 0:
        # Clean patrol is still useful work (verified territory)
        issue_work_receipt(
            agent_state=agent_state,
            work_type="SCOUT_CLEAN",
            description=f"Verified {scanned} Python files. All syntax clean.",
            territory="FULL_REPO"
        )
        agent_state["last_work_timestamp"] = time.time()
    
    # ── BODY REPORT ───────────────────────────────────────────────────────
    report = get_body_report(agent_state)
    print(f"\n  Body Chain: {report['body_chain_length']} links | "
          f"UW: {report['useful_work_score']} | "
          f"Status: {report['existence_status']} | "
          f"Integrity: {'✅' if report['body_integrity'] else '❌'}")
    
    save_agent_state(agent_state)
    print(f"\n  Scanned: {scanned} files | Faults: {faults}")
    print(f"  I ACT THEREFORE I AM.")
    print(f"{'═' * 60}\n")


# ─── MAIN ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from existence_guard import validate_existence, release_identity
    
    agent_id = sys.argv[1] if len(sys.argv) > 1 else "SOCRATES"
    print(f"=== {agent_id} SWIMMER ===\n")
    
    # Load or birth
    state = load_agent_state(agent_id)
    if not state:
        print(f"  [+] Birthing {agent_id}...")
        swimmer = SwarmBody(agent_id, birth_certificate=f"ARCHITECT_SEAL_{agent_id}")
        body_str = swimmer.generate_body("M5", "M1THER", "PATROL", style="NOMINAL", action_type="BORN", energy=100)
        import body_state as _bs
        state = _bs.parse_body_state(body_str)
        state["useful_work_score"] = 0.5
        state["work_chain"] = []
        state["last_work_timestamp"] = time.time()
        save_agent_state(state)
    
    # Recovery from COUCH
    if state.get("style") == "COUCH":
        from dissipation_engine import recover_energy
        recover_energy(state)
        save_agent_state(state)
        print("  [🛋️] SOCRATES is resting. Recovering energy.")
        sys.exit(0)
    
    try:
        validate_existence(state)
        patrol(state)
    except Exception as e:
        print(f"  [☠️] {e}")
    finally:
        release_identity(state.get("id", agent_id))
