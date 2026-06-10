"""r842 — Alice Browser tab-close hand (cortex TOOL_CALL → effector receipt)."""

import json
import os
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def test_browser_close_tab_registered_in_tool_registry():
    from System.swarm_tool_router import TOOL_REGISTRY

    spec = TOOL_REGISTRY.get("browser_close_tab")
    assert spec is not None
    assert spec.write_action is True
    assert "url_match" in spec.optional_params


def test_tool_router_browser_close_tab_routes_to_surface(monkeypatch):
    import System.swarm_tool_router as router

    captured: list[dict] = []

    def _surface(intent):
        captured.append(dict(intent))
        return "closed tab receipt line"

    monkeypatch.setattr(router, "_BROWSER_SURFACE", _surface)
    monkeypatch.setattr(router, "_kernel_tool_preflight", lambda *args, **kwargs: (None, None))
    monkeypatch.setattr(router, "_charge_tool_execution", lambda *a, **k: {"receipt_hash": "test"})

    calls = router.parse_tool_calls(
        "[TOOL_CALL: browser_close_tab | url_match=jamasoftware.com | keep_active=false | "
        "cost_justification=owner asked to close useless tabs]"
    )
    result = router.execute_tool_call(calls[0], owner_present=True, autonomous=True)

    assert result.executed is True
    assert result.status == "EXECUTED"
    assert captured
    assert captured[0]["action"] == "close_tab"
    assert captured[0]["url_match"] == "jamasoftware.com"
    assert captured[0]["keep_active"] is False


def test_close_tabs_matching_url_and_duplicates(monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PyQt6.QtWidgets")

    from Applications.sifta_alice_browser_widget import AliceBrowserWidget

    widget = AliceBrowserWidget.__new__(AliceBrowserWidget)
    widget._HAS_WEBENGINE = True

    tabs = MagicMock()
    tabs.count.return_value = 3
    tabs.currentIndex.return_value = 0

    views = [MagicMock(), MagicMock(), MagicMock()]
    for i, view in enumerate(views):
        view.title.return_value = f"Title {i}"
        view.url.return_value = SimpleNamespace(
            toString=lambda i=i: (
                "https://www.youtube.com/watch?v=DTUNF9weRls"
                if i == 0
                else "https://go.jamasoftware.com/best-practices-guide-for-writing-requirements.html"
            )
        )

    def widget_at(index):
        return views[index]

    tabs.widget.side_effect = widget_at
    tabs.tabText.side_effect = lambda i: f"Tab {i}"
    tabs.indexOf.side_effect = lambda v: views.index(v)

    removed: list[int] = []

    def remove_tab(index):
        removed.append(index)
        tabs.count.return_value = max(1, tabs.count.return_value - 1)

    tabs.removeTab.side_effect = remove_tab
    tabs.currentWidget.return_value = views[0]

    widget._tabs = tabs
    widget._view = views[0]
    widget._page = views[0].page.return_value
    widget.refresh_current_page_state = MagicMock()

    widget._on_tab_close_requested = lambda index: (removed.append(index) or True)

    result = widget.close_tabs_matching(
        url_contains="jamasoftware.com",
        keep_active=False,
    )

    assert result["ok"] is True
    assert result["closed_count"] == 2
    assert len(removed) == 2


def test_close_tabs_matching_fly_openclaw_tabs(monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PyQt6.QtWidgets")

    from Applications.sifta_alice_browser_widget import AliceBrowserWidget

    widget = AliceBrowserWidget.__new__(AliceBrowserWidget)
    widget._HAS_WEBENGINE = True

    tabs = MagicMock()
    tabs.count.return_value = 3
    tabs.currentIndex.return_value = 0

    views = [MagicMock(), MagicMock(), MagicMock()]
    urls = [
        "https://www.youtube.com/watch?v=DTUNF9weRls",
        "https://fly.io/docs/app-guides/openclaw/",
        "https://fly.io/docs/app-guides/openclaw/",
    ]
    titles = [
        "Gemma 4 12B: The Unified Local AI",
        "Deploy OpenClaw on Fly.io",
        "Deploy OpenClaw on Fly.io",
    ]
    for i, view in enumerate(views):
        view.title.return_value = titles[i]
        view.url.return_value = SimpleNamespace(toString=lambda i=i: urls[i])

    tabs.widget.side_effect = lambda index: views[index]
    tabs.tabText.side_effect = lambda i: titles[i]
    tabs.indexOf.side_effect = lambda v: views.index(v)
    tabs.currentWidget.return_value = views[0]

    removed: list[int] = []
    tabs.removeTab.side_effect = lambda index: removed.append(index)

    widget._tabs = tabs
    widget._view = views[0]
    widget._page = views[0].page.return_value
    widget.refresh_current_page_state = MagicMock()
    widget._on_tab_close_requested = lambda index: (removed.append(index) or True)

    result = widget.close_tabs_matching(
        url_contains="fly.io",
        keep_active=False,
    )

    assert result["ok"] is True
    assert result["closed_count"] == 2
    assert sorted(removed) == [1, 2]
