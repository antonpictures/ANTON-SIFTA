import time
from body_state import parse_body_state

class QuorumNode:
    def __init__(self, node_id, threshold=3):
        self.node_id = node_id
        self.threshold = threshold
        self.payload_ledger = {} 

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
        if payload_hash not in self.payload_ledger:
            self.payload_ledger[payload_hash] = set()
        
        self.payload_ledger[payload_hash].add(agent_id)
        cluster_size = len(self.payload_ledger[payload_hash])

        print(f"[ARRIVAL] Agent {agent_id} arrived carrying payload {payload_hash}. Cluster size: {cluster_size}/{self.threshold}")

        if cluster_size >= self.threshold:
            print(f"[QUORUM REACHED] Superbot formed. Executing Payload {payload_hash}.")
            return True
        return False
