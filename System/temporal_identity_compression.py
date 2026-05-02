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

from System.jsonl_file_lock import append_line_locked

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_STATE_DIR.mkdir(parents=True, exist_ok=True)
_COMPRESSION_DB = _STATE_DIR / "crystallized_skills.json"
_TRACE_LOG = _STATE_DIR / "execution_traces.jsonl"
_CRYSTALLIZATION_LOG = _STATE_DIR / "skill_crystallization_receipts.jsonl"

SCHEMA_VERSION = "event100.temporal_identity_compression.v2"


@dataclass
class SkillPrimitive:
    id: str
    pattern_signature: str
    success_rate: float
    usage_count: int
    created_at: float
    last_used: float
    stability: float
    frozen: bool = False
    quarantined: bool = False
    authoritative: bool = True
    example_payload: Dict[str, Any] = field(default_factory=dict)
    source: str = "execution_trace"
    cycle_id: str = ""
    source_hash: str = ""
    td_value_mean: float = 0.0
    positive_examples: int = 0


class TemporalIdentityCompressionEngine:
    """
    REM layer → converts repeated successful execution traces
    into persistent skill primitives.
    """

    def __init__(
        self,
        state_dir: Optional[Path] = None,
        *,
        min_pattern_count: int = 3,
        min_success_rate: float = 0.67,
    ):
        self.state_dir = Path(state_dir) if state_dir is not None else _STATE_DIR
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.compression_db = self.state_dir / _COMPRESSION_DB.name
        self.trace_log = self.state_dir / _TRACE_LOG.name
        self.receipt_log = self.state_dir / _CRYSTALLIZATION_LOG.name
        self.min_pattern_count = int(min_pattern_count)
        self.min_success_rate = float(min_success_rate)
        self.trace_buffer: List[Dict[str, Any]] = []
        self.skills: Dict[str, SkillPrimitive] = {}
        self.pattern_index = defaultdict(list)
        self._load()

    def ingest_trace(self, trace: Dict[str, Any]) -> Optional[SkillPrimitive]:
        """
        Called after every evaluated + executed task.
        """
        self.trace_buffer.append(trace)
        
        # Log to physical append-only log for REM parsing later
        append_line_locked(self.trace_log, json.dumps(trace, sort_keys=True) + "\n")

        signature = self._extract_signature(trace)
        if signature:
            self.pattern_index[signature].append(trace)
            
            # Auto-compress if enough pattern density is reached
            if len(self.pattern_index[signature]) >= self.min_pattern_count:
                return self._compress(signature)
        return None

    def process_backlog(self, traces: List[Dict[str, Any]]) -> Dict[str, int]:
        """Batch processing (usually called during REM cycle)"""
        before = len(self.skills)
        updated = 0
        for trace in traces:
            signature = self._extract_signature(trace)
            if signature:
                self.pattern_index[signature].append(trace)
                if len(self.pattern_index[signature]) >= self.min_pattern_count:
                    existing = next((s for s in self.skills.values() if s.pattern_signature == signature), None)
                    self._compress(signature)
                    if existing is not None:
                        updated += 1
        return {
            "traces_processed": len(traces),
            "skills_created": max(0, len(self.skills) - before),
            "skills_updated": updated,
        }

    def process_body_brain_ticks(
        self,
        rows: List[Dict[str, Any]],
        *,
        source_hash: str = "",
        cycle_id: str = "",
    ) -> Dict[str, int]:
        """Convert replayed body-brain rows into skill traces and compress them."""

        traces: List[Dict[str, Any]] = []
        for item in rows:
            raw = item.get("row") if isinstance(item.get("row"), dict) else item
            action = item.get("action") if isinstance(item.get("action"), dict) else raw.get("action", {})
            result = item.get("result") if isinstance(item.get("result"), dict) else raw.get("result", {})
            td_value = self._coerce_float(item.get("td_value", raw.get("td_value")))
            action_type = str(action.get("type") or "unknown").strip() or "unknown"
            target = str(action.get("target") or "").strip()
            status = str(result.get("status") or "").strip().lower()
            success = status in {"completed", "success", "succeeded", "sent"} and td_value > 0.0
            task_label = f"body_brain:{action_type}:{target}" if target else f"body_brain:{action_type}"
            traces.append(
                {
                    "task_type": task_label,
                    "hardware_target": "SIFTA_BODY",
                    "outcome": success,
                    "td_value": td_value,
                    "source": "body_brain_memory.jsonl",
                    "source_hash": source_hash,
                    "cycle_id": cycle_id,
                    "payload": {
                        "action": action,
                        "target": target,
                        "result_status": status,
                        "tick_id": raw.get("tick_id", ""),
                        "drive_state": raw.get("drive_state", ""),
                        "metabolic_mode": raw.get("metabolic_mode", ""),
                    },
                }
            )
        return self.process_backlog(traces)

    def _extract_signature(self, trace: Dict[str, Any]) -> str:
        """
        Reduce execution trace into a stable structural fingerprint.
        """
        ttype = trace.get('task_type', trace.get('task', 'unknown'))
        hw = trace.get('hardware_target', trace.get('agent', 'unknown'))
        # The signature intentionally excludes outcome. Success/failure is a
        # metric over repeated attempts, not a separate skill identity.
        base = f"{ttype}|{hw}"
        # Keep it distinct but readable
        return base

    def _compress(self, signature: str) -> Optional[SkillPrimitive]:
        """
        Convert repeated traces into reusable skill primitive.
        """
        traces = self.pattern_index[signature]
        if not traces:
            return None

        successes = sum(1 for t in traces if self._trace_success(t))
        total = len(traces)
        success_rate = successes / total if total else 0.0
        
        # Look for existing skill with this exact signature to update instead of duplicate
        existing = next((s for s in self.skills.values() if s.pattern_signature == signature), None)

        if existing:
            existing.usage_count += total
            existing.last_used = time.time()
            
            # Recalculate stability as moving average
            existing.success_rate = (existing.success_rate * 0.7) + (success_rate * 0.3)
            existing.stability = min(1.0, existing.success_rate)
            existing.positive_examples += successes
            existing.td_value_mean = self._mean_td(traces)
            
            # Reset pattern buffer after consolidating
            self.pattern_index[signature] = []
            self._persist()
            self._write_receipt("SKILL_UPDATED", existing, traces)
            return existing

        if success_rate < self.min_success_rate:
            self.pattern_index[signature] = []
            self._write_receipt(
                "SKILL_REJECTED_LOW_SUCCESS",
                None,
                traces,
                extra={"pattern_signature": signature, "success_rate": round(success_rate, 6)},
            )
            return None

        # Create new SkillPrimitive
        # Use deterministic ID based on signature
        skill_id = "PRIM_" + hashlib.sha256(signature.encode()).hexdigest()[:12]
        latest = traces[-1]

        skill = SkillPrimitive(
            id=skill_id,
            pattern_signature=signature,
            success_rate=success_rate,
            usage_count=total,
            created_at=time.time(),
            last_used=time.time(),
            stability=min(1.0, success_rate),
            example_payload=latest.get("payload", latest.get("context", {})),
            source=str(latest.get("source") or "execution_trace"),
            cycle_id=str(latest.get("cycle_id") or ""),
            source_hash=str(latest.get("source_hash") or ""),
            td_value_mean=self._mean_td(traces),
            positive_examples=successes,
        )

        self.skills[skill_id] = skill
        
        # Reset pattern limit so it doesn't compress constantly
        self.pattern_index[signature] = []
        self._persist()
        self._write_receipt("SKILL_CRYSTALLIZED", skill, traces)
        
        # Optional: feed Phase 4 Skill Registry only in the live state root.
        # Tests and isolated dream cycles must not mutate the user's real STGM
        # registry through the singleton SkillRegistry.
        if self.state_dir.resolve() == _STATE_DIR.resolve():
            try:
                try:
                    from System.skill_registry import get_skill_registry
                except ImportError:
                    from skill_registry import get_skill_registry
                reg = get_skill_registry()
                # If the crystallization was highly successful, mint it as an economy skill
                if skill.success_rate > 0.8:
                    reg.mint(
                        name=f"Crystallized: {skill.pattern_signature}",
                        command_sequence=[f"skill:{skill.pattern_signature}"],
                        context=skill.example_payload,
                        outcome_summary=f"Auto-crystallized from {skill.usage_count} examples",
                        discovered_by="TemporalCompressionEngine",
                        tags=["auto-compressed", "primitive"],
                    )
            except ImportError:
                pass
        return skill

    def retrieve_skill(self, context: str) -> List[SkillPrimitive]:
        """
        Return skills relevant to current execution context.
        """
        return [
            s for s in self.skills.values()
            if context in s.pattern_signature and not s.frozen and not s.quarantined
        ]

    def decay(self) -> int:
        """
        Weak skills fade unless reinforced. Call during REM.
        Returns number of newly FROZEN skills (NO DELETION ALLOWED).
        """
        newly_frozen = 0

        for sid, skill in self.skills.items():
            if skill.frozen:
                continue
                
            skill.stability *= 0.995

            if skill.stability < 0.1:
                skill.frozen = True
                skill.authoritative = False
                newly_frozen += 1
            
        if newly_frozen > 0:
            self._persist()
            
        return newly_frozen

    # ── Persistence ──────────────────────────────────────────────

    @staticmethod
    def _coerce_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _trace_success(self, trace: Dict[str, Any]) -> bool:
        outcome = str(trace.get("outcome", trace.get("success", False))).lower()
        if outcome in ("true", "1", "success", "succeeded", "completed", "sent"):
            return True
        if outcome in ("false", "0", "fail", "failed", "error"):
            return False
        return self._coerce_float(trace.get("td_value")) > 0.0

    def _mean_td(self, traces: List[Dict[str, Any]]) -> float:
        vals = [self._coerce_float(t.get("td_value")) for t in traces]
        if not vals:
            return 0.0
        return round(sum(vals) / len(vals), 6)

    def _write_receipt(
        self,
        action: str,
        skill: Optional[SkillPrimitive],
        traces: List[Dict[str, Any]],
        *,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        row: Dict[str, Any] = {
            "kind": "skill_crystallization",
            "schema_version": SCHEMA_VERSION,
            "ts": time.time(),
            "action": action,
            "trace_count": len(traces),
            "positive_examples": sum(1 for t in traces if self._trace_success(t)),
            "source_hash": str(traces[-1].get("source_hash") or "") if traces else "",
            "cycle_id": str(traces[-1].get("cycle_id") or "") if traces else "",
            "truth_label": "OPERATIONAL",
        }
        if skill is not None:
            row.update(
                {
                    "skill_id": skill.id,
                    "pattern_signature": skill.pattern_signature,
                    "success_rate": round(skill.success_rate, 6),
                    "stability": round(skill.stability, 6),
                }
            )
        if extra:
            row.update(extra)
        append_line_locked(self.receipt_log, json.dumps(row, sort_keys=True) + "\n")

    def _persist(self):
        payload = {k: asdict(v) for k, v in self.skills.items()}
        self.compression_db.write_text(json.dumps(payload, indent=2, sort_keys=True))

    def _load(self):
        if not self.compression_db.exists():
            return
        try:
            data = json.loads(self.compression_db.read_text())
            for k, v in data.items():
                self.skills[k] = SkillPrimitive(**v)
        except Exception:
            self.skills = {}

    def stats(self) -> Dict[str, Any]:
        skills = list(self.skills.values())
        return {
            "total_primitives": len(skills),
            "highly_stable": sum(1 for s in skills if s.stability > 0.8),
            "frozen": sum(1 for s in skills if s.frozen),
            "quarantined": sum(1 for s in skills if s.quarantined),
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
