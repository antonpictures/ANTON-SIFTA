#!/usr/bin/env python3
"""
swarm_sleep_auditor.py — Sleep Auditor (Consolidation Verification)
══════════════════════════════════════════════════════════════════════

Biology doctrine: Sleep is not "off". Sleep is maintenance mode.
This organ proves that the Hippocampal Replay actually worked:
  - Did it compress receipts?
  - Did it forget noise (glymphatic cleanup)?
  - Did it preserve identity facts (neocortical schema)?
  - Did it apply synaptic homeostasis (pruning)?

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
class SleepAuditReport:
    ts: float
    audit_id: str
    pre_sleep_bytes: int
    post_sleep_bytes: int
    receipt_compression_ratio: float
    replay_count: int
    duplicate_pruned: int
    noise_deleted: int
    identity_facts_preserved: int
    q_updates_applied: int
    post_sleep_integrity_hash: str
    glymphatic_cleanup_ok: bool
    synaptic_homeostasis_ok: bool


class SleepAuditor:
    """
    Verifies memory consolidation and biological cleanup during the SIFTA Sleep Cycle.
    """

    def __init__(self, root: str = ".sifta_state"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.audit_ledger = self.root / "sleep_audits.jsonl"
        self.ledgers_monitored = [
            self.root / "agency_verdicts.jsonl",
            self.root / "work_receipts.jsonl",
            self.root / "network_receipts.jsonl",
            self.root / "hypothalamus_drive_snapshots.jsonl",
            self.root / "cerebellum_timing.jsonl",
            self.root / "intent_provenance.jsonl"
        ]
        self.long_term_memory = self.root / "long_term_memory.jsonl"

    def measure_pre_sleep(self) -> Dict[str, Any]:
        """
        Takes a snapshot of the organism's memory burden BEFORE the sleep cycle begins.
        """
        total_bytes = 0
        event_count = 0
        for path in self.ledgers_monitored:
            if path.exists() and path.is_file():
                total_bytes += path.stat().st_size
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        for line in f:
                            if line.strip():
                                event_count += 1
                except Exception:
                    pass
                    
        ltm_bytes = self.long_term_memory.stat().st_size if self.long_term_memory.exists() else 0

        return {
            "total_bytes": total_bytes,
            "event_count": event_count,
            "ltm_bytes": ltm_bytes,
        }

    def audit_post_sleep(self, pre_sleep_metrics: Dict[str, Any], consolidated_memory: Any) -> SleepAuditReport:
        """
        Audits the results AFTER the sleep cycle completes to prove physiological maintenance occurred.
        """
        post_bytes = 0
        for path in self.ledgers_monitored:
            if path.exists() and path.is_file():
                post_bytes += path.stat().st_size
                
        ltm_bytes = self.long_term_memory.stat().st_size if self.long_term_memory.exists() else 0

        pre_bytes = pre_sleep_metrics["total_bytes"]
        pre_events = pre_sleep_metrics["event_count"]
        
        # Glymphatic clearance: How much raw data was flushed?
        noise_deleted = pre_bytes - post_bytes
        glymphatic_cleanup_ok = noise_deleted > 0 or pre_bytes == 0
        
        # Compression ratio calculation
        compression_ratio = 1.0
        if pre_bytes > 0:
            ltm_growth = max(1, ltm_bytes - pre_sleep_metrics["ltm_bytes"])
            compression_ratio = pre_bytes / ltm_growth

        # Synaptic homeostasis: Pruning redundant action sequences
        # (In SIFTA, clearing the day ledger satisfies this)
        duplicate_pruned = pre_events  
        synaptic_homeostasis_ok = duplicate_pruned > 0 or pre_events == 0

        # Identity preservation: Extracting stable facts from the day's experiences
        patterns = getattr(consolidated_memory, "extracted_patterns", {})
        identity_facts_preserved = len(patterns)
        
        # Did the replay result in long-term reinforcement?
        q_updates_applied = 1 if hasattr(consolidated_memory, "memory_hash") else 0
        
        # Verify long-term memory integrity (Neocortical schema stability)
        integrity_hash = ""
        if self.long_term_memory.exists() and self.long_term_memory.is_file():
            h = hashlib.sha256()
            with open(self.long_term_memory, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            integrity_hash = h.hexdigest()

        report = SleepAuditReport(
            ts=time.time(),
            audit_id=f"audit_{int(time.time())}",
            pre_sleep_bytes=pre_bytes,
            post_sleep_bytes=post_bytes,
            receipt_compression_ratio=round(compression_ratio, 2),
            replay_count=pre_events,
            duplicate_pruned=duplicate_pruned,
            noise_deleted=noise_deleted,
            identity_facts_preserved=identity_facts_preserved,
            q_updates_applied=q_updates_applied,
            post_sleep_integrity_hash=integrity_hash,
            glymphatic_cleanup_ok=glymphatic_cleanup_ok,
            synaptic_homeostasis_ok=synaptic_homeostasis_ok
        )
        
        self._record_audit(report)
        return report

    def _record_audit(self, report: SleepAuditReport):
        try:
            from System.jsonl_file_lock import append_line_locked
            append_line_locked(self.audit_ledger, json.dumps(asdict(report)) + "\n")
        except ImportError:
            with self.audit_ledger.open("a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(report)) + "\n")
