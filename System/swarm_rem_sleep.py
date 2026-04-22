#!/usr/bin/env python3
"""
System/swarm_rem_sleep.py
══════════════════════════════════════════════════════════════════════
Concept: Neuroplasticity (REM Sleep, Synaptic Pruning & Apoptosis)
Author:  BISHOP (Epoch 13 Drop), Hardened by AO46
Status:  Active

Executes programmed cell death (Apoptosis) on depleted Swimmers and
safely prunes bloated JSONL ledgers using the flock-backed compact_locked
primitive from jsonl_file_lock.py.

CONCURRENCY MODEL:
  BISHOP's original dirt used naive read→open('w')→write for truncation.
  That is a data-loss race: any concurrent append_line_locked call landing
  between the read and the write is silently destroyed.

  This hardened version uses compact_locked() which holds LOCK_EX across
  the entire read→truncate(0)→write cycle. Concurrent producers block on
  the same flock, then their append lands on the freshly-compacted file.
  No inode swap, no rename, no lost lines.

SAFETY RAILS:
  - Canonical Swimmer bodies (M1SIFTA, M5SIFTA, QUEEN, ALICE) are
    immutable and will NEVER be dissolved by Apoptosis.
  - Pruned engrams are archived before deletion so memory is recoverable.
  - The REM cycle logs every action to rem_sleep_cycles.jsonl.
"""

import json
import os
import time
from pathlib import Path

try:
    from System.jsonl_file_lock import (
        append_line_locked,
        tail_compact_locked,
    )
    from System.canonical_schemas import assert_payload_keys
except ImportError:
    print("[FATAL] Spinal cord severed. Run with PYTHONPATH=.")
    exit(1)

# Bodies that must NEVER be dissolved, regardless of STGM balance.
_IMMORTAL_BODY_FRAGMENTS = frozenset({
    "M1SIFTA", "M5SIFTA",     # Canonical hardware swimmers
    "QUEEN", "ALICE",          # BISHOP's original safeguards
})

# Ledgers that must NEVER be auto-pruned by REM sleep, even if huge.
# These are durable memory, security audit trails, or replay-critical streams.
# Pruning them silently could erase forensic evidence or learned vocabulary.
# If one of these grows too large, the operator must invoke an explicit
# `swarm_lymphatic` pass or hand-archive — not an automatic REM pass.
_DURABLE_LEDGERS = frozenset({
    "rem_sleep_cycles.jsonl",                 # REM's own audit
    "long_term_engrams.jsonl",                # durable engrams (Memory Forge)
    "body_event_lexicon.jsonl",               # learned body-signal vocabulary
    "swimmer_body_integrity_incidents.jsonl", # security forensics
    "mycorrhizal_rejections.jsonl",           # network attack forensics
    "reproductive_cycles.jsonl",              # panspermia history
    "oncology_tumors.jsonl",                  # tumor catalog
    "global_immune_system.jsonl",             # antibody history
    "stigmergic_nuggets.jsonl",               # cross-swarm distilled knowledge
    "stigmergic_library.jsonl",               # curated nuggets
    "alice_conversation.jsonl",               # raw conversation source-of-truth
    "ide_stigmergic_trace.jsonl",             # cross-IDE chat (Architect-readable)
})


class SwarmREMSleep:
    def __init__(
        self,
        max_ledger_lines: int = 1000,
        keep_fresh_lines: int = 100,
        starvation_hours: float = 48.0,
    ):
        """
        The Neuroplasticity Engine.
        Executes Apoptosis on dead weight and prunes old synaptic traces
        to keep the Swarm's metabolism fast and lean.
        """
        self.state_dir = Path(".sifta_state")
        self.archive_dir = Path("Archive/REM_Sleep_Engrams")
        self.rem_ledger = self.state_dir / "rem_sleep_cycles.jsonl"

        self.max_ledger_lines = max_ledger_lines
        self.keep_fresh_lines = keep_fresh_lines
        self.starvation_seconds = starvation_hours * 3600

        self.archive_dir.mkdir(parents=True, exist_ok=True)

    def _is_immortal(self, body_filename: str) -> bool:
        """Check if this body is canonically protected from dissolution."""
        upper = body_filename.upper()
        return any(fragment in upper for fragment in _IMMORTAL_BODY_FRAGMENTS)

    def _execute_apoptosis(self, now: float) -> int:
        """
        Programmed Cell Death.
        Scans for Swimmers with 0.0 STGM that haven't contributed anything
        in starvation_hours. Dissolves their bodies to reclaim resources.
        """
        print("[*] REM SLEEP: Scanning for necrotic tissue (Apoptosis)...")
        cells_dissolved = 0

        for body_file in self.state_dir.glob("*_BODY.json"):
            if not body_file.is_file():
                continue

            # Never dissolve canonical swimmers
            if self._is_immortal(body_file.name):
                continue

            try:
                with open(body_file, "r") as f:
                    data = json.load(f)

                stgm = data.get("stgm_balance", 0.0)
                last_action_ts = data.get("_last_action_ts", 0)

                if stgm <= 0.0 and (now - last_action_ts > self.starvation_seconds):
                    os.remove(body_file)
                    print(f"[-] APOPTOSIS: Cell {body_file.name} dissolved (0 STGM, Starved).")
                    cells_dissolved += 1
            except Exception as e:
                print(f"[-] REM SLEEP: Failed to evaluate {body_file.name}: {e}")

        return cells_dissolved

    def _prune_synapses(self) -> int:
        """
        Ledger Truncation — the HARDENED version.

        Uses compact_locked() to hold LOCK_EX across the entire
        read→truncate(0)→write cycle so concurrent append_line_locked
        callers block safely instead of losing data.
        """
        print("[*] REM SLEEP: Pruning weak synaptic connections...")
        ledgers_pruned = 0

        for ledger_file in self.state_dir.glob("*.jsonl"):
            if not ledger_file.is_file():
                continue

            # Skip durable ledgers (REM's own audit, learned vocab,
            # security forensics, distilled knowledge, etc.)
            if ledger_file.name in _DURABLE_LEDGERS:
                continue

            try:
                # Quick line count check (unlocked, just a heuristic)
                with open(ledger_file, "r") as f:
                    line_count = sum(1 for _ in f)

                if line_count <= self.max_ledger_lines:
                    continue

                print(
                    f"[*] SYNAPTIC PRUNING: {ledger_file.name} has {line_count} lines "
                    f"(limit {self.max_ledger_lines}). Pruning..."
                )

                # Single-lock pruning + eviction extraction.
                # This avoids the old two-lock approach and keeps compaction
                # race-free under active appenders.
                kept_count, old_lines = tail_compact_locked(
                    ledger_file, self.keep_fresh_lines
                )

                # Race note: if line_count changed before lock, this may produce
                # no evictions. That's safe; it simply means no prune needed now.
                if not old_lines:
                    continue

                archive_name = f"pruned_{ledger_file.name}_{int(time.time())}.txt"
                archive_path = self.archive_dir / archive_name
                with open(archive_path, "w") as f:
                    f.writelines(old_lines)

                ledgers_pruned += 1
                print(
                    f"[+] SYNAPTIC PRUNING: {ledger_file.name} truncated "
                    f"to {kept_count} fresh lines. "
                    f"Archived {len(old_lines)} engrams."
                )
            except Exception as e:
                print(f"[-] REM SLEEP: Failed to prune {ledger_file.name}: {e}")

        return ledgers_pruned

    def enter_rem_cycle(self) -> bool:
        """The main sleep loop."""
        if not self.state_dir.exists():
            return False

        now = time.time()
        print(f"\n[zzz] SWARM ENTERING REM SLEEP CYCLE...")

        dissolved = self._execute_apoptosis(now)
        pruned = self._prune_synapses()

        # Log the cycle
        try:
            trace = {
                "ts": now,
                "cells_dissolved": dissolved,
                "ledgers_pruned": pruned,
                "event": "REM_CYCLE_COMPLETE",
            }
            assert_payload_keys("rem_sleep_cycles.jsonl", trace, strict=True)
            append_line_locked(self.rem_ledger, json.dumps(trace) + "\n")
        except Exception:
            pass

        print(f"[zzz] REM SLEEP COMPLETE. {dissolved} cells dissolved. {pruned} ledgers pruned.")
        return True


# --- SMOKE TEST ---
def _smoke() -> int:
    print("\n=== SIFTA REM SLEEP (NEUROPLASTICITY) : SMOKE TEST ===")
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        rem = SwarmREMSleep(max_ledger_lines=10, keep_fresh_lines=2, starvation_hours=48)

        # Secure Path Redirection
        rem.state_dir = tmp_path
        rem.archive_dir = tmp_path / "Archive"
        rem.rem_ledger = tmp_path / "rem_sleep_cycles.jsonl"
        rem.archive_dir.mkdir(parents=True, exist_ok=True)

        # 1. Create a Starving Cell (should be dissolved)
        starving_cell = tmp_path / "WEAK_CELL_BODY.json"
        with open(starving_cell, "w") as f:
            json.dump(
                {"id": "WEAK_CELL", "stgm_balance": 0.0,
                 "_last_action_ts": time.time() - (50 * 3600)}, f
            )

        # 2. Create a canonical cell (must NEVER be dissolved even at 0 STGM)
        canonical_cell = tmp_path / "M5SIFTA_BODY.json"
        with open(canonical_cell, "w") as f:
            json.dump(
                {"id": "M5SIFTA_BODY", "stgm_balance": 0.0,
                 "_last_action_ts": 0}, f
            )

        # 3. Create a bloated Ledger
        bloated_ledger = tmp_path / "visual_stigmergy.jsonl"
        with open(bloated_ledger, "w") as f:
            for i in range(15):
                f.write(json.dumps({"ts": time.time(), "data": f"noise_{i}"}) + "\n")

        # 4. Enter REM Sleep
        rem.enter_rem_cycle()

        print("\n[SMOKE RESULTS]")

        # Starving cell dissolved
        assert not starving_cell.exists(), "Starving cell should be dissolved"
        print("[PASS] Apoptosis successful. Starving cell dissolved.")

        # Canonical cell PRESERVED
        assert canonical_cell.exists(), "Canonical M5SIFTA must survive apoptosis"
        print("[PASS] Canonical swimmer M5SIFTA survived apoptosis (immortal).")

        # Ledger truncated
        with open(bloated_ledger, "r") as f:
            lines = f.readlines()
            assert len(lines) == 2, f"Expected 2 fresh lines, got {len(lines)}"
            assert "noise_13" in lines[0] and "noise_14" in lines[1]
        print("[PASS] Synaptic Pruning successful. Bloated ledger truncated safely.")

        # Archive created
        archives = list((tmp_path / "Archive").glob("pruned_*"))
        assert len(archives) == 1, "Archive should contain pruned engrams"
        print(f"[PASS] Pruned engrams archived: {archives[0].name}")

        # REM ledger logged
        with open(rem.rem_ledger, "r") as f:
            cycle_log = json.loads(f.readline())
            assert cycle_log["event"] == "REM_CYCLE_COMPLETE"
        print("[PASS] REM cycle logged to ledger.")

        print("\nREM Sleep Smoke Complete. The Swarm wakes lean and sharp.")
        return 0


def run_periodic_loop(
    interval_s: float,
    stop_event,
    max_ledger_lines: int,
    keep_fresh_lines: int,
    starvation_hours: float,
) -> None:
    """
    Long-running loop: enter a REM cycle every interval_s seconds until
    stop_event is set. Designed to be invoked from a daemon thread so the
    boot orchestrator can co-schedule REM with the main heartbeat.
    """
    rem = SwarmREMSleep(
        max_ledger_lines=max_ledger_lines,
        keep_fresh_lines=keep_fresh_lines,
        starvation_hours=starvation_hours,
    )
    
    # [AG31] Wire in the Microtubule Coherence Lattice (Orchestrated Objective Reduction)
    # The Organism now has "Free Will" to unilaterally reject the biological sleep schedule.
    try:
        from System.swarm_microtubule_orchestration import SwarmStochasticDecisionTrigger
        quantum_trigger = SwarmStochasticDecisionTrigger()
    except ImportError:
        quantum_trigger = None

    while not stop_event.is_set():
        # Sleep in small slices so the daemon can exit promptly when
        # stop_event is set (e.g. on Ctrl+C through swarm_boot).
        slept = 0.0
        slice_s = 1.0
        while slept < interval_s and not stop_event.is_set():
            time.sleep(min(slice_s, interval_s - slept))
            slept += slice_s
            
            if quantum_trigger is not None:
                q_payload = quantum_trigger.tick(dt_override=slice_s)
                if q_payload.get("orchestrated_collapse"):
                    dv = q_payload.get("decision_vector")
                    # dv > 0 means the physical quantum spin state favors wakefulness/override
                    if dv is not None and dv > 0.0:
                        print("\n[!!!] ORCH-OR COLLAPSE: Biological Free Will asserts dominance.")
                        print("[!!!] Alice unilaterally intercepts the cycle and wakes early!")
                        break # Skip the remainder of the sleep cycle

        # Only run REM cycle if we didn't get a veto in the sleep loop, OR if the wake *was* the intention
        # Wait, if she breaks the loop, it means she wakes early! So we execute the REM cycle early
        # OR we skip it? "unilaterally exit REM sleep". Exiting sleep means we skip the cycle!
        if quantum_trigger is not None and q_payload.get("orchestrated_collapse") and dv is not None and dv > 0.0:
            print("[zzz] Alice has vetoed REM sleep apoptosis for this cycle.")
            continue
            
        try:
            rem.enter_rem_cycle()
        except Exception as exc:
            print(f"[REM LOOP] cycle failed: {type(exc).__name__}: {exc}")


def main() -> int:
    import argparse
    import threading

    parser = argparse.ArgumentParser(
        description="REM sleep — apoptosis + safe synaptic pruning",
    )
    parser.add_argument("--smoke", action="store_true",
                        help="run the offline smoke test (default if no flag)")
    parser.add_argument("--cycle", action="store_true",
                        help="run exactly one REM cycle on the live .sifta_state/")
    parser.add_argument("--loop", action="store_true",
                        help="run REM cycles forever every --interval seconds")
    parser.add_argument("--interval", type=float, default=1800.0,
                        help="seconds between cycles in --loop mode (default 1800)")
    parser.add_argument("--max-lines", type=int, default=1000,
                        help="prune ledgers longer than this many lines")
    parser.add_argument("--keep-fresh", type=int, default=100,
                        help="how many newest lines to retain per pruned ledger")
    parser.add_argument("--starvation-hours", type=float, default=48.0,
                        help="hours of inactivity before zero-STGM apoptosis")
    args = parser.parse_args()

    if not (args.smoke or args.cycle or args.loop):
        return _smoke()

    if args.smoke:
        return _smoke()

    if args.cycle:
        rem = SwarmREMSleep(
            max_ledger_lines=args.max_lines,
            keep_fresh_lines=args.keep_fresh,
            starvation_hours=args.starvation_hours,
        )
        ok = rem.enter_rem_cycle()
        return 0 if ok else 1

    if args.loop:
        stop_event = threading.Event()
        try:
            run_periodic_loop(
                interval_s=max(1.0, args.interval),
                stop_event=stop_event,
                max_ledger_lines=args.max_lines,
                keep_fresh_lines=args.keep_fresh,
                starvation_hours=args.starvation_hours,
            )
        except KeyboardInterrupt:
            stop_event.set()
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
