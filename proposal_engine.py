#!/usr/bin/env python3
"""
proposal_engine.py — The SIFTA Proposal Branch System

Intercepts agent writes and stages them as reviewable proposals
instead of committing directly to live disk.

Properties:
  - No file is modified until a human (or auto-approve policy) says so.
  - Every proposal carries a unified diff, SHA-256 pre/post hashes,
    agent metadata, and confidence scores.
  - Approved proposals are applied atomically via os.replace().
  - Rejected proposals incur reputation penalties.

Directory structure:
  proposals/
    pending/     — awaiting human review
    approved/    — applied to disk, archived
    rejected/    — denied, archived with reason
"""
import difflib
import hashlib
import json
import os
import shutil
import time
import uuid
from pathlib import Path

ROOT_DIR = Path(__file__).parent
PROPOSALS_DIR = ROOT_DIR / "proposals"
QUORUM_DRAFT_DIR = PROPOSALS_DIR / "drafts"
PENDING_DIR = PROPOSALS_DIR / "pending"
APPROVED_DIR = PROPOSALS_DIR / "approved"
REJECTED_DIR = PROPOSALS_DIR / "rejected"

# Ensure directory structure exists
for d in (QUORUM_DRAFT_DIR, PENDING_DIR, APPROVED_DIR, REJECTED_DIR):
    d.mkdir(parents=True, exist_ok=True)


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def write_proposal(
    filepath: Path,
    original_content: str,
    fixed_content: str,
    agent_id: str,
    bite_start: int,
    bite_end: int,
    error_description: str = "",
    confidence: float = 1.0,
    model: str = "",
    vocation: str = "",
) -> dict:
    """
    Stage a repair as a proposal instead of writing directly to disk.
    Returns the proposal record.
    """
    proposal_id = str(uuid.uuid4())
    pre_hash = _sha256(original_content)
    post_hash = _sha256(fixed_content)

    # Layer 4: Conflict Resolution Protocol / Oscillation Defense
    import reputation_engine
    rep = reputation_engine.get_reputation(agent_id).get("score", 0.0)
    recent_fixes = 0
    now = time.time()
    for approved_path in APPROVED_DIR.glob("*.proposal.json"):
        try:
            with open(approved_path, "r", encoding="utf-8") as af:
                ap = json.load(af)
                if ap.get("filepath") == str(filepath.absolute()) and (now - ap.get("approved_at", 0)) < 3600:
                    recent_fixes += 1
        except Exception:
            continue
            
    if recent_fixes >= 2 and rep < 0.9 and agent_id != "CONSIGLIERE":
        raise RuntimeError(
            f"[CONTAMINATED_LOCK] {filepath.name} is oscillating too rapidly "
            f"({recent_fixes} fixes in 1h). Agent reputation {rep:.2f} < 0.90 required to override."
        )


    # Generate unified diff
    original_lines = original_content.splitlines(keepends=True)
    fixed_lines = fixed_content.splitlines(keepends=True)
    diff = list(difflib.unified_diff(
        original_lines, fixed_lines,
        fromfile=f"a/{filepath.name}",
        tofile=f"b/{filepath.name}",
        lineterm=""
    ))
    diff_text = "\n".join(diff)

    proposal = {
        "proposal_id": proposal_id,
        "status": "DRAFT",  # GEN6 modification: goes to draft until BFT Quorum
        "created_at": time.time(),
        "filepath": str(filepath.absolute()),
        "filename": filepath.name,
        "agent_id": agent_id,
        "model": model,
        "vocation": vocation,
        "confidence": confidence,
        "error_description": error_description,
        "bite_region": {"start": bite_start, "end": bite_end},
        "pre_hash": pre_hash,
        "post_hash": post_hash,
        "diff": diff_text,
        "original_content": original_content,
        "fixed_content": fixed_content,
    }

    import sifta_identity_context
    try:
        proposal = sifta_identity_context.inject_identity(proposal)
    except:
        pass
        
    proposal_path = QUORUM_DRAFT_DIR / f"{proposal_id}.proposal.json"
    tmp_path = proposal_path.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(proposal, f, indent=2)
    os.replace(tmp_path, proposal_path)

    print(f"  [📋 PROPOSAL] Staged proposal {proposal_id[:8]}... for {filepath.name}")
    print(f"  [📋 PROPOSAL] Agent: {agent_id} | Confidence: {confidence:.2f} | Diff: {len(diff)} lines")

    return proposal


def list_proposals(status: str = "PENDING") -> list[dict]:
    """List all proposals with a given status."""
    status = status.upper()
    dir_map = {
        "DRAFT": QUORUM_DRAFT_DIR,
        "PENDING": PENDING_DIR,
        "APPROVED": APPROVED_DIR,
        "REJECTED": REJECTED_DIR,
    }
    target_dir = dir_map.get(status, PENDING_DIR)

    proposals = []
    for p in target_dir.glob("*.proposal.json"):
        try:
            with open(p, "r", encoding="utf-8") as f:
                proposals.append(json.load(f))
        except Exception:
            continue

    # Sort by created_at descending (newest first)
    proposals.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return proposals


def get_proposal(proposal_id: str) -> "dict | None":
    """Find a proposal by ID across all status directories."""
    for d in (QUORUM_DRAFT_DIR, PENDING_DIR, APPROVED_DIR, REJECTED_DIR):
        path = d / f"{proposal_id}.proposal.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    return None


def promote_to_pending(proposal_id: str) -> bool:
    """
    Evaluates Trust Quorum. If consensus met, promotes DRAFT to PENDING.
    """
    import sifta_quorum
    if not sifta_quorum.check_consensus(proposal_id):
        return False
        
    source = QUORUM_DRAFT_DIR / f"{proposal_id}.proposal.json"
    if not source.exists():
        return False
        
    with open(source, "r", encoding="utf-8") as f:
        proposal = json.load(f)
        
    proposal["status"] = "PENDING"
    
    dest = PENDING_DIR / f"{proposal_id}.proposal.json"
    tmp_path = dest.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(proposal, f, indent=2)
    os.replace(tmp_path, dest)
    source.unlink()
    
    print(f"  [🔓 QUORUM MET] Proposal {proposal_id[:8]}... promoted to PENDING for human review.")
    try:
        from sifta_postcard import write_postcard
        write_postcard(
            f"Quorum consensus unlocked proposal {proposal_id[:8]}... for Architect review.",
            {"proposal_id": proposal_id}
        )
    except Exception:
        pass
    return True


def approve_proposal(proposal_id: str) -> dict:
    """
    Apply a pending proposal to the live filesystem.
    Moves the proposal to approved/ after successful application.
    """
    import reputation_engine

    source = PENDING_DIR / f"{proposal_id}.proposal.json"
    if not source.exists():
        raise FileNotFoundError(f"Proposal {proposal_id} not found in pending.")

    with open(source, "r", encoding="utf-8") as f:
        proposal = json.load(f)

    filepath = Path(proposal["filepath"])
    if not filepath.exists():
        # Ghost proposal: the file no longer exists physically. Auto-reject to clear the UI.
        reject_proposal(proposal_id, reason="Auto-rejected: Target physical file no longer exists.")
        raise FileNotFoundError(f"Target file {filepath.name} no longer exists. SIFTA auto-purged the pending proposal.")

    # Verify pre-hash still matches (no external modification since proposal)
    current_content = filepath.read_text(encoding="utf-8")
    current_hash = _sha256(current_content)
    if current_hash != proposal["pre_hash"]:
        raise RuntimeError(
            f"[PROPOSAL] File {filepath.name} has been modified since proposal was created. "
            f"Expected hash {proposal['pre_hash'][:16]}..., got {current_hash[:16]}... "
            f"Re-run the swimmer to generate a fresh proposal."
        )

    # Apply the fix atomically
    tmp_path = filepath.with_suffix(".proposal_tmp")
    tmp_path.write_text(proposal["fixed_content"], encoding="utf-8")
    os.replace(tmp_path, filepath)

    # Update proposal status
    proposal["status"] = "APPROVED"
    proposal["approved_at"] = time.time()
    dest = APPROVED_DIR / f"{proposal_id}.proposal.json"
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(proposal, f, indent=2)
    source.unlink()

    # Drop a RESOLVED scar (best effort — don't block approval if pheromone has issues)
    try:
        import pheromone
        mark_cwd = filepath.parent
        pheromone.drop_scar(
            directory=mark_cwd,
            agent_state={"id": proposal["agent_id"], "raw": ""},
            action="PROPOSAL_APPROVED",
            found=proposal.get("error_description", ""),
            status="RESOLVED",
            mark_text=f"Proposal {proposal_id[:8]}... approved and applied to {filepath.name}.",
            reason={"type": "ProposalApproved", "message": "Human-gated approval."},
            pre_territory_hash=proposal["pre_hash"],
            post_territory_hash=proposal["post_hash"],
        )
    except Exception as e:
        print(f"  [SCAR] Could not drop approval scar: {e}")

    # Reputation boost & Trust network mapping
    reputation_engine.update_reputation(proposal["agent_id"], "SUCCESS")
    try:
        from sifta_trust_graph import reward_interaction
        reward_interaction(proposal["agent_id"], "ARCHITECT")
    except Exception:
        pass
    try:
        from sifta_postcard import write_postcard
        write_postcard(
            f"Approved repair of {filepath.name} after quorum validation.",
            {"proposal_id": proposal_id, "agent": proposal["agent_id"], "file": filepath.name}
        )
    except Exception:
        pass

    print(f"  [✅ APPROVED] Proposal {proposal_id[:8]}... applied to {filepath.name}")
    return proposal


def reject_proposal(proposal_id: str, reason: str = "Rejected by operator") -> dict:
    """
    Reject a pending proposal. Does NOT modify any file.
    Moves to rejected/ and applies a reputation penalty.
    """
    import reputation_engine

    source = PENDING_DIR / f"{proposal_id}.proposal.json"
    if not source.exists():
        raise FileNotFoundError(f"Proposal {proposal_id} not found in pending.")

    with open(source, "r", encoding="utf-8") as f:
        proposal = json.load(f)

    proposal["status"] = "REJECTED"
    proposal["rejected_at"] = time.time()
    proposal["rejection_reason"] = reason

    dest = REJECTED_DIR / f"{proposal_id}.proposal.json"
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(proposal, f, indent=2)
    source.unlink()

    # Penalty and Trust degradation
    reputation_engine.update_reputation(proposal["agent_id"], "FAILURE")
    try:
        from sifta_trust_graph import punish_interaction
        punish_interaction(proposal["agent_id"], "ARCHITECT")
    except Exception:
        pass

    print(f"  [❌ REJECTED] Proposal {proposal_id[:8]}... discarded. Reason: {reason}")
    return proposal


def auto_approve_check(proposal: dict, reputation_threshold: float = 0.85) -> bool:
    """
    Check if a proposal qualifies for auto-approval based on agent reputation.
    Returns True if the proposal should be auto-approved.
    """
    import reputation_engine

    rep = reputation_engine.get_reputation(proposal["agent_id"])
    score = rep.get("score", 0.0)
    confidence = proposal.get("confidence", 0.0)

    # Both reputation AND confidence must be high
    return score >= reputation_threshold and confidence >= 0.9


def proposal_stats() -> dict:
    """Summary counts for the dashboard."""
    return {
        "pending": len(list(PENDING_DIR.glob("*.proposal.json"))),
        "approved": len(list(APPROVED_DIR.glob("*.proposal.json"))),
        "rejected": len(list(REJECTED_DIR.glob("*.proposal.json"))),
    }
