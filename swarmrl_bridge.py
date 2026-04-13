"""
swarmrl_bridge.py — SIFTA ↔ SwarmRL Integration Layer
======================================================
Written against the real body_state.py + scar_kernel.py APIs.

Maps SwarmRL's actor_critic.py action execution flow onto SIFTA's
Proposal-First architecture:
  - Agent generates a cryptographically signed PROPOSE_MOVE body
  - Action is submitted as a .scar proposal (not executed directly)
  - Quorum / canonical_winner() resolves conflicts deterministically
  - Only LOCKED proposals are forwarded to the SwarmRL environment step

No modifications required to the upstream SwarmRL package.
"""

import hashlib
import time
from pathlib import Path
from typing import Any, Optional

from body_state import SwarmBody, parse_body_state, NULL_TERRITORY
from scar_kernel import Kernel, Scar, content_addressed_id, canonical_winner

# ────────────────────────────────────────────────────────────
# ScarFieldObservable
#
# Replaces SwarmRL's raw physics observables with a pheromone
# field derived from .scar files in the agent's vicinity.
# Drop this into swarmrl/observables/ as a new observable type.
# ────────────────────────────────────────────────────────────

SCAR_DIR = Path(__file__).parent / ".sifta" / "scars"
SCAR_DIR.mkdir(parents=True, exist_ok=True)


class ScarFieldObservable:
    """
    Reads the local .scar directory and computes a pheromone strength
    vector for the agent's observation space.

    SwarmRL integration:
        observable = ScarFieldObservable(target="file.py")
        obs_vector = observable.compute(agent_position)

    Returns a float in [0, 1]: higher = stronger existing pheromone trail.
    A value near 1.0 means a fossil exists — replay, don't recompute.
    """

    def __init__(self, target: str):
        self.target = target
        self._kernel = Kernel()

    def compute(self, agent_id: str) -> float:
        """Return pheromone field strength at this target for the given agent."""
        # Fast-path: fossil exists → maximum signal, no recomputation needed
        if self.target in self._kernel.fossils:
            return 1.0

        # Active scars in this target's conflict domain
        competing = [
            s for s in self._kernel.scars.values()
            if s.target == self.target
        ]
        if not competing:
            return 0.0

        # Return normalized strength of the strongest current proposal
        from scar_kernel import pheromone_score
        scores = [pheromone_score(s, competing) for s in competing]
        return max(scores)


# ────────────────────────────────────────────────────────────
# SIFTAAgentBridge
#
# Wraps a SwarmRL actor_critic agent with SIFTA's proposal-first
# execution boundary.
#
# Usage:
#   bridge = SIFTAAgentBridge(agent_id="HERMES", kernel=kernel)
#   scar_id = bridge.propose_action(target="file.py", action="MOVE_RIGHT")
#   bridge.execute_if_won(scar_id, approve=True)
# ────────────────────────────────────────────────────────────

class SIFTAAgentBridge:
    """
    Wraps a SwarmRL agent with SIFTA's cryptographic proposal layer.

    Claude's observation (April 13, 2026):
    'SwarmBody.generate_body() with action_type is already the SCAR analog —
    an agent declares intent cryptographically before acting. The bridge can be
    written against what's actually committed.'

    This class is that bridge.
    """

    def __init__(self, agent_id: str, kernel: Kernel,
                 birth_certificate: Optional[str] = None):
        self.agent_id = agent_id.upper()
        self.kernel = kernel

        # Load or create the agent body
        try:
            self.body = SwarmBody(agent_id, birth_certificate=birth_certificate)
        except PermissionError as e:
            raise RuntimeError(
                f"SIFTAAgentBridge: Cannot initialize {agent_id} without Architect baptism. "
                f"Original error: {e}"
            )

    def propose_action(self, target: str, action_content: str,
                       pre_hash: str = NULL_TERRITORY,
                       post_hash: str = NULL_TERRITORY) -> str:
        """
        Cryptographically sign the agent's intent, then submit as a SCAR proposal.

        Steps:
          1. generate_body() — Ed25519 signed declaration of intent
          2. kernel.propose() — enters the arbitration pipeline
          3. Returns scar_id for subsequent resolve/execute calls

        The action is NOT executed here. This is the execution boundary.
        """
        # Step 1: Cryptographic intent declaration (the body IS the proposal)
        ascii_body = self.body.generate_body(
            origin=self.agent_id,
            destination=target,
            payload=action_content,
            action_type="PROPOSE_MOVE",
            pre_territory_hash=pre_hash,
            post_territory_hash=post_hash
        )

        # Verify our own body (proves we didn't corrupt it in generation)
        parse_body_state(ascii_body)  # raises on any integrity failure

        # Step 2: Use content-addressed ID so identical proposals from
        # multiple agents produce the same scar_id (no duplication)
        ca_id = content_addressed_id(target, action_content)

        # Insert directly with the content-addressed ID
        scar = Scar(ca_id, target, action_content)
        self.kernel.scars[ca_id] = scar
        self.kernel._log("PROPOSED", ca_id, target)

        return ca_id

    def resolve(self, scar_id: str):
        """Run deterministic conflict resolution on this proposal."""
        self.kernel.resolve(scar_id)

    def execute_if_won(self, scar_id: str, approve: bool = True) -> bool:
        """
        Execute only if this scar won arbitration (state == LOCKED).
        Returns True if executed, False if contested or already resolved.

        This is the human gate. In supervised mode, approve=True is passed
        by the human dashboard. In auto mode (non-critical tasks only),
        approve is set by a trust threshold.
        """
        scar = self.kernel.scars.get(scar_id)
        if not scar:
            return False

        if scar.state != "LOCKED":
            return False

        self.kernel.execute(scar_id, approve=approve)
        return approve

    def observe(self, target: str) -> float:
        """
        Return pheromone field strength at target.
        Use as input feature to SwarmRL's actor_critic forward pass.
        """
        obs = ScarFieldObservable(target)
        obs._kernel = self.kernel
        return obs.compute(self.agent_id)


# ────────────────────────────────────────────────────────────
# Multi-agent Consensus Round
#
# Given N SwarmRL agents all proposing actions on the same target,
# run one full SIFTA consensus round and return the winning agent.
# ────────────────────────────────────────────────────────────

def run_consensus_round(bridges: list["SIFTAAgentBridge"],
                        target: str,
                        actions: list[str],
                        approve: bool = True) -> Optional[str]:
    """
    Simulate one consensus round across multiple SwarmRL agents.

    Returns the scar_id of the winning proposal, or None if no winner.

    Protocol:
      1. Each agent proposes its action as a SCAR
      2. All agents call resolve() — deterministic winner elected
      3. Winner's SCAR is executed (if approved)
      4. Losing SCARs are CONTESTED — wait for next cycle or cancel
    """
    assert len(bridges) == len(actions), "Each agent must have exactly one action"

    scar_ids = []
    for bridge, action in zip(bridges, actions):
        sid = bridge.propose_action(target, action)
        scar_ids.append(sid)

    # Resolve all — deterministic, same result regardless of call order
    for sid in scar_ids:
        bridges[0].kernel.resolve(sid)

    # Find and execute winner
    kernel = bridges[0].kernel
    winners = [s for s in kernel.scars.values()
               if s.target == target and s.state == "LOCKED"]

    if not winners:
        return None

    winner_id = canonical_winner(winners).scar_id
    kernel.execute(winner_id, approve=approve)
    return winner_id


# ────────────────────────────────────────────────────────────
# Demo: Two SwarmRL agents competing on the same target
# ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from scar_kernel import Kernel

    k = Kernel()

    # Two agents — would normally be actor_critic.py outputs
    agent_a = SIFTAAgentBridge("HERMES",  k, birth_certificate="ARCHITECT_SEAL_HERMES")
    agent_b = SIFTAAgentBridge("ANTIALICE", k, birth_certificate="ARCHITECT_SEAL_ANTIALICE")

    # Both propose actions on the same file
    winner = run_consensus_round(
        bridges=[agent_a, agent_b],
        target="broken_module.py",
        actions=["ADD_IMPORT_JSON", "FIX_SYNTAX_LINE_7"],
        approve=True
    )

    print(f"\n✅ Consensus reached. Winning SCAR: {winner}")
    print(f"   Ledger events: {len(k.ledger)}")
    for e in k.ledger:
        print(f"   {e}")
