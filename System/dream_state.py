#!/usr/bin/env python3
"""
dream_state.py — SIFTA OS Swarm Dreaming (hippocampal-style consolidation)
════════════════════════════════════════════════════════════════════════════
NOVEL: Literal replay synthesis during Architect absence — not metaphor.

When the Temporal Spine (or any caller) detects meaningful absence, the
DreamEngine reads the memory ledger, pairs traces that share semantic tags,
and writes DreamTrace records — always marked INFERRED, never ground truth.

Does NOT mutate the primary memory ledger.
Does NOT delete swimmer state.
STGM dream rewards append to the same jsonl pattern as StigmergicMemoryBus.

Integration: see TemporalSpine.open_session / close_session hooks.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_DREAM_DIR = _STATE / "dreams"
_DREAM_LOG = _DREAM_DIR / "dream_traces.jsonl"
_LEDGER_FILE = _STATE / "memory_ledger.jsonl"
_STGM_LOG = _STATE / "stgm_memory_rewards.jsonl"

STGM_DREAM_REWARD = 0.08
MIN_OVERLAP = 2
MAX_DREAM_CYCLES = 50


def _mint_stgm_dream(amount: float, trace_id: str, app: str = "dream_state") -> None:
    """Same shape as StigmergicMemoryBus _mint_stgm — no silent free mint elsewhere."""
    entry = {
        "ts": time.time(),
        "reason": "DREAM_SYNTHESIS",
        "amount": amount,
        "trace_id": trace_id,
        "app": app,
    }
    _STATE.mkdir(parents=True, exist_ok=True)
    try:
        with open(_STGM_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


@dataclass
class DreamTrace:
    """Synthesized connection — INFERRED only."""

    dream_id: str
    source_ids: list[str]
    synthesis: str
    semantic_tags: list[str]
    confidence: float
    timestamp: float
    stgm_minted: float
    cycle: int
    kind: str = "INFERRED"


class DreamEngine:
    """
    Runs when the Architect is away (caller supplies absence_hours).
    Graph: tag overlap → template synthesis. No LLM required.
    """

    def __init__(self, architect_id: str):
        self.architect_id = architect_id
        self.cycles_run = 0
        self.stgm_earned = 0.0
        _DREAM_DIR.mkdir(parents=True, exist_ok=True)

    def dream(self, absence_hours: float = 0.0) -> list[DreamTrace]:
        cycles = max(1, min(int(absence_hours / 2) if absence_hours > 0 else 1, MAX_DREAM_CYCLES))
        # Deeper absence → higher synthesis budget (not repeated passes over the same pairs).
        max_syntheses = min(12 * cycles, 400)
        print(f"💤 Dream state initiated — depth={cycles} — {absence_hours:.1f}h absence (cap {max_syntheses})")

        traces = self._load_traces()
        dreams = self._run_cycle(traces, cycle=0, max_syntheses=max_syntheses)
        self.cycles_run += 1

        print(f"💤 Dream complete — {len(dreams)} syntheses — {self.stgm_earned:.3f} STGM attributed\n")
        return dreams

    def morning_briefing(self) -> str:
        """Inject above first LLM user message of the day (optional)."""
        dreams = self._load_dreams()
        if not dreams:
            return ""

        recent = [d for d in dreams if (time.time() - d.get("timestamp", 0)) < 86400]
        if not recent:
            return ""

        recent.sort(key=lambda d: float(d.get("confidence", 0)), reverse=True)
        lines = ["[SWARM DREAM REPORT — while you were away, I made these connections:]\n"]
        for d in recent[:5]:
            syn = d.get("synthesis", "")
            conf = float(d.get("confidence", 0))
            nsrc = len(d.get("source_ids", []))
            lines.append(f"  • {syn} (confidence: {conf:.0%}, from: {nsrc} memories)")
        lines.append("\n[These are inferences, not facts. Correct me if I'm wrong.]")
        return "\n".join(lines)

    def _run_cycle(
        self,
        traces: list[dict[str, Any]],
        cycle: int,
        max_syntheses: int = 400,
    ) -> list[DreamTrace]:
        new_dreams: list[DreamTrace] = []
        # Only ground-truth ledger rows — never pair INFERRED dream rows (prevents combinatorial blow-up).
        mine = [
            t
            for t in traces
            if t.get("architect_id") == self.architect_id
            and not t.get("is_inferred")
            and t.get("app_context") != "dream"
        ]

        for t1, t2 in itertools.combinations(mine, 2):
            if len(new_dreams) >= max_syntheses:
                break
            id1, id2 = t1.get("trace_id"), t2.get("trace_id")
            if not id1 or not id2 or id1 == id2:
                continue

            tags1 = set(t1.get("semantic_tags") or [])
            tags2 = set(t2.get("semantic_tags") or [])
            overlap = tags1 & tags2
            if len(overlap) < MIN_OVERLAP:
                continue

            pk = _pair_key(str(id1), str(id2))
            if self._already_dreamed(pk):
                continue

            synthesis = self._synthesize(
                str(t1.get("raw_text", "")),
                str(t2.get("raw_text", "")),
                overlap,
            )
            confidence = min(1.0, len(overlap) * 0.25 + 0.3)
            did = hashlib.sha256(f"{pk}:{cycle}".encode()).hexdigest()[:10]

            dream = DreamTrace(
                dream_id=did,
                source_ids=[str(id1), str(id2)],
                synthesis=synthesis,
                semantic_tags=sorted(overlap),
                confidence=confidence,
                timestamp=time.time(),
                stgm_minted=STGM_DREAM_REWARD,
                cycle=cycle,
            )

            with open(_DREAM_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(dream)) + "\n")

            _mint_stgm_dream(STGM_DREAM_REWARD, did, "dream_state")
            self.stgm_earned += STGM_DREAM_REWARD
            new_dreams.append(dream)
            print(f"  💭 [{did}] {synthesis[:100]}... ({confidence:.0%})")

        return new_dreams

    def _synthesize(self, text1: str, text2: str, shared_tags: set) -> str:
        tag_str = " + ".join(sorted(shared_tags))
        return (
            f"INFERRED [{tag_str}]: '{text1.strip()[:200]}' and '{text2.strip()[:200]}' "
            f"are related — the Architect may expect these to connect."
        )

    def _load_traces(self) -> list[dict[str, Any]]:
        if not _LEDGER_FILE.exists():
            return []
        out: list[dict[str, Any]] = []
        with open(_LEDGER_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
        return out

    def _load_dreams(self) -> list[dict[str, Any]]:
        if not _DREAM_LOG.exists():
            return []
        out: list[dict[str, Any]] = []
        with open(_DREAM_LOG, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
        return out

    def _already_dreamed(self, pair_key: str) -> bool:
        if not _DREAM_LOG.exists():
            return False
        with open(_DREAM_LOG, encoding="utf-8") as f:
            for line in f:
                try:
                    d = json.loads(line)
                    sids = d.get("source_ids") or []
                    if len(sids) >= 2 and _pair_key(str(sids[0]), str(sids[1])) == pair_key:
                        return True
                except Exception:
                    pass
        return False

def _pair_key(id1: str, id2: str) -> str:
    return hashlib.sha256("".join(sorted([id1, id2])).encode()).hexdigest()[:16]


if __name__ == "__main__":
    _LEDGER_FILE.parent.mkdir(parents=True, exist_ok=True)
    seeds = [
        {
            "trace_id": "aaa1",
            "architect_id": "Ioan_M5",
            "app_context": "simulation_1",
            "raw_text": "My shirt is red",
            "semantic_tags": ["clothing", "identity"],
            "timestamp": time.time() - 7200,
            "stgm_paid": 0.05,
            "recall_count": 0,
        },
        {
            "trace_id": "bbb2",
            "architect_id": "Ioan_M5",
            "app_context": "simulation_2",
            "raw_text": "I am going to the store today",
            "semantic_tags": ["location", "identity"],
            "timestamp": time.time() - 5400,
            "stgm_paid": 0.05,
            "recall_count": 0,
        },
        {
            "trace_id": "ccc3",
            "architect_id": "Ioan_M5",
            "app_context": "simulation_2",
            "raw_text": "Remember the number six",
            "semantic_tags": ["numbers", "memory"],
            "timestamp": time.time() - 3600,
            "stgm_paid": 0.05,
            "recall_count": 0,
        },
        {
            "trace_id": "ddd4",
            "architect_id": "Ioan_M5",
            "app_context": "simulation_3",
            "raw_text": "I prefer red things",
            "semantic_tags": ["clothing", "identity", "general"],
            "timestamp": time.time() - 1800,
            "stgm_paid": 0.05,
            "recall_count": 0,
        },
    ]
    with open(_LEDGER_FILE, "w", encoding="utf-8") as f:
        for s in seeds:
            f.write(json.dumps(s) + "\n")

    print("=" * 62)
    print("  SIFTA — DREAM STATE")
    print("  Consolidation during absence (INFERRED only).")
    print("=" * 62 + "\n")

    engine = DreamEngine(architect_id="Ioan_M5")
    print("── DREAMING (8h absence) ───────────────────────────────────\n")
    engine.dream(absence_hours=8.0)
    print("── MORNING BRIEFING ────────────────────────────────────────")
    print(engine.morning_briefing())
    print("\n  POWER TO THE SWARM")
