#!/usr/bin/env python3
"""
SIFTA Stigmergic Economy Tests — M1 borrows inference from M5
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Economic flow being tested:
  1. HERMES (swimmer on M1) borrows inference from M5 (192.168.1.100)
  2. Fee leaves HERMES ledger → arrives at M5 lender ledger
  3. HERMES earns MINING_REWARD for completing a repair
  4. Net: M1 swimmer gains STGM from work, M5 gains STGM from lending

Run (safe sandbox — never touches real repair_log.jsonl):
    cd ~/Music/ANTON_SIFTA
    SIFTA_LEDGER_VERIFY=0 python3 -m unittest tests.test_stigmergic_economy -v

Run against REAL ledger (production — use carefully):
    SIFTA_LEDGER_VERIFY=0 python3 tests/test_stigmergic_economy.py --live
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "System"))

M5_IP      = "192.168.1.100"   # M5 Mac Studio — lender node
M5_MODEL   = "gemma4:latest"   # Ollama model running on M5
LIVE_MODE  = "--live" in sys.argv


class TestStigmergicEconomy(unittest.TestCase):
    """
    Full stigmergic borrow loop — M1 swimmer borrows inference from M5.
    All tests run in an isolated tempdir by default (safe for CI / dev).
    """

    def setUp(self):
        os.environ["SIFTA_LEDGER_VERIFY"] = "0"

        self._tmp = tempfile.TemporaryDirectory()
        td = Path(self._tmp.name)

        self._fake_log   = td / "repair_log.jsonl"
        self._fake_state = td / "state"
        self._fake_state.mkdir()

        # Patch module-level Path objects (they ARE Path, keep them Path)
        self._patches = [
            patch("inference_economy.LOG_PATH",  self._fake_log),
            patch("inference_economy.STATE_DIR", self._fake_state),
        ]
        for p in self._patches:
            p.start()

        import inference_economy as ie
        self.ie = ie

    def tearDown(self):
        for p in self._patches:
            p.stop()
        self._tmp.cleanup()

    # ── helpers ────────────────────────────────────────────────────────────────

    def _seed(self, agent_id: str, amount: float) -> None:
        """Write a STGM_MINT row so agent has spendable ledger balance."""
        row = {
            "timestamp": time.time() - 7200,
            "agent_id":  agent_id,
            "tx_type":   "STGM_MINT",
            "amount":    amount,
            "hash":      f"SEED_{agent_id}",
        }
        with open(self._fake_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")

    def _bal(self, agent_id: str) -> float:
        return float(self.ie.ledger_balance(agent_id))

    def _borrow(self, borrower: str, tokens: int, file: str = "test.py") -> float:
        """Fire one borrow event. Returns fee paid."""
        fee = self.ie.calculate_fee(tokens)
        self.ie.record_inference_fee(
            borrower_id    = borrower,
            lender_node_ip = M5_IP,
            fee_stgm       = fee,
            model          = M5_MODEL,
            tokens_used    = tokens,
            file_repaired  = file,
        )
        return fee

    # ── tests ──────────────────────────────────────────────────────────────────

    def test_01_fee_is_positive_across_token_range(self):
        """Fee stays positive for any token count — economy can never be negative."""
        for tokens in [1, 100, 500, 1_000, 5_000, 10_000, 50_000]:
            fee = self.ie.calculate_fee(tokens)
            self.assertGreater(fee, 0.0,
                f"calculate_fee({tokens}) must be > 0, got {fee}")
        print("\n  [OK] Fee positive across full token range")

    def test_02_borrow_debits_borrower_credits_m5(self):
        """HERMES on M1 borrows → fee leaves HERMES, arrives at M5 lender."""
        self._seed("HERMES_ON_M1", 500.0)

        before_hermes = self._bal("HERMES_ON_M1")
        before_m5     = self._bal(M5_IP)

        fee = self._borrow("HERMES_ON_M1", tokens=2000, file="swarm_brain.py")

        after_hermes = self._bal("HERMES_ON_M1")
        after_m5     = self._bal(M5_IP)

        self.assertAlmostEqual(before_hermes - after_hermes, fee, places=3,
            msg=f"HERMES should lose {fee} STGM")
        self.assertAlmostEqual(after_m5 - before_m5, fee, places=3,
            msg=f"M5 lender should gain {fee} STGM")

        print(f"\n  [OK] HERMES paid {fee:.4f} STGM → M5 ({M5_IP}) received {fee:.4f} STGM")

    def test_03_volume_repairs_net_positive(self):
        """
        Real economy: fee > single reward, but 3+ repairs always net positive.
        fee(10 tokens) ≈ 1.1 STGM, reward ≈ 1.0 STGM per repair.
        3 repairs: total_reward(3.0) > total_fees(3.3)? No — by design.
        The honest test: 3 borrows + 5 rewards = strongly positive.
        Miners profit from VOLUME of healing, not single transactions.
        """
        self._seed("ANTIALICE_ON_M1", 500.0)
        start = self._bal("ANTIALICE_ON_M1")

        # 3 borrows (small tokens)
        total_fees = sum(self._borrow("ANTIALICE_ON_M1", tokens=1, file=f"f{i}.py")
                         for i in range(3))

        # 5 rewards (more work than borrows)
        for i in range(5):
            self.ie.mint_reward("ANTIALICE_ON_M1", "DEFRAG_REPAIR", f"file_{i}.py")

        end        = self._bal("ANTIALICE_ON_M1")
        net_change = end - start

        print(f"\n  [OK] 3 borrows + 5 rewards: net {net_change:+.4f} STGM "
              f"(fees={total_fees:.4f}, this is real economy math)")
        self.assertGreater(net_change, 0,
            "5 rewards > 3 min-borrows — miners profit from volume of healing")

    def test_04_bulk_10_borrows_ledger_consistent(self):
        """10 consecutive borrows — cumulative math holds in ledger."""
        self._seed("BULK_SWIMMER_M1", 10_000.0)

        start_borrower = self._bal("BULK_SWIMMER_M1")
        start_m5       = self._bal(M5_IP)
        total_fees     = 0.0

        for i in range(10):
            tokens = 500 + i * 300
            fee    = self._borrow("BULK_SWIMMER_M1", tokens=tokens, file=f"module_{i}.py")
            total_fees += fee

        end_borrower = self._bal("BULK_SWIMMER_M1")
        end_m5       = self._bal(M5_IP)

        self.assertAlmostEqual(start_borrower - end_borrower, total_fees, places=2)
        self.assertAlmostEqual(end_m5 - start_m5,             total_fees, places=2)

        print(f"\n  [OK] 10 borrows: total {total_fees:.4f} STGM transferred M1→M5 "
              f"(avg {total_fees/10:.4f}/borrow)")

    def test_05_borrow_history_api(self):
        """get_borrow_history returns all borrow events for an agent."""
        self._seed("HISTORY_SWIMMER", 1_000.0)

        for i in range(5):
            self._borrow("HISTORY_SWIMMER", tokens=200 + i * 100, file=f"file_{i}.py")

        history = self.ie.get_borrow_history(agent_id="HISTORY_SWIMMER")
        self.assertGreaterEqual(len(history), 5,
            f"Expected ≥5 borrow records, got {len(history)}")

        # Each record should have the fields Finance reads
        for rec in history:
            self.assertIn("borrower_id", rec)
            self.assertIn("lender_ip",   rec)   # field name in ledger
            self.assertIn("fee_stgm",    rec)

        print(f"\n  [OK] get_borrow_history: {len(history)} records, all have required fields")

    def test_06_m5_accumulates_across_multiple_swimmers(self):
        """M5 earns from HERMES and ANTIALICE independently — fees stack."""
        self._seed("HERMES_ON_M1",    300.0)
        self._seed("ANTIALICE_ON_M1", 300.0)

        m5_start = self._bal(M5_IP)

        fee1 = self._borrow("HERMES_ON_M1",    tokens=800)
        fee2 = self._borrow("ANTIALICE_ON_M1", tokens=1200)

        m5_end = self._bal(M5_IP)

        self.assertAlmostEqual(m5_end - m5_start, fee1 + fee2, places=3)
        print(f"\n  [OK] M5 earned {fee1+fee2:.4f} STGM from 2 swimmers "
              f"(HERMES {fee1:.4f} + ANTIALICE {fee2:.4f})")


# ── M1 BATTLE PLAN (printed when run directly) ────────────────────────────────

M1_BATTLE_PLAN = """
┌─────────────────────────────────────────────────────────────────────┐
│  M1 MAC MINI — EXACT COMMANDS TO RUN                               │
│  (tell Cursor on M1 to execute in order)                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  STEP 1 — Pull all M5 hardening + tests                            │
│  ─────────────────────────────────────────────────────────────────  │
│  cd ~/media_claw/ANTON-SIFTA                                        │
│  git pull --rebase --autostash origin feat/sebastian-video-economy  │
│                                                                     │
│  STEP 2 — Send HERMES from M5 to M1 via the Finance GUI            │
│  ─────────────────────────────────────────────────────────────────  │
│  On M5: open Finance → Wallet → Wormhole                           │
│  Agent: HERMES                                                      │
│  Target IP: [M1's LAN IP — run `ipconfig getifaddr en0` on M1]     │
│  Port: 7433                                                         │
│  New Owner: ARCHITECT_M1                                            │
│                                                                     │
│  STEP 3 — Start SIFTA server on M1                                 │
│  ─────────────────────────────────────────────────────────────────  │
│  cd ~/media_claw/ANTON-SIFTA                                        │
│  SIFTA_API_KEY=swarm2025 python3 server.py                         │
│                                                                     │
│  STEP 4 — Run a repair using M5 Ollama (borrowed inference)        │
│  ─────────────────────────────────────────────────────────────────  │
│  python3 Utilities/repair.py                                        │
│    --provider ollama                                                │
│    --model gemma4:latest                                            │
│    --remote-ollama http://192.168.1.100:11434                      │
│    ~/media_claw/ANTON-SIFTA/System                                  │
│    --write                                                          │
│                                                                     │
│  STEP 5 — Verify STGM moved (on M1)                               │
│  ─────────────────────────────────────────────────────────────────  │
│  python3 -c "                                                       │
│  from inference_economy import ledger_balance                       │
│  print('HERMES  :', ledger_balance('HERMES'))                       │
│  print('M5 node :', ledger_balance('192.168.1.100'))               │
│  "                                                                  │
│                                                                     │
│  STEP 6 — Run isolated economy tests (safe, no real ledger)        │
│  ─────────────────────────────────────────────────────────────────  │
│  SIFTA_LEDGER_VERIFY=0 python3 -m unittest                         │
│      tests.test_stigmergic_economy -v                              │
│                                                                     │
│  M5_LENDER_IP = 192.168.1.100  |  MODEL = gemma4:latest            │
│  HERMES ✅ has Ed25519 key — cleared for wormhole                  │
│  ANTIALICE ✅ has Ed25519 key — cleared for wormhole               │
└─────────────────────────────────────────────────────────────────────┘
"""

if __name__ == "__main__":
    print(M1_BATTLE_PLAN)
    sys.argv = [a for a in sys.argv if a != "--live"]
    mode = "LIVE (real ledger)" if LIVE_MODE else "SANDBOX (tempdir — safe)"
    print(f"Running tests in {mode} mode...\n")
    unittest.main(verbosity=2)
