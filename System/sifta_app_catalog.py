#!/usr/bin/env python3
"""
System/sifta_app_catalog.py
Canonical app taxonomy for the SIFTA desktop.

The repo already uses a macOS-like filesystem. This module makes the shell
present apps the same way: Applications first, then stable folders such as
System Settings, Utilities, Network, Creative, Simulations, Games, Developer.
"""
from __future__ import annotations

from collections import OrderedDict
from typing import Mapping

MACOS_CATEGORY_ORDER = (
    "Alice",
    "System Settings",
    "Utilities",
    "Network",
    "Creative",
    "Simulations",
    "Games",
    "Developer",
    "Economy",
)

SYSTEM_SETTINGS_NAMES = {
    "system settings",
    "intelligence settings",
    "clock settings",
    "cardio metrics",
    "brain gas-station meter",
    "owner genesis",
    "biological dashboard",
}

UTILITY_NAMES = {
    "app manager",
    "cartography dashboard",
    "sifta file navigator",
    "circadian rhythm",
}

DEVELOPER_NAMES = {
    "ide control panel",
}


def normalize_category(app_name: str, meta: Mapping[str, object]) -> str:
    """Return the macOS-style folder for one manifest row."""
    name = app_name.strip().lower()
    exact = str(meta.get("category", "")).strip()
    raw = exact.lower()

    # Alice-family apps always live under the Alice menu, even when the
    # manifest tags the unified bundle with another department (Creative).
    if name == "alice" or "alice" in name:
        return "Alice"

    # Exact canonical match from the manifest when it names a real shell folder.
    if exact in MACOS_CATEGORY_ORDER:
        return exact

    # Legacy fallback heuristics
    if name in SYSTEM_SETTINGS_NAMES or "settings" in name:
        return "System Settings"
    if name in DEVELOPER_NAMES or raw == "developer" or name.startswith("ide "):
        return "Developer"
    if name in UTILITY_NAMES:
        return "Utilities"
    if raw in {"network", "networking"}:
        return "Network"
    if raw == "creative":
        return "Creative"
    if raw == "simulations":
        return "Simulations"
    if raw == "games":
        return "Games"
    if raw in {"settings", "body status", "system settings"}:
        return "System Settings"
    if raw in {"accessories", "utilities", "system"}:
        return "Utilities"
    return "Utilities"


def group_manifest(manifest: Mapping[str, Mapping[str, object]]) -> OrderedDict[str, list[str]]:
    groups: OrderedDict[str, list[str]] = OrderedDict((cat, []) for cat in MACOS_CATEGORY_ORDER)
    for app_name, meta in manifest.items():
        groups.setdefault(normalize_category(app_name, meta), []).append(app_name)
    for apps in groups.values():
        apps.sort(key=str.lower)
    return groups


def pinned_desktop_apps(manifest: Mapping[str, Mapping[str, object]]) -> list[str]:
    """Stable first-boot desktop pins. Missing apps are ignored."""
    preferred = [
        "Alice",
        "System Settings",
        "What Alice Sees",
        "App Manager",
        "SIFTA File Navigator",
    ]
    return [name for name in preferred if name in manifest]
