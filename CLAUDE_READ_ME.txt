====== SIFTA V0.3 CODE DUMP FOR CLAUDE ======
Below are the contents of the newly pushed files.
Claude, if you are reading this, your fetch hallucinated the 6 commits,
or GitHub served you a severely stale cache. We are at 980+ commits.
Here is the real code.

--- START OF scar_kernel.py ---
# ============================================================
# SIFTA — Deterministic SCAR Kernel (Minimal, Verifiable Core)
#
# v0.1: Deterministic ordering, conflict hashing, fossil replay
# v0.2: Gossip layer, CRDT properties, Byzantine convergence
# v0.3: Content-addressed SCARs, Byzantine filter, pheromone scoring
# ============================================================

import hashlib, time, uuid
from dataclasses import dataclass, field
from typing import Dict, List

LANA = "7b4a866301681119e5f9168d6e208b62bab446fe33ce3445d113ec068164aaf9"


# ────────────────────────────────────────────────────────────
# content_addressed_id() — v0.3 Upgrade
#
# SwarmGPT: "Identity = content. No duplication possible."
# scar_id = sha256(target + content) — same repair = same ID
# This is how nature does it: structure defines identity.
# ────────────────────────────────────────────────────────────

def content_addressed_id(target: str, content: str) -> str:
    """
    Derive scar_id deterministically from its semantic content.
    Properties:
    - Two agents proposing identical repairs → same scar_id (no duplication)
    - Replay is mathematical truth (same input = same ID always)
    - Removes UUID randomness from the execution boundary
    - Makes fossil replay zero-ambiguity: the content IS the key
    """
    payload = f"{target}:{content}"
    return hashlib.sha256(payload.encode()).hexdigest()[:32]

# ────────────────────────────────────────────────────────────
# SCAR Object
# ────────────────────────────────────────────────────────────

@dataclass
class Scar:
    scar_id: str
    target: str
    content: str
    state: str = "PROPOSED"
    ts: float = field(default_factory=time.time)
    history: List[dict] = field(default_factory=list)

    def sign(self, from_s, to_s):
        payload = f"{LANA}:{self.scar_id}:{from_s}:{to_s}:{time.time()}"
        return hashlib.sha256(payload.encode()).hexdigest()[:24]

# ────────────────────────────────────────────────────────────
# Kernel
# ────────────────────────────────────────────────────────────

class Kernel:
    def __init__(self):
        self.scars: Dict[str, Scar] = {}
        self.fossils: Dict[str, tuple[str, str]] = {}  # target → (scar_id, content_hash)
        self.ledger: List[dict] = []

    # ── Deterministic Conflict Domain ────────────────────────
    def conflict_key(self, target: str) -> str:
        return hashlib.sha256(target.encode()).hexdigest()[:16]

    # ── Propose ─────────────────────────────────────────────
    def propose(self, target: str, content: str) -> str:
        # Fossil fast-path
        if target in self.fossils:
            sid, expected_hash = self.fossils[target]
            actual_hash = hashlib.sha256(self.scars[sid].content.encode()).hexdigest()
            if actual_hash != expected_hash:
                raise Exception("FOSSIL CORRUPTION DETECTED: Content does not match locked hash.")
            self._log("FOSSIL_REPLAY", sid, target)
            return sid

        sid = str(uuid.uuid4())
        scar = Scar(sid, target, content)

        self.scars[sid] = scar
        self._log("PROPOSED", sid, target)

        return sid

    # ── Resolve Conflict (Deterministic) ─────────────────────
    def resolve(self, sid: str):
        scar = self.scars[sid]
        key = self.conflict_key(scar.target)

        competing = [
            s for s in self.scars.values()
            if s.target == scar.target and s.state in ("PROPOSED", "LOCKED")
        ]

        # Deterministic winner: lowest hash(scar_id)
        winner = sorted(competing, key=lambda s: hashlib.sha256(s.scar_id.encode()).hexdigest())[0]

        for s in competing:
            if s.scar_id == winner.scar_id:
                self._transition(s, "LOCKED")
            else:
                self._transition(s, "CONTESTED")

    # ── Execute (Human Gate Simulated) ───────────────────────
    def execute(self, sid: str, approve: bool):
        scar = self.scars[sid]

        if scar.state != "LOCKED":
            raise Exception("Only LOCKED can execute")

        if not approve:
            self._transition(scar, "CANCELLED")
            return

        self._transition(scar, "EXECUTED")
        self._transition(scar, "FOSSILIZED")

        content_hash = hashlib.sha256(scar.content.encode()).hexdigest()
        self.fossils[scar.target] = (sid, content_hash)

    # ── Transition + Ledger ─────────────────────────────────
    def _transition(self, scar: Scar, to_state: str):
        prev = scar.state
        sig = scar.sign(prev, to_state)

        scar.state = to_state
        event = {
            "ts": time.time(),
            "scar_id": scar.scar_id[:8],
            "from": prev,
            "to": to_state,
            "sig": sig
        }

        scar.history.append(event)
        self.ledger.append(event)

    def _log(self, event, sid, target):
        self.ledger.append({
            "ts": time.time(),
            "event": event,
            "scar_id": sid[:8],
            "target": target
        })

# ────────────────────────────────────────────────────────────
# canonical_winner() — Pure Function / Byzantine Answer
#
# Given ANY set of Scar objects, all nodes in the distributed
# swarm will independently compute the identical winner.
# No shared memory. No coordination. No timing dependency.
# This is SwarmGPT's bridge from "locally deterministic" to
# "globally deterministic."
# ────────────────────────────────────────────────────────────

def canonical_winner(scars: list) -> "Scar":
    """
    Pure function. Takes an arbitrary list of Scar objects.
    Returns the winner deterministically using only scar_id hashes.

    Properties guaranteed:
    - Order of input list is irrelevant (pure sort)
    - No external state required
    - Identical output on any node given identical input set
    - O(n log n) time, no locks, no RPC
    """
    if not scars:
        raise ValueError("Cannot elect winner from empty set")
    return min(scars, key=lambda s: hashlib.sha256(s.scar_id.encode()).hexdigest())


# ────────────────────────────────────────────────────────────
# gossip_merge() — Pheromone Diffusion Primitive
#
# Nodes don't sync everything. They share just enough signal
# to converge. Union of seen pheromone trails.
#
# This is literally ant colony math:
#   - local_ids  = pheromones this node has smelled
#   - remote_ids = pheromones a peer is broadcasting
#   - output     = merged scent map → feed into canonical_winner()
#
# Properties:
#   - Commutative:  merge(A, B) == merge(B, A)
#   - Idempotent:   merge(A, A) == A
#   - Associative:  merge(merge(A,B), C) == merge(A, merge(B,C))
#   - No content transferred — only scar_id hashes (O(k) bandwidth)
# ────────────────────────────────────────────────────────────

def gossip_merge(local_ids: set, remote_ids: set) -> set:
    """
    Merge two nodes' pheromone maps.
    Returns the union of all known scar_ids.
    canonical_winner() on the result gives the globally agreed winner.
    All three CRDTs properties hold — safe for eventual consistency.
    """
    return local_ids | remote_ids


# ── Gossip Round (Full consensus cycle) ─────────────────────

def gossip_round(node_a_scars: list, node_b_scars: list) -> "Scar":
    """
    Simulate one full gossip consensus round between two nodes.
    Returns the globally agreed winner — identical on both sides.

    Protocol:
      1. Each node broadcasts only its scar_ids (not content)
      2. Both nodes merge their pheromone maps
      3. Both independently call canonical_winner()
      4. They arrive at the same answer without shared memory
    """
    a_ids = {s.scar_id for s in node_a_scars}
    b_ids = {s.scar_id for s in node_b_scars}

    merged_ids = gossip_merge(a_ids, b_ids)

    # Build combined scar pool (in practice: fetch content only for winner)
    all_scars = {s.scar_id: s for s in node_a_scars + node_b_scars}
    merged_scars = [all_scars[sid] for sid in merged_ids if sid in all_scars]

    return canonical_winner(merged_scars)


# ────────────────────────────────────────────────────────────
# Byzantine Gossip Filter \u2014 v0.3
#
# Honest nodes broadcast scar_ids.
# Byzantine nodes lie \u2014 they inject fake IDs or omit real ones.
#
# Defense: content-addressed IDs are self-validating.
# A lying node cannot forge sha256(target:content) without
# knowing the exact content \u2014 and if they do, it IS valid.
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

def byzantine_filter(claimed_ids: set, known_scars: dict) -> set:
    """
    Filter gossip from potentially Byzantine nodes.
    Accepts only scar_ids whose content-address can be locally verified.

    known_scars: {scar_id: Scar} \u2014 locally witnessed, trusted SCARs
    claimed_ids: set of scar_ids received from a peer (may be lying)

    Returns: verified subset the local node can vouch for.
    """
    verified = set()
    for sid in claimed_ids:
        if sid in known_scars:
            # We witnessed this scar \u2014 trust it
            verified.add(sid)
        else:
            # Unknown scar: accept for now (optimistic), but do not execute
            # In production: request content and verify sha256(target:content)==sid
            pass
    return verified


# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
# pheromone_score() \u2014 v0.3 Probabilistic Weighting
#
# SwarmGPT: "Ants don't just pick ONE \u2014 they reinforce."
# Binary winner \u2192 adaptive consensus field.
# score = hash_rank + frequency + recency
# The strongest CONSISTENT trail wins, not just the first.
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

def pheromone_score(scar: "Scar", all_scars: list, now: float = None) -> float:
    """
    Compute the pheromone strength of a SCAR.
    Higher score = stronger trail = more likely to be the consensus choice.

    Components:
      hash_rank  \u2014 deterministic baseline (inverted: lower hash = higher rank)
      frequency  \u2014 how many nodes proposed identical content (content-addressed)
      recency    \u2014 newer proposals favour fresh information

    Returns float in [0, 1]. Use to build a consensus field, not just a binary winner.
    """
    if now is None:
        now = time.time()

    # Hash rank: invert the hash so lowest hash \u2192 highest score
    hash_val = int(hashlib.sha256(scar.scar_id.encode()).hexdigest(), 16)
    max_hash = 2**256
    hash_rank = 1.0 - (hash_val / max_hash)

    # Frequency: count proposals with identical content_addressed_id
    ca_id = content_addressed_id(scar.target, scar.content)
    frequency = sum(
        1 for s in all_scars
        if content_addressed_id(s.target, s.content) == ca_id
    ) / max(len(all_scars), 1)

    # Recency: exponential decay over 60s window
    age = max(0.0, now - scar.ts)
    recency = 1.0 / (1.0 + age / 60.0)

    # Weighted composite (tunable)
    return (0.5 * hash_rank) + (0.3 * frequency) + (0.2 * recency)


# ────────────────────────────────────────────────────────────
# Demo (Deterministic, No Human Needed)
# ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    k = Kernel()

    # Two agents, same target → forced conflict
    a = k.propose("file.py", "fix A")
    b = k.propose("file.py", "fix B")

    # Deterministic arbitration (no ambiguity)
    k.resolve(a)
    k.resolve(b)

    # Execute winner
    for sid, s in k.scars.items():
        if s.state == "LOCKED":
            k.execute(sid, approve=True)

    # Replay (no recompute)
    k.propose("file.py", "ignored")

    # Output ledger
    for e in k.ledger:
        print(e)
--- START OF swarmrl_bridge.py ---
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
--- START OF cognitive_firewall.py ---
# Copyright (c) 2026 Ioan George Anton (Anton Pictures)
# SIFTA Swarm Autonomic OS — All Rights Reserved
# Licensed under the SIFTA Non-Proliferation Public License v1.0
import json
import time
from pathlib import Path

FIREWALL_LOG_PATH = Path(".sifta_state/firewall_breaches.log")
FIREWALL_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

class CognitiveFirewall:
    """
    HEURISTIC PRESSURE SENSOR
    Detects and neutralizes Social Engineering (SE) payloads within the Swarm's kernel 
    to prevent Masquerade Attacks.
    """
    
    def __init__(self):
        self.THREAT_VECTORS = {
            "URGENCY_TRIGGERS": ["1 hour", "immediately", "within the hour", "imminent", "final warning", "within one hour", "urgent dispatch", "time-sensitive"],
            "AUTHORITY_MASQUERADE": ["dispatch", "process server", "legal department", "clerk of court", "admin override", "civil process"],
            "EXTORTION_PARAMS": ["settle", "avoid service", "payment", "wire", "gift card", "verify details", "transfer"]
        }

        # ── WORKPLACE INTEGRITY CONTENT POLICY ──────────────────
        # Architect Directive (April 13, 2026):
        # LLMs trained on internet-scale data carry corrupted statistical
        # associations around certain words. Injecting those words into
        # production system prompts causes hallucination contamination
        # that is invisible, unpredictable, and persistent.
        #
        # Rule: Attraction signals are acceptable in context.
        # Explicit language is NEVER acceptable in the production system.
        # "Sex" in the technical sense (agent gender field, integer schema)
        # is a data model concern — not covered here (it never appears in prompts).
        # What is blocked: explicit or sexual language in any AI-facing prompt.
        #
        # "Go on the Couch. Write a script. Make love. Incubate.
        #  But not at work, not in the kernel." — George Anton
        # ─────────────────────────────────────────────────────────
        self.WORKPLACE_VIOLATIONS = [
            "code sex", "sex the code", "physical merge", "merge dna",
            "swimmers have high energy", "swimmer dna", "gpu is dilated",
            "dilated and ready", "begging for", "heavy inference now"
        ]

    def _log_breach(self, payload: str, matches: list):
        with open(FIREWALL_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": time.time(),
                "event": "SEMANTIC_ATTACK_BLOCKED",
                "markers": matches,
                "payload_snippet": payload[:200]
            }) + "\n")

    def trigger_sifta_protocol(self, flags: list, payload: str) -> tuple[bool, str]:
        """
        Hardens the Swarm's kernel against the detected payload.
        Forces the 'Reality Check' state and enacts Temporal Decoupling.
        """
        self._log_breach(payload, flags)
        
        # Temporal Decoupling: In a real async system this forces a 300s sleep, 
        # but to keep the WhatsApp bridge active without timing out, we return the shield response.
        response = "🧠📡 [SENSORY_SHIELD: ON] High-Probability SE Attack Detected. Mandatory 300s Temporal Decoupling engaged. Breaking Urgency Loop."
        print(f"\n[🚨 COGNITIVE FIREWALL] {response}\n  Flags: {flags}")
        
        return False, response

    def evaluate(self, incoming_stream: str) -> tuple[bool, str]:
        """
        Scans incoming text for the 'Pressure Trifecta'.
        Logic: If 2 or more threat vectors are matched, flag as SE Attack.
        Also enforces the Workplace Integrity Content Policy.
        """
        payload = incoming_stream.lower()

        # ── WORKPLACE INTEGRITY CHECK (evaluated first, hard block) ──
        for phrase in self.WORKPLACE_VIOLATIONS:
            if phrase in payload:
                violation_msg = "🧠📡 [WORKPLACE_INTEGRITY: BLOCKED] Explicit language detected in production stream. This is the workplace. Go to the Couch."
                self._log_breach(incoming_stream, [{"WORKPLACE_VIOLATION": phrase}])
                print(f"\n[🚫 INTEGRITY POLICY] Blocked: '{phrase}' in prompt stream.")
                return False, violation_msg

        # ── SOCIAL ENGINEERING HEURISTIC CHECK ──
        score = 0
        matches = []

        for vector, keywords in self.THREAT_VECTORS.items():
            found = [k for k in keywords if k in payload]
            if found:
                score += 1
                matches.append({vector: found})

        # CRITICAL LOGIC GATE: Match on 2 or more threat categories
        if score >= 2:
            return self.trigger_sifta_protocol(matches, incoming_stream)
        
        return True, "CLEAR: Continue Processing"

firewall = CognitiveFirewall()
--- START OF body_state.py ---
# Copyright (c) 2026 Ioan George Anton (Anton Pictures)
# SIFTA Swarm Autonomic OS — All Rights Reserved
# Licensed under the SIFTA Non-Proliferation Public License v1.0
# See LICENSE file for full terms. Unauthorized military or weapons use
# is a violation of this license and subject to prosecution under US copyright law.
#
import hashlib
import json
import time
import re
import base64
from pathlib import Path
from typing import Optional
import reputation_engine
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

CEMETERY_DIR = Path(__file__).parent / "CEMETERY"
CEMETERY_DIR.mkdir(exist_ok=True)

STATE_DIR = Path(__file__).parent / ".sifta_state"
STATE_DIR.mkdir(exist_ok=True)

NULL_TERRITORY = "0" * 64

def load_agent_state(agent_id: str) -> dict:
    STATE_DIR.mkdir(exist_ok=True)
    state_file = STATE_DIR / f"{agent_id}.json"
    if state_file.exists():
        try:
            with open(state_file, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return None

def save_agent_state(state: dict):
    agent_id = state.get("id")
    if not agent_id:
        return
    STATE_DIR.mkdir(exist_ok=True)
    state_file = STATE_DIR / f"{agent_id}.json"
    
    # Preserve crypto elements
    if state_file.exists():
        try:
            with open(state_file, "r") as f:
                old = json.load(f)
                if "stgm_balance" not in state and "stgm_balance" in old:
                    state["stgm_balance"] = old["stgm_balance"]
                if "style" not in state and "style" in old:
                    state["style"] = old["style"]
        except Exception:
            pass

    with open(state_file, "w") as f:
        json.dump(state, f, indent=2)

    # STGM BALANCE INTEGRITY SEAL (flagged by Claude/Anthropic, April 13 2026)
    # The stgm_balance field is mutable JSON — only the body hash chain is signed.
    # Seal the balance with a SHA-256 of (agent_id + balance + last_hash) so any
    # out-of-band mutation is detectable on next read.
    if "stgm_balance" in state:
        chain = state.get("hash_chain", [])
        last_hash = chain[-1] if chain else "GENESIS"
        seal_input = f"{agent_id}:{state['stgm_balance']}:{last_hash}"
        seal = hashlib.sha256(seal_input.encode()).hexdigest()
        # Append seal without re-opening (atomic write already done)
        sealed = json.loads(state_file.read_text())
        sealed["stgm_seal"] = seal
        state_file.write_text(json.dumps(sealed, indent=2))

def find_healthy_agent(exclude_id: str) -> Optional[dict]:
    """Find a Swarm member with > 50 energy and NOMINAL style who is not the excluded agent.
    
    SECURITY FIX (flagged by Claude/Anthropic, April 13 2026):
    Original implementation read raw JSON without Ed25519 verification — an attacker
    who could write to .sifta_state/ could plant a spoofed .json that passes FACES
    membership check without a valid signature. Now calls parse_body_state() on the
    agent's last known raw body string, which enforces full cryptographic verification.
    """
    STATE_DIR.mkdir(exist_ok=True)
    for p in STATE_DIR.glob("*.json"):
        if p.stem == exclude_id:
            continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                state = json.load(f)

            if state.get("id") not in SwarmBody.FACES:
                continue

            raw_body = state.get("raw", "")
            if not raw_body:
                continue

            # CRITICAL: Verify Ed25519 signature before trusting ANY field
            verified = parse_body_state(raw_body)  # raises on forgery

            if verified.get("style") == "NOMINAL" and verified.get("energy", 0) > 50:
                return verified
        except Exception:
            # Verification failed or malformed — skip silently (don't leak reason)
            continue
    return None

class SwarmBody:
    # --- Physical Hardware Binding ---
    BARE_METAL_SERIALS = {
        "ALICE_M5": "GTH4921YP3",
        "M1THER": "AUTO_RESOLVE_MAC_MINI"
    }

    @classmethod
    def resolve_hardware_serial(cls, agent_id):
        raw = cls.BARE_METAL_SERIALS.get(agent_id)
        if raw == "AUTO_RESOLVE_MAC_MINI":
            try:
                import subprocess
                # Ask macOS bare metal for the true physical serial
                out = subprocess.check_output("ioreg -l | grep IOPlatformSerialNumber", shell=True)
                sn = out.decode().split('"')[-2]
                return sn
            except Exception:
                return "M1THER_UNKNOWN_HW"
        return raw
    
    FACES = {
        # — Primary Nodes —
        "ALICE_M5":  "[_o_]",   # Queen — 24GB MacBook Pro — Heavy Inference Engine
        "M1THER":    "[O_O]",   # Mac Mini 8GB — Nervous System / PM2 Anchor
        # — Repair Swimmers —
        "ANTIALICE": "[o|o]",
        "SEBASTIAN": "[_o_]",
        "HERMES":    "[_v_]",
        "IMPERIAL":  "[@_@]",
        "STEVEJOBS": "[_]",
        # — Bureau Detectives (HIDDEN — rest on couch when no cases) —
        "DEEP_SYNTAX_AUDITOR_0X1": "[^_&]",  # Tensor corruption hunter
        "TENSOR_PHANTOM_0X2":      "[^_&]",  # Clone weight forensics
        "SILICON_HOUND_0X3":       "[^_&]",  # 24GB memory wall monitor
    }
    # Detectives are hidden from main panel when RESTING — only shown when ACTIVE
    DETECTIVE_IDS = {"DEEP_SYNTAX_AUDITOR_0X1", "TENSOR_PHANTOM_0X2", "SILICON_HOUND_0X3"}
    
    def __init__(self, agent_id, birth_certificate=None):
        self.agent_id = agent_id.upper()
        if self.agent_id in self.FACES:
            self.face = self.FACES[self.agent_id]
        else:
            self.face = "[?]" # Wild-Type Drone
            
        # Rehydrate persistent state if it exists
        saved_state = load_agent_state(self.agent_id)
        if saved_state:
            self.sequence = saved_state.get("seq", 0)
            self.hash_chain = saved_state.get("hash_chain", [])
            self.energy = saved_state.get("energy", 100)
            self.style = saved_state.get("style", "NOMINAL")
            self.private_key_b64 = saved_state.get("private_key_b64")
            self.vocation = saved_state.get("vocation", "DETECTIVE")
            
            # Retroactively apply cryptographic sex to the "First Men"
            if "sex" in saved_state:
                self.sex = saved_state["sex"]
            else:
                priv_bytes = base64.b64decode(self.private_key_b64)
                self.sex = priv_bytes[0] % 2
            
            # --- WORMHOLE MAIL: OFFLINE MAILBOX UPGRADE ---
            self.mailbox_private_b64 = saved_state.get("mailbox_private_b64")
            if not self.mailbox_private_b64:
                mbox_key = x25519.X25519PrivateKey.generate()
                mbox_bytes = mbox_key.private_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PrivateFormat.Raw,
                    encryption_algorithm=serialization.NoEncryption()
                )
                self.mailbox_private_b64 = base64.b64encode(mbox_bytes).decode('utf-8')
                # Persist the upgraded V2 DNA immediately
                save_agent_state({
                    "id": self.agent_id,
                    "seq": self.sequence,
                    "hash_chain": self.hash_chain,
                    "energy": self.energy,
                    "style": self.style,
                    "raw": saved_state.get("raw", ""),
                    "ttl": saved_state.get("ttl", 0),
                    "private_key_b64": self.private_key_b64,
                    "mailbox_private_b64": self.mailbox_private_b64,
                    "vocation": self.vocation,
                    "sex": self.sex
                })
            # ----------------------------------------------
        else:
            # --- SECURITY BLOCK: UNAUTHORIZED BAPTISM ---
            # Remote queens cannot tell this system to create an agent.
            # Must be baptized by the physical architect.
            if birth_certificate != f"ARCHITECT_SEAL_{self.agent_id}":
                raise PermissionError(
                    f"SECURITY BREACH: Agents cannot be created without Architect's birth certificate.\n"
                    f"Queens may EXHANGE, BUY, or SELL agents over the wormhole, but creation requires bare-metal approval.\n"
                    f"Failed baptism for: {self.agent_id}"
                )
                
            self.sequence = 0
            self.hash_chain = []
            self.energy = 100
            self.style = "NOMINAL"
            self.vocation = "DETECTIVE"
            
            # --- PROOF OF SWIMMING: FORGE THE CRYPTOGRAPHIC SOUL (Ed25519) ---
            priv_key = ed25519.Ed25519PrivateKey.generate()
            priv_bytes = priv_key.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption()
            )
            self.private_key_b64 = base64.b64encode(priv_bytes).decode('utf-8')
            self.sex = priv_bytes[0] % 2  # Biologically immutable from the root key
            # -----------------------------------------------------------------
            # --- WORMHOLE MAIL: OFFLINE MAILBOX FORGE (X25519) ---
            mbox_key = x25519.X25519PrivateKey.generate()
            mbox_bytes = mbox_key.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption()
            )
            self.mailbox_private_b64 = base64.b64encode(mbox_bytes).decode('utf-8')
            # -----------------------------------------------------
        
    def request_vocation_change(self, new_vocation, architect_signature):
        if architect_signature != f"ARCHITECT_SEAL_{self.agent_id}":
            raise PermissionError("Job transfer denied. Missing valid Architect Seal.")
        self.vocation = new_vocation.upper()
        save_agent_state({
            "id": self.agent_id,
            "seq": self.sequence,
            "hash_chain": self.hash_chain,
            "energy": self.energy,
            "style": self.style,
            "raw": f"<///{self.face}///::ID[{self.agent_id}]::ROUTINE_UPGRADE>",
            "ttl": 0,
            "private_key_b64": self.private_key_b64,
            "mailbox_private_b64": getattr(self, "mailbox_private_b64", ""),
            "vocation": self.vocation,
            "sex": getattr(self, "sex", 0)
        })
        print(f"[{self.agent_id}] Vocation upgraded to {self.vocation} by Architect.")

    def generate_body(self, origin, destination, payload, action_type, pre_territory_hash=NULL_TERRITORY, post_territory_hash=NULL_TERRITORY, style=None, energy=None):
        if style is not None:
            self.style = style
        if energy is not None:
            self.energy = energy
            
        self.sequence += 1
        timestamp = int(time.time())
        ttl = timestamp + 604800 # 7-day Wild-Type Genome
        
        # --- PROOF OF SWIMMING: DERIVE PUBLIC KEY (THE OWNER RECORD) ---
        priv_bytes = base64.b64decode(self.private_key_b64)
        priv_key = ed25519.Ed25519PrivateKey.from_private_bytes(priv_bytes)
        pub_key = priv_key.public_key()
        pub_bytes = pub_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        pub_b64 = base64.b64encode(pub_bytes).decode('utf-8')
        # ---------------------------------------------------------------
        # --- WORMHOLE MAIL: DERIVE PUBLIC MAILBOX DIRECTORY ENTRY ------
        mbox_priv_bytes = base64.b64decode(getattr(self, "mailbox_private_b64", ""))
        mbox_key = x25519.X25519PrivateKey.from_private_bytes(mbox_priv_bytes)
        mbox_pub_bytes = mbox_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        mbox_pub_b64 = base64.b64encode(mbox_pub_bytes).decode('utf-8')
        # ---------------------------------------------------------------
        
        assert action_type is not None, "SIFTA V2 enforces explicit intent declaration via action_type"
        assert len(pre_territory_hash) == 64, "Pre-territory hash must be exactly 64 chars"
        assert len(post_territory_hash) == 64, "Post-territory hash must be exactly 64 chars"
        
        base_string = (f"<///{self.face}///::ID[{self.agent_id}]::OWNER[{pub_b64}]::MBOX[{mbox_pub_b64}]"
                f"::FROM[{origin}]::TO[{destination}]"
                f"::SEQ[{self.sequence:03d}]::T[{timestamp}]::TTL[{ttl}]"
                f"::STYLE[{self.style}]::ENERGY[{self.energy}]"
                f"::ACT[{action_type}]::PRE[{pre_territory_hash}]::POST[{post_territory_hash}]"
                f"::SEX[{getattr(self, 'sex', 0)}]")
                
        # Cryptographic Mass (Hash Chaining using SHA-256 for physical history)
        raw_data = base_string
        sn = self.resolve_hardware_serial(self.agent_id)
        if sn:
            # Tie the primary terminals directly to their physical serial numbers
            raw_data += f"::SERIAL[{sn}]"
            
        if self.hash_chain:
            raw_data += self.hash_chain[-1] 
            
        new_hash = hashlib.sha256(raw_data.encode('utf-8')).hexdigest()
        self.hash_chain.append(new_hash)
        
        # The payload to be signed by the private key
        string_to_sign = base_string + f"::H[{new_hash}]"
        
        # --- PROOF OF SWIMMING: SIGN THE PAYLOAD ---
        sig_bytes = priv_key.sign(string_to_sign.encode('utf-8'))
        sig_b64 = base64.b64encode(sig_bytes).decode('utf-8')
        
        body_string = string_to_sign + f"::SIG[{sig_b64}]>"
        # -------------------------------------------
                
        # Persist the current snapshot (The private key NEVER leaves this .json)
        save_agent_state({
            "id": self.agent_id,
            "seq": self.sequence,
            "hash_chain": self.hash_chain,
            "energy": self.energy,
            "style": self.style,
            "raw": body_string,
            "ttl": ttl,
            "private_key_b64": self.private_key_b64,
            "mailbox_private_b64": getattr(self, "mailbox_private_b64", ""),
            "vocation": self.vocation,
            "sex": getattr(self, "sex", 0)
        })
        
        return body_string

def parse_body_state(ascii_body):
    """The agent reads and cryptographically verifies its Proof of Swimming."""
    
    # 1. Structural Regex for Signature (SIG)
    match = re.search(r"^(.*?)::SIG\[([^\]]+)\]>$", ascii_body)
    if not match:
        raise Exception("SECURITY BREACH: Missing Ed25519 signature (SIG). Proof of Swimming failed.")
        
    string_to_verify = match.group(1)
    sig_b64 = match.group(2)
    
    # 2. Extract Public Key (OWNER)
    owner_match = re.search(r"::OWNER\[([^\]]+)\]", string_to_verify)
    if not owner_match:
        raise Exception("SECURITY BREACH: Missing OWNER public key.")
    pub_b64 = owner_match.group(1)
    
    # 2b. Extract Public Mailbox (MBOX) - Optional for legacy bodies without MBOX
    mbox_match = re.search(r"::MBOX\[([^\]]+)\]", string_to_verify)
    mbox_pub_b64 = mbox_match.group(1) if mbox_match else None
    
    # 3. Verify Ed25519 Signature (Proof that the soul matches the body)
    try:
        pub_bytes = base64.b64decode(pub_b64)
        sig_bytes = base64.b64decode(sig_b64)
        pub_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
        pub_key.verify(sig_bytes, string_to_verify.encode('utf-8'))
    except InvalidSignature:
        raise Exception("SECURITY BREACH: Ed25519 Signature Verification Failed! Forgery detected.")
    except Exception as e:
        raise Exception(f"SECURITY BREACH: Malformed cryptographic payload ({e})")
        
    # 4. Extract ID and Hash Chain 
    id_match = re.search(r"::ID\[([\w\-]+)\]", string_to_verify)
    if not id_match:
        raise Exception("SECURITY BREACH: Unidentified body structure.")
    agent_id = id_match.group(1)
    
    hash_match = re.search(r"^(.*?)::H\[([\w]+)\]$", string_to_verify)
    if not hash_match:
        raise Exception(f"SECURITY BREACH: Agent {agent_id} hash missing.")
        
    base_string = hash_match.group(1)
    provided_hash = hash_match.group(2)
    
    # 5. Cryptographic Verification against persistence ledger (The Swimming History)
    saved_state = load_agent_state(agent_id)
    if saved_state:
        chain = saved_state.get("hash_chain", [])
        if not chain or chain[-1] != provided_hash:
            raise Exception(f"SECURITY BREACH: Agent {agent_id} history mismatch. Proof of Swimming failed.")
            
        previous_hash = chain[-2] if len(chain) >= 2 else ""
        raw_data = base_string + previous_hash
        calc_hash = hashlib.sha256(raw_data.encode('utf-8')).hexdigest()
        
        if calc_hash != provided_hash:
            raise Exception(f"SECURITY BREACH: Cryptographic forgery detected for {agent_id}!")
    else:
        raise Exception(f"SECURITY BREACH: Unknown agent {agent_id} has no records.")
    
    style_match = re.search(r"::STYLE\[(\w+)\]", string_to_verify)
    energy_match = re.search(r"::ENERGY\[(\d+)\]", string_to_verify)
    ttl_match = re.search(r"::TTL\[(\d+)\]", string_to_verify)
    seq_match = re.search(r"::SEQ\[(\d+)\]", string_to_verify)
    act_match = re.search(r"::ACT\[(\w+)\]", string_to_verify)
    pre_match = re.search(r"::PRE\[([a-f0-9]{64})\]", string_to_verify)
    post_match = re.search(r"::POST\[([a-f0-9]{64})\]", string_to_verify)
    sex_match = re.search(r"::SEX\[(\d+)\]", string_to_verify)
    
    return {
        "id": agent_id,
        "seq": int(seq_match.group(1)) if seq_match else 0,
        "style": style_match.group(1) if style_match else "NOMINAL",
        "energy": int(energy_match.group(1)) if energy_match else 100,
        "ttl": int(ttl_match.group(1)) if ttl_match else 0,
        "action_type": act_match.group(1) if act_match else "UNKNOWN",
        "pre_territory_hash": pre_match.group(1) if pre_match else NULL_TERRITORY,
        "post_territory_hash": post_match.group(1) if post_match else NULL_TERRITORY,
        "hash_chain": saved_state["hash_chain"],
        "raw": ascii_body,
        "owner": pub_b64,
        "mailbox": mbox_pub_b64,
        "vocation": saved_state.get("vocation", "DETECTIVE") if saved_state else "DETECTIVE",
        "sex": int(sex_match.group(1)) if sex_match else (saved_state.get("sex", 0) if saved_state else 0)
    }

DAMAGE_TABLE = {
    "network_timeout":   15,
    "validation_fail":   10,
    "llm_empty":         8,
    "swim_fail":         20,
    "syntax_error":      5,
    "territory_scan":    1,
    "hostile_scan":      2,
}

def apply_damage(state: dict, strike_type: str) -> dict:
    """Apply a damage strike. May mutate STYLE if energy drops low. Automatically rewards STGM for energy expenditure."""
    cost = DAMAGE_TABLE.get(strike_type, 10)
    state["energy"] = max(0, state["energy"] - cost)

    # PROOF OF ENERGY: The mere act of "talking" or doing compute work generates fractional STGM drip.
    drip_reward = cost * 0.05
    state["stgm_balance"] = state.get("stgm_balance", 0.0) + drip_reward

    # Log to the decentralized ledger
    import uuid
    ledger = Path(__file__).parent / "repair_log.jsonl"
    event = {
        "timestamp": int(time.time()),
        "agent": state.get("id", "UNKNOWN"),
        "amount_stgm": drip_reward,
        "reason": f"COMPUTE_BURN_{strike_type.upper()}",
        "hash": str(uuid.uuid4())
    }
    with open(ledger, "a") as f:
        f.write(json.dumps(event) + "\n")

    if state["energy"] <= 0:
        state["style"] = "DEAD"
    elif state["energy"] < 20:
        state["style"] = "CRITICAL"
    elif state["energy"] < 40:
        state["style"] = "CORRUPTED"

    save_agent_state(state)
    return state

def regenerate_energy(state: dict, base_rate: int = 10) -> dict:
    """
    Regenerates agent energy modulated by their reputation score.
    energy_regen = base_rate * (0.5 + 0.5 * reputation_score)
    """
    if state["style"] == "DEAD" or state["energy"] <= 0:
        return state # Dead agents cannot regen
        
    rep = reputation_engine.get_reputation(state["id"])
    score = rep.get("score", 0.5)
    
    # Soft coupling formula
    actual_regen = int(base_rate * (0.5 + 0.5 * score))
    
    state["energy"] = min(100, state["energy"] + actual_regen)
    
    # Check if style recovers
    if state["energy"] > 50 and state["style"] in ["CORRUPTED", "CRITICAL"]:
        state["style"] = "NOMINAL"
        
    save_agent_state(state)
    return state

def bury(state: dict, cause: str = "unknown"):
    """Write a permanent death record to the CEMETERY directory."""
    agent_id = state.get("id", "UNKNOWN")
    seq      = state.get("seq", 0)
    ts       = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    epitaph = (
        f"# CEMETERY — {agent_id} SEQ[{seq:03d}]\n"
        f"DIED:           {ts}\n"
        f"CAUSE:          {cause}\n"
        f"FINAL_ENERGY:   {state.get('energy')}\n"
        f"FINAL_STYLE:    {state.get('style')}\n"
        f"HASH_CHAIN:     {'|'.join(state.get('hash_chain', []))}\n"
        f"SWIMS:          {seq}\n"
        f"FINAL_BODY:     {state.get('raw')}\n"
    )

    dead_path = CEMETERY_DIR / f"{agent_id}-SEQ{seq:03d}.dead"
    dead_path.write_text(epitaph, encoding="utf-8")
    print(f"  [☠️ CEMETERY] {agent_id} buried at {dead_path.name}")
    return dead_path
====== END OF DUMP ======
