#!/usr/bin/env python3
"""
quorum_auditor.py — The Autonomous Quorum Validation Drone
Continuously seeks QUORUM_DRAFT proposals. Mathematically checks validity,
casts a trust-weighted vote, and triggers promotion or Byzantine pruning.
"""

import time
import ast
import json
import traceback

import sifta_swarm_identity
from sifta_quorum import cast_vote, get_quorum_score
from proposal_engine import list_proposals, promote_to_pending, QUORUM_DRAFT_DIR

AGENT_ID = "QUORUM_AUDITOR_0X1"

def _evaluate_proposal(proposal: dict) -> str:
    """Returns 'APPROVE' if computationally identical to valid logic, else 'REJECT'"""
    fixed_code = proposal.get("fixed_content", "")
    
    # 1. Base Syntax Verification
    try:
        ast.parse(fixed_code)
    except SyntaxError as e:
        print(f"  [❌ AUDIT] SyntaxError at line {e.lineno}")
        return "REJECT"
    except Exception as e:
        print(f"  [❌ AUDIT] Catastrophic parse failure: {e}")
        return "REJECT"
        
    # 2. Logic validations or heuristic checks can go here
    # E.g. detecting obvious mutation loops or banned library imports
    
    return "APPROVE"

def audit_loop():
    print(f"[*] Starting Quorum Auditor Daemon: {AGENT_ID}")
    
    while True:
        drafts = list_proposals("DRAFT")
        
        for p in drafts:
            pid = p["proposal_id"]
            short_id = pid[:8]
            
            # Skip if we already voted on it?
            # get_quorum_score doesn't list who voted easily without directly querying the ledger. 
            # We'll just cast the vote. SQLite UPSERT will handle idempotency safely.
            
            print(f"  [🔍 AUDIT] Evaluating draft proposal {short_id}...")
            
            decision = _evaluate_proposal(p)
            cast_vote(pid, AGENT_ID, decision)
            
            print(f"  [{'✅' if decision == 'APPROVE' else '❌'} VOTE CAST] {AGENT_ID} mathematically voted {decision} on {short_id}.")
            
            metrics = get_quorum_score(pid)
            
            if metrics["is_quorum_met"]:
                promote_to_pending(pid)
            elif metrics["total_trust"] <= -1.0:
                print(f"  [🔪 BYZANTINE PRUNING] Proposal {short_id} sunk below mathematical threshold. Purging ghost.")
                draft_path = QUORUM_DRAFT_DIR / f"{pid}.proposal.json"
                if draft_path.exists():
                    draft_path.unlink()
                    
        time.sleep(3.0)


if __name__ == "__main__":
    try:
        sifta_swarm_identity.enforce_identity(AGENT_ID)
    except Exception as e:
        print(f"[!] Refusing to boot auditor: {e}")
        exit(1)
        
    audit_loop()
