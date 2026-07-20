"""r1623-02 needle rules router."""
from __future__ import annotations

from System.swarm_needle_tool_router import needle_probe_status, route_tool_intent


def test_routes_self_code_and_switch():
    assert route_tool_intent("Alice go code R1621-01 with SELF_CODE_CUT")["intent"] == "self_code"
    assert route_tool_intent("switch cortex to pick qwenpaw")["intent"] == "cortex_switch"
    assert route_tool_intent("open instagram.com")["intent"] == "browser_open"


def test_needle_probe_honest():
    p = needle_probe_status()
    assert "installed" in p
