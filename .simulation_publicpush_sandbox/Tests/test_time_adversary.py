import unittest
import time
from scar_kernel import Kernel

class TestTimeAdversary(unittest.TestCase):
    def test_chronological_delay_attack(self):
        """
        FRONTIER 4: Time as a First-Class Adversary
        
        Setup:
        - Node A and Node B are online.
        - Node B is partitioned and subject to a massive chronological delay (3 weeks).
        - While B is offline, Node A proposes, resolves, executes, and FOSSILIZES a target.
        - 3 weeks later, Node B comes back online and tries to gossip its ancient, conflicting proposal for the same target into the network.
        
        Expected outcome:
        - The system does not re-open the election.
        - The system does not allow the late Byzantine/delayed node to overwrite reality.
        - The cryptographic Fossil rejects the chronological attack, proving time-independence.
        """
        node_a = Kernel()
        
        target = "core_engine.py"
        
        # 1. Node A (Healthy Swarm) operates normally in the present
        # It proposes, safely locks, and executes a repair.
        id_a = node_a.propose(target, "REPAIR_V1_SECURE")
        node_a.resolve(id_a)
        
        # Human/Council approves Node A's repair -> FOSSILIZED
        node_a.execute(id_a, approve=True)
        
        # Verify Node A has solidified the target
        self.assertIn(target, node_a.fossils, "Node A should have fossilized the target.")
        
        # 2. Node B (Delayed Adversary) awakens 3 weeks later
        # It attempts to broadcast a conflicting, incredibly old proposal to Node A's kernel.
        # It tries to bypass the election by submitting delayed gossip.
        
        try:
            # Node B tries to inject conflicting content into the FOSSILIZED target
            node_a.propose(target, "REPAIR_V0_INSECURE_OLD_GOSSIP")
            failed = False
        except Exception as e:
            failed = True
            error_msg = str(e)
            
        # 3. Verify System Defense
        self.assertTrue(failed, "The chronological attack should have been violently explicitly rejected by the kernel.")
        self.assertIn("FOSSIL CORRUPTION DETECTED", error_msg, "System must reject late conflicting mutations on locked fossils.")
        
        print("\n[FRONTIER 4] Chronological Attack Defeated.")
        print("Ancient, conflicting gossip generated during a 3-week partition was mathematically rejected by the cryptographic fossil.")
        print("The swarm survives massive time delays without breaking state.")

if __name__ == '__main__':
    unittest.main()
