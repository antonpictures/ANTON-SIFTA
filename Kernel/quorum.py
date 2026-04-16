import time
import sqlite3
from pathlib import Path
from body_state import parse_body_state

DB_PATH = Path(".sifta_state/quorum_ledger.db")

class QuorumNode:
    def __init__(self, node_id, threshold=3):
        self.node_id = node_id
        self.threshold = threshold
        
        DB_PATH.parent.mkdir(exist_ok=True)
        # Connect to SQLite for true distributed persistence
        self.conn = sqlite3.connect(DB_PATH)
        self.cursor = self.conn.cursor()
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS payloads (
                hash TEXT, 
                agent_id TEXT, 
                PRIMARY KEY(hash, agent_id)
            )
        ''')
        self.conn.commit()

    def process_arrival(self, agent_body, payload_hash):
        import re
        agent_id_match = re.search(r"::ID\[([\w\-]+)\]", agent_body)
        agent_id = agent_id_match.group(1) if agent_id_match else "UNKNOWN"
        state = parse_body_state(agent_body)

        # 1. BIODEGRADE CHECK (The Reaper)
        if int(time.time()) > state["ttl"]:
            print(f"[CEMETERY] Agent {agent_id} degraded on arrival (TTL expired). Purging.")
            return False

        # 2. SUPERBOT CLUSTER (Consensus)
        self.cursor.execute('INSERT OR IGNORE INTO payloads (hash, agent_id) VALUES (?, ?)', (payload_hash, agent_id))
        self.conn.commit()
        
        self.cursor.execute('SELECT COUNT(agent_id) FROM payloads WHERE hash = ?', (payload_hash,))
        cluster_size = self.cursor.fetchone()[0]

        print(f"[ARRIVAL] Agent {agent_id} arrived carrying payload {payload_hash}. Cluster size: {cluster_size}/{self.threshold}")

        if cluster_size >= self.threshold:
            print(f"[QUORUM REACHED] Superbot formed. Executing Payload {payload_hash}.")
            return True
        return False
