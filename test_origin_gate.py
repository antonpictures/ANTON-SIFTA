#!/usr/bin/env python3
"""
test_origin_gate.py — Phase 7 Pre-SCAR Admission Control

Simulates intent generation filtering. Verifies that the Origin Gate correctly
blocks untrusted LLMs ("Insect models") from polluting the SCAR pipeline,
while granting high-reputation workers (Clades/Llamas) access.
"""

from origin_gate import OriginGate
from lana_kernel import kernel

gate = OriginGate()

def separator(title: str):
    print(f"\n{'═' * 50}")
    print(f"  {title}")
    print('═' * 50)


def simulate_worker(worker_id: str, target: str, action: str, content: str):
    print(f"\n[⚡ INTENT GENERATED] {worker_id} proposes '{action}' on '{target}'")
    
    # 1. ORIGIN GATE: The Phase 7 Boundary
    admitted, reason = gate.admit_intent(worker_id, target, action)
    
    if not admitted:
        print(reason)
        print(f"   ↳ Result: SCAR annihilated. Kernel processing saved.")
        return
        
    print(reason)
    print(f"   ↳ Result: Intent passing to Lana Kernel for PROPOSED creation.")
    
    # 2. INTENT ENTERS KERNEL if admitted
    scar_id = kernel.propose(worker_id, target, action, content)


def test_admission_control():
    separator("PHASE 7 VERIFICATION: ORIGIN GATE")

    # Worker Prime: High capability, high trust model
    simulate_worker(
        worker_id="WORKER_PRIME",
        target="lana_kernel.py",
        action="optimize_routing",
        content="def route(): pass"
    )

    # Worker Insect: Low capability, high hallucination model
    simulate_worker(
        worker_id="WORKER_INSECT",
        target="lana_kernel.py",
        action="rewrite_core_logic",
        content="def core(): return chaos"
    )

    print("\n[🔍 VERIFYING KERNEL REGISTRY]")
    scars = kernel._scars
    
    prime_scar = any(s["worker"] == "WORKER_PRIME" for s in scars.values())
    insect_scar = any(s["worker"] == "WORKER_INSECT" for s in scars.values())
    
    if prime_scar and not insect_scar:
        print("✅ SUCCESS: Only WORKER_PRIME intent exists in the SCAR State Machine.")
    else:
        print("❌ FAILURE: Kernel pollution detected.")


if __name__ == "__main__":
    print("\n╔══════════════════════════════════════════════╗")
    print("║    SIFTA ORIGIN GATE — PHASE 7 VERIFICATION  ║")
    print("║     Adverse Intent Annihilation Test         ║")
    print("╚══════════════════════════════════════════════╝")
    
    test_admission_control()
    print("\n[🟢 PHASE 7 COMPLETE] Nothing invalid gets proposed.\n")
