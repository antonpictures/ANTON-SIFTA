#!/usr/bin/env python3
"""
quorum_sense.py — Bacterial quorum sensing for dangerous OS actions
====================================================================

Before the OS does anything irreversible — kills a process, migrates
an agent, mints a large STGM block — it requires a quorum.

Multiple independent "voter" swimmers must deposit pheromone above a
threshold.  No single agent, no single code path, can unilaterally
make a catastrophic decision.

Protocol:
  1. Proposer calls propose(action_id, action_type, payload)
  2. Independent voters call vote(action_id, voter_id)
  3. When enough votes accumulate, resolve(action_id) returns APPROVED
  4. Proposals expire after TTL seconds without quorum

Persistence: .sifta_state/quorum_proposals.json
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

_STATE_DIR = Path(__file__).resolve().parent.parent / ".sifta_state"
_PROPOSALS_FILE = _STATE_DIR / "quorum_proposals.json"


class ActionType(str, Enum):
    KILL_PROCESS = "kill_process"
    AGENT_MIGRATE = "agent_migrate"
    LARGE_MINT = "large_mint"
    CONFIG_CHANGE = "config_change"
    NODE_SHUTDOWN = "node_shutdown"
    LEDGER_PURGE = "ledger_purge"


QUORUM_THRESHOLDS: dict[str, int] = {
    ActionType.KILL_PROCESS: 2,
    ActionType.AGENT_MIGRATE: 3,
    ActionType.LARGE_MINT: 3,
    ActionType.CONFIG_CHANGE: 2,
    ActionType.NODE_SHUTDOWN: 4,
    ActionType.LEDGER_PURGE: 5,
}

DEFAULT_QUORUM = 3
PROPOSAL_TTL_SEC = 300  # 5 minutes to reach quorum


class QuorumStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    EXPIRED = "expired"
    REJECTED = "rejected"


@dataclass
class Proposal:
    action_id: str
    action_type: str
    payload: dict[str, Any]
    proposer: str
    proposed_at: float
    votes: list[str] = field(default_factory=list)
    status: str = QuorumStatus.PENDING
    resolved_at: float | None = None

    def quorum_needed(self) -> int:
        return QUORUM_THRESHOLDS.get(self.action_type, DEFAULT_QUORUM)

    def has_quorum(self) -> bool:
        return len(set(self.votes)) >= self.quorum_needed()

    def is_expired(self) -> bool:
        return (time.time() - self.proposed_at) > PROPOSAL_TTL_SEC

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Proposal":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


def _load() -> dict[str, Proposal]:
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    if not _PROPOSALS_FILE.exists():
        return {}
    try:
        raw = json.loads(_PROPOSALS_FILE.read_text())
        return {k: Proposal.from_dict(v) for k, v in raw.items()}
    except Exception:
        return {}


def _save(proposals: dict[str, Proposal]) -> None:
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    _PROPOSALS_FILE.write_text(
        json.dumps({k: v.to_dict() for k, v in proposals.items()}, indent=2) + "\n"
    )


def _expire_stale(proposals: dict[str, Proposal]) -> dict[str, Proposal]:
    for p in proposals.values():
        if p.status == QuorumStatus.PENDING and p.is_expired():
            p.status = QuorumStatus.EXPIRED
            p.resolved_at = time.time()
    return proposals


def _action_hash(action_type: str, payload: dict[str, Any]) -> str:
    raw = json.dumps({"type": action_type, **payload}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def propose(
    action_type: str,
    payload: dict[str, Any],
    proposer: str = "ARCHITECT_M5",
) -> Proposal:
    """Create a new proposal. The proposer's vote is automatically counted."""
    proposals = _expire_stale(_load())
    action_id = _action_hash(action_type, payload)

    if action_id in proposals and proposals[action_id].status == QuorumStatus.PENDING:
        return proposals[action_id]

    p = Proposal(
        action_id=action_id,
        action_type=action_type,
        payload=payload,
        proposer=proposer,
        proposed_at=time.time(),
        votes=[proposer],
    )
    proposals[action_id] = p
    _save(proposals)
    return p


def vote(action_id: str, voter_id: str) -> Proposal | None:
    """Cast a vote on an existing proposal. Returns updated proposal or None."""
    proposals = _expire_stale(_load())
    p = proposals.get(action_id)
    if p is None or p.status != QuorumStatus.PENDING:
        return p
    if voter_id not in p.votes:
        p.votes.append(voter_id)
    if p.has_quorum():
        p.status = QuorumStatus.APPROVED
        p.resolved_at = time.time()
    _save(proposals)
    return p


def resolve(action_id: str) -> QuorumStatus:
    """Check if a proposal reached quorum, expired, or is still pending."""
    proposals = _expire_stale(_load())
    _save(proposals)
    p = proposals.get(action_id)
    if p is None:
        return QuorumStatus.EXPIRED
    return QuorumStatus(p.status)


def require_quorum(
    action_type: str,
    payload: dict[str, Any],
    voters: list[str],
    proposer: str = "ARCHITECT_M5",
) -> bool:
    """Convenience: propose + collect all votes + return True if approved.
    Used for synchronous quorum checks (all voters available now)."""
    p = propose(action_type, payload, proposer)
    for v in voters:
        result = vote(p.action_id, v)
        if result and result.status == QuorumStatus.APPROVED:
            return True
    return resolve(p.action_id) == QuorumStatus.APPROVED


def active_proposals() -> list[dict[str, Any]]:
    """Return all non-expired pending proposals for dashboard display."""
    proposals = _expire_stale(_load())
    _save(proposals)
    return [
        {
            "action_id": p.action_id,
            "type": p.action_type,
            "votes": len(set(p.votes)),
            "needed": p.quorum_needed(),
            "status": p.status,
            "age_sec": round(time.time() - p.proposed_at),
        }
        for p in proposals.values()
        if p.status == QuorumStatus.PENDING
    ]


if __name__ == "__main__":
    p = propose(ActionType.LARGE_MINT, {"amount": 100, "reason": "test"}, "ARCHITECT_M5")
    print(f"Proposed: {p.action_id} votes={len(p.votes)}/{p.quorum_needed()} status={p.status}")

    vote(p.action_id, "HERMES")
    vote(p.action_id, "M1THER")
    status = resolve(p.action_id)
    print(f"After 3 votes: {status}")

    approved = require_quorum(
        ActionType.KILL_PROCESS,
        {"pid": 12345, "reason": "runaway"},
        ["HERMES", "ANTIALICE"],
    )
    print(f"Kill process quorum: {approved}")
