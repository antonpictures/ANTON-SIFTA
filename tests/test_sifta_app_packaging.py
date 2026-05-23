from __future__ import annotations

import importlib.util


def test_py2app_includes_current_package_router_and_stgm_modules():
    from System import setup_sifta_app

    assert "swarm_tool_router" in setup_sifta_app.INCLUDES
    assert "swarm_stgm_billing" in setup_sifta_app.INCLUDES
    assert "swarm_skill_library" in setup_sifta_app.INCLUDES


def test_py2app_include_list_contains_only_importable_modules():
    from System import setup_sifta_app

    missing = [
        name
        for name in setup_sifta_app.INCLUDES
        if importlib.util.find_spec(name) is None
    ]

    assert missing == []
