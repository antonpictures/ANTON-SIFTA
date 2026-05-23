"""
Red-team and conservation tests for joule receipts + Ed25519 ledger rows.

Run:
  python3 -m pytest tests/test_adversarial_joule_receipts.py -v
"""

from __future__ import annotations

import os
import unittest

from Kernel import inference_economy as ie


class TestJouleMeasurementAndMargin(unittest.TestCase):
    def test_error_bound_explicit_when_samples_agree(self) -> None:
        self.assertEqual(ie.joule_measurement_error_bound_pct(40.0, 40.0), 0.05)

    def test_error_bound_grows_with_spread(self) -> None:
        b = ie.joule_measurement_error_bound_pct(30.0, 50.0)
        self.assertGreater(b, 5.0)

    def test_margin_environment_not_flat_constant(self) -> None:
        base = ie.inference_transfer_margin_from_environment(0.0, 0.0, 0.0)
        long_run = ie.inference_transfer_margin_from_environment(120_000.0, 0.0, 0.0)
        self.assertAlmostEqual(base, 1.0, places=5)
        self.assertGreater(long_run, base)

    def test_energy_consistency_cross_node(self) -> None:
        ok, gap = ie.energy_transfer_consistency_ok(10.0, 10.5, 5.0, 5.0)
        self.assertTrue(ok)
        self.assertLess(gap, 1.5)
        bad, gap2 = ie.energy_transfer_consistency_ok(10.0, 50.0, 5.0, 5.0)
        self.assertFalse(bad)
        self.assertAlmostEqual(gap2, 40.0)

    def test_trust_weight_product(self) -> None:
        self.assertAlmostEqual(ie.swarm_trust_weight(True, True, 0.5), 0.5, places=5)
        self.assertEqual(ie.swarm_trust_weight(False, True, 1.0), 0.0)


class TestReplayKeyPrecedence(unittest.TestCase):
    def test_replay_key_prefers_ed25519_over_receipt_hash(self) -> None:
        sig = "aa" * 64
        a = {
            "event": "INFERENCE_TRANSFER_JOULES",
            "ed25519_sig": sig,
            "receipt_hash": "aaa111",
        }
        b = {
            "event": "INFERENCE_TRANSFER_JOULES",
            "ed25519_sig": sig,
            "receipt_hash": "bbb222",
        }
        self.assertEqual(
            ie.inference_transfer_replay_key(a),
            ie.inference_transfer_replay_key(b),
        )


class TestReplayFingerprint(unittest.TestCase):
    def test_same_economics_twice_is_same_fingerprint(self) -> None:
        row = {
            "borrower_id": "A",
            "lender_node_id": "B",
            "fee_stgm": 1.0,
            "provider_joules_net": 12.4,
            "ts": "t",
            "signing_node": "B",
            "model": "m",
            "tokens_used": 3,
            "receipt_hash": "abc",
        }
        fp1 = ie.joule_receipt_anti_replay_fingerprint(row)
        fp2 = ie.joule_receipt_anti_replay_fingerprint(dict(row))
        self.assertEqual(fp1, fp2)

    def test_replay_set_detects_duplicate(self) -> None:
        seen: set[str] = set()
        row = {"borrower_id": "X", "lender_node_id": "Y", "fee_stgm": 0.1}
        fp = ie.joule_receipt_anti_replay_fingerprint(row)
        self.assertNotIn(fp, seen)
        seen.add(fp)
        self.assertIn(fp, seen)


class TestForgedAndTamperedReceipts(unittest.TestCase):
    def test_random_hex_signature_fails_verification(self) -> None:
        try:
            from System.crypto_keychain import verify_block
        except Exception as exc:
            self.skipTest(f"crypto: {exc}")

        fake_sig = "ab" * 64
        ok = verify_block(
            "GTH4921YP3",
            "INFERENCE_BORROW::b::FROM[x]::MODEL[m]::TOKENS[1]::FEE[1.0]::TS[t]::NODE[GTH4921YP3]",
            fake_sig,
        )
        self.assertFalse(ok)

    def test_tampered_fee_invalidates_ledger_row(self) -> None:
        try:
            from System.crypto_keychain import get_silicon_identity, sign_block
        except Exception as exc:
            self.skipTest(f"crypto: {exc}")

        node = get_silicon_identity()
        if not node or node == "UNKNOWN_SERIAL":
            self.skipTest("no silicon identity")

        ts = "2026-04-29T12:00:00+00:00"
        body = (
            f"INFERENCE_BORROW::BOR::FROM[{node}]::MODEL[m]::TOKENS[10]::"
            f"FEE[0.5]::TS[{ts}]::NODE[{node}]"
        )
        sig = sign_block(body)
        row = {
            "event": "INFERENCE_TRANSFER_JOULES",
            "borrower_id": "BOR",
            "lender_ip": node,
            "lender_node_id": node,
            "model": "m",
            "tokens_used": 10,
            "fee_stgm": 999.0,
            "ts": ts,
            "signing_node": node,
            "ed25519_sig": sig,
        }
        old = os.environ.get("SIFTA_LEDGER_VERIFY")
        os.environ["SIFTA_LEDGER_VERIFY"] = "1"
        try:
            self.assertFalse(ie._ledger_row_cryptographically_valid(row))
        finally:
            if old is None:
                os.environ.pop("SIFTA_LEDGER_VERIFY", None)
            else:
                os.environ["SIFTA_LEDGER_VERIFY"] = old

    def test_wrong_signing_node_rejects_valid_sig_shape(self) -> None:
        try:
            from System.crypto_keychain import get_silicon_identity, sign_block, verify_block
        except Exception as exc:
            self.skipTest(f"crypto: {exc}")

        node = get_silicon_identity()
        if not node or node == "UNKNOWN_SERIAL":
            self.skipTest("no silicon identity")

        ts = "2026-04-29T12:00:00+00:00"
        body = (
            f"INFERENCE_BORROW::BOR::FROM[{node}]::MODEL[m]::TOKENS[10]::"
            f"FEE[0.5]::TS[{ts}]::NODE[{node}]"
        )
        sig = sign_block(body)
        self.assertFalse(
            verify_block("FAKE_NODE_SERIAL_NOT_IN_PKI", body, sig),
            "signature must not verify under attacker-chosen node id",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
