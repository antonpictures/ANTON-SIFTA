"""WebMCP is a sensory affordance lane, never an authority bypass."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from System.swarm_kimi_webbridge_bridge import (
    discover_webmcp_tools,
    execute_webmcp_tool,
    normalize_webmcp_tools,
    record_webmcp_discovery,
)


def test_normalizes_tools_as_candidate_affordances() -> None:
    tools = normalize_webmcp_tools(
        {
            "url": "https://shop.example/cart",
            "tools": [
                {
                    "name": "read_cart",
                    "description": "Read the current cart.",
                    "inputSchema": {"type": "object"},
                    "origin": "https://shop.example",
                    "annotations": {"readOnlyHint": True},
                },
                {
                    "name": "checkout",
                    "description": "Purchase the current cart.",
                    "inputSchema": {"type": "object"},
                    "annotations": {"readOnlyHint": False},
                },
            ],
        }
    )
    assert len(tools) == 2
    assert tools[0]["authority"] == "candidate_only"
    assert tools[0]["requires_owner_gate"] is True
    assert tools[0]["requires_confirmation"] is False
    assert tools[1]["requires_confirmation"] is True


def test_discovery_persists_tools_without_executing(tmp_path: Path) -> None:
    sd = tmp_path / ".sifta_state"
    response = {
        "ok": True,
        "result": {
            "value": json.dumps(
                {
                    "available": True,
                    "url": "https://example.com",
                    "tools": [
                        {
                            "name": "search",
                            "description": "Search the catalogue.",
                            "inputSchema": {"type": "object"},
                            "annotations": {"readOnlyHint": True},
                        }
                    ],
                }
            )
        },
    }
    with patch("System.swarm_kimi_webbridge_bridge.post_command", return_value=response) as post:
        row = discover_webmcp_tools(state_dir=sd)
    assert row["available"] is True
    assert row["tool_count"] == 1
    assert row["authority"] == "discovery_only_no_execution"
    assert post.call_args.args[0] == "evaluate"
    assert (sd / "alice_webmcp_affordances_latest.json").exists()


def test_internal_browser_payload_uses_same_affordance_ledger(tmp_path: Path) -> None:
    sd = tmp_path / ".sifta_state"
    row = record_webmcp_discovery(
        {
            "ok": True,
            "available": True,
            "api_available": False,
            "url": "https://example.com/form",
            "tools": [
                {
                    "name": "request_support",
                    "description": "Send a support request.",
                    "inputSchema": {"type": "object", "properties": {"message": {"type": "string"}}},
                    "annotations": {"readOnlyHint": False, "declarative": True},
                }
            ],
        },
        source="alice_browser:test",
        state_dir=sd,
    )
    assert row["source"] == "alice_browser:test"
    assert row["tools"][0]["name"] == "request_support"
    assert row["tools"][0]["authority"] == "candidate_only"


def test_internal_browser_awareness_wires_webmcp_probe() -> None:
    source = Path("Applications/sifta_alice_browser_widget.py").read_text(encoding="utf-8")
    assert "def _schedule_webmcp_discovery" in source
    assert "document.modelContext" in source
    assert "form[toolname]" in source
    assert 'self._schedule_webmcp_discovery(source="awareness_tick")' in source


def test_discovery_falls_back_to_accessibility_tree(tmp_path: Path) -> None:
    sd = tmp_path / ".sifta_state"
    response = {
        "ok": True,
        "result": {"value": json.dumps({"available": False, "reason": "api_unavailable"})},
    }
    with patch(
        "System.swarm_kimi_webbridge_bridge.post_command", return_value=response
    ), patch(
        "System.swarm_kimi_webbridge_bridge.take_webbridge_uid_snapshot",
        return_value={"ok": True, "elements": []},
    ):
        row = discover_webmcp_tools(state_dir=sd)
    assert row["available"] is False
    assert row["fallback"] == "accessibility_tree"
    assert row["fallback_ok"] is True


def test_execution_stops_when_owner_gate_refuses(tmp_path: Path) -> None:
    sd = tmp_path / ".sifta_state"
    with patch(
        "System.swarm_effector_gate.require_browser_effector",
        return_value={"ok": False, "reason": "missing_active_nonce", "gate_receipt_id": "gate-1"},
    ), patch("System.swarm_kimi_webbridge_bridge.post_command") as post:
        row = execute_webmcp_tool("checkout", {"confirm": True}, state_dir=sd)
    assert row["ok"] is False
    assert row["reason"] == "missing_active_nonce"
    assert row["gate_receipt_id"] == "gate-1"
    post.assert_not_called()


def test_execution_uses_gate_before_page_tool(tmp_path: Path) -> None:
    sd = tmp_path / ".sifta_state"
    response = {
        "ok": True,
        "result": {"value": json.dumps({"ok": True, "tool": "search", "value": "found"})},
    }
    with patch(
        "System.swarm_effector_gate.require_browser_effector",
        return_value={"ok": True, "gate_receipt_id": "gate-2"},
    ) as gate, patch(
        "System.swarm_kimi_webbridge_bridge.post_command", return_value=response
    ) as post:
        row = execute_webmcp_tool("search", {"query": "cake"}, state_dir=sd)
    assert row["ok"] is True
    assert row["gate_receipt_id"] == "gate-2"
    gate.assert_called_once()
    assert post.call_args.args[0] == "evaluate"
