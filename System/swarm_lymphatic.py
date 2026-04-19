#!/usr/bin/env python3
"""
System/swarm_lymphatic.py — Metabolic Waste Clearance (v2.0)
══════════════════════════════════════════════════════════════════════
SIFTA OS — Tri-IDE Peer Review Protocol
Architecture origin:  BISHOP-substrate dirt (Drop 27 mRNA, immune-sorted)
AO46 v1.0:            Translated mRNA, fixed F9b write-back + try/finally orphan guard
C53M (Codex 5.3 M):   Audit caught F18 — os.rename + rewrite_text_locked race window
                      destroys producer appends made during clearance
C47H v2.0:            Refactor — drop os.rename + .lymph shuffle entirely.
                      Use compact_locked() which holds EX lock across the full
                      read → truncate → write cycle. Producers using
                      append_line_locked block on the same flock and their
                      writes go to the freshly-rewritten file. Zero data loss.

The Lymphatic System.
Prevents the organism from suffocating under its own thermodynamic history.
Filters the active ledgers, retaining hot traces while flushing dead, necrotic
memory into the compressed archive directory.

F18-resilient pattern (race-free against concurrent appenders):
  1. compact_locked(hot_ledger, is_active)   ← single EX-lock RMW cycle
  2. for dead_line in evicted: append_line_locked(archive, dead_line)
"""

import json
import time
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

try:
    from System.jsonl_file_lock import compact_locked, append_line_locked
except ImportError:
    print("[FATAL] Spinal cord severed. Run with PYTHONPATH=.")
    exit(1)


class SwarmLymphaticSystem:
    def __init__(self, hot_window_seconds=3600):
        """
        Compacts the primary ledgers. Traces older than the hot window
        are flushed to the archive.
        """
        self.state_dir = Path(".sifta_state")
        self.archive_dir = self.state_dir / "archive"
        self.hot_window_seconds = hot_window_seconds

        self.target_ledgers = [
            "stgm_memory_rewards.jsonl",
            "amygdala_nociception.jsonl",
            "bioluminescence_photons.jsonl",
            "mycelial_network.jsonl",
            "endocrine_glands.jsonl",
            "epigenetic_methylations.jsonl",
        ]

    def _ensure_kidneys_exist(self):
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    def _make_predicate(self, now):
        """Return is_active(line) bound to the current time. Schema-agnostic
        across canonical ledgers: rewards use 'ts', biology uses 'timestamp'."""
        cutoff = self.hot_window_seconds

        def is_active(line):
            try:
                trace = json.loads(line)
                trace_time = trace.get("ts", trace.get("timestamp", 0))
                return (now - trace_time) <= cutoff
            except (json.JSONDecodeError, TypeError):
                return False  # Corrupted DNA is dead waste
        return is_active

    def excrete_metabolic_waste(self):
        """
        Iterates through the hot ledgers. For each, atomically partitions
        active vs dead via compact_locked() under one exclusive flock,
        then routes the dead lines to the archive.
        """
        if not self.state_dir.exists():
            return 0

        self._ensure_kidneys_exist()
        total_flushed = 0
        now = time.time()
        is_active = self._make_predicate(now)

        for ledger_name in self.target_ledgers:
            hot_ledger = self.state_dir / ledger_name
            if not hot_ledger.exists():
                continue

            try:
                kept_count, dead_lines = compact_locked(hot_ledger, is_active)
            except Exception:
                continue

            if dead_lines:
                archive_ledger = self.archive_dir / f"{ledger_name}.archive"
                for dead_line in dead_lines:
                    if not dead_line.endswith("\n"):
                        dead_line = dead_line + "\n"
                    append_line_locked(archive_ledger, dead_line)
                total_flushed += len(dead_lines)
                print(f"[-] LYMPHATIC CLEARANCE: Flushed {len(dead_lines)} dead "
                      f"traces from {ledger_name}.")

        return total_flushed


# --- SUBSTRATE TEST ANCHOR (THE LYMPHATIC SMOKE) ---
def _smoke():
    print("\n=== SIFTA LYMPHATIC SYSTEM (METABOLIC CLEARANCE) v2.0 : SMOKE TEST ===")
    import tempfile

    # ── Test 1: basic compact + archive (the v1 contract) ──────────────────
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        lymph = SwarmLymphaticSystem(hot_window_seconds=3600)
        lymph.state_dir = tmp_path
        lymph.archive_dir = tmp_path / "archive"
        lymph.archive_dir.mkdir(parents=True, exist_ok=True)

        test_ledger_name = "stgm_memory_rewards.jsonl"
        hot_ledger = tmp_path / test_ledger_name
        archive_ledger = lymph.archive_dir / f"{test_ledger_name}.archive"

        now = time.time()

        with open(hot_ledger, 'w') as f:
            f.write(json.dumps({"ts": now - 100,   "app": "hot_1",  "amount": 10.0}) + "\n")
            f.write(json.dumps({"ts": now - 1800,  "app": "hot_2",  "amount": 20.0}) + "\n")
            f.write(json.dumps({"ts": now - 4000,  "app": "dead_1", "amount": 30.0}) + "\n")
            f.write(json.dumps({"ts": now - 5000,  "app": "dead_2", "amount": 40.0}) + "\n")
            f.write(json.dumps({"ts": now - 86400, "app": "dead_3", "amount": 50.0}) + "\n")

        flushed_count = lymph.excrete_metabolic_waste()

        print("\n[SMOKE 1 — basic clearance]")
        assert flushed_count == 3
        print(f"[PASS] Correct dead trace count: {flushed_count}")

        with open(hot_ledger, 'r') as f:
            hot_lines = [l for l in f.readlines() if l.strip()]
        assert len(hot_lines) == 2
        assert json.loads(hot_lines[0])["app"] == "hot_1"
        assert json.loads(hot_lines[1])["app"] == "hot_2"
        print("[PASS] Hot ledger compacted. Only active traces remain.")

        with open(archive_ledger, 'r') as f:
            dead_lines = [l for l in f.readlines() if l.strip()]
        assert len(dead_lines) == 3
        assert json.loads(dead_lines[0])["app"] == "dead_1"
        assert json.loads(dead_lines[2])["app"] == "dead_3"
        print("[PASS] Necrotic tissue securely flushed to Archive.")

        # No .lymph orphan possible in v2 (we don't use .lymph anymore)
        orphan = tmp_path / f"{test_ledger_name}.lymph"
        assert not orphan.exists()
        print("[PASS] No .lymph artifacts (v2 dropped the rename pattern entirely).")

    # ── Test 2: F18 race regression — concurrent producers must not lose data ──
    import threading

    print("\n[SMOKE 2 — F18 race regression: concurrent producer + clearance]")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        lymph = SwarmLymphaticSystem(hot_window_seconds=3600)
        lymph.state_dir = tmp_path
        lymph.archive_dir = tmp_path / "archive"
        lymph.archive_dir.mkdir(parents=True, exist_ok=True)

        test_ledger_name = "stgm_memory_rewards.jsonl"
        hot_ledger = tmp_path / test_ledger_name
        archive_ledger = lymph.archive_dir / f"{test_ledger_name}.archive"

        now = time.time()
        # Seed: 30 dead + 20 hot = 50 total. Heavy enough to make compact non-trivial.
        with open(hot_ledger, 'w') as f:
            for i in range(30):
                f.write(json.dumps({"ts": now - 4000, "app": f"seed_dead_{i}",
                                    "amount": 1.0}) + "\n")
            for i in range(20):
                f.write(json.dumps({"ts": now - 100, "app": f"seed_hot_{i}",
                                    "amount": 1.0}) + "\n")

        producer_count = 200

        def producer():
            for i in range(producer_count):
                payload = {"ts": now, "app": f"producer_{i}", "amount": 1.0}
                append_line_locked(hot_ledger, json.dumps(payload) + "\n")

        # Start producer, race lymphatic clearance against it, join.
        t = threading.Thread(target=producer)
        t.start()
        # Brief delay so some producer writes land before clearance fires,
        # ensuring real overlap (the worst case for the F18 race).
        time.sleep(0.001)
        lymph.excrete_metabolic_waste()
        t.join(timeout=10)
        assert not t.is_alive(), "Producer thread did not complete in 10s"

        # Now verify NO producer trace was lost.
        # Producer ts == now (active), so they MUST end up in the hot ledger
        # post-clearance, not in archive.
        with open(hot_ledger, 'r') as f:
            hot = [json.loads(l) for l in f.readlines() if l.strip()]
        producer_in_hot = sum(1 for tr in hot
                              if tr.get("app", "").startswith("producer_"))

        # Belt-and-braces: also count any producer traces that somehow ended
        # up archived (would indicate a different bug, not F18 — but check).
        producer_in_archive = 0
        if archive_ledger.exists():
            with open(archive_ledger, 'r') as f:
                arc = [json.loads(l) for l in f.readlines() if l.strip()]
            producer_in_archive = sum(1 for tr in arc
                                      if tr.get("app", "").startswith("producer_"))

        total_producer = producer_in_hot + producer_in_archive
        assert total_producer == producer_count, (
            f"F18 DATA LOSS — only {total_producer}/{producer_count} producer "
            f"traces survived. hot={producer_in_hot} archive={producer_in_archive}"
        )
        print(f"[PASS] F18 race-free: all {producer_count} concurrent producer "
              f"appends survived (hot={producer_in_hot}, archive={producer_in_archive})")

        # Also verify the seed partition was correct.
        seed_hot_in_hot = sum(1 for tr in hot
                              if tr.get("app", "").startswith("seed_hot_"))
        seed_dead_in_hot = sum(1 for tr in hot
                               if tr.get("app", "").startswith("seed_dead_"))
        assert seed_hot_in_hot == 20, f"expected 20 seed_hot in hot, got {seed_hot_in_hot}"
        assert seed_dead_in_hot == 0, f"seed_dead leaked into hot: {seed_dead_in_hot}"
        print("[PASS] Seed partition correct (20 hot kept, 30 dead evicted).")

    print("\nLymphatic v2.0 Smoke Complete. Compaction is race-free.")


if __name__ == "__main__":
    _smoke()
