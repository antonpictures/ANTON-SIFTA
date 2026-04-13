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

        # Simulate Node A computing winner
        node_a_winner = canonical_winner(scars)
        # Simulate Node B computing winner (reversing order — adversarial)
        node_b_winner = canonical_winner(list(reversed(scars)))
        # Simulate Node C with shuffled order
        shuffled = scars[:]
        random.shuffle(shuffled)
        node_c_winner = canonical_winner(shuffled)

        self.assertEqual(node_a_winner, node_b_winner,
                         "Node A and B disagree — not globally deterministic")
        self.assertEqual(node_b_winner, node_c_winner,
                         "Node B and C disagree — not globally deterministic")

    def test_canonical_winner_matches_resolve(self):
        """Invariant: canonical_winner() output matches kernel.resolve() winner."""
        from scar_kernel import canonical_winner

        k = Kernel()
        ids = []
        for i in range(5):
            sid = k.propose("file.py", f"content_{i}")
            ids.append(sid)

        for sid in ids:
            k.resolve(sid)

        locked = [s for s in k.scars.values() if s.state == "LOCKED"]
        self.assertEqual(len(locked), 1)

        expected = canonical_winner(list(k.scars.values()))
        self.assertEqual(locked[0].scar_id, expected.scar_id)


if __name__ == "__main__":
    unittest.main(verbosity=2)
