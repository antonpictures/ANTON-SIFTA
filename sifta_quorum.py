import sqlite3
import time
from pathlib import Path
from sifta_trust_graph import get_trust_score

STATE_DIR = Path(".sifta_state")
QUORUM_DB = STATE_DIR / "quorum_ledger.db"
QUORUM_THRESHOLD = 1.0  # Trust required to pass

def _conn():
    STATE_DIR.mkdir(exist_ok=True)
    return sqlite3.connect(QUORUM_DB)


def init_quorum_db():
    with _conn() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS quorum_votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proposal_id TEXT,
            agent_id TEXT,
            vote_type TEXT,
            timestamp REAL,
            UNIQUE(proposal_id, agent_id)
        )
        """)
        conn.commit()


def cast_vote(proposal_id: str, agent_id: str, vote_type: str):
    """
    Agent casts a mathematical token ('APPROVE' or 'REJECT').
    Replacing previous votes natively.
    """
    if vote_type not in ("APPROVE", "REJECT"):
        raise ValueError("Vote type must be APPROVE or REJECT.")

    with _conn() as conn:
        conn.execute("""
        INSERT INTO quorum_votes (proposal_id, agent_id, vote_type, timestamp)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(proposal_id, agent_id) DO UPDATE SET 
            vote_type=excluded.vote_type,
            timestamp=excluded.timestamp
        """, (proposal_id, agent_id, vote_type, time.time()))
        conn.commit()


def get_quorum_score(proposal_id: str) -> dict:
    """
    Returns the calculus state of a specific proposal.
    Total Trust = sum(Approvers' Trust) - sum(Rejecters' Trust)
    """
    total_trust = 0.0
    approvers = 0
    rejecters = 0

    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT agent_id, vote_type FROM quorum_votes WHERE proposal_id=?", (proposal_id,))
        rows = cur.fetchall()

    for agent_id, vote_type in rows:
        trust = get_trust_score(agent_id)
        if vote_type == "APPROVE":
            total_trust += trust
            approvers += 1
        elif vote_type == "REJECT":
            total_trust -= trust
            rejecters += 1

    return {
        "total_trust": total_trust,
        "approvers": approvers,
        "rejecters": rejecters,
        "is_quorum_met": total_trust >= QUORUM_THRESHOLD
    }


def check_consensus(proposal_id: str) -> bool:
    """Simple wrapper returning True if mathematical BFT is met."""
    return get_quorum_score(proposal_id)["is_quorum_met"]


if __name__ == "__main__":
    init_quorum_db()
    print("[+] Quorum Ledger DB initialized.")
