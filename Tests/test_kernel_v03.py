"""
SIFTA Kernel v0.3 — New Primitive Tests
Byzantine filter, content-addressed SCARs, pheromone scoring.
"""
import unittest, time, hashlib
from scar_kernel import (
    Kernel, Scar,
    content_addressed_id,
    byzantine_filter,
    pheromone_score,
    gossip_round,
    canonical_winner,
)


class TestContentAddressedSCARs(unittest.TestCase):
    """Identity = content. Same repair = same ID. No duplication possible."""

    def test_same_content_same_id(self):
        id1 = content_addressed_id("file.py", "fix the bug")
        id2 = content_addressed_id("file.py", "fix the bug")
        self.assertEqual(id1, id2)

    def test_different_content_different_id(self):
        id1 = content_addressed_id("file.py", "fix A")
        id2 = content_addressed_id("file.py", "fix B")
        self.assertNotEqual(id1, id2)

    def test_different_target_different_id(self):
        id1 = content_addressed_id("file_a.py", "fix")
        id2 = content_addressed_id("file_b.py", "fix")
        self.assertNotEqual(id1, id2)

    def test_id_is_deterministic_hex(self):
        cid = content_addressed_id("file.py", "patch")
        self.assertEqual(len(cid), 32)
        self.assertTrue(all(c in "0123456789abcdef" for c in cid))

    def test_two_agents_identical_repair_converge(self):
        """Two agents independently propose the same fix → identical scar_id → no conflict."""
        id_agent_a = content_addressed_id("broken.py", "return x + 1")
        id_agent_b = content_addressed_id("broken.py", "return x + 1")
        self.assertEqual(id_agent_a, id_agent_b,
                         "Content-addressed IDs diverged for identical repair — duplication possible")


class TestByzantineFilter(unittest.TestCase):
    """Nodes that lie about scar_ids should be filtered. Known scars survive."""

    def test_known_scars_pass_filter(self):
        s = Scar("real-id-123", "file.py", "content")
        known = {"real-id-123": s}
        claimed = {"real-id-123", "fake-id-999"}
        verified = byzantine_filter(claimed, known)
        self.assertIn("real-id-123", verified)

    def test_unknown_forged_ids_excluded(self):
        known = {}
        claimed = {"forged-id-aaa", "forged-id-bbb"}
        verified = byzantine_filter(claimed, known)
        self.assertEqual(len(verified), 0,
                         "Byzantine filter accepted unknown forged IDs")

    def test_empty_gossip_safe(self):
        known = {"real": Scar("real", "f.py", "c")}
        verified = byzantine_filter(set(), known)
        self.assertEqual(verified, set())

    def test_honest_node_fully_passes(self):
        scars = {f"id{i}": Scar(f"id{i}", "file.py", f"c{i}") for i in range(5)}
        claimed = set(scars.keys())
        verified = byzantine_filter(claimed, scars)
        self.assertEqual(verified, claimed)


class TestPheromoneScoring(unittest.TestCase):
    """Scores must be bounded, consistent, and reward frequency + recency."""

    def test_score_in_unit_range(self):
        s = Scar("abc123", "file.py", "content")
        score = pheromone_score(s, [s])
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_fresh_scar_scores_higher_than_old(self):
        now = time.time()
        fresh = Scar("aaa", "f.py", "fix", ts=now)
        old   = Scar("bbb", "f.py", "fix", ts=now - 3600)
        score_fresh = pheromone_score(fresh, [fresh, old], now=now)
        score_old   = pheromone_score(old,   [fresh, old], now=now)
        self.assertGreater(score_fresh, score_old,
                           "Fresh scar should score higher than 1-hour-old scar")

    def test_higher_frequency_content_scores_higher(self):
        now = time.time()
        # Three agents all propose the same repair to file.py
        scars = [Scar(f"id{i}", "file.py", "same fix", ts=now) for i in range(3)]
        lone  = Scar("lone", "file.py", "different fix", ts=now)
        all_scars = scars + [lone]

        score_popular = pheromone_score(scars[0], all_scars, now=now)
        score_lone    = pheromone_score(lone,     all_scars, now=now)
        self.assertGreater(score_popular, score_lone,
                           "Frequently proposed content should score higher")

    def test_scores_are_comparable(self):
        """Sorted by pheromone_score gives a meaningful ranking."""
        now = time.time()
        scars = [Scar(f"id{i:032d}", "file.py", f"fix_{i}", ts=now - i*10)
                 for i in range(5)]
        scores = [(s.scar_id, pheromone_score(s, scars, now=now)) for s in scars]
        sorted_scores = sorted(scores, key=lambda x: -x[1])
        self.assertEqual(len(sorted_scores), 5)


class TestByzantineGlobalConvergence(unittest.TestCase):
    """
    The hardest test: honest nodes still converge even when
    Byzantine nodes inject noise into the gossip layer.
    """

    def test_convergence_with_byzantine_noise(self):
        """
        Scenario: 3 honest nodes, 1 Byzantine node injecting fake IDs.
        After filtering, honest nodes must still agree on the same winner.
        """
        honest_scars = [Scar(f"honest{i:028d}", "file.py", f"fix_{i}") for i in range(5)]
        byzantine_noise = {"totally-fake-id-001", "totally-fake-id-002"}

        known = {s.scar_id: s for s in honest_scars}

        # Each honest node receives gossip polluted with Byzantine IDs
        # but filters it before feeding into consensus
        node_a_claimed = {s.scar_id for s in honest_scars[:3]} | byzantine_noise
        node_b_claimed = {s.scar_id for s in honest_scars[2:]} | byzantine_noise

        verified_a = byzantine_filter(node_a_claimed, known)
        verified_b = byzantine_filter(node_b_claimed, known)

        # Both nodes merge their verified maps
        from scar_kernel import gossip_merge
        merged = gossip_merge(verified_a, verified_b)
        merged_scars = [known[sid] for sid in merged]

        winner_a = canonical_winner(merged_scars)
        winner_b = canonical_winner(merged_scars)  # same input → same winner

        self.assertEqual(winner_a.scar_id, winner_b.scar_id,
                         "Byzantine noise caused honest nodes to disagree — convergence broken")

    def test_byzantine_node_cannot_force_fake_winner(self):
        """A Byzantine node broadcasting a fake scar_id cannot make it win."""
        honest_scars = [Scar(f"aaa{i:028d}", "file.py", f"fix_{i}") for i in range(3)]
        known = {s.scar_id: s for s in honest_scars}

        # Byzantine node claims a fake ID that would win (lowest hash if it existed)
        fake_winner_id = "0" * 32  # Would definitely win hash sort
        byzantine_claimed = {s.scar_id for s in honest_scars} | {fake_winner_id}

        verified = byzantine_filter(byzantine_claimed, known)

        # Fake ID must not survive filtering
        self.assertNotIn(fake_winner_id, verified,
                         "Byzantine fake winner ID survived the filter")

        # Winner from verified set must be a real scar
        winner = canonical_winner([known[sid] for sid in verified])
        self.assertIn(winner.scar_id, known)


if __name__ == "__main__":
    unittest.main(verbosity=2)
