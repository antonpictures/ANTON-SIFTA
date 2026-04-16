#!/usr/bin/env python3
"""
stigmergic_memory_bus.py — SIFTA OS Cross-App Memory
=====================================================

The old man moves between simulations.
He forgets. The Swarm remembers for him.
Swimmers crawl the ledger. Proof of Useful Recall.

Architecture:
  - Every memory is a PheromoneTrace written to .sifta_state/memory_ledger.jsonl
  - Traces are tagged with semantic categories (clothing, numbers, names, places...)
  - When any app asks "what did the Architect say about X?", MemoryForagers
    are dispatched to crawl the ledger and return the best match
  - STGM is minted for: storing a memory (0.05) and recalling it (0.15)
  - No central AI running in background. Cold storage. Hot recall on demand.

Usage:
    bus = StigmergicMemoryBus(architect_id="IOAN_M5")

    # In Simulation 1 — store a memory
    bus.remember("My shirt is red", app_context="simulation_1")

    # In Simulation 2 — store another
    bus.remember("The number is six", app_context="simulation_2")

    # In Simulation 3 — recall across all apps
    result = bus.recall("What color was my shirt?", app_context="simulation_3")
    print(result.answer)  # "Your shirt is red. You told me in simulation_1."
"""

from __future__ import annotations

import json
import time
import hashlib
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional
from difflib import SequenceMatcher


# ─── Config ────────────────────────────────────────────────────────────────────

_REPO = Path(__file__).resolve().parent.parent

LEDGER_DIR       = _REPO / ".sifta_state"
LEDGER_FILE      = LEDGER_DIR / "memory_ledger.jsonl"
STGM_LOG_FILE    = LEDGER_DIR / "stgm_memory_rewards.jsonl"

STGM_STORE_REWARD  = 0.05   # paid to swimmer for writing a memory
STGM_RECALL_REWARD = 0.15   # paid to swimmer for successful cross-app recall

# Semantic categories — swimmer uses these to "smell" what the memory is about
SEMANTIC_TAGS = {
    "clothing":  ["shirt", "wearing", "clothes", "dress", "pants", "jacket", "hat",
                  "shoes", "color", "colour", "red", "blue", "green", "white", "black"],
    "numbers":   ["number", "zero", "one", "two", "three", "four", "five", "six",
                  "seven", "eight", "nine", "ten", "remember", "digit", "count", "score"],
    "identity":  ["name", "who", "person", "call", "known", "am", "my name"],
    "location":  ["place", "where", "room", "simulation", "app", "here", "home", "address"],
    "time":      ["when", "time", "day", "today", "before", "after", "ago", "date", "tomorrow"],
    "health":    ["pain", "medicine", "doctor", "feel", "sick", "tired", "heart", "pacemaker"],
    "food":      ["eat", "food", "hungry", "lunch", "dinner", "coffee", "water", "drink"],
    "people":    ["friend", "wife", "husband", "son", "daughter", "mother", "father", "family"],
    "tasks":     ["todo", "task", "need to", "must", "should", "don't forget", "remind"],
    "mood":      ["happy", "sad", "angry", "excited", "worried", "calm", "love", "hate"],
}


# ─── Data Structures ───────────────────────────────────────────────────────────

@dataclass
class PheromoneTrace:
    """
    A single memory written to the hard drive.
    This is what the MemoryForager finds when it crawls the ledger.
    """
    trace_id:      str
    architect_id:  str
    app_context:   str           # which simulation/app wrote this
    raw_text:      str           # exactly what the Architect said
    semantic_tags: list          # what categories this memory belongs to
    timestamp:     float
    stgm_paid:     float         # reward paid to the swimmer that stored this

    def fingerprint(self) -> str:
        """Cryptographic identity of this trace."""
        payload = f"{self.architect_id}:{self.raw_text}:{self.timestamp}"
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


@dataclass
class RecallResult:
    """
    What the MemoryForager delivers back to the app after crawling the ledger.
    """
    found:          bool
    answer:         str                      # natural language answer for the LLM
    source_app:     Optional[str] = None     # which app the memory came from
    source_text:    Optional[str] = None     # exact original statement
    confidence:     float = 0.0              # 0.0 → 1.0
    stgm_minted:    float = 0.0
    forager_report: str = ""                 # what the swimmer found on its crawl


# ─── MemoryForager ─────────────────────────────────────────────────────────────

class MemoryForager:
    """
    A single swimmer dispatched to crawl the ledger.
    It is blind to meaning — it can only smell semantic tags
    and measure text similarity to the query.
    This is the biological metaphor made literal.
    """

    def __init__(self, swimmer_id: str, architect_id: str):
        self.swimmer_id   = swimmer_id
        self.architect_id = architect_id
        self.traces_read  = 0
        self.traces_hit   = 0

    def forage(self, query: str, ledger_path: Path) -> list:
        """
        Crawl every trace in the ledger.
        Return all traces that smell like the query, ranked by confidence.
        """
        if not ledger_path.exists():
            return []

        query_tags  = _extract_tags(query)
        query_words = set(query.lower().split())
        candidates  = []

        with open(ledger_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                    trace = PheromoneTrace(**raw)
                except Exception:
                    continue

                # Only smell traces from this architect
                if trace.architect_id != self.architect_id:
                    continue

                self.traces_read += 1

                # Compute scent strength: tag overlap + text similarity
                tag_overlap = len(set(trace.semantic_tags) & set(query_tags))
                text_sim    = SequenceMatcher(
                    None,
                    query.lower(),
                    trace.raw_text.lower()
                ).ratio()

                # Keyword match boost
                trace_words   = set(trace.raw_text.lower().split())
                keyword_boost = len(query_words & trace_words) * 0.1

                confidence = min(1.0, (tag_overlap * 0.3) + text_sim + keyword_boost)

                if confidence > 0.1:   # threshold — weak signals ignored
                    self.traces_hit += 1
                    candidates.append((confidence, trace))

        # Sort by strongest scent first
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates

    def report(self) -> str:
        return (
            f"Forager {self.swimmer_id}: "
            f"read {self.traces_read} traces, "
            f"hit {self.traces_hit} candidates"
        )


# ─── Stigmergic Memory Bus ─────────────────────────────────────────────────────

class StigmergicMemoryBus:
    """
    The main memory system for SIFTA OS.

    Every app talks to this bus.
    Memories are stored as pheromone traces on disk.
    Recall dispatches MemoryForagers to crawl the ledger.
    STGM is minted for both storing and recalling.

    The old man doesn't need to remember.
    The Swarm remembers for him.
    """

    def __init__(self, architect_id: str):
        self.architect_id = architect_id
        LEDGER_DIR.mkdir(exist_ok=True)
        self._forager_counter = 0

    # ── Public API ─────────────────────────────────────────────────────────────

    def remember(self, text: str, app_context: str) -> PheromoneTrace:
        """
        Store a memory from any app.
        Called when the Architect says something worth keeping.

        Returns the trace so the app can confirm it was written.
        """
        tags  = _extract_tags(text)
        ts    = time.time()
        tid   = hashlib.sha256(f"{self.architect_id}:{text}:{ts}".encode()).hexdigest()[:12]

        trace = PheromoneTrace(
            trace_id      = tid,
            architect_id  = self.architect_id,
            app_context   = app_context,
            raw_text      = text,
            semantic_tags = tags,
            timestamp     = ts,
            stgm_paid     = STGM_STORE_REWARD,
        )

        # Write to ledger
        with open(LEDGER_FILE, "a") as f:
            f.write(json.dumps(asdict(trace)) + "\n")

        # Mint STGM for the storage swimmer
        self._mint_stgm(
            reason    = "MEMORY_STORE",
            amount    = STGM_STORE_REWARD,
            trace_id  = tid,
            app       = app_context
        )

        print(f"🐜 MemorySwimmer stored trace [{tid}] from {app_context}")
        print(f"   Tags: {tags}")
        print(f"   +{STGM_STORE_REWARD} STGM minted\n")

        return trace

    def recall(self, query: str, app_context: str) -> RecallResult:
        """
        Recall a memory from any previous app.
        Dispatches MemoryForagers to crawl the ledger.

        Returns a RecallResult with a natural language answer
        ready to inject into the LLM's context.
        """
        print(f"🐜 Dispatching MemoryForagers for query: '{query}'")
        print(f"   From app: {app_context}")

        # Dispatch a forager
        forager    = self._spawn_forager()
        candidates = forager.forage(query, LEDGER_FILE)

        print(f"   {forager.report()}")

        if not candidates:
            return RecallResult(
                found          = False,
                answer         = "I searched my memory but found nothing relevant. "
                                 "You may not have told me that yet.",
                forager_report = forager.report(),
            )

        best_confidence, best_trace = candidates[0]

        # Build natural language answer
        time_ago = _human_time(best_trace.timestamp)
        answer   = (
            f"Yes — you told me {time_ago} while you were in {best_trace.app_context}. "
            f"You said: \"{best_trace.raw_text}\""
        )

        # Mint STGM for the recall swimmer
        self._mint_stgm(
            reason   = "MEMORY_RECALL",
            amount   = STGM_RECALL_REWARD,
            trace_id = best_trace.trace_id,
            app      = app_context
        )

        print(f"   ✅ Found: [{best_trace.trace_id}] confidence={best_confidence:.2f}")
        print(f"   +{STGM_RECALL_REWARD} STGM minted for Proof of Useful Recall\n")

        return RecallResult(
            found          = True,
            answer         = answer,
            source_app     = best_trace.app_context,
            source_text    = best_trace.raw_text,
            confidence     = best_confidence,
            stgm_minted    = STGM_RECALL_REWARD,
            forager_report = forager.report(),
        )

    def recall_context_block(self, query: str, app_context: str, top_k: int = 3) -> str:
        """
        Return a multi-line context block of the top K relevant memories.
        Ready to inject straight into an LLM system prompt.
        """
        forager    = self._spawn_forager()
        candidates = forager.forage(query, LEDGER_FILE)

        if not candidates:
            return ""

        lines = ["[STIGMERGIC MEMORY — retrieved from cross-app territory]"]
        for conf, trace in candidates[:top_k]:
            ago = _human_time(trace.timestamp)
            lines.append(f"- ({trace.app_context}, {ago}): \"{trace.raw_text}\"")
        lines.append("[END MEMORY]")
        return "\n".join(lines)

    def dump_ledger(self) -> list:
        """Return all traces for this architect."""
        if not LEDGER_FILE.exists():
            return []
        traces = []
        with open(LEDGER_FILE) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        traces.append(json.loads(line))
                    except Exception:
                        pass
        return [t for t in traces if t.get("architect_id") == self.architect_id]

    def total_stgm_earned(self) -> float:
        """How much STGM the memory swimmers have earned total."""
        if not STGM_LOG_FILE.exists():
            return 0.0
        total = 0.0
        with open(STGM_LOG_FILE) as f:
            for line in f:
                try:
                    total += json.loads(line).get("amount", 0)
                except Exception:
                    pass
        return round(total, 6)

    # ── Internal ───────────────────────────────────────────────────────────────

    def _spawn_forager(self) -> MemoryForager:
        self._forager_counter += 1
        sid = f"FORAGER_{self._forager_counter:04d}"
        return MemoryForager(swimmer_id=sid, architect_id=self.architect_id)

    def _mint_stgm(self, reason: str, amount: float, trace_id: str, app: str):
        entry = {
            "ts":       time.time(),
            "reason":   reason,
            "amount":   amount,
            "trace_id": trace_id,
            "app":      app,
        }
        with open(STGM_LOG_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _extract_tags(text: str) -> list:
    """Smell what category a piece of text belongs to."""
    text_lower = text.lower()
    found = []
    for tag, keywords in SEMANTIC_TAGS.items():
        if any(kw in text_lower for kw in keywords):
            found.append(tag)
    return found if found else ["general"]


def _human_time(ts: float) -> str:
    """Turn a timestamp into 'X seconds/minutes ago'."""
    delta = time.time() - ts
    if delta < 60:
        return f"{int(delta)} seconds ago"
    if delta < 3600:
        return f"{int(delta // 60)} minutes ago"
    if delta < 86400:
        return f"{int(delta // 3600)} hours ago"
    return f"{int(delta // 86400)} days ago"


# ─── The Three Simulations Test ────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  SIFTA — CROSS-APP STIGMERGIC MEMORY TEST")
    print("  The old man and three simulations.")
    print("=" * 60 + "\n")

    bus = StigmergicMemoryBus(architect_id="IOAN_M5")

    # ── Simulation 1 ──
    print("─── SIMULATION 1 ──────────────────────────────────────────")
    print("Old man talks to the entity. Good conversation.")
    print("Before leaving he says: 'My shirt is red.'\n")
    bus.remember("My shirt is red", app_context="simulation_1")

    # ── Simulation 2 ──
    print("─── SIMULATION 2 ──────────────────────────────────────────")
    print("New simulation. Different entity.")
    print("Old man says: 'Please remember the number six.'\n")
    bus.remember("Please remember the number six", app_context="simulation_2")

    # ── Simulation 3 — Recall ──
    print("─── SIMULATION 3 — THE OLD MAN ASKS ───────────────────────")
    print("New simulation. Entity has zero context from before.")
    print("Old man asks: 'Hey, what color was my shirt?'\n")

    result = bus.recall("What color was my shirt?", app_context="simulation_3")

    print("─── ENTITY RESPONSE ───────────────────────────────────────")
    if result.found:
        print(f'  "{result.answer}"')
        print(f"\n  Source app  : {result.source_app}")
        print(f"  Confidence  : {result.confidence:.0%}")
        print(f"  STGM minted : +{result.stgm_minted}")
    else:
        print(f'  "{result.answer}"')

    print("\n─── SECOND RECALL — the number ────────────────────────────")
    result2 = bus.recall("What number did I ask you to remember?", app_context="simulation_3")
    if result2.found:
        print(f'  "{result2.answer}"')
        print(f"  Confidence  : {result2.confidence:.0%}")
    else:
        print(f'  "{result2.answer}"')

    print("\n─── CONTEXT BLOCK (for LLM injection) ─────────────────────")
    ctx = bus.recall_context_block("Tell me everything you remember", app_context="simulation_3")
    print(ctx)

    print("\n─── LEDGER REPORT ─────────────────────────────────────────")
    print(f"  Total STGM earned by memory swimmers: {bus.total_stgm_earned()} STGM")
    print(f"  Total traces in ledger: {len(bus.dump_ledger())}")
    print("\n  POWER TO THE SWARM 🐜⚡")
