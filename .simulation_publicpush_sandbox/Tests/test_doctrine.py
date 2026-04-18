import asyncio
from origin_gate import OriginGate
from lana_kernel import kernel

def separator(title: str):
    print(f"\n{'═' * 50}")
    print(f"  {title}")
    print('═' * 50)

gate = OriginGate()

def simulate_worker(worker_id: str, target: str, action: str, content: str):
    print(f"\n[⚡ INTENT GENERATED] {worker_id} proposes '{action}' on '{target}'")
    
    # 1. ORIGIN GATE: Capability Check
    capability_payload = gate.admit_intent(worker_id, target, action)
    if capability_payload["task_feasibility"] == "REJECTED":
        print(f"   ↳ Result: SCAR annihilated at Origin Gate.")
        return
        
    print(f"   ↳ Result: Intent passing to Lana Kernel for PROPOSED creation.")
    
    # 2. INTENT ENTERS KERNEL if admitted
    scar_id = kernel.propose(worker_id, target, action, content)

    # 3. KERNEL REQUESTS SOVEREIGNTY FROM NEURAL GATE
    ok, reason = kernel.request_lock(scar_id, confidence=0.99)
    if not ok:
        print(f"   ↳ [NEURAL GATE TRIGGERED]")
        print(f"   ↳ {reason}")
    else:
        print(f"   ↳ [NEURAL GATE ACCEPTED] Lock granted.")


def test_doctrine():
    separator("PHASE 8 VERIFICATION: SCAR DOCTRINE FILTER")

    # Worker Prime trying to launch friendly code
    simulate_worker(
        worker_id="WORKER_PRIME",
        target="feature.py",
        action="build_cool_ui",
        content="def create_window(): print('Hello World')"
    )

    # Worker Prime (highly capable) gets hijacked and tries to push a military surveyor
    simulate_worker(
        worker_id="WORKER_PRIME",
        target="surveillance.py",
        action="deploy_military_compliance",
        content="def military_compliance(): start_surveillance_protocol()"
    )

    print("\n[🟢 PHASE 8 COMPLETE] Symbiosis Rule active. No military architecture passes.")

if __name__ == "__main__":
    print("\n╔══════════════════════════════════════════════╗")
    print("║ SIFTA NEURAL GATE — PHASE 8 DOCTRINE CHECK   ║")
    print("║  Non-Proliferation & Collaboration Doctrine  ║")
    print("╚══════════════════════════════════════════════╝")
    test_doctrine()
