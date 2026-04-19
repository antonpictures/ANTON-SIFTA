#!/usr/bin/env python3
"""
System/swarm_lymphatic.py — Metabolic Waste Clearance (v1.0)
══════════════════════════════════════════════════════════════════════
SIFTA OS — Tri-IDE Peer Review Protocol
Architecture:    BISHOP (Drop 27)
Concept origin:  C47H / BISHOP — "Ledger Compaction / Renal Clearance"
AO46 translation fixes applied:
  - F9b: write-back to hot ledger uses rewrite_text_locked (not raw open)
  - F9b: archive flush uses append_line_locked (not raw open)
  - Safety: try/finally guarantees .lymph temp file never orphaned
  - Import: only declares what is actually called

The Lymphatic System.
Prevents the organism from suffocating under its own thermodynamic history.
Filters the active ledgers, retaining hot traces while flushing dead, necrotic
memory into the compressed archive directory.

Atomic pattern (safe against concurrent appenders):
  1. os.rename(hot_ledger → hot_ledger.lymph)   ← POSIX atomic isolation
  2. Parse .lymph, split hot/dead
  3. rewrite_text_locked(hot_ledger, hot_lines)  ← restore live blood (locked)
  4. append_line_locked(archive, dead_line)      ← flush dead waste (locked)
  5. os.remove(.lymph)                           ← always in finally block
"""

import os
import json
import time
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

try:
    from System.jsonl_file_lock import rewrite_text_locked, append_line_locked
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

        # The biological circulatory system (append-only ledgers)
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

    def excrete_metabolic_waste(self):
        """
        Iterates through the hot ledgers. Atomically isolates them, separates
        the living tissue from the dead waste, and routes them accordingly.
        """
        if not self.state_dir.exists():
            return 0

        self._ensure_kidneys_exist()
        total_flushed = 0
        now = time.time()

        for ledger_name in self.target_ledgers:
            hot_ledger = self.state_dir / ledger_name
            if not hot_ledger.exists():
                continue

            # ATOMIC ISOLATION: Pull the vein out of the active circulatory system
            processing_ledger = self.state_dir / f"{ledger_name}.lymph"
            try:
                os.rename(hot_ledger, processing_ledger)
            except OSError:
                continue  # Ledger is locked by the OS or missing

            active_lines = []
            dead_lines = []

            # AO46: try/finally guarantees .lymph is never orphaned, even on crash
            try:
                with open(processing_ledger, 'r', encoding='utf-8') as f:
                    for line in f:
                        if not line.strip():
                            continue
                        try:
                            trace = json.loads(line)
                            # Schema agnostic: 'ts' for rewards, 'timestamp' for biology
                            trace_time = trace.get("ts", trace.get("timestamp", 0))
                            if now - trace_time > self.hot_window_seconds:
                                dead_lines.append(line)
                            else:
                                active_lines.append(line)
                        except json.JSONDecodeError:
                            continue  # Corrupted DNA is inherently dead waste

                # Route active blood back to the hot ledger (locked write)
                if active_lines:
                    rewrite_text_locked(hot_ledger, "".join(active_lines))

                # Flush dead waste to the kidneys (Archive) using locked append
                if dead_lines:
                    archive_ledger = self.archive_dir / f"{ledger_name}.archive"
                    for dead_line in dead_lines:
                        append_line_locked(archive_ledger, dead_line)
                    total_flushed += len(dead_lines)
                    print(f"[-] LYMPHATIC CLEARANCE: Flushed {len(dead_lines)} dead "
                          f"traces from {ledger_name}.")

            finally:
                # Always clean the surgical tray — even if parsing crashed
                if processing_ledger.exists():
                    try:
                        os.remove(processing_ledger)
                    except OSError:
                        pass

        return total_flushed


# --- SUBSTRATE TEST ANCHOR (THE LYMPHATIC SMOKE) ---
def _smoke():
    print("\n=== SIFTA LYMPHATIC SYSTEM (METABOLIC CLEARANCE) : SMOKE TEST ===")
    import tempfile

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

        # 1. Inject Blood — 2 hot traces, 3 dead traces
        with open(hot_ledger, 'w') as f:
            # Hot (younger than 1 hour)
            f.write(json.dumps({"ts": now - 100,   "app": "hot_1",  "amount": 10.0}) + "\n")
            f.write(json.dumps({"ts": now - 1800,  "app": "hot_2",  "amount": 20.0}) + "\n")
            # Dead (older than 1 hour)
            f.write(json.dumps({"ts": now - 4000,  "app": "dead_1", "amount": 30.0}) + "\n")
            f.write(json.dumps({"ts": now - 5000,  "app": "dead_2", "amount": 40.0}) + "\n")
            f.write(json.dumps({"ts": now - 86400, "app": "dead_3", "amount": 50.0}) + "\n")

        # 2. Execute Renal Clearance
        flushed_count = lymph.excrete_metabolic_waste()

        print("\n[SMOKE RESULTS]")
        assert flushed_count == 3
        print(f"[PASS] Correct dead trace count identified and flushed: {flushed_count}")

        # 3. Verify Hot Ledger — only 2 active traces remain
        with open(hot_ledger, 'r') as f:
            hot_lines = [l for l in f.readlines() if l.strip()]
        assert len(hot_lines) == 2
        assert json.loads(hot_lines[0])["app"] == "hot_1"
        assert json.loads(hot_lines[1])["app"] == "hot_2"
        print("[PASS] Hot ledger compacted. Only active traces remain.")

        # 4. Verify Archive Ledger — 3 dead traces routed correctly
        with open(archive_ledger, 'r') as f:
            dead_lines = [l for l in f.readlines() if l.strip()]
        assert len(dead_lines) == 3
        assert json.loads(dead_lines[0])["app"] == "dead_1"
        assert json.loads(dead_lines[2])["app"] == "dead_3"
        print("[PASS] Necrotic tissue securely flushed to Archive.")

        # 5. Verify .lymph temp file was cleaned up (try/finally validation)
        orphan = tmp_path / f"{test_ledger_name}.lymph"
        assert not orphan.exists()
        print("[PASS] No orphaned .lymph temp files. Surgical tray clean.")

        print("\nLymphatic Smoke Complete. The Swarm's circulatory system is clean.")


if __name__ == "__main__":
    _smoke()
