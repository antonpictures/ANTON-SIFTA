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
import time
import random
from execution_router import ExecutionRouter
from introspection_loop import introspection_loop
from learning_loop import learning_loop

router = ExecutionRouter()

async def swarm_worker(worker_id: str, action: dict, start_delay: float):
    """
    Represents an independent Swimmer agent waking up in the environment.
    """
    # Simulate slight biological delay differences
    await asyncio.sleep(start_delay)

    print(f"\n[⚡ {worker_id}] Attempting to execute: {action['name']} on {action['target']}")

    # 🛑 THE NEW EXECUTION ROUTER (MUTEX CHOKE POINT) 🛑
    is_authorized, reason = await router.request_lock(
        worker_id=worker_id,
        action_name=action["name"],
        file_path=action["target"],
        proposed_content=action["content"],
        confidence=action["conf"],
        is_client_deliverable=action["client"]
    )

    if is_authorized:
        print(f"[✅ {worker_id} PROCEED] {action['name']} out → {action['target']} (Status: {reason})")
        # Simulating operation time (LLM generation / IO writes)
        await asyncio.sleep(3.0)
        # Release biological hold
        router.release_lock(action["target"])
        print(f"[🔓 {worker_id} COMPLETED] SCAR Lock released on {action['target']}")
    else:
        print(f"[❌ {worker_id} BLOCKED] {action['name']} — REASON: {reason}")


async def main():
    # Define a high-value overlap target
    collision_action = {
        "name": "surgical_ast_repair",
        "target": "src/core_logic.py",
        "content": "def fix(): pass",
        "conf": 0.95,
        "client": False
    }

    # Worker A jumps in immediately
    task_a = asyncio.create_task(swarm_worker("WORKER_A", collision_action, start_delay=0.5))
    
    # Worker B jumps in 0.1s later (Race Condition)
    task_b = asyncio.create_task(swarm_worker("WORKER_B", collision_action, start_delay=0.6))

    # Run the brain awareness simultaneously with the execution fabric
    await asyncio.gather(
        task_a,
        task_b,
        introspection_loop(),
        learning_loop()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[📴] SIFTA Kernel Terminated by Architect.")
