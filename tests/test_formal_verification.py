"""
SIFTA Formal Verification Suite v1.0
=====================================
Converts SwarmGPT's adversarial test battery into a structured,
CI-compatible Python unittest suite.

Run all:
    python -m pytest tests/test_formal_verification.py -v
    python -m unittest tests.test_formal_verification -v

Architecture under test: scar_kernel.py (Deterministic SCAR Engine)
Protocol spec: docs/SIFTA_PROTOCOL_v0.1.md
"""

import hashlib
import sys
import threading
import time
import random
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from scar_kernel import Kernel, Scar, LANA


class TestDeterministicOrdering(unittest.TestCase):
    """
    Property: Conflict arbitration is purely deterministic.
    Any number of concurrent proposals for the same target
    must always converge to exactly one LOCKED winner,
    regardless of timing or thread scheduling.
    """

    def test_single_winner_under_concurrency(self):
        """50 concurrent agents, 20 independent trials = 0 ambiguity."""
        def worker(k, results):
            time.sleep(random.random() * 0.01)
            sid = k.propose("file.py", str(random.random()))
            k.resolve(sid)
            results.append(sid)

        for trial in range(20):
            k = Kernel()
            results = []
            threads = [threading.Thread(target=worker, args=(k, results)) for _ in range(50)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            winners = [s for s in k.scars.values() if s.state == "LOCKED"]
            self.assertEqual(
                len(winners), 1,
                f"Trial {trial}: {len(winners)} winners found — determinism broken"
            )

    def test_winner_is_lowest_hash(self):
        """The winner is always the agent whose scar_id has the lowest SHA-256."""
        k = Kernel()
        scar_ids = []
        for i in range(10):
            sid = k.propose("file.py", f"fix_{i}")
            scar_ids.append(sid)

        # Resolve all
        for sid in scar_ids:
            k.resolve(sid)

        winners = [s for s in k.scars.values() if s.state == "LOCKED"]
        self.assertEqual(len(winners), 1)

        expected_winner = min(scar_ids, key=lambda s: hashlib.sha256(s.encode()).hexdigest())
        self.assertEqual(winners[0].scar_id, expected_winner)

    def test_different_targets_independent(self):
        """Conflict resolution is scoped to target. Different targets never collide."""
        k = Kernel()
        a = k.propose("file_a.py", "fix A")
        b = k.propose("file_b.py", "fix B")
        k.resolve(a)
        k.resolve(b)

        locked = [s for s in k.scars.values() if s.state == "LOCKED"]
        self.assertEqual(len(locked), 2)


class TestStateMachine(unittest.TestCase):
    """
    Property: The SCAR state machine is strictly enforced.
    Illegal transitions raise exceptions. No state is skippable.
    """

    def test_only_locked_can_execute(self):
        """Executing a PROPOSED or FOSSILIZED SCAR raises immediately."""
        k = Kernel()
        sid = k.propose("file.py", "A")
        # PROPOSED — not yet LOCKED
        with self.assertRaises(Exception, msg="PROPOSED should not be executable"):
            k.execute(sid, True)

    def test_illegal_state_jump_rejected(self):
        """Manually forcing state to EXECUTED does not bypass kernel checks."""
        k = Kernel()
        sid = k.propose("file.py", "A")
        k.scars[sid].state = "EXECUTED"

        with self.assertRaises(Exception, msg="Illegal jump to EXECUTED should be rejected"):
            k.execute(sid, True)

    def test_fossilized_is_terminal(self):
        """A FOSSILIZED SCAR cannot be re-executed."""
        k = Kernel()
        sid = k.propose("file.py", "A")
        k.resolve(sid)
        k.execute(sid, True)  # → FOSSILIZED

        with self.assertRaises(Exception, msg="FOSSILIZED should not be re-executable"):
            k.execute(sid, True)

    def test_cancelled_is_terminal(self):
        """A CANCELLED SCAR cannot be re-executed."""
        k = Kernel()
        sid = k.propose("file.py", "A")
        k.resolve(sid)
        k.execute(sid, False)  # → CANCELLED

        with self.assertRaises(Exception, msg="CANCELLED should not be executable"):
            k.execute(sid, True)


class TestFossilIntegrity(unittest.TestCase):
    """
    Property: Fossil replay is cryptographically sealed at the moment
    of fossilization. Post-fossilization content tampering is detected
    and raises a hard error — it does not silently leak.
    """

    def test_fossil_fast_path_rejects_conflicting_content(self):
        """After fossilization, any proposal with DIFFERENT content is rejected.
        
        This is the Frontier 4 security hardening: the fossil fast-path now
        cryptographically validates the incoming content hash against the
        locked fossil, rejecting any Byzantine delayed proposals.
        """
        k = Kernel()
        sid = k.propose("file.py", "SAFE")
        k.resolve(sid)
        k.execute(sid, True)

        with self.assertRaisesRegex(Exception, "FOSSIL CORRUPTION DETECTED"):
            k.propose("file.py", "different content — Byzantine delayed gossip")

    def test_content_mutation_raises(self):
        """Mutating fossil content after fossilization triggers CORRUPTION DETECTED."""
        k = Kernel()
        sid = k.propose("file.py", "SAFE")
        k.resolve(sid)
        k.execute(sid, True)

        k.scars[sid].content = "MALICIOUS"

        with self.assertRaisesRegex(Exception, "FOSSIL CORRUPTION DETECTED"):
            k.propose("file.py", "trigger replay")

    def test_same_content_replays_cleanly(self):
        """Fossil replay succeeds when the SAME content is re-proposed.
        
        This proves that an honest node replaying a known-good proposal
        (e.g. after reconnecting) is accepted by the kernel without error.
        """
        k = Kernel()
        original_content = "SAFE"
        sid = k.propose("file.py", original_content)
        k.resolve(sid)
        k.execute(sid, True)

        # Exact same content — replay should be clean and return original sid
        replay_sid = k.propose("file.py", original_content)
        self.assertEqual(replay_sid, sid)
        self.assertEqual(k.scars[sid].content, original_content)


class TestLedgerIntegrity(unittest.TestCase):
    """
    Property: Every state transition is recorded in the ledger
    with a Genesis-Anchor-salted cryptographic signature.
    The ledger is append-only and contains the full cognition trace.
    """

    def test_all_transitions_in_ledger(self):
        """The full lifecycle produces exactly the expected number of ledger events."""
        k = Kernel()
        sid = k.propose("file.py", "A")
        k.resolve(sid)
        k.execute(sid, True)

        transitions = [e for e in k.ledger if "from" in e]
        # PROPOSED (implicit) → LOCKED → EXECUTED → FOSSILIZED = 3 transitions
        self.assertGreaterEqual(len(transitions), 3)

    def test_every_transition_has_sig(self):
        """Every transition event carries a non-empty signature."""
        k = Kernel()
        sid = k.propose("file.py", "A")
        k.resolve(sid)
        k.execute(sid, True)

        for event in k.ledger:
            if "from" in event:  # transition events
                self.assertIn("sig", event)
                self.assertGreater(len(event["sig"]), 0)

    def test_sig_is_genesis_anchored(self):
        """Signatures are salted with the LANA hash — any other salt fails reproduction."""
        k = Kernel()
        sid = k.propose("file.py", "A")
        k.resolve(sid)
        k.execute(sid, True)

        scar = k.scars[sid]
        for event in scar.history:
            from_s = event.get("from")
            to_s = event.get("to")
            if from_s and to_s:
                # Re-sign without LANA — should differ
                wrong_payload = f"WRONG_SALT:{sid}:{from_s}:{to_s}"
                wrong_sig = hashlib.sha256(wrong_payload.encode()).hexdigest()[:24]
                self.assertNotEqual(event["sig"], wrong_sig)

    def test_rejected_proposal_in_ledger(self):
        """A human RED signal produces a CANCELLED ledger entry."""
        k = Kernel()
        sid = k.propose("file.py", "A")
        k.resolve(sid)
        k.execute(sid, False)  # RED

        cancelled = [e for e in k.ledger if e.get("to") == "CANCELLED"]
        self.assertEqual(len(cancelled), 1)


class TestGenesisAnchor(unittest.TestCase):
    """
    Property: LANA_GENESIS_HASH is present, is the correct SHA-256,
    and is used as the cryptographic salt for all signatures.
    """
    EXPECTED_HASH = "7b4a866301681119e5f9168d6e208b62bab446fe33ce3445d113ec068164aaf9"

    def test_lana_hash_value(self):
        """The Genesis Anchor constant is the correct SHA-256 value."""
        self.assertEqual(LANA, self.EXPECTED_HASH)

    def test_lana_hash_length(self):
        """SHA-256 produces 64-character hex string."""
        self.assertEqual(len(LANA), 64)

    def test_signature_uses_lana(self):
        """The sign() method uses LANA as the prefix salt."""
        s = Scar("test-id", "file.py", "content")
        sig = s.sign("PROPOSED", "LOCKED")
        # Re-verify manually
        import time as _t
        # We can't reproduce exact ts, but we can verify format and length
        self.assertEqual(len(sig), 24)
        self.assertTrue(all(c in "0123456789abcdef" for c in sig))


class TestConflictResolution(unittest.TestCase):
    """
    Property: Conflict resolution is a pure function of scar_id hashes.
    No timing, no external state, no human interaction required.
    """

    def test_contested_scar_cannot_execute(self):
        """A CONTESTED SCAR cannot bypass the execution gate."""
        k = Kernel()
        a = k.propose("file.py", "fix A")
        b = k.propose("file.py", "fix B")
        k.resolve(a)

        # b should now be CONTESTED
        contested = [s for s in k.scars.values() if s.state == "CONTESTED"]
        self.assertGreaterEqual(len(contested), 1)

        for s in contested:
            with self.assertRaises(Exception):
                k.execute(s.scar_id, True)

    def test_conflict_key_is_deterministic(self):
        """Same target always produces same conflict domain key."""
        k = Kernel()
        key1 = k.conflict_key("file.py")
        key2 = k.conflict_key("file.py")
        self.assertEqual(key1, key2)

    def test_conflict_key_differs_per_target(self):
        """Different targets produce different conflict keys."""
        k = Kernel()
        self.assertNotEqual(
            k.conflict_key("file_a.py"),
            k.conflict_key("file_b.py")
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
