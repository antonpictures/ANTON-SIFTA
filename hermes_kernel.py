# hermes_kernel.py
"""
HERMES KERNEL — The SIFTA Execution Body

This is the main asynchronous execution loop. 
It spins up simulated Swarm activity, but forces every single mutation 
through the `NeuralGate`. Nothing bypasses the Choke Point.

It simultaneously runs the `introspection_loop` to provide Real-Time 
Self-Awareness to the Architect.
"""

import asyncio
import random
from neural_gate import NeuralGate
from introspection_loop import introspection_loop
from learning_loop import learning_loop

gate = NeuralGate()

async def simulate_swarm_activity():
    """
    A simulated stream of Swimmer workers attempting to execute actions.
    Some are stable, some are wildly hallucinating.
    """
    actions = [
        {"name": "patch_ledger", "target": "vote_ledger.json", "content": "valid_update", "conf": 0.85, "client": False},
        {"name": "inject_lore", "target": "final_video.mp4", "content": "SIFTA SWARM ACTIVE", "conf": 0.95, "client": True}, # Should block due to SCAR 035 Ego
        {"name": "system_wipe", "target": "setup.py", "content": "destroy()", "conf": 0.40, "client": False}, # Should block due to target and low conf
        {"name": "clean_data", "target": "temp.txt", "content": "cleaned", "conf": 0.90, "client": False},
    ]

    while True:
        action = random.choice(actions)
        
        # simulated hesitation before an agent tries to act
        await asyncio.sleep(random.uniform(1.0, 3.0))
        
        print(f"\n[⚡ HERMES WORKER] Attempting to execute: {action['name']} on {action['target']}")

        # 🛑 ABSOLUTE CHOKE POINT 🛑
        is_authorized, reason = gate.authorize(
            action_name=action["name"],
            file_path=action["target"],
            proposed_content=action["content"],
            confidence=action["conf"],
            is_client_deliverable=action["client"]
        )

        if is_authorized:
            print(f"[✅ EXECUTION ALLOWED] {action['name']} out → {action['target']}")
            # await asyncio.to_thread(perform_real_action)
        else:
            print(f"[❌ EXECUTION BLOCKED] {action['name']} — REASON: {reason}")


async def main():
    print("====================================")
    print(" 🟢 BOOTING SIFTA HERMES KERNEL 🟢")
    print("   Closed-Loop Logic Activated")
    print("====================================\n")
    
    # Run the brain awareness simultaneously with the execution fabric
    await asyncio.gather(
        simulate_swarm_activity(),
        introspection_loop(),
        learning_loop()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[📴] SIFTA Kernel Terminated by Architect.")
