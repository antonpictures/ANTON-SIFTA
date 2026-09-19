#!/usr/bin/env python3
"""
System/app_skill_domains.py
===========================
Stigmergic App → Skill Domain Binding.

Each app declares the skill/habit domains it cares about.
When the app has focus, Alice's capability field gets biased toward those domains.

This is how one Alice stays coherent across many different apps with different needs.
The app "releases pheromones" (its current needs), and the skill system reacts.

Apps can change their needs over time (stigmergic).
"""

from __future__ import annotations

from typing import Dict, List

# Central registry: app_name (or partial match) → list of skill domains
# These domains should match tags in the skill library (we can add "domains" to skills later).

APP_SKILL_DOMAINS: Dict[str, List[str]] = {
    # World of Warcraft — Azeroth Bridge (owner request 2026-09-19)
    "world_of_warcraft": [
        "game_world_knowledge",
        "companion_not_automation",
        "eula_boundary_respect",
        "human_in_the_loop_confirmation",
        "owner_lived_history",
        "paladin_lore_2003_2006",
        "battle_net_api_reading",
        "honest_unverified_labelling",
        "long_horizon_world_memory",
        "never_claim_what_alice_did_not_do",
    ],
    "azeroth": [
        "game_world_knowledge",
        "companion_not_automation",
        "eula_boundary_respect",
        "human_in_the_loop_confirmation",
        "honest_unverified_labelling",
        "long_horizon_world_memory",
    ],
    # WordAce / Teach Ace to Read
    "wordace": [
        "reading_teaching",
        "phonics",
        "sentence_construction",
        "vocabulary_building",
        "teaching_children",
        "language_play",
        "reading_comprehension",
        "positive_reinforcement",
        "breaking_down_language",
        "patience_with_learners",
    ],
    "teach_ace": [
        "reading_teaching",
        "phonics",
        "sentence_construction",
        "vocabulary_building",
        "teaching_children",
        "language_play",
        "reading_comprehension",
        "positive_reinforcement",
        "breaking_down_language",
        "patience_with_learners",
    ],
    "sifta_teach_ace_to_read": [
        "reading_teaching",
        "phonics",
        "sentence_construction",
        "vocabulary_building",
        "teaching_children",
        "language_play",
        "reading_comprehension",
        "positive_reinforcement",
        "breaking_down_language",
        "patience_with_learners",
    ],

    # Example for future apps
    "gps": ["navigation", "location_services", "mapping", "geofencing", "gps_hardware"],
    "network": ["networking", "mesh", "ble", "awdl", "connectivity", "p2p"],
    "camera": ["vision", "image_processing", "ocr", "face_detection", "photo_analysis"],
}

def get_domains_for_app(app_name: str) -> List[str]:
    """Return the skill domains for a given app name (case-insensitive partial match)."""
    app_lower = app_name.lower()
    for key, domains in APP_SKILL_DOMAINS.items():
        if key in app_lower:
            return domains
    return []

def current_app_skill_domains() -> List[str]:
    """
    Read the latest app_focus.jsonl and return the skill domains
    for the currently focused app.
    """
    from pathlib import Path
    import json

    focus_path = Path(__file__).resolve().parent.parent / ".sifta_state" / "app_focus.jsonl"
    if not focus_path.exists():
        return []

    try:
        with focus_path.open(encoding="utf-8", errors="ignore") as f:
            lines = [line.strip() for line in f if line.strip()]
        if not lines:
            return []
        last = json.loads(lines[-1])
        app_name = last.get("app", "") or last.get("selection", "") or ""
        return get_domains_for_app(app_name)
    except Exception:
        return []
