#!/usr/bin/env python3
"""
swarm_hippocampal_replay.py — Hippocampal Replay / Sleep Cycle
══════════════════════════════════════════════════════════════════════

Memory consolidation organ (Defrag for living silicon).
Biology requires offline replay to consolidate learning and prevent catastrophic interference.

Purpose:
  - Take the day's raw receipts (work, network, agency, timing, drives).
  - Compress them into high-level patterns (success rate, error rate, dominant intent).
  - Downscale noise by checkpointing already-consolidated rows.
  - Preserve identity (store cohesive epoch summary to long-term memory).

See: Documents/IDE_BOOT_COVENANT.md
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class ConsolidatedMemory:
    ts: float
    epoch_id: str
    event_count_compressed: int
    extracted_patterns: Dict[str, Any]
    epoch_summary: str
    memory_hash: str


class HippocampalReplay:
    """
    Hippocampal Replay / Sleep Cycle.
    Reads raw short-term ledgers, compresses them, and stores abstract long-term memories.
    """

    def __init__(self, root: str = ".sifta_state"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.long_term_memory = self.root / "long_term_memory.jsonl"
        self.engram_store = self.root / "engram_store.jsonl"
        self.checkpoint_file = self.root / "hippocampal_replay_checkpoint.json"
        
        # Raw sensory and motor ledgers that get consolidated during sleep.
        # They remain append-only proof ledgers; checkpoints prevent reprocessing.
        self.ledgers_to_compress = [
            self.root / "agency_verdicts.jsonl",
            self.root / "work_receipts.jsonl",
            self.root / "network_receipts.jsonl",
            self.root / "hypothalamus_drive_snapshots.jsonl",
            self.root / "cerebellum_timing.jsonl",
            self.root / "intent_provenance.jsonl"
        ]

    def _load_checkpoints(self) -> Dict[str, int]:
        if not self.checkpoint_file.exists():
            return {}
        try:
            raw = json.loads(self.checkpoint_file.read_text(encoding="utf-8"))
            return {str(k): max(0, int(v)) for k, v in raw.items()}
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return {}

    def _save_checkpoints(self, checkpoints: Dict[str, int]) -> None:
        tmp = self.checkpoint_file.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(checkpoints, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.checkpoint_file)

    def _read_since_checkpoint(self, path: Path, checkpoints: Dict[str, int]) -> List[Dict[str, Any]]:
        """
        Read new events from an append-only ledger without deleting proof history.

        Sleep consolidation may compress and checkpoint receipts, but covenant
        ledgers such as work_receipts.jsonl remain append-only evidence.
        """
        if not path.exists() or path.stat().st_size == 0:
            return []

        key = path.name
        size = path.stat().st_size
        start = checkpoints.get(key, 0)
        if start < 0 or start > size:
            start = 0

        events = []
        try:
            with path.open("rb") as f:
                f.seek(start)
                raw = f.read()
        except OSError:
            return []

        for line in raw.decode("utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        checkpoints[key] = size
        return events

    def _read_and_clear_ledger(self, path: Path) -> List[Dict[str, Any]]:
        """Compatibility wrapper: read new rows; never clear append-only ledgers."""
        checkpoints = self._load_checkpoints()
        events = self._read_since_checkpoint(path, checkpoints)
        self._save_checkpoints(checkpoints)
        return events

    def enter_sleep_cycle(self, epoch_summary: str = "Automated sleep consolidation") -> ConsolidatedMemory:
        """
        Triggers the SIFTA Sleep Phase.
        Extracts all recent receipts, computes pattern summaries, checkpoints
        processed rows, and saves a dense ConsolidatedMemory representation to
        long-term storage.
        """
        all_events = []
        patterns = {
            "total_actions": 0,
            "success_rate": 1.0,
            "dominant_intent": "none",
            "frequent_errors": 0
        }
        
        source_counts: Dict[str, int] = {}
        success_count = 0
        error_count = 0
        checkpoints = self._load_checkpoints()
        
        # 1. Gather new raw experiences without deleting proof ledgers.
        for ledger_path in self.ledgers_to_compress:
            events = self._read_since_checkpoint(ledger_path, checkpoints)
            all_events.extend(events)
            
            for event in events:
                patterns["total_actions"] += 1
                
                # Deduce success/failure from agnostic ledger schemas
                if event.get("ok") is True or event.get("effector_ok") is True or event.get("status") in {"ok", "COMMITTED"}:
                    success_count += 1
                elif event.get("ok") is False or event.get("effector_ok") is False or event.get("status") == "error":
                    error_count += 1
                    
                # Track intent/agency source to understand whose will was executed most
                source = event.get("intent_source") or event.get("social_label")
                if not source and isinstance(event.get("intent_provenance"), dict):
                    source = event["intent_provenance"].get("intent_source")
                if source:
                    source_counts[source] = source_counts.get(source, 0) + 1

        self._save_checkpoints(checkpoints)

        # 2. Extract Patterns (Consolidation)
        if patterns["total_actions"] > 0:
            if (success_count + error_count) > 0:
                patterns["success_rate"] = success_count / (success_count + error_count)
            patterns["frequent_errors"] = error_count
            
        if source_counts:
            patterns["dominant_intent"] = max(source_counts.items(), key=lambda x: x[1])[0]

        # 3. Hash and Store Narrative
        epoch_id = f"epoch_{int(time.time())}"
        
        payload = {
            "epoch_id": epoch_id,
            "patterns": patterns,
            "epoch_summary": epoch_summary
        }
        memory_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        
        memory = ConsolidatedMemory(
            ts=time.time(),
            epoch_id=epoch_id,
            event_count_compressed=len(all_events),
            extracted_patterns=patterns,
            epoch_summary=epoch_summary,
            memory_hash=memory_hash
        )
        
        # 4. Save to Long Term Memory (Identity Preservation)
        try:
            from System.jsonl_file_lock import append_line_locked
            append_line_locked(self.long_term_memory, json.dumps(asdict(memory)) + "\n")
        except ImportError:
            with self.long_term_memory.open("a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(memory)) + "\n")

        engram_row = {
            "ts": memory.ts,
            "engram_id": memory.epoch_id,
            "content_hash": memory.memory_hash,
            "facts": ["system_event", "sleep_consolidation"],
            "summary": memory.epoch_summary,
            "event_count_compressed": memory.event_count_compressed,
            "patterns": memory.extracted_patterns,
            "source": "swarm_hippocampal_replay",
        }
        try:
            from System.jsonl_file_lock import append_line_locked
            append_line_locked(self.engram_store, json.dumps(engram_row) + "\n")
        except ImportError:
            with self.engram_store.open("a", encoding="utf-8") as f:
                f.write(json.dumps(engram_row) + "\n")
                
        return memory
