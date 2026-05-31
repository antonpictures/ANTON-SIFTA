from __future__ import annotations

import json

from System import swarm_claude_arm as claude_arm
from System import swarm_claude_swimmer_arm as claude_swimmer_arm


def test_catalog_loads_from_cloned_port() -> None:
    commands = claude_arm.list_commands()
    tools = claude_arm.list_tools()

    assert len(commands) >= 150
    assert len(tools) >= 100
    assert "summary" in commands
    assert "BashTool" in tools
    assert "MCPTool" in tools


def test_alias_module_reexports_operational_arm() -> None:
    assert claude_swimmer_arm.dispatch is claude_arm.dispatch
    assert claude_swimmer_arm.list_commands is claude_arm.list_commands
    assert claude_swimmer_arm.list_tools is claude_arm.list_tools


def test_dispatch_writes_receipt_to_temp_ledger(tmp_path, monkeypatch) -> None:
    ledger = tmp_path / "claude_arm_organ.jsonl"
    monkeypatch.setattr(claude_arm, "LEDGER_PATH", ledger)

    result = claude_arm.dispatch("bash", "echo hello from the claude swimmer arm")

    assert result["outcome"] in {"executed_as_alice_swimmer", "executed_bash_as_alice_swimmer"}
    assert result["ledger"] == str(ledger)
    assert ledger.exists()

    row = json.loads(ledger.read_text(encoding="utf-8").splitlines()[-1])
    assert row["truth_label"] == "OPERATIONAL"
    assert row["lane"] == "ALICE_ARM"
    assert row["name"] == "bash"
    assert row["extra"]["alice_swimmer_id"]


def test_get_catalog_summary_reports_current_counts() -> None:
    summary = claude_arm.get_catalog_summary()
    assert summary["commands"] >= 150
    assert summary["tools"] >= 100
    assert "instructkr/claude-code" in summary["source"]
