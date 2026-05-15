#!/usr/bin/env python3
"""Regression guards for the consolidated SIFTA MAMMAL app."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "Applications" / "apps_manifest.json"
APP = ROOT / "Applications" / "sifta_stigmergic_mammal_widget.py"
HELP = ROOT / "Documents" / "APP_HELP.md"


def _public_mammal_entries() -> list[tuple[str, dict]]:
    manifest = json.loads(MANIFEST.read_text())
    out: list[tuple[str, dict]] = []
    for name, entry in manifest.items():
        haystack = " ".join(
            str(part)
            for part in (
                name,
                entry.get("entry_point"),
                entry.get("widget_class"),
                entry.get("description"),
            )
        ).lower()
        if "mammal" not in haystack:
            continue
        if entry.get("_hidden_from_launcher") or not entry.get("entry_point"):
            continue
        out.append((name, entry))
    return out


def test_manifest_exposes_one_public_mammal_app():
    entries = _public_mammal_entries()
    assert [name for name, _entry in entries] == ["SIFTA MAMMAL Lab — Unified Field"]
    entry = entries[0][1]
    assert entry["entry_point"] == "Applications/sifta_stigmergic_mammal_widget.py"
    assert entry["widget_class"] == "StigmergicMammalWidget"
    assert "one window" in entry["description"].lower()
    assert "live token ecology canvas" in entry["description"].lower()
    assert "drug-discovery lab" in entry["description"].lower()


def test_consolidated_widget_declares_the_three_public_tabs_and_single_help_hint():
    source = APP.read_text()
    for label in (
        "💊 Drug Discovery Lab",
        "🧬 Live Token Ecology",
        "🧪 Modality Detail",
        "Use the window ? button for the unified operator manual.",
        "SIFTA MAMMAL Lab — Unified Field",
    ):
        assert label in source
    assert "? Show Help" not in source
    assert "def show_help_dialog" not in source
    assert "def _help_html" not in source


def test_app_help_points_to_the_consolidated_launcher_name():
    help_text = HELP.read_text()
    assert "### SIFTA MAMMAL Lab — Unified Field" in help_text
    assert "Open **SIFTA MAMMAL Lab — Unified Field** from the launcher." in help_text
    assert "one app, three tabs" in help_text.lower()
    assert "One help path only" in help_text
    assert "Stigmergic MAMMAL — Token Ecology" not in help_text
    assert "window ? button" in help_text
