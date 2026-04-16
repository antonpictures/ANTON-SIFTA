import unittest
import time
from scar_kernel import Kernel, Scar, byzantine_filter

class TestNetworkPartition(unittest.TestCase):
    def test_partition_convergence(self):
        """
        FRONTIER 1: Network Partition & Healing Simulation
        
        Setup:
        - Node A and Node B start fully synchronized.
        - A network partition occurs.
        - Node A and Node B receive DIFFERENT, conflicting proposals for the same target.
        - They each resolve their local state (divergence).
        - The partition heals. They exchange gossip.
        - After merging gossip and re-resolving, they must both converge to the exact same global winner.
        """
        # 1. Initialize two isolated nodes (The Partition)
        node_a = Kernel()
        node_b = Kernel()
        
        target = "server.py"
        
        # 2. Divergent History during partition
        # Node A receives Proposal X
        id_x = node_a.propose(target, "REPAIR_X_PORT_8080")
        node_a.resolve(id_x)
        
        # Node B receives Proposal Y
        id_y = node_b.propose(target, "REPAIR_Y_PORT_9000")
        node_b.resolve(id_y)
        
        # Verify divergence
        winner_a = [s for s in node_a.scars.values() if s.state == "LOCKED"][0]
        winner_b = [s for s in node_b.scars.values() if s.state == "LOCKED"][0]
        self.assertNotEqual(winner_a.scar_id, winner_b.scar_id, "Nodes should be diverged during partition")
        
        # 3. The Partition Heals (Gossip Exchange)
        # Node A shares its known IDs with Node B
        gossip_from_a = set(node_a.scars.keys())
        
        # Node B receives gossip, but can only accept what it can verify (it doesn't have A's content yet)
        # In a real swarm, B would request the missing SCAR files from A. 
        # Here we simulate the successful sync of the underlying .scar files:
        node_b.scars[id_x] = node_a.scars[id_x] # syncing the file
        
        # Node B shares its known IDs with Node A (syncing files)
        node_a.scars[id_y] = node_b.scars[id_y]
        
        # 4. Re-Resolve after sync
        node_a.resolve(id_x)
        node_b.resolve(id_y)
        
        # 5. Verify Convergence
        final_winner_a = [s for s in node_a.scars.values() if s.state == "LOCKED" and s.target == target][0]
        final_winner_b = [s for s in node_b.scars.values() if s.state == "LOCKED" and s.target == target][0]
        
        self.assertEqual(final_winner_a.scar_id, final_winner_b.scar_id, "Nodes did not converge after partition")
        print(f"\n[FRONTIER 1] Partition healed. Both nodes converged on deterministic winner: {final_winner_a.scar_id}")

if __name__ == '__main__':
    unittest.main()
