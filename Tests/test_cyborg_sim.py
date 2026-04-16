from __future__ import annotations

import unittest
from pathlib import Path


class TestCyborgImmuneSystem(unittest.TestCase):
    def test_rejects_invalid_signature(self):
        from Applications.sifta_cyborg_sim import (
            Cyborg,
            OwnerKeyring,
            SimulationLedger,
            SwimmerToken,
            mint_swimmer_token,
        )

        ledger = SimulationLedger(Path(".sifta") / "test_cyborg" / "ledger.jsonl")
        cy = Cyborg(ledger)
        keys = OwnerKeyring()

        cy.immune.register_owner("ARCH", keys.pubkey_hex("ARCH"))

        tok = mint_swimmer_token(keys, "S1", "ARCH", "pacemaker", "set", {"bpm_target": 80})
        cy.submit(tok)  # should pass

        bad = SwimmerToken(**{**tok.__dict__, "sig_hex": "00" * 64})  # type: ignore[arg-type]
        with self.assertRaises(Exception):
            cy.submit(bad)

    def test_rejects_unregistered_owner(self):
        from Applications.sifta_cyborg_sim import (
            Cyborg,
            OwnerKeyring,
            SimulationLedger,
            mint_swimmer_token,
        )

        ledger = SimulationLedger(Path(".sifta") / "test_cyborg" / "ledger2.jsonl")
        cy = Cyborg(ledger)
        keys = OwnerKeyring()
        tok = mint_swimmer_token(keys, "S2", "NO_REG", "nfc", "set", {"enabled": True})
        with self.assertRaises(Exception):
            cy.submit(tok)

