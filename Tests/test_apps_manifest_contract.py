import json
import pytest
from pathlib import Path
from sifta_os_desktop import (
    _desktop_autostart_enabled,
    _load_widget_class,
    _session_restore_from_wm_enabled,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "Applications" / "apps_manifest.json"

@pytest.fixture
def manifest_data():
    with open(MANIFEST_PATH, "r") as f:
        return json.load(f)

def test_manifest_structure(manifest_data):
    """Ensure the manifest is a valid dictionary mapping app names to their metadata."""
    assert isinstance(manifest_data, dict)
    assert len(manifest_data) > 0
    for name, app in manifest_data.items():
        assert "entry_point" in app, f"Missing entry_point for {name}"
        assert "category" in app, f"Missing category for {name}"

def test_manifest_app_launch_contract(manifest_data):
    """
    Iterate over every app in the manifest and ensure it resolves
    through the canonical file-path loader used by the desktop.
    Missing modules/classes will produce a structured test failure.
    """
    failed_apps = []
    
    for name, app in manifest_data.items():
        # Some manifests might have an enabled flag, but typically we try to load everything listed
        if app.get("enabled", True) is False:
            continue
            
        entry_point = app.get("entry_point")
        class_name = app.get("widget_class")
        
        if not entry_point:
            failed_apps.append({"name": name, "entry_point": entry_point, "class_name": class_name, "error": "Missing entry_point"})
            continue
            
        if not class_name:
            # Script app: just ensure file exists
            path = (REPO_ROOT / entry_point).resolve()
            if not path.is_file():
                failed_apps.append({"name": name, "entry_point": entry_point, "class_name": "N/A", "error": f"Script file not found: {path}"})
            continue
        
        try:
            widget_class = _load_widget_class(entry_point, class_name)
            assert widget_class is not None, f"Widget class {class_name} loaded as None"
        except Exception as e:
            failed_apps.append({
                "name": name,
                "entry_point": entry_point,
                "class_name": class_name,
                "error": str(e)
            })
            
    if failed_apps:
        error_msg = "Manifest Launch Contract Failed for the following apps:\n"
        for fail in failed_apps:
            error_msg += f"- [{fail['name']}] Failed to load '{fail['class_name']}' from '{fail['entry_point']}': {fail['error']}\n"
        pytest.fail(error_msg)

def test_critical_apps_present(manifest_data):
    """Ensure minimum critical apps are in the manifest per Codex directive."""
    app_names = list(manifest_data.keys())
    critical_apps = [
        "Finance",
        "SIFTA NLE",
        "SIFTA File Navigator",
        "System Settings",
        "Alice"
    ]
    for critical in critical_apps:
        assert critical in app_names, f"Critical app '{critical}' is missing from apps_manifest.json"


def test_manifest_has_no_default_autostart_apps(manifest_data):
    """Mermaid OS should boot to a clean desktop unless autostart is explicitly enabled."""
    autostart_apps = [
        name for name, app in manifest_data.items()
        if app.get("autostart") is True
    ]
    assert autostart_apps == []


def test_desktop_autostart_requires_explicit_enable(monkeypatch):
    monkeypatch.delenv("SIFTA_DESKTOP_ENABLE_AUTOSTART", raising=False)
    monkeypatch.delenv("SIFTA_DESKTOP_SKIP_WM_AUTOSTART", raising=False)
    assert _desktop_autostart_enabled() is False

    monkeypatch.setenv("SIFTA_DESKTOP_ENABLE_AUTOSTART", "1")
    assert _desktop_autostart_enabled() is True

    monkeypatch.setenv("SIFTA_DESKTOP_SKIP_WM_AUTOSTART", "1")
    assert _desktop_autostart_enabled() is False


def test_wm_session_restore_independent_of_manifest_autostart(monkeypatch):
    """last_session restore is opt-in via SIFTA_DESKTOP_ENABLE_SESSION_RESTORE, not autostart alone."""
    monkeypatch.delenv("SIFTA_DESKTOP_ENABLE_SESSION_RESTORE", raising=False)
    monkeypatch.delenv("SIFTA_DESKTOP_ENABLE_AUTOSTART", raising=False)
    assert _session_restore_from_wm_enabled() is False
    monkeypatch.setenv("SIFTA_DESKTOP_ENABLE_AUTOSTART", "1")
    assert _session_restore_from_wm_enabled() is False
    monkeypatch.setenv("SIFTA_DESKTOP_ENABLE_SESSION_RESTORE", "1")
    assert _session_restore_from_wm_enabled() is True
