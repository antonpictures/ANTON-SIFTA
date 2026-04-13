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
        self.fossils: Dict[str, str] = {}  # target → scar_id
        self.ledger: List[dict] = []

    # ── Deterministic Conflict Domain ────────────────────────
    def conflict_key(self, target: str) -> str:
        return hashlib.sha256(target.encode()).hexdigest()[:16]

    # ── Propose ─────────────────────────────────────────────
    def propose(self, target: str, content: str) -> str:
        # Fossil fast-path
        if target in self.fossils:
            sid = self.fossils[target]
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

        self.fossils[scar.target] = sid

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
