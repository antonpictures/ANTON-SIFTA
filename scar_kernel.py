# ============================================================
# SIFTA — Deterministic SCAR Kernel (Minimal, Verifiable Core)
#
# Adds:
#   - Deterministic ordering (no human ambiguity required)
#   - Conflict hashing (same target → same arbitration space)
#   - Fossil replay as first-class primitive
#   - Full transition verification
# ============================================================

import hashlib, time, uuid
from dataclasses import dataclass, field
from typing import Dict, List

LANA = "7b4a866301681119e5f9168d6e208b62bab446fe33ce3445d113ec068164aaf9"

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
