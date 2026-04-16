import unittest
from scar_kernel import Kernel, Scar

class TestStableSetConvergence(unittest.TestCase):
    def test_pareto_stable_set(self):
        """
        FRONTIER 3: Stable Set Convergence
        
        Setup:
        - We have 3 independent agents (Claude, Nemotron, Antigravity) running on the same Swarm.
        - They all observe the same target (sifta_kernel.py) and propose a fix.
        - The proposals are technically on the same target, but computationally NON-CONFLICTING.
        - Instead of forcing exactly 1 winner (which wastes computation), the swarm elects a Pareto-stable set containing all valid non-conflicting proposals.
        """
        kernel = Kernel()
        
        target = "sifta_kernel.py"
        
        # Node A (Claude) proposes a fix
        id_claude = kernel.propose(target, "[CLAUDE] Added hardware serial to hash context")
        
        # Node B (Nemotron) proposes insight logging
        id_nemotron = kernel.propose(target, "[NEMOTRON] Added code immutability vs narrative log")
        
        # Node C (Antigravity/Gemini) proposes identity unification
        id_antigravity = kernel.propose(target, "[ANTIGRAVITY] Unify identifiers to content-addressed ID")
        
        # We define a strict semantic conflict evaluator: 
        # Two proposals conflict ONLY if they are trying to insert the exact same change,
        # or if one directly overwrites the other. For these 3 unique insights, they do not conflict.
        def non_conflicting_evaluator(a: Scar, b: Scar) -> bool:
            return a.content == b.content # Only conflict if exact duplicate
            
        # The swarm resolves the stable set
        kernel.resolve_stable_set(id_claude, conflict_evaluator=non_conflicting_evaluator)
        kernel.resolve_stable_set(id_nemotron, conflict_evaluator=non_conflicting_evaluator)
        kernel.resolve_stable_set(id_antigravity, conflict_evaluator=non_conflicting_evaluator)
        
        # Verify Convergence: ALL THREE should emerge as winners, without breaking system invariants.
        winners = [s for s in kernel.scars.values() if s.state == "LOCKED" and s.target == target]
        
        self.assertEqual(len(winners), 3, "The swarm failed to construct a stable set of 3 winners.")
        
        print("\n[FRONTIER 3] Stable Set Convergence Successful.")
        print(f"The environment emerged with {len(winners)} simultaneous non-conflicting winners:")
        for w in winners:
            print(f" - {w.content}")


if __name__ == '__main__':
    unittest.main()
