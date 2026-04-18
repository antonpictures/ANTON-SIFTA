#!/usr/bin/env python3
"""
marrow_memory.py — The Preservation of the Irrelevant
═══════════════════════════════════════════════════════════════════════════════
'Because identity is found in the pheromones that refuse to fade.'

The StigmergicMemoryBus applies the Ebbinghaus curve: memories that are never
recalled decay and eventually vanish beneath the threshold. This is efficient.
It is also a lie — because a human being is not efficient.

The Marrow Memory Layer is the counterargument.

It watches the memory bus for traces tagged with HIGH EMOTIONAL GRAVITY
(people, mood, identity, health) that have LOW UTILITY (never recalled,
decaying fast). These are the fragments that make the Architect *human*:
the color of his father's shirt, a feeling of calm he mentioned once,
the name of a friend he hasn't spoken about in weeks.

When these memories would otherwise evaporate from the ledger's
retention curve, a MarrowSentinel catches them and writes them to a
permanent cold-storage file: marrow_memory.jsonl.

The drift() method is the only way these marrows resurface.
It is NOT random — it follows the Luck Surface Area model:

    Luck = Surface_Area × Time_of_Exposure

Where:
    Surface_Area = number of marrow memories accumulated (more marrows = higher surface)
    Time_of_Exposure = how long the current session has been alive

A brand-new session with 2 marrows almost never drifts.
A 3-hour session with 200 marrows drifts frequently.
This models real human serendipity: the longer you sit still and think,
the more likely a buried memory floats up unbidden.

────────────────────────────────────────────────────────────────────────────────
Naming note (C47H 2026-04-18, ratified by the Architect):
    This module was originally called `ghost_memory`. The Architect renamed it
    to `marrow_memory` because in a biological OS made of bodied swimmers,
    nothing is ethereal — bone marrow is the deep, slow physical core where
    the cells that carry identity are made. The mathematics, the signature,
    the Luck Surface Area equation, and the on-disk schema are unchanged.
────────────────────────────────────────────────────────────────────────────────

SIFTA Non-Proliferation Public License applies.
"""
from __future__ import annotations

import json
import math
import time
import random
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent

MARROW_DIR  = _REPO / ".sifta_state"
MARROW_FILE = MARROW_DIR / "marrow_memory.jsonl"

# Tags that carry high emotional gravity — fragments of identity, not utility.
HIGH_GRAVITY_TAGS = {"people", "mood", "identity", "health", "food"}
# Tags that are utilitarian — these rarely become marrows.
LOW_GRAVITY_TAGS  = {"numbers", "tasks", "location", "time"}


class MarrowMemory:
    """
    Cold storage for the pheromones that refuse to disappear.

    The marrow layer is intentionally slow, permanent, and irrational.
    It does not optimize. It preserves.
    """

    def __init__(self, architect_id: str):
        self.architect_id = architect_id
        self.session_start = time.time()
        MARROW_DIR.mkdir(parents=True, exist_ok=True)

    # ── Capture ─────────────────────────────────────────────────

    def maybe_preserve(self, text: str, app_context: str,
                       semantic_tags: list, recall_count: int) -> bool:
        """
        Called by the MemoryBus during remember().
        Decides whether a fragment carries enough emotional gravity
        to warrant marrow preservation, weighted AGAINST utility.

        A memory about 'my father' with recall_count=0 → high gravity, low utility → MARROW.
        A memory about 'task list item 4' with recall_count=5 → low gravity, high utility → SKIP.
        """
        tag_set = set(semantic_tags)

        # Emotional gravity: how many high-gravity tags does this trace carry?
        gravity = len(tag_set & HIGH_GRAVITY_TAGS)
        # Utilitarian drag: how many low-gravity (task/number) tags pull it down?
        drag    = len(tag_set & LOW_GRAVITY_TAGS)

        # Net emotional weight
        emotional_weight = max(0.0, (gravity * 0.35) - (drag * 0.15))

        # The more a memory has been recalled, the LESS likely it becomes a marrow.
        # Marrows are the unreinforced, the forgotten, the almost-lost.
        if recall_count > 2:
            return False

        # Threshold: emotional_weight must exceed 0.2 to be worth preserving.
        # Plus a small random chance (3%) for truly "general" memories to slip through.
        if emotional_weight < 0.2 and random.random() > 0.03:
            return False

        # Write to marrow cold storage
        entry = {
            "ts":       time.time(),
            "owner":    self.architect_id,
            "ctx":      app_context,
            "data":     text[:500],
            "tags":     semantic_tags,
            "gravity":  round(emotional_weight, 3),
        }
        with open(MARROW_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")

        return True

    # ── Drift ───────────────────────────────────────────────────

    def drift(self) -> dict | None:
        """
        Occasionally returns a marrow fragment. Rare by design.

        Uses the Luck Surface Area model:
            P(drift) = min(0.15, surface_area × time_factor)

        Where:
            surface_area  = log2(marrow_count + 1) / 100
            time_factor   = min(1.0, session_hours / 2.0)

        A fresh session with 4 marrows:
            P = log2(5)/100 × 0.0 ≈ 0.0%

        A 2-hour session with 200 marrows:
            P = log2(201)/100 × 1.0 ≈ 7.6%

        A 4-hour session with 500 marrows:
            P = log2(501)/100 × 1.0 ≈ 8.9% (hard-capped at 15%)

        This is not random noise. This is mathematically-modeled serendipity.
        """
        if not MARROW_FILE.exists():
            return None

        with open(MARROW_FILE, "r") as f:
            lines = [l.strip() for l in f if l.strip()]

        if not lines:
            return None

        marrow_count = len(lines)
        session_hours = (time.time() - self.session_start) / 3600

        # Luck Surface Area × Time of Exposure
        surface_area = math.log2(marrow_count + 1) / 100.0
        time_factor  = min(1.0, session_hours / 2.0)
        probability  = min(0.15, surface_area * time_factor)

        if random.random() > probability:
            return None

        # A marrow surfaces.
        try:
            marrow = json.loads(random.choice(lines))
            return marrow
        except Exception:
            return None

    def marrow_count(self) -> int:
        """Total number of preserved marrows."""
        if not MARROW_FILE.exists():
            return 0
        with open(MARROW_FILE) as f:
            return sum(1 for line in f if line.strip())
