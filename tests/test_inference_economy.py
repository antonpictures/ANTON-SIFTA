"""
Economy + inference borrow — isolated temp ledger/state (does not touch repo repair_log).

Run:
  python3 -m unittest tests.test_inference_economy -v
  python3 -m pytest tests/test_inference_economy.py -v
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import inference_economy as ie


class TestLedgerBalanceDialects(unittest.TestCase):
    """ledger_balance replays repair_log dialects A + B + legacy compute drip."""

    def setUp(self):
        self._td = tempfile.mkdtemp()
        self._log = Path(self._td) / "repair_log.jsonl"
        self._state = Path(self._td) / ".sifta_state"
        self._state.mkdir(parents=True, exist_ok=True)
        self._old_log = ie.LOG_PATH
        self._old_state = ie.STATE_DIR
        self._old_verify = os.environ.get("SIFTA_LEDGER_VERIFY")
        ie.LOG_PATH = self._log
        ie.STATE_DIR = self._state
        os.environ["SIFTA_LEDGER_VERIFY"] = "0"

    def tearDown(self):
        ie.LOG_PATH = self._old_log
        ie.STATE_DIR = self._old_state
        if self._old_verify is None:
            os.environ.pop("SIFTA_LEDGER_VERIFY", None)
        else:
            os.environ["SIFTA_LEDGER_VERIFY"] = self._old_verify
        shutil.rmtree(self._td, ignore_errors=True)

    def _append(self, row: dict) -> None:
        with open(self._log, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")

    def test_stgm_mint_and_spend(self):
        self._append(
            {
                "timestamp": 1,
                "agent_id": "UNIT_AGENT",
                "tx_type": "STGM_MINT",
                "amount": 1000.0,
                "hash": "SEAL_testmint",
            }
        )
        self._append(
            {
                "timestamp": 2,
                "agent_id": "UNIT_AGENT",
                "tx_type": "STGM_SPEND",
                "amount": 250.0,
                "target_node": "SOME_NODE",
                "hash": "MARKET_tests",
            }
        )
        self.assertAlmostEqual(ie.ledger_balance("UNIT_AGENT"), 750.0, places=2)

    def test_mining_reward_and_inference_borrow(self):
        self._append(
            {
                "event": "MINING_REWARD",
                "miner_id": "BORROWER_X",
                "amount_stgm": 500.0,
                "ts": "t0",
                "action": "repair",
                "file_repaired": "x.py",
            }
        )
        self._append(
            {
                "event": "INFERENCE_BORROW",
                "borrower_id": "BORROWER_X",
                "lender_ip": "LENDER_Y",
                "fee_stgm": 40.0,
                "model": "m",
                "tokens_used": 100,
                "ts": "t1",
            }
        )
        self.assertAlmostEqual(ie.ledger_balance("BORROWER_X"), 460.0, places=2)
        self.assertAlmostEqual(ie.ledger_balance("LENDER_Y"), 40.0, places=2)

    def test_legacy_compute_drip_agent_field(self):
        self._append(
            {
                "timestamp": 3,
                "agent": "DRIP_AGENT",
                "amount_stgm": 2.5,
                "reason": "COMPUTE_BURN_TEST",
                "hash": "uuid-test",
            }
        )
        self.assertAlmostEqual(ie.ledger_balance("DRIP_AGENT"), 2.5, places=2)


class TestRecordInferenceFee(unittest.TestCase):
    """record_inference_fee writes ledger row and updates JSON wallets."""

    def setUp(self):
        self._td = tempfile.mkdtemp()
        self._log = Path(self._td) / "repair_log.jsonl"
        self._state = Path(self._td) / ".sifta_state"
        self._state.mkdir(parents=True, exist_ok=True)
        self._old_log = ie.LOG_PATH
        self._old_state = ie.STATE_DIR
        self._old_verify = os.environ.get("SIFTA_LEDGER_VERIFY")
        ie.LOG_PATH = self._log
        ie.STATE_DIR = self._state
        os.environ["SIFTA_LEDGER_VERIFY"] = "0"

        br = self._state / "BORROWER_Q.json"
        br.write_text(
            json.dumps(
                {"id": "BORROWER_Q", "stgm_balance": 200.0, "energy": 80},
                indent=2,
            ),
            encoding="utf-8",
        )
        ln = self._state / "LENDER_Z.json"
        ln.write_text(
            json.dumps(
                {"id": "LENDER_Z", "stgm_balance": 10.0, "energy": 100},
                indent=2,
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        ie.LOG_PATH = self._old_log
        ie.STATE_DIR = self._old_state
        if self._old_verify is None:
            os.environ.pop("SIFTA_LEDGER_VERIFY", None)
        else:
            os.environ["SIFTA_LEDGER_VERIFY"] = self._old_verify
        shutil.rmtree(self._td, ignore_errors=True)

    def test_borrow_debits_borrower_and_credits_lender_ledger(self):
        # ledger_balance only replays repair_log (not wallet JSON). Seed prior credit.
        with open(ie.LOG_PATH, "a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "timestamp": 0,
                        "agent_id": "BORROWER_Q",
                        "tx_type": "STGM_MINT",
                        "amount": 200.0,
                        "hash": "SEAL_unittest_seed",
                    }
                )
                + "\n"
            )

        ev = ie.record_inference_fee(
            borrower_id="BORROWER_Q",
            lender_node_ip="LENDER_Z",
            fee_stgm=35.0,
            model="test-model",
            tokens_used=500,
            file_repaired="proof.py",
        )
        self.assertEqual(ev.get("event"), "INFERENCE_BORROW")
        self.assertEqual(ev.get("borrower_id"), "BORROWER_Q")
        self.assertEqual(ev.get("lender_ip"), "LENDER_Z")
        self.assertEqual(ev.get("fee_stgm"), 35.0)

        self.assertAlmostEqual(ie.ledger_balance("BORROWER_Q"), 165.0, places=2)
        # Lender only has the borrow credit on-ledger (JSON 10.0 is not replayed).
        self.assertAlmostEqual(ie.ledger_balance("LENDER_Z"), 35.0, places=2)

        hist = ie.get_borrow_history("BORROWER_Q", tail=5)
        self.assertTrue(any(h.get("fee_stgm") == 35.0 for h in hist))


class TestFeeFormula(unittest.TestCase):
    def test_calculate_fee_positive(self):
        f = ie.calculate_fee(tokens=100)
        self.assertGreater(f, 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
