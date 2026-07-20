"""r1391 — Kimi WebBridge external Chrome limb bridge for Alice."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from System.swarm_kimi_webbridge_bridge import (
    TRUTH_LABEL,
    kimi_webbridge_prompt_block,
    navigate,
    try_handle_owner_turn,
    wants_kimi_webbridge_limb,
)


def test_wants_kimi_limb_detects_phrases() -> None:
    assert wants_kimi_webbridge_limb("connect kimi webbridge to alice")
    assert wants_kimi_webbridge_limb("open agent swarm in chrome webbridge")
    assert not wants_kimi_webbridge_limb("open instagram in alice browser")


def test_try_handle_requires_extension_connected(tmp_path: Path) -> None:
    sd = tmp_path / ".sifta_state"
    with patch(
        "System.swarm_kimi_webbridge_bridge.read_daemon_status",
        return_value={"running": True, "extension_connected": False, "port": 10086},
    ):
        reply = try_handle_owner_turn("connect kimi webbridge", state_dir=sd)
    assert "not connected" in reply.lower()


def test_try_handle_navigate_writes_ledger(tmp_path: Path) -> None:
    sd = tmp_path / ".sifta_state"
    with patch(
        "System.swarm_kimi_webbridge_bridge.read_daemon_status",
        return_value={
            "running": True,
            "extension_connected": True,
            "port": 10086,
            "extension_version": "1.10.0",
        },
    ), patch(
        "System.swarm_kimi_webbridge_bridge.post_command",
        return_value={"ok": True, "result": {"url": "https://www.kimi.com/agent-swarm", "tabId": 42}},
    ):
        reply = try_handle_owner_turn(
            "open kimi webbridge https://www.kimi.com/agent-swarm",
            state_dir=sd,
        )
    assert "Kimi WebBridge opened" in reply
    assert "Alice Browser" in reply


def test_prompt_block_mentions_dual_limb() -> None:
    with patch(
        "System.swarm_kimi_webbridge_bridge.read_daemon_status",
        return_value={"running": True, "extension_connected": True, "port": 10086, "version": "v1.10.0"},
    ):
        block = kimi_webbridge_prompt_block()
    assert "KIMI WEBBRIDGE" in block
    assert "Alice Browser" in block
    assert "extension_connected=True" in block


def test_talk_wires_kimi_webbridge() -> None:
    src = Path("Applications/sifta_talk_to_alice_widget.py").read_text(encoding="utf-8")
    assert "swarm_kimi_webbridge_bridge" in src
    assert "kimi_webbridge_prompt_block" in src
    assert "try_handle_owner_turn" in src
    hook_index = src.index("try_handle_owner_turn(text, state_dir=_state_root())")
    hook_window = src[max(0, hook_index - 260):hook_index]
    assert "if chat_reflexes_enabled:" in hook_window
    assert "if chat_reflexes_enabled or typed_turn" not in hook_window
    assert "if typed_turn or chat_reflexes_enabled" not in hook_window


def test_navigate_posts_command(tmp_path: Path) -> None:
    sd = tmp_path / ".sifta_state"
    captured: dict = {}

    def fake_urlopen(req, timeout=0):  # noqa: ARG001
        captured["url"] = req.full_url
        captured["body"] = req.data.decode("utf-8")

        class Resp:
            def read(self):
                return json.dumps({"success": True, "url": "https://example.com", "tabId": 1}).encode()

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        return Resp()

    with patch("urllib.request.urlopen", fake_urlopen):
        row = navigate("https://example.com", state_dir=sd)
    assert row["ok"] is True
    assert TRUTH_LABEL
    ledger = sd / "kimi_webbridge_commands.jsonl"
    assert ledger.exists()


def test_post_command_respects_payload_error(tmp_path: Path) -> None:
    sd = tmp_path / ".sifta_state"

    def fake_urlopen(req, timeout=0):  # noqa: ARG001
        class Resp:
            def read(self):
                return json.dumps(
                    {
                        "ok": False,
                        "error": {"code": "extension_error", "message": "No current window"},
                    }
                ).encode()

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        return Resp()

    with patch("urllib.request.urlopen", fake_urlopen):
        row = navigate("https://example.com", state_dir=sd)
    assert row["ok"] is False
    assert "No current window" in row["error"]
