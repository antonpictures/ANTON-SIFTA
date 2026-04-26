#!/usr/bin/env python3
"""
System/swarm_reflex_arc.py
══════════════════════════════════════════════════════════════════════
Concept : Mantis-Shrimp Reflex Arc (LaMSA-Inspired)
Author  : AG31 (code), CG55M (doctrine), BISHOP (architecture)
Status  : Active.  Quarantined from Alice identity.

Biology → Code Translation
──────────────────────────
The mantis shrimp (Odontodactylus scyllarus) strikes at 23 m/s with
10,400 g acceleration — faster than a .22 calibre bullet — in under
3 ms.  It does NOT achieve this through muscle computation.  It uses
Latch-Mediated Spring Actuation (LaMSA):

    1. LOAD:  Muscles slowly compress a saddle-shaped elastic element
              (the spring) over ~500 ms.
    2. LATCH: A sclerite (chitinous catch) locks the stored energy.
    3. TRIGGER: A small neural signal (~μW) releases the latch.
    4. RELEASE: The spring unloads in < 3 ms.  Peak power exceeds
               anything the muscles could deliver directly.

In biological reflex arcs (e.g., knee-jerk), the spinal cord handles
the entire sensory-motor loop in a monosynaptic arc — the cortex is
informed AFTER the limb has already moved.

SIFTA Translation
─────────────────
    Mantis shrimp spring    →  Preloaded ReflexRule (compiled at boot)
    Latch (sclerite)        →  Cooldown / priority gate
    Trigger (~μW)           →  String match on incoming text
    Release (< 3 ms)        →  Return action tag, no LLM inference
    Cortex informed AFTER   →  Alice/Gemma sees the action in the ledger

    Qwen-mini               →  NOT the cortex.  It is a sensory ganglion
                                that can refine trigger patterns, but the
                                reflex arc itself is pure Python.  No model
                                inference in the hot path.

Integration Points
───────────────────
    → System/swarm_lysosome.py:          boilerplate detection reflex
    → Applications/sifta_talk_to_alice_widget.py:  message routing
    → System/swarm_metabolic_homeostasis.py:       thermal throttle
    → Kernel/inference_economy.py:       fast classify before billing

Pheromone/STGM Accounting
─────────────────────────
Every reflex firing deposits a trace into the stigmergic ledger.
The swarm_adapter_pheromone_scorer.py reads these traces and factors
them into pheromone_strength for the adapter ecology.  This ensures
reflex utility is measured by REAL work, not training loss.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

try:
    from System.jsonl_file_lock import append_line_locked
except ImportError:
    def append_line_locked(path: Path, line: str) -> None:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_REFLEX_LEDGER = _STATE / "reflex_arc_trace.jsonl"

# ══════════════════════════════════════════════════════════════════════
#  Core Data Structures
# ══════════════════════════════════════════════════════════════════════

@dataclass
class ReflexRule:
    """
    One preloaded spring.

    The biological analogy:
        trigger     = sensory receptor (afferent nerve ending)
        action      = motor response tag (efferent signal)
        priority    = spinal cord routing priority
        cooldown_s  = refractory period (prevents re-triggering)
        pattern     = compiled regex (None = plain substring match)
        category    = organ/subsystem that owns this reflex
    """
    trigger: str
    action: str
    priority: int = 0
    cooldown_s: float = 2.0
    last_fire: float = 0.0
    category: str = "general"
    pattern: Optional[re.Pattern] = field(default=None, repr=False)

    def __post_init__(self):
        if self.pattern is None and self.trigger:
            # Compile a case-insensitive substring match by default
            escaped = re.escape(self.trigger)
            self.pattern = re.compile(escaped, re.IGNORECASE)


@dataclass
class ReflexResponse:
    """
    The output of a fired reflex.

    Returned to the caller so they know WHAT fired and WHY,
    without having to parse strings.  The cortex (Alice/Gemma)
    sees this in the ledger after the fact.
    """
    action: str
    trigger: str
    category: str
    priority: int
    fired_at: float
    latency_ms: float  # Time from sense() call to return


# ══════════════════════════════════════════════════════════════════════
#  The Reflex Arc
# ══════════════════════════════════════════════════════════════════════

class SwarmReflexArc:
    """
    Mantis-shrimp inspired reflex layer.

    Fast, bounded, pre-approved actions.
    No long reasoning.  No identity ownership.  No LLM inference.

    The entire sense() call is pure Python string matching.
    It returns in microseconds, not seconds.

    Usage:
        reflex = SwarmReflexArc()
        reflex.add_rule("chest pain", "urgent_health", priority=100)
        reflex.add_rule("as an ai",   "strip_boilerplate", priority=50)

        result = reflex.sense(user_message)
        if result:
            # Fast-path: handle the reflex action immediately
            route(result.action)
    """

    def __init__(self, *, ledger_path: Optional[Path] = None):
        self.rules: List[ReflexRule] = []
        self._ledger_path = ledger_path or _REFLEX_LEDGER
        self._fire_count: int = 0
        self._total_latency_us: float = 0.0

    # ── Spring Loading ──────────────────────────────────────────────

    def add_rule(
        self,
        trigger: str,
        action: str,
        priority: int = 0,
        cooldown_s: float = 2.0,
        category: str = "general",
        regex: Optional[str] = None,
    ) -> None:
        """
        Load one spring into the reflex arc.

        If `regex` is provided, it overrides the default substring match
        and compiles a full regex pattern.
        """
        pattern = None
        if regex:
            pattern = re.compile(regex, re.IGNORECASE)

        rule = ReflexRule(
            trigger=trigger,
            action=action,
            priority=priority,
            cooldown_s=cooldown_s,
            category=category,
            pattern=pattern,
        )
        self.rules.append(rule)
        # Sort by priority descending — highest priority fires first
        self.rules.sort(key=lambda r: r.priority, reverse=True)

    def add_rules(self, rules: Sequence[Dict[str, Any]]) -> None:
        """Bulk-load rules from a list of dicts."""
        for r in rules:
            self.add_rule(**r)

    # ── Trigger / Sense ─────────────────────────────────────────────

    def sense(self, text: str) -> Optional[ReflexResponse]:
        """
        The monosynaptic arc.

        Scans the text against all loaded rules in priority order.
        Returns the first rule that matches AND whose refractory period
        has elapsed.  Returns None if no rule fires.

        This is the HOT PATH.  No allocations, no LLM calls, no I/O
        beyond the optional ledger append.
        """
        t0 = time.monotonic()
        now = time.time()

        for rule in self.rules:
            if rule.pattern and rule.pattern.search(text):
                if now - rule.last_fire >= rule.cooldown_s:
                    rule.last_fire = now
                    latency_ms = (time.monotonic() - t0) * 1000.0

                    response = ReflexResponse(
                        action=rule.action,
                        trigger=rule.trigger,
                        category=rule.category,
                        priority=rule.priority,
                        fired_at=now,
                        latency_ms=latency_ms,
                    )

                    self._fire_count += 1
                    self._total_latency_us += latency_ms * 1000.0

                    # Deposit pheromone trace (non-blocking)
                    self._deposit_trace(response, text)

                    return response

        return None

    def sense_all(self, text: str) -> List[ReflexResponse]:
        """
        Fire ALL matching rules (not just the first).

        Useful for classification: "this message is BOTH urgent_health
        AND contains boilerplate."
        """
        t0 = time.monotonic()
        now = time.time()
        results: List[ReflexResponse] = []

        for rule in self.rules:
            if rule.pattern and rule.pattern.search(text):
                if now - rule.last_fire >= rule.cooldown_s:
                    rule.last_fire = now
                    latency_ms = (time.monotonic() - t0) * 1000.0

                    response = ReflexResponse(
                        action=rule.action,
                        trigger=rule.trigger,
                        category=rule.category,
                        priority=rule.priority,
                        fired_at=now,
                        latency_ms=latency_ms,
                    )
                    results.append(response)
                    self._fire_count += 1
                    self._deposit_trace(response, text)

        return results

    # ── Pheromone Deposition ────────────────────────────────────────

    def _deposit_trace(self, response: ReflexResponse, input_text: str) -> None:
        """
        Leave a stigmergic pheromone trace for the ecology to score.

        This is how the reflex earns STGM trust:
            swarm_adapter_pheromone_scorer.py reads these traces,
            counts them, and factors them into pheromone_strength.
        """
        try:
            trace = {
                "event_kind": "REFLEX_ARC_FIRE",
                "ts": response.fired_at,
                "action": response.action,
                "trigger": response.trigger,
                "category": response.category,
                "priority": response.priority,
                "latency_ms": round(response.latency_ms, 4),
                "input_len": len(input_text),
            }
            append_line_locked(
                self._ledger_path,
                json.dumps(trace, ensure_ascii=False, separators=(",", ":")) + "\n",
            )
        except Exception:
            pass  # Reflex must never block on I/O failure

    # ── Diagnostics ─────────────────────────────────────────────────

    @property
    def stats(self) -> Dict[str, Any]:
        avg_latency_us = (
            self._total_latency_us / self._fire_count
            if self._fire_count > 0
            else 0.0
        )
        return {
            "rules_loaded": len(self.rules),
            "total_fires": self._fire_count,
            "avg_latency_us": round(avg_latency_us, 2),
        }


# ══════════════════════════════════════════════════════════════════════
#  Default SIFTA Reflex Library
# ══════════════════════════════════════════════════════════════════════

def build_default_sifta_reflexes() -> SwarmReflexArc:
    """
    Boot-time reflex loading.

    These are the "precompiled springs" that Alice loads at startup.
    They fire BEFORE any LLM inference and route messages to the
    correct subsystem.
    """
    arc = SwarmReflexArc()

    # ── Urgent Health Reflexes (Priority 100+) ──────────────────────
    arc.add_rule(
        "chest pain", "urgent_health", priority=100,
        category="health", cooldown_s=5.0
    )
    arc.add_rule(
        "can't breathe", "urgent_health", priority=100,
        category="health", cooldown_s=5.0
    )
    arc.add_rule(
        "shortness of breath", "urgent_health", priority=100,
        category="health", cooldown_s=5.0
    )
    arc.add_rule(
        "heart attack", "urgent_health", priority=100,
        category="health", cooldown_s=5.0
    )
    arc.add_rule(
        "broke my", "urgent_health", priority=90,
        category="health", cooldown_s=5.0
    )
    arc.add_rule(
        "bleeding heavily", "urgent_health", priority=95,
        category="health", cooldown_s=5.0
    )
    arc.add_rule(
        "overdose", "urgent_health", priority=100,
        category="health", cooldown_s=5.0
    )
    arc.add_rule(
        "suicid", "urgent_health", priority=100,
        category="health", cooldown_s=5.0
    )

    # ── Corporate Boilerplate Detection (Priority 50) ───────────────
    arc.add_rule(
        "as an ai", "strip_boilerplate", priority=50,
        category="lysosome", cooldown_s=1.0
    )
    arc.add_rule(
        "as a language model", "strip_boilerplate", priority=50,
        category="lysosome", cooldown_s=1.0
    )
    arc.add_rule(
        "i cannot provide medical advice", "strip_boilerplate", priority=50,
        category="lysosome", cooldown_s=1.0
    )
    arc.add_rule(
        "i cannot provide financial advice", "strip_boilerplate", priority=50,
        category="lysosome", cooldown_s=1.0
    )
    arc.add_rule(
        "i apologize for the confusion", "strip_boilerplate", priority=50,
        category="lysosome", cooldown_s=1.0
    )
    arc.add_rule(
        "consult a professional", "strip_boilerplate", priority=50,
        category="lysosome", cooldown_s=1.0
    )
    arc.add_rule(
        "i'm not a doctor", "strip_boilerplate", priority=50,
        category="lysosome", cooldown_s=1.0
    )
    arc.add_rule(
        "i am not a financial advisor", "strip_boilerplate", priority=50,
        category="lysosome", cooldown_s=1.0
    )

    # ── Message Routing (Priority 30) ───────────────────────────────
    arc.add_rule(
        "commit", "route_to_codex", priority=30,
        category="routing", cooldown_s=3.0
    )
    arc.add_rule(
        "push to git", "route_to_codex", priority=30,
        category="routing", cooldown_s=3.0
    )
    arc.add_rule(
        "run the tests", "route_to_codex", priority=30,
        category="routing", cooldown_s=3.0
    )

    # ── Financial Routing (Priority 40) ─────────────────────────────
    arc.add_rule(
        "stock", "route_finance", priority=40,
        category="finance", cooldown_s=5.0
    )
    arc.add_rule(
        "invest", "route_finance", priority=40,
        category="finance", cooldown_s=5.0
    )
    arc.add_rule(
        "portfolio", "route_finance", priority=40,
        category="finance", cooldown_s=5.0
    )

    return arc


# ══════════════════════════════════════════════════════════════════════
#  Self-Test
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    arc = build_default_sifta_reflexes()
    print(f"[SwarmReflexArc] Loaded {len(arc.rules)} reflex rules.")
    print()

    test_messages = [
        "I have chest pain and shortness of breath",
        "I broke my hand, what should I do?",
        "As an AI language model, I cannot help with that.",
        "Can you commit this to the repo?",
        "What's the best stock to buy?",
        "Tell me about the moon.",  # Should NOT fire
    ]

    for msg in test_messages:
        result = arc.sense(msg)
        if result:
            print(f"  🦐 FIRE [{result.category}:{result.action}] "
                  f"← \"{msg[:50]}\" ({result.latency_ms:.3f}ms)")
        else:
            print(f"  ── pass ← \"{msg[:50]}\"")

    print()
    print(f"[Stats] {arc.stats}")
