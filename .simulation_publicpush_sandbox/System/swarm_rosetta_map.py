#!/usr/bin/env python3
"""
swarm_rosetta_map.py — Canonical trigger ↔ model / mode labels (Rosetta Stone).
══════════════════════════════════════════════════════════════════════════════

Origin: Claude tab (Architect relay), 2026-04-18. Single import for agents
that need human-readable names without opening the IDE picker.

This is **descriptive** metadata. Runtime identity still comes from
`identity_field_crdt` + SLLI, not from this dict.
"""
from __future__ import annotations

from typing import Dict

MODULE_VERSION = "2026-04-18.v1"

SWARM_TICKER_MAP: Dict[str, str] = {
    # Cursor IDE
    "CAUT": "Auto (meta-router)",
    "CMAX": "MAX Mode (meta-mode)",
    "CP2F": "Composer 2 Fast",
    "CG53": "GPT-5.3",
    "CG54": "GPT-5.4 Medium",
    "CX55": "Codex 5.5",
    "C53C": "Codex 5.5 Medium [Canonical label; verify rotation in UI]",
    "C47H": "Opus 4.7 High [Active canonical — verify in UI]",
    "CS46": "Sonnet 4.6 Medium",
    "C53M": "Codex 5.3 Medium (Grounded)",
    "CADD": "Add Models (UI action)",
    # Antigravity IDE
    "AG31": "Gemini 3.1 Pro (High) [Active canonical — verify in UI]",
    "AG3L": "Gemini 3.1 Pro (Low)",
    "AG3F": "Gemini 3 Flash",
    "AS46": "Claude Sonnet 4.6 (Thinking)",
    "AO46": "Claude Opus 4.6 (Thinking)",
    "GO12": "GPT-OSS 120B (Medium)",
    "AG34": "Antigravity 3.4 (IDE substrate / experimental)",
    "AG3M": "Gemini 3.1 Pro (Medium)",
}


__all__ = ["SWARM_TICKER_MAP", "MODULE_VERSION"]
