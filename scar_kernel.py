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
            
            # Check if this proposal matches the fossil
            new_hash = hashlib.sha256(content.encode()).hexdigest()
            if new_hash != expected_hash:
                raise Exception("FOSSIL CORRUPTION DETECTED: Incoming proposal conflicts with fossilized target.")
                
            self._log("FOSSIL_REPLAY", sid, target)
            return sid

        # Make sure scar identity corresponds strictly to its semantics (content)
        sid = content_addressed_id(target, content)
        
        # If the exact same repair was already proposed (still active), return existing sid
        if sid in self.scars:
            return sid
            
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

    # ── Resolve Pareto-Stable Set (Frontier 3) ───────────────────
    def resolve_stable_set(self, sid: str, conflict_evaluator=None):
        """
        Instead of electing a single binary winner for a target,
        this elects a Pareto-stable set of multiple non-conflicting
        proposals.
        """
        scar = self.scars[sid]

        competing = [
            s for s in self.scars.values()
            if s.target == scar.target and s.state in ("PROPOSED", "LOCKED")
        ]

        # Use default crude semantic overlap check if none provided
        if conflict_evaluator is None:
            def conflict_evaluator(a: Scar, b: Scar) -> bool:
                # Mock: if one tries to completely overwrite the other's exact string
                return a.content in b.content or b.content in a.content

        # Deterministic ordering before set insertion
        sorted_competing = sorted(competing, key=lambda s: hashlib.sha256(s.scar_id.encode()).hexdigest())
        
        stable_set = []
        for s in sorted_competing:
            # Check if this scar conflicts with ANY already admitted into the stable set
            is_conflicting = any(conflict_evaluator(s, admitted) for admitted in stable_set)
            
            if not is_conflicting:
                stable_set.append(s)
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
            # Reject unknown; in production, request content and
            # verify sha256(target:content)==sid before admitting.
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
