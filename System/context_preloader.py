#!/usr/bin/env python3
"""
context_preloader.py — Active Recall Brainstem for SIFTA OS
===========================================================

Anticipatory cognition layer.
Watches the user type and pulls intent/memory before they finish,
creating real-time continuity of thought.
"""

from __future__ import annotations
from System.stigmergic_memory_bus import StigmergicMemoryBus

class ContextPreloader:
    def __init__(self, architect_id: str):
        self.bus = StigmergicMemoryBus(architect_id)
        self.last_query = None

    def preload(self, partial_text: str, app_context: str) -> str | None:
        """
        Run lightweight recall on partial input.
        Avoid duplicate work.
        """
        if len(partial_text) < 7:
            return None

        # Simple fuzzy skip to avoid hammering the bus on every single keystroke.
        # We only really care if the word changed enough. But matching EXACT last_query is fine 
        # since we type character by character.
        if partial_text == self.last_query:
            return None

        self.last_query = partial_text

        # Use the Stigmergic bus to recall
        result = self.bus.recall(partial_text, app_context)

        if result.found and result.confidence > 0.4:
            return result.answer

        return None
