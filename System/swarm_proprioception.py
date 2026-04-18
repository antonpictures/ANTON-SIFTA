#!/usr/bin/env python3
"""
swarm_proprioception.py — Biological Body Schema (R3)
════════════════════════════════════════════════════════
SIFTA OS — DeepMind Cognitive Suite

Implements the proprioceptive bounding box for the Swarm.
A Swimmer derives its "limbs" from historical PoW receipts.
It must know where its body ends to prevent territorial autoimmune
collisions with other Swimmers during autonomous edits.

Daughter-safe: Read-only memory parsing. Violations emit an append-only
audit row (territorial_violations.jsonl) but do not raise exceptions, 
allowing Architect-overridden cross-pollination if necessary.
"""

import json
import time
from pathlib import Path
from typing import Dict, Set, Union

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_STATE.mkdir(parents=True, exist_ok=True)

RECEIPTS_LOG = _STATE / "work_receipts.jsonl"
VIOLATIONS_LOG = _STATE / "territorial_violations.jsonl"


# ─── C47H 2026-04-18 (R3 audit fix #1): path canonicalization ──────────────
# Real callers pass `Path(__file__).resolve()` which produces an absolute
# path. The receipts ledger stores repo-relative paths (e.g. "Kernel/agent.py").
# Without canonicalization, `is_mine(s, "/abs/.../Kernel/agent.py")` returns
# False even when the receipts say SOCRATES owns "Kernel/agent.py", which
# silently disables the entire bounding-box gate.
def _canonicalize(p: Union[str, Path]) -> Path:
    """
    Normalize any path to the same repo-relative form receipts store.

    • Absolute paths under the repo are stripped to repo-relative.
    • Absolute paths outside the repo are returned as-is (genuine foreign).
    • Leading "./" is stripped.
    • Any other relative path passes through unchanged.
    """
    target = Path(p)
    if target.is_absolute():
        try:
            return target.relative_to(_REPO)
        except ValueError:
            return target
    s = str(target)
    if s.startswith("./"):
        return Path(s[2:])
    return target


class SwarmProprioception:
    def __init__(self):
        self.limbs: Dict[str, Set[Path]] = {}
        self._build_body_map()

    def _build_body_map(self):
        """Scans stigmergic PoW to map the physical territorial body of each Swimmer."""
        self.limbs = {}
        if not RECEIPTS_LOG.exists():
            return

        try:
            for line in RECEIPTS_LOG.read_text("utf-8").splitlines():
                if not line.strip(): continue
                try:
                    row = json.loads(line)
                    agent = row.get("agent_id", "unknown")
                    # "territory" in receipt matches the path they operated on
                    territory = row.get("territory")
                    
                    if agent and territory:
                        if agent not in self.limbs:
                            self.limbs[agent] = set()
                        # C47H R3 audit fix #1: store canonical form so set
                        # membership is path-shape-invariant.
                        self.limbs[agent].add(_canonicalize(territory))
                except Exception: pass
        except Exception:
            pass

    def is_mine(self, swimmer_id: str, path: Union[str, Path]) -> bool:
        """A limb is a file the swimmer has actively modified in the past."""
        target = _canonicalize(path)
        return target in self.limbs.get(swimmer_id, set())

    def is_kin(self, swimmer_id: str, path: Union[str, Path]) -> bool:
        """
        An organ (kin) is a file residing in the exact immediate directory
        of a known limb that is NOT itself a limb of mine and NOT claimed
        by another swimmer. C47H R3 audit fix #2: kin is mutually exclusive
        with mine and foreign; otherwise the three predicates contradict
        each other for any path in a shared parent directory.
        """
        target = _canonicalize(path)
        if self.is_mine(swimmer_id, target):
            return False
        if self.is_foreign(swimmer_id, target):
            return False
        my_limbs = self.limbs.get(swimmer_id, set())
        for limb in my_limbs:
            if limb.parent == target.parent:
                return True
        return False

    def is_foreign(self, swimmer_id: str, path: Union[str, Path]) -> bool:
        """A path is foreign if it explicitly belongs to the limbs of another swimmer and not myself."""
        target = _canonicalize(path)
        
        if self.is_mine(swimmer_id, target):
            return False
            
        for owner, their_limbs in self.limbs.items():
            if owner == swimmer_id: continue
            if target in their_limbs:
                return True
        return False

    def preflight_write(self, swimmer_id: str, path: Union[str, Path]) -> bool:
        """
        The formal bounding box gate. Call this before a swimmer modifies a file.
        Returns True if safe (mine or unclaimed kinship).
        Returns False and emits an audit row if touching foreign territory.
        """
        # Auto-refresh schema in case real-time PoW was emitted
        self._build_body_map()
        
        if self.is_foreign(swimmer_id, path):
            # The agent is triggering an autoimmune reaction. Log the violation.
            try:
                with open(VIOLATIONS_LOG, "a") as f:
                    f.write(json.dumps({
                        "timestamp": time.time(),
                        "swimmer_id": swimmer_id,
                        "territorial_invasion": str(_canonicalize(path)),
                        "warning": "Swarm autoimmune boundary crossed."
                    }) + "\n")
            except Exception: pass
            return False # Foreign
            
        return True # Safe or unclaimed

if __name__ == "__main__":
    # Smoke Test
    print("═" * 58)
    print("  SIFTA — R3: PROPRIOCEPTION SENSORY SMOKE TEST")
    print("═" * 58 + "\n")
    
    import tempfile
    
    # Mocking a pristine ledger context
    _tmp = Path(tempfile.mkdtemp())
    _mock_receipts = _tmp / "work_receipts.jsonl"
    _mock_violations = _tmp / "territorial_violations.jsonl"
    
    _real_receipts = RECEIPTS_LOG
    _real_violations = VIOLATIONS_LOG
    
    RECEIPTS_LOG = _mock_receipts
    VIOLATIONS_LOG = _mock_violations
    
    try:
        with open(RECEIPTS_LOG, "w") as f:
            f.write(json.dumps({"agent_id": "SOCRATES", "territory": "Kernel/agent.py"}) + "\n")
            f.write(json.dumps({"agent_id": "M1THER", "territory": "System/whatsapp_bridge.py"}) + "\n")
            
        schema = SwarmProprioception()
        
        print("Testing SOCRATES bounding box...")
        # 1. is_mine
        assert schema.is_mine("SOCRATES", "Kernel/agent.py") == True, "Limb detection failed."
        # 2. is_kin (same directory as agent.py)
        assert schema.is_kin("SOCRATES", "Kernel/pheromone.py") == True, "Organ kinship detection failed."
        # 3. is_foreign (touching M1THER's limb)
        assert schema.is_foreign("SOCRATES", "System/whatsapp_bridge.py") == True, "Foreign detection failed."
        
        print("Pre-flight write testing...")
        safe_action = schema.preflight_write("SOCRATES", "Kernel/new_script.py")
        assert safe_action == True
        
        unsafe_action = schema.preflight_write("SOCRATES", "System/whatsapp_bridge.py")
        assert unsafe_action == False
        
        # Verify Audit Emit
        if VIOLATIONS_LOG.exists():
            rows = VIOLATIONS_LOG.read_text().splitlines()
            assert len(rows) == 1
            print("Autoimmune violation successfully written to ledger.")
            
        print("\n[SUCCESS] 5/5 Proprioceptive Bounding Box tests passed.")
        print("Result: SIFTA Swimmers now possess physical awareness of their spatial terrain.")
        
    finally:
        import shutil
        shutil.rmtree(_tmp, ignore_errors=True)
        RECEIPTS_LOG = _real_receipts
        VIOLATIONS_LOG = _real_violations
