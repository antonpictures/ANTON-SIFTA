# sifta_trust_graph.py
# GEN5 — Trust is no longer scalar (reputation), it's relational (graph)

import sqlite3
import time
from pathlib import Path
from collections import defaultdict

STATE_DIR = Path(".sifta_state")
DB_PATH = STATE_DIR / "task_ledger.db"

def _conn():
    # Ensure directory exists before connecting
    STATE_DIR.mkdir(exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_trust_graph():
    with _conn() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS trust_edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_agent TEXT,
            to_agent TEXT,
            weight REAL,
            last_update REAL
        )
        """)
        conn.commit()


def update_trust(from_agent: str, to_agent: str, delta: float):
    now = time.time()
    with _conn() as conn:
        cur = conn.cursor()

        cur.execute("""
        SELECT weight FROM trust_edges
        WHERE from_agent=? AND to_agent=?
        """, (from_agent, to_agent))

        row = cur.fetchone()

        if row:
            new_weight = max(0.0, min(1.0, row[0] + delta))
            cur.execute("""
            UPDATE trust_edges
            SET weight=?, last_update=?
            WHERE from_agent=? AND to_agent=?
            """, (new_weight, now, from_agent, to_agent))
        else:
            cur.execute("""
            INSERT INTO trust_edges (from_agent, to_agent, weight, last_update)
            VALUES (?, ?, ?, ?)
            """, (from_agent, to_agent, max(0.0, min(1.0, 0.5 + delta)), now))
            # Start at base 0.5 for a neutral new edge + delta

        conn.commit()


def get_trust_score(agent: str) -> float:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("""
        SELECT AVG(weight) FROM trust_edges
        WHERE to_agent=?
        """, (agent,))
        row = cur.fetchone()
        return row[0] if row and row[0] else 0.5


def rank_agents(agent_list):
    scores = {a: get_trust_score(a) for a in agent_list}
    return sorted(agent_list, key=lambda a: scores[a], reverse=True)


# --- INTEGRATION HOOKS ---

def reward_interaction(proposer: str, approver: str):
    update_trust(approver, proposer, +0.05)


def punish_interaction(proposer: str, rejector: str):
    update_trust(rejector, proposer, -0.08)


def handshake(agent_a: str, agent_b: str) -> dict:
    """Explicitly logs a cooperative greeting and relational score."""
    return {
        "type": "HANDSHAKE",
        "from": agent_a,
        "to": agent_b,
        "timestamp": time.time(),
        "trust": get_trust_score(agent_b)
    }


# --- DEBUG ---

if __name__ == "__main__":
    init_trust_graph()

    update_trust("HERMES", "ANTIALICE", 0.1)
    update_trust("M1THER", "ANTIALICE", 0.2)

    print("Trust ANTIALICE:", get_trust_score("ANTIALICE"))
    print("Ranking:", rank_agents(["ANTIALICE", "HERMES", "M1THER"]))
