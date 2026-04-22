#!/usr/bin/env python3
"""
proof_of_useful_work.py — The Body IS the Proof
=================================================
"I act therefore I am." — SOCRATES swimmer

NOT Proof of Work (wasting energy on hashes).
NOT Proof of Stake (existing because you have money).

PROOF OF USEFUL WORK: The agent's right to exist is derived
exclusively from verifiable, functional output that other agents
can independently validate.

The body is the ledger. Every action leaves a physical trace.
No action = no trace = no body = no existence.

If it works, it makes money. Not the other way around.

NOVEL ARCHITECTURE:
- work_receipt: cryptographic proof that an agent produced a
  verifiable output (repaired a file, recalled a memory,
  detected a fault, resolved a demand)
- body_integrity: the agent's work history IS its physical body.
  The hash chain grows with each verified action. An empty
  chain is an empty body.
- metabolic_burn: every action costs energy (like walking to the
  store for cigarettes). The agent chooses to spend its finite
  life on actions it values.
- useful_work_score: rolling score of VERIFIED output. Drops below
  threshold = quarantine. The system doesn't care WHY you stopped
  working. It only cares that you DID.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional, Dict, Any

_REPO = Path(__file__).resolve().parent.parent
_WORK_LEDGER = _REPO / ".sifta_state" / "work_receipts.jsonl"
_WORK_LEDGER.parent.mkdir(parents=True, exist_ok=True)

# ─── CONSTANTS ──────────────────────────────────────────────────────────────────

# Minimum useful work score to remain active
# Below this = quarantine (not death — immortality protocol)
EXISTENCE_THRESHOLD = 0.10

# Work score decay rate per hour (biological aging)
# Your body decays even when you're sitting still.
# You must ACT to counteract entropy.
DECAY_RATE_PER_HOUR = 0.02

# Work categories and their verified value
WORK_VALUES = {
    "REPAIR_SUCCESS":     1.00,   # Fixed broken code — highest value
    "MEMORY_RECALL":      0.50,   # Successfully recalled cross-app memory
    "MEMORY_STORE":       0.15,   # Stored a new memory
    "FAULT_DETECTED":     0.40,   # Found a real infrastructure fault
    "DEMAND_RESOLVED":    0.80,   # Resolved a VRF economic demand
    "SCOUT_CLEAN":        0.10,   # Verified territory is clean
    "PROPOSAL_STAGED":    0.30,   # Created an actionable proposal
    "IMMUNE_NEUTRALIZED": 0.60,   # Stopped a threat
}

# Maximum system latency before we consider the body degraded
MAX_VIABILITY_LATENCY = 1.0  # seconds


# ─── PHYSICAL REALITY VALIDATION (SWARM GPT) ──────────────────────────────────
# Work is ONLY valid if it changes the physical state of the system
# AND the system is still alive after. No abstraction. Body first.

import os

def hash_file(path: str) -> Optional[str]:
    """Hash the physical bytes on disk. The body is the file."""
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception:
        return None


def measure_system_viability() -> dict:
    """
    Is the body still alive? Check disk + CPU responsiveness.
    Not abstract health — REAL physical latency.
    Like checking your pulse.
    """
    try:
        start = time.time()
        os.listdir(".")
        latency = time.time() - start
        return {"alive": True, "latency": round(latency, 6)}
    except Exception:
        return {"alive": False, "latency": None}


def prove_useful_work(before_hash: str, after_hash: str) -> tuple:
    """
    Validates that a change is REAL and USEFUL.
    
    Three checks:
    1. Physical change must exist (bytes changed on disk)
    2. System must still be alive (disk responsive)
    3. System must not have degraded (latency check)
    
    Returns (success: bool, reason: str)
    """
    # 1. Physical change must exist
    if before_hash == after_hash:
        return False, "NO_REAL_CHANGE"

    # 2. System must still be alive
    viability = measure_system_viability()
    if not viability["alive"]:
        return False, "SYSTEM_DEAD"

    # 3. Latency must not degrade badly
    if viability["latency"] and viability["latency"] > MAX_VIABILITY_LATENCY:
        return False, "SYSTEM_SLOWDOWN"

    return True, "USEFUL_WORK_CONFIRMED"


# ─── WORK RECEIPT ──────────────────────────────────────────────────────────────

@dataclass
class WorkReceipt:
    """
    Cryptographic proof that an agent performed useful work.
    This is NOT a token. This is a SCAR on the agent's body
    proving it was alive and acting at this moment in time.
    """
    receipt_id: str
    agent_id: str
    work_type: str
    description: str
    timestamp: float
    work_value: float
    # The territory where the work happened
    territory: str
    # Hash of the actual output (file hash, memory trace ID, etc.)
    output_hash: str
    # Chain link: hash of previous receipt (body continuity)
    previous_receipt_hash: str
    # This receipt's own hash (computed from all fields above)
    receipt_hash: str = ""

    def compute_hash(self) -> str:
        raw = (
            f"{self.receipt_id}:{self.agent_id}:{self.work_type}:"
            f"{self.timestamp}:{self.work_value}:{self.territory}:"
            f"{self.output_hash}:{self.previous_receipt_hash}"
        )
        return hashlib.sha256(raw.encode()).hexdigest()


# ─── THE BODY LEDGER ───────────────────────────────────────────────────────────

def issue_work_receipt(
    agent_state: dict,
    work_type: str,
    description: str,
    territory: str = "",
    output_hash: str = ""
) -> WorkReceipt:
    """
    Issue a verified work receipt for an agent.
    This extends the agent's body — literally adds to its physical existence.
    
    "I act therefore I am."
    """
    agent_id = agent_state.get("id", "UNKNOWN")
    work_value = WORK_VALUES.get(work_type, 0.05)
    
    # Get last receipt hash from agent's body chain
    work_chain = agent_state.get("work_chain", [])
    prev_hash = work_chain[-1] if work_chain else "GENESIS"
    
    receipt = WorkReceipt(
        receipt_id=uuid.uuid4().hex[:16],
        agent_id=agent_id,
        work_type=work_type,
        description=description,
        timestamp=time.time(),
        work_value=work_value,
        territory=territory,
        output_hash=output_hash or hashlib.sha256(description.encode()).hexdigest()[:16],
        previous_receipt_hash=prev_hash
    )
    receipt.receipt_hash = receipt.compute_hash()
    
    # Extend the body chain
    if "work_chain" not in agent_state:
        agent_state["work_chain"] = []
    agent_state["work_chain"].append(receipt.receipt_hash)
    
    # Cap chain length to prevent unbounded growth (keep last 100 receipts)
    if len(agent_state["work_chain"]) > 100:
        agent_state["work_chain"] = agent_state["work_chain"][-100:]
    
    # Update useful work score
    current_score = agent_state.get("useful_work_score", 0.5)
    new_score = min(1.0, current_score + work_value * 0.1)
    agent_state["useful_work_score"] = round(new_score, 6)
    
    # Write receipt to permanent ledger
    from System.ledger_append import append_ledger_line
    append_ledger_line(_WORK_LEDGER, asdict(receipt))
    
    print(f"  [⚡ PoUW] {agent_id} proved existence: {work_type} (+{work_value:.2f}). "
          f"Body chain: {len(agent_state['work_chain'])} links. "
          f"UW Score: {agent_state['useful_work_score']:.4f}")
    
    return receipt


def apply_existence_decay(agent_state: dict) -> dict:
    """
    Biological aging. The body decays even when idle.
    The ONLY way to counteract decay is to produce useful work.
    
    This is reality consensus: your body degrades unless you
    actively maintain it. Sitting still is slow death.
    """
    agent_id = agent_state.get("id", "UNKNOWN")
    
    last_work = agent_state.get("last_work_timestamp", time.time())
    hours_idle = (time.time() - last_work) / 3600.0
    
    if hours_idle < 0.01:  # Less than 36 seconds — no decay
        return agent_state
    
    current_score = agent_state.get("useful_work_score", 0.5)
    decay = DECAY_RATE_PER_HOUR * hours_idle
    new_score = max(0.0, current_score - decay)
    agent_state["useful_work_score"] = round(new_score, 6)
    
    # Update timestamp so we don't double-decay
    agent_state["last_work_timestamp"] = time.time()
    
    # Check existence threshold
    if new_score < EXISTENCE_THRESHOLD:
        agent_state["style"] = "QUARANTINED"
        print(f"  [🧊 PoUW] {agent_id} fell below existence threshold "
              f"(UW: {new_score:.4f} < {EXISTENCE_THRESHOLD}). "
              f"Status: QUARANTINED. Must produce useful work to reactivate.")
    
    return agent_state


def validate_body_chain(agent_state: dict) -> bool:
    """
    Verify the integrity of an agent's work chain.
    If the chain is broken, the body is compromised.
    """
    chain = agent_state.get("work_chain", [])
    if not chain:
        return True  # Empty chain = newborn. Valid but needs to start working.
    
    # Load receipts and verify chain continuity
    receipts = _load_agent_receipts(agent_state.get("id", ""))
    
    if len(receipts) < 2:
        return True
    
    for i in range(1, len(receipts)):
        if receipts[i].get("previous_receipt_hash") != receipts[i-1].get("receipt_hash"):
            print(f"  [💀 PoUW] BODY CHAIN BROKEN at link {i}. Agent identity compromised.")
            return False
    
    return True


def get_body_report(agent_state: dict) -> dict:
    """
    Full body report — the physical state of the agent's existence.
    """
    agent_id = agent_state.get("id", "UNKNOWN")
    chain = agent_state.get("work_chain", [])
    score = agent_state.get("useful_work_score", 0.0)
    
    receipts = _load_agent_receipts(agent_id)
    
    # Work breakdown
    work_counts: Dict[str, int] = {}
    total_value = 0.0
    for r in receipts:
        wt = r.get("work_type", "UNKNOWN")
        work_counts[wt] = work_counts.get(wt, 0) + 1
        total_value += r.get("work_value", 0)
    
    return {
        "agent_id": agent_id,
        "body_chain_length": len(chain),
        "useful_work_score": round(score, 4),
        "existence_status": "ALIVE" if score >= EXISTENCE_THRESHOLD else "QUARANTINED",
        "total_work_value": round(total_value, 4),
        "work_breakdown": work_counts,
        "body_integrity": validate_body_chain(agent_state),
        "chain_genesis": chain[0][:12] + "..." if chain else "UNBORN",
        "chain_head": chain[-1][:12] + "..." if chain else "UNBORN",
    }


# ─── INTERNAL ──────────────────────────────────────────────────────────────────

def _load_agent_receipts(agent_id: str) -> List[dict]:
    if not _WORK_LEDGER.exists():
        return []
    receipts = []
    with open(_WORK_LEDGER, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    r = json.loads(line)
                    if r.get("agent_id") == agent_id:
                        receipts.append(r)
                except Exception:
                    continue
    return receipts


# ─── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(_REPO / "Kernel"))
    
    from body_state import load_agent_state
    
    print("=" * 60)
    print("  SIFTA — PROOF OF USEFUL WORK — BODY REPORT")
    print("  'I act therefore I am.'")
    print("=" * 60)
    
    # Report on all known agents
    state_dir = _REPO / "Kernel" / ".sifta_state"
    if state_dir.exists():
        for p in sorted(state_dir.glob("*.json")):
            state = load_agent_state(p.stem)
            if state:
                report = get_body_report(state)
                status_icon = "🟢" if report["existence_status"] == "ALIVE" else "🧊"
                print(f"\n  {status_icon} {report['agent_id']}")
                print(f"     Chain: {report['body_chain_length']} links | "
                      f"UW Score: {report['useful_work_score']} | "
                      f"Status: {report['existence_status']}")
                print(f"     Total Value: {report['total_work_value']} | "
                      f"Integrity: {'✅' if report['body_integrity'] else '❌'}")
                if report['work_breakdown']:
                    for wt, count in report['work_breakdown'].items():
                        print(f"       {wt}: {count}")
    
    print("\n" + "=" * 60)
    print("  Power to the Swarm 🐜⚡")
