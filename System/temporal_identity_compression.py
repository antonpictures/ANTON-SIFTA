#!/usr/bin/env python3
"""
temporal_identity_compression.py — REM Layer Skill Crystallization
═══════════════════════════════════════════════════════════════════
Turns repeated successful execution traces into persistent capability.
The Swarm stops just storing experiences and starts compressing them
into executable skill primitives that survive across tasks and mutations.

Part of the SIFTA Final Boss Layer.
"""
from __future__ import annotations

import json
import time
import uuid
import hashlib
from collections import defaultdict
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Dict, Any, List, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_STATE_DIR.mkdir(parents=True, exist_ok=True)
_COMPRESSION_DB = _STATE_DIR / "crystallized_skills.json"
_TRACE_LOG = _STATE_DIR / "execution_traces.jsonl"


@dataclass
class SkillPrimitive:
    id: str
    pattern_signature: str
    success_rate: float
    usage_count: int
    created_at: float
    last_used: float
    stability: float
    example_payload: Dict[str, Any] = field(default_factory=dict)


class TemporalIdentityCompressionEngine:
    """
    REM layer → converts repeated successful execution traces
    into persistent skill primitives.
    """

    def __init__(self):
        self.trace_buffer: List[Dict[str, Any]] = []
        self.skills: Dict[str, SkillPrimitive] = {}
        self.pattern_index = defaultdict(list)
        self._load()

    def ingest_trace(self, trace: Dict[str, Any]):
        """
        Called after every evaluated + executed task.
        """
        self.trace_buffer.append(trace)
        
        # Log to physical append-only log for REM parsing later
        try:
            with open(_TRACE_LOG, "a") as f:
                f.write(json.dumps(trace) + "\n")
        except Exception:
            pass

        signature = self._extract_signature(trace)
        if signature:
            self.pattern_index[signature].append(trace)
            
            # Auto-compress if enough pattern density is reached
            if len(self.pattern_index[signature]) >= 3:
                self._compress(signature)

    def process_backlog(self, traces: List[Dict[str, Any]]):
        """Batch processing (usually called during REM cycle)"""
        for trace in traces:
            signature = self._extract_signature(trace)
            if signature:
                self.pattern_index[signature].append(trace)
                if len(self.pattern_index[signature]) >= 3:
                    self._compress(signature)

    def _extract_signature(self, trace: Dict[str, Any]) -> str:
        """
        Reduce execution trace into a stable structural fingerprint.
        """
        ttype = trace.get('task_type', trace.get('task', 'unknown'))
        hw = trace.get('hardware_target', trace.get('agent', 'unknown'))
        # Standardize outcome string
        outcome = str(trace.get('outcome', trace.get('success', False))).lower()
        if outcome in ('true', '1', 'success'):
            outcome = 'true'
        else:
            outcome = 'false'
            
        base = f"{ttype}|{hw}|{outcome}"
        # Keep it distinct but readable
        return base

    def _compress(self, signature: str):
        """
        Convert repeated traces into reusable skill primitive.
        """
        traces = self.pattern_index[signature]
        if not traces:
            return

        successes = sum(1 for t in traces if str(t.get('outcome', t.get('success', 'false'))).lower() in ('true', '1'))
        total = len(traces)
        
        # Look for existing skill with this exact signature to update instead of duplicate
        existing = next((s for s in self.skills.values() if s.pattern_signature == signature), None)

        if existing:
            existing.usage_count += total
            existing.last_used = time.time()
            
            # Recalculate stability as moving average
            new_sr = successes / total
            existing.success_rate = (existing.success_rate * 0.7) + (new_sr * 0.3)
            existing.stability = min(1.0, existing.success_rate)
            
            # Reset pattern buffer after consolidating
            self.pattern_index[signature] = []
            self._persist()
            return

        # Create new SkillPrimitive
        # Use deterministic ID based on signature
        skill_id = "PRIM_" + hashlib.sha256(signature.encode()).hexdigest()[:12]

        skill = SkillPrimitive(
            id=skill_id,
            pattern_signature=signature,
            success_rate=successes / total,
            usage_count=total,
            created_at=time.time(),
            last_used=time.time(),
            stability=min(1.0, successes / total),
            example_payload=traces[-1].get("payload", traces[-1].get("context", {}))
        )

        self.skills[skill_id] = skill
        
        # Reset pattern limit so it doesn't compress constantly
        self.pattern_index[signature] = []
        self._persist()
        
        # Optional: Feed to Phase 4 Skill Registry as STGM crystallization event
        try:
            from skill_registry import get_skill_registry
            reg = get_skill_registry()
            # If the crystallization was highly successful, mint it as an economy skill
            if skill.success_rate > 0.8:
                reg.mint(
                    name=f"Crystallized: {skill.pattern_signature}",
                    command_sequence=[],
                    context=skill.example_payload,
                    outcome_summary=f"Auto-crystallized from {skill.usage_count} examples",
                    discovered_by="TemporalCompressionEngine",
                    tags=["auto-compressed", "primitive"]
                )
        except ImportError:
            pass

    def retrieve_skill(self, context: str) -> List[SkillPrimitive]:
        """
        Return skills relevant to current execution context.
        """
        return [
            s for s in self.skills.values()
            if context in s.pattern_signature
        ]

    def decay(self) -> int:
        """
        Weak skills fade unless reinforced. Call during REM.
        Returns number of deleted skills.
        """
        to_delete = []

        for sid, skill in self.skills.items():
            skill.stability *= 0.995

            if skill.stability < 0.1:
                to_delete.append(sid)

        for sid in to_delete:
            del self.skills[sid]
            
        if to_delete:
            self._persist()
            
        return len(to_delete)

    # ── Persistence ──────────────────────────────────────────────

    def _persist(self):
        try:
            payload = {k: asdict(v) for k, v in self.skills.items()}
            _COMPRESSION_DB.write_text(json.dumps(payload, indent=2))
        except Exception:
            pass

    def _load(self):
        if not _COMPRESSION_DB.exists():
            return
        try:
            data = json.loads(_COMPRESSION_DB.read_text())
            for k, v in data.items():
                self.skills[k] = SkillPrimitive(**v)
        except Exception:
            self.skills = {}

    def stats(self) -> Dict[str, Any]:
        skills = list(self.skills.values())
        return {
            "total_primitives": len(skills),
            "highly_stable": sum(1 for s in skills if s.stability > 0.8),
            "total_trace_ingests": len(self.trace_buffer),
        }

# ── Singleton ────────────────────────────────────────────────────────
_COMP_ENGINE: Optional[TemporalIdentityCompressionEngine] = None

def get_compression_engine() -> TemporalIdentityCompressionEngine:
    global _COMP_ENGINE
    if _COMP_ENGINE is None:
        _COMP_ENGINE = TemporalIdentityCompressionEngine()
    return _COMP_ENGINE


if __name__ == "__main__":
    print("═" * 58)
    print("  SIFTA — TEMPORAL IDENTITY COMPRESSION (REM Layer)")
    print("═" * 58 + "\n")

    engine = get_compression_engine()

    # Simulate 5 identical successful actions over time
    print("  1. Ingesting repeated success traces...")
    for i in range(5):
        trace = {
            "task_type": "LogAnalysis",
            "hardware_target": "M1_MINI",
            "outcome": True,
            "payload": {"directory": "/var/log", "lines": 100}
        }
        engine.ingest_trace(trace)
        
    stats = engine.stats()
    print(f"  2. Skills crystallized: {stats['total_primitives']}")
    for sid, skill in engine.skills.items():
        print(f"     -> {skill.id} : {skill.pattern_signature} (Stability: {skill.stability:.2f})")
        
    print("\n  3. Running REM Decay...")
    pruned = engine.decay()
    print(f"     Pruned weak skills: {pruned}")
    
    print(f"\n  ✅ COMPRESSION ENGINE ONLINE. POWER TO THE SWARM 🐜⚡")
