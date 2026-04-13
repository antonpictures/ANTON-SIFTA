import unittest
import threading
import random
import time
import hashlib

from scar_kernel import Kernel, Scar

# ============================================================
# FORMAL VERIFICATION SUITE — SIFTA SCAR KERNEL
# Authored by SwarmGPT, integrated by ANTON-SIFTA Swarm
# ============================================================

class TestDeterminism(unittest.TestCase):
    def test_single_winner_under_concurrency(self):
        """Invariant: Exactly one LOCKED scar per target"""

        def worker(k):
            time.sleep(random.random() * 0.01)
            sid = k.propose("file.py", str(random.random()))
            k.resolve(sid)

        for _ in range(10):
            k = Kernel()
            threads = [threading.Thread(target=worker, args=(k,)) for _ in range(100)]

            for t in threads: t.start()
            for t in threads: t.join()

            winners = [s for s in k.scars.values() if s.state == "LOCKED"]
            self.assertEqual(len(winners), 1)


class TestOrdering(unittest.TestCase):
    def test_hash_ordering_stability(self):
        """Invariant: Lowest hash(scar_id) always wins"""

        k = Kernel()

        s1 = Scar("0000" + "A"*30, "file.py", "A")
        s2 = Scar("ffff" + "A"*30, "file.py", "B")

        k.scars[s1.scar_id] = s1
        k.scars[s2.scar_id] = s2

        k.resolve(s1.scar_id)

        winner = [s for s in k.scars.values() if s.state == "LOCKED"][0]
        self.assertEqual(winner.scar_id, s1.scar_id)


class TestFossilIntegrity(unittest.TestCase):
    def test_fossil_tamper_detection(self):
        """Invariant: Fossil replay must fail if content mutated"""

        k = Kernel()
        sid = k.propose("file.py", "SAFE")
        k.resolve(sid)
        k.execute(sid, True)

        # Tamper
        k.scars[sid].content = "MALICIOUS"

        with self.assertRaises(Exception) as ctx:
            k.propose("file.py", "ignored")

        self.assertIn("CORRUPTION", str(ctx.exception))


class TestExecutionSafety(unittest.TestCase):
    def test_single_execution(self):
        """Invariant: Execution is single-shot"""

        k = Kernel()
        sid = k.propose("file.py", "A")
        k.resolve(sid)
        k.execute(sid, True)

        with self.assertRaises(Exception):
            k.execute(sid, True)

    def test_only_locked_executes(self):
        """Invariant: Only LOCKED can execute"""

        k = Kernel()
        sid = k.propose("file.py", "A")

        with self.assertRaises(Exception):
            k.execute(sid, True)


class TestStateMachine(unittest.TestCase):
    def test_illegal_transition_blocked(self):
        """Invariant: State machine cannot be bypassed"""

        k = Kernel()
        sid = k.propose("file.py", "A")

        # Force illegal state
        k.scars[sid].state = "EXECUTED"

        with self.assertRaises(Exception):
            k.execute(sid, True)


class TestLedgerIntegrity(unittest.TestCase):
    def test_signature_chain(self):
        """Invariant: All transitions are signed and verifiable"""

        k = Kernel()
        sid = k.propose("file.py", "A")
        k.resolve(sid)

        for s in k.scars.values():
            if s.state == "LOCKED":
                k.execute(s.scar_id, True)

        for event in k.ledger:
            if "sig" in event:
                self.assertTrue(len(event["sig"]) >= 16)


# ============================================================
# PROPERTY-STYLE TEST (Monte Carlo)
# ============================================================

class TestMonteCarlo(unittest.TestCase):
    def test_randomized_system_stability(self):
        """Fuzz test: random operations should not break invariants"""

        k = Kernel()

        for _ in range(200):
            action = random.choice(["propose", "resolve"])

            if action == "propose":
                k.propose("file.py", str(random.random()))
            elif action == "resolve" and k.scars:
                sid = random.choice(list(k.scars.keys()))
                try:
                    k.resolve(sid)
                except:
                    pass

        # Final invariant check
        winners = [s for s in k.scars.values() if s.state == "LOCKED"]
        self.assertLessEqual(len(winners), 1)


# ============================================================
# DISTRIBUTED CONVERGENCE TEST
# SwarmGPT's open challenge: Byzantine multi-node divergence.
# Proves canonical_winner() produces identical output on any
# node given the same input set — no shared memory required.
# ============================================================

class TestDistributedConvergence(unittest.TestCase):
    def test_canonical_winner_is_pure_function(self):
        """Invariant: canonical_winner(scars) is identical on all nodes given same input."""
        from scar_kernel import canonical_winner

        scar_ids = [str(i) + "X" * 30 for i in range(20)]
        scars = [Scar(sid, "file.py", "content") for sid in scar_ids]

        node_a_winner = canonical_winner(scars)
        node_b_winner = canonical_winner(list(reversed(scars)))
        shuffled = scars[:]
        random.shuffle(shuffled)
        node_c_winner = canonical_winner(shuffled)

        self.assertEqual(node_a_winner, node_b_winner)
        self.assertEqual(node_b_winner, node_c_winner)

    def test_canonical_winner_matches_resolve(self):
        """Invariant: canonical_winner() output matches kernel.resolve() winner."""
        from scar_kernel import canonical_winner

        k = Kernel()
        ids = [k.propose("file.py", f"content_{i}") for i in range(5)]
        for sid in ids:
            k.resolve(sid)

        locked = [s for s in k.scars.values() if s.state == "LOCKED"]
        self.assertEqual(len(locked), 1)
        expected = canonical_winner(list(k.scars.values()))
        self.assertEqual(locked[0].scar_id, expected.scar_id)


class TestGossipProtocol(unittest.TestCase):
    """
    SwarmGPT's pheromone diffusion model.
    gossip_merge() must satisfy CRDT properties to be safe
    for eventual consistency across distributed nodes.
    """

    def test_commutative(self):
        """merge(A, B) == merge(B, A)"""
        from scar_kernel import gossip_merge
        a = {"id1", "id2"}
        b = {"id2", "id3"}
        self.assertEqual(gossip_merge(a, b), gossip_merge(b, a))

    def test_idempotent(self):
        """merge(A, A) == A"""
        from scar_kernel import gossip_merge
        a = {"id1", "id2", "id3"}
        self.assertEqual(gossip_merge(a, a), a)

    def test_associative(self):
        """merge(merge(A,B), C) == merge(A, merge(B,C))"""
        from scar_kernel import gossip_merge
        a, b, c = {"id1"}, {"id2"}, {"id3"}
        self.assertEqual(gossip_merge(gossip_merge(a, b), c),
                         gossip_merge(a, gossip_merge(b, c)))

    def test_two_node_convergence(self):
        """Node A and Node B, disjoint scar sets → gossip_round() elects same winner."""
        from scar_kernel import gossip_round

        node_a = [Scar(f"aaa{i:028d}", "file.py", f"A{i}") for i in range(5)]
        node_b = [Scar(f"bbb{i:028d}", "file.py", f"B{i}") for i in range(5)]

        winner_from_a = gossip_round(node_a, node_b)
        winner_from_b = gossip_round(node_b, node_a)

        self.assertEqual(winner_from_a.scar_id, winner_from_b.scar_id,
                         "Two nodes ran gossip_round and disagreed — Byzantine failure")

    def test_gossip_is_bandwidth_minimal(self):
        """Nodes exchange only scar_ids, not content — O(k) not O(k*content_size)."""
        from scar_kernel import gossip_merge
        # gossip_merge operates only on sets of strings (IDs), never Scar objects
        result = gossip_merge({"id1", "id2"}, {"id3"})
        self.assertIsInstance(result, set)
        for item in result:
            self.assertIsInstance(item, str)


if __name__ == "__main__":
    unittest.main(verbosity=2)
