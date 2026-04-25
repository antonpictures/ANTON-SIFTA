from __future__ import annotations

import json
from pathlib import Path

from Applications.sifta_system_settings import read_system_settings_snapshot
from System.sifta_app_catalog import group_manifest, normalize_category, pinned_desktop_apps


REPO = Path(__file__).resolve().parent.parent


def _manifest():
    return json.loads((REPO / "Applications" / "apps_manifest.json").read_text())


def test_manifest_projects_into_macos_style_categories():
    manifest = _manifest()

    assert normalize_category("Alice", manifest["Alice"]) == "Alice"
    assert normalize_category("System Settings", manifest["System Settings"]) == "System Settings"
    assert normalize_category("Biological Dashboard", manifest["Biological Dashboard"]) == "System Settings"
    assert normalize_category("Network Control Center", manifest["Network Control Center"]) == "Network"
    assert normalize_category("SIFTA File Navigator", manifest["SIFTA File Navigator"]) == "Utilities"

    grouped = group_manifest(manifest)
    flattened = [app for apps in grouped.values() for app in apps]
    assert sorted(flattened) == sorted(manifest)


def test_desktop_pins_are_existing_apps():
    manifest = _manifest()
    pins = pinned_desktop_apps(manifest)

    assert "Alice" in pins
    assert "System Settings" in pins
    assert all(name in manifest for name in pins)


def test_system_settings_snapshot_is_lightweight_and_structured():
    snap = read_system_settings_snapshot()

    assert {"score", "grade", "state_mb", "iris_mb", "apps_total", "app_groups"} <= set(snap)
    assert snap["apps_total"] >= 1
    assert snap["state_mb"] >= 0.0
    assert snap["iris_mb"] >= 0.0

