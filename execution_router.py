# execution_router.py
"""
EXECUTION ROUTER — Phase 3: SCAR-Mediated Swarm Coordination

A deterministic arbitration layer that prevents autonomous race conditions.
Swimmers do not interact directly with the Neural Gate; they request a SCAR lock here.
If another worker is currently mutating the reality of a target file, this router
will bounce the incoming swimmer with a DEFER response. 
"Permissioned Reality Editing."
"""

import asyncio
from state_bus import get_state, set_state
from neural_gate import NeuralGate

class ExecutionRouter:
    def __init__(self):
        self.gate = NeuralGate()
        # Ensure active locks dictionary exists on the state bus
        if get_state("active_scars", "MISSING") == "MISSING":
            set_state("active_scars", {})

    async def request_lock(
        self,
        worker_id: str,
        action_name: str,
        file_path: str,
        proposed_content: str,
        confidence: float,
        is_client_deliverable: bool
    ) -> tuple[bool, str]:
        """
        Arbitrates multi-agent execution. Checks SCAR locks before authorizing.
        Returns (is_approved, explanation).
        """
        
        # 0. MEDBAY SHIELD FAST-PATH
        if get_state("MEDBAY_ACTIVE", False):
            return False, "[DEFER] SYSTEM IN MEDBAY. MUTATIONS FROZEN."

        # 1. Biological Mutex check (SCAR Lock)
        active_scars = get_state("active_scars", {})
        
        if file_path in active_scars:
            occupying_worker = active_scars[file_path]
            # Mutex collision!
            return False, f"[DEFER] Reality currently locked by {occupying_worker}. SCAR collision prevented."

        # 2. Lock the target immediately to prevent micro-millisecond concurrency races
        active_scars[file_path] = worker_id
        set_state("active_scars", active_scars)

        # 3. Route to Neural Gate for system stability / physics / muscle memory authorization
        # We simulate the async context gate check
        decision, reason = self.gate.authorize(
            action_name=action_name,
            file_path=file_path,
            proposed_content=proposed_content,
            confidence=confidence,
            is_client_deliverable=is_client_deliverable
        )

        if decision:
            return True, f"[LOCK_GRANTED] SCAR active. Mutating authorized."
        else:
            # If the Gate violently rejects the mutation based on high Volatility,
            # we instantly release the biological lock so others aren't waiting on a dead operation.
            self.release_lock(file_path)
            return False, reason

    def release_lock(self, file_path: str):
        """
        Called when a worker finishes mutating or fails. Dissolves the biological SCAR lock.
        """
        active_scars = get_state("active_scars", {})
        if file_path in active_scars:
            del active_scars[file_path]
            set_state("active_scars", active_scars)
