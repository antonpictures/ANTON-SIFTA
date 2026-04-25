import json
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / "Applications" / "apps_manifest.json"
DESKTOP = REPO / ".simulation_publicpush_sandbox" / "sifta_os_desktop.py"

ALLOWED_CATEGORIES = {
    "Alice",
    "System Settings",
    "Utilities",
    "Network",
    "Creative",
    "Simulations",
    "Games",
    "Developer",
    "Economy",
}


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_apps_manifest_is_valid_and_points_to_existing_apps():
    apps = _manifest()
    assert apps, "apps_manifest.json should not be empty"
    for app_name, entry in apps.items():
        category = entry.get("category")
        assert category in ALLOWED_CATEGORIES, f"{app_name}: bad category {category!r}"

        entry_point = entry.get("entry_point")
        assert entry_point, f"{app_name}: missing entry_point"
        assert (REPO / entry_point).exists(), f"{app_name}: missing {entry_point}"

        widget_class = entry.get("widget_class")
        if widget_class is not None:
            assert isinstance(widget_class, str) and widget_class.strip()


def test_body_and_settings_apps_live_in_macos_style_buckets():
    apps = _manifest()
    expected = {
        "Biological Dashboard": "System Settings",
        "Brain Gas-Station Meter": "System Settings",
        "Clock Settings": "System Settings",
        "Intelligence Settings": "System Settings",
        "Owner Genesis": "System Settings",
        "IDE Control Panel": "Developer",
        "Swarm Chat": "Network",
        "Swarm Browser": "Network",
        "Conversation History": "Network",
        "Stigmergic Library": "Utilities",
        "App Manager": "Utilities",
        "Pheromone Symphony (Generative Music)": "Creative",
        "Stigmergic Video Poker": "Games",
    }
    for app_name, category in expected.items():
        assert apps[app_name]["category"] == category


def test_manifest_rejects_generic_macos_clone_shells():
    apps = _manifest()
    generic_shells = {
        "Activity Monitor",
        "App Store",
        "Calculator",
        "Calendar",
        "Contacts",
        "Notes",
        "Photos",
        "Preview",
        "Safari (Swarm)",
        "System Information",
        "Weather",
    }
    assert sorted(generic_shells & set(apps)) == []


def test_desktop_routes_all_manifest_categories_to_real_menus():
    source = DESKTOP.read_text(encoding="utf-8")
    assert "Applications ▶" in source
    assert "MACOS_CATEGORY_ORDER" in source
    assert "normalize_category(app_name, app_data)" in source

    from System.sifta_app_catalog import MACOS_CATEGORY_ORDER, normalize_category

    apps = _manifest()
    labels = {f"{category} ▶" for category in MACOS_CATEGORY_ORDER}
    assert {
        "Alice ▶",
        "System Settings ▶",
        "Utilities ▶",
        "Network ▶",
        "Creative ▶",
        "Simulations ▶",
        "Games ▶",
        "Developer ▶",
        "Economy ▶",
    } == labels

    expected_routes = {
        "Biological Dashboard": "System Settings",
        "Brain Gas-Station Meter": "System Settings",
        "Clock Settings": "System Settings",
        "IDE Control Panel": "Developer",
        "Stigmergic Video Poker": "Games",
        "Network Control Center": "Network",
    }
    for app_name, menu_name in expected_routes.items():
        assert normalize_category(app_name, apps[app_name]) == menu_name
