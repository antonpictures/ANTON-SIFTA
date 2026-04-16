"""
Enforce SIFTA_MAX_STGM_LEDGER_CREDIT on repair_log.jsonl appends (anti mega-mint).
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
import sys

sys.path.insert(0, str(ROOT / "System"))

from ledger_append import append_ledger_line  # noqa: E402


class TestLedgerCreditCeiling(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.log = Path(self._td.name) / "repair_log.jsonl"
        self._old = os.environ.get("SIFTA_MAX_STGM_LEDGER_CREDIT")

    def tearDown(self):
        self._td.cleanup()
        if self._old is None:
            os.environ.pop("SIFTA_MAX_STGM_LEDGER_CREDIT", None)
        else:
            os.environ["SIFTA_MAX_STGM_LEDGER_CREDIT"] = self._old

    def test_rejects_100k_mint_under_default_cap(self):
        os.environ.pop("SIFTA_MAX_STGM_LEDGER_CREDIT", None)
        with self.assertRaises(ValueError) as ctx:
            append_ledger_line(
                self.log,
                {
                    "timestamp": 1,
                    "agent_id": "ATTACKER",
                    "tx_type": "STGM_MINT",
                    "amount": 100000.0,
                    "hash": "HEIST",
                },
            )
        self.assertIn("25000", str(ctx.exception))

    def test_allows_large_mint_when_ceiling_disabled(self):
        os.environ["SIFTA_MAX_STGM_LEDGER_CREDIT"] = "0"
        append_ledger_line(
            self.log,
            {
                "timestamp": 1,
                "agent_id": "WHALE",
                "tx_type": "STGM_MINT",
                "amount": 100000.0,
                "hash": "SEAL_OK",
            },
        )
        body = self.log.read_text(encoding="utf-8").strip()
        self.assertIn("100000", body)

    def test_small_mint_always_ok(self):
        os.environ.pop("SIFTA_MAX_STGM_LEDGER_CREDIT", None)
        append_ledger_line(
            self.log,
            {
                "timestamp": 2,
                "agent_id": "HERMES",
                "tx_type": "STGM_MINT",
                "amount": 2.5,
                "hash": "SEAL_small",
            },
        )
        row = json.loads(self.log.read_text(encoding="utf-8").strip().splitlines()[-1])
        self.assertEqual(row["amount"], 2.5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
