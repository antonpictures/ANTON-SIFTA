"""MCP receipt manifest keeps IDE MANA separate from Alice STGM."""
from __future__ import annotations

import json

import sifta_mcp_server
from System.swarm_mcp_receipt_manifest import build_mcp_receipt_manifest, write_mcp_receipt_manifest


def test_manifest_marks_mana_non_crypto_and_stgm_crypto():
    manifest = build_mcp_receipt_manifest()
    assert manifest["summary"]["mana_is_crypto"] is False
    assert manifest["summary"]["stgm_is_crypto"] is True
    assert manifest["economy_boundary"]["MANA"]["crypto"] is False
    assert manifest["economy_boundary"]["STGM"]["crypto"] is True

    by_tool = {row["tool"]: row for row in manifest["tools"]}
    assert by_tool["get_ledger"]["requires_owner_nonce"] is False
    assert by_tool["get_ledger"]["doctor_trace_currency"] == "MANA"
    assert by_tool["propose_scar"]["requires_owner_nonce"] is True
    assert by_tool["propose_scar"]["stgm_spend_proof"] == "required_before_execution"
    assert by_tool["grok.oauth_chat"]["external_spend"] is True
    assert by_tool["grok.bridge"]["external_spend"] is True


def test_write_manifest_to_state_dir(tmp_path):
    sd = tmp_path / ".sifta_state"
    out = write_mcp_receipt_manifest(state_dir=sd)
    path = sd / "mcp_receipt_manifest.json"
    assert path.exists()
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["truth_label"] == "MCP_STGM_RECEIPT_MANIFEST_V1"
    assert out["manifest_path"] == str(path)


def test_mcp_server_exposes_manifest_tool(tmp_path, monkeypatch):
    monkeypatch.setattr(sifta_mcp_server, "_REPO", tmp_path)
    listed = sifta_mcp_server.process_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    names = {tool["name"] for tool in listed["result"]["tools"]}
    assert "get_mcp_receipt_manifest" in names

    called = sifta_mcp_server.process_request(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "get_mcp_receipt_manifest", "arguments": {}},
        }
    )
    assert called["result"]["isError"] is False
    payload = json.loads(called["result"]["content"][0]["text"])
    assert payload["summary"]["mana_is_crypto"] is False
    assert payload["summary"]["stgm_is_crypto"] is True


def test_grok_bridge_routes_to_cli_when_present(tmp_path, monkeypatch):
    cli_bin = tmp_path / "grok"
    cli_bin.write_text("", encoding="utf-8")
    monkeypatch.setattr(sifta_mcp_server, "_resolve_grok_cli_bin", lambda: str(cli_bin))

    seen = {}

    def fake_cli(prompt, model="", timeout_s=300, max_turns=1):
        seen["cli"] = (prompt, model, timeout_s, max_turns)
        return {"ok": True, "reply": "cli", "stdout": "cli"}

    def fake_oauth(prompt, model="grok-4", image_paths=None, timeout_s=180):
        seen["oauth"] = (prompt, model, image_paths, timeout_s)
        return {"ok": True, "reply": "oauth"}

    monkeypatch.setattr(sifta_mcp_server, "_grok_build_cli", fake_cli)
    monkeypatch.setattr(sifta_mcp_server, "_grok_oauth_chat", fake_oauth)

    result = sifta_mcp_server._grok_bridge("code the test", lane="auto", model="grok-4.3")

    assert result["ok"] is True
    assert result["lane"] == "cli"
    assert result["tool"] == "grok.build_cli"
    assert seen["cli"] == ("code the test", "grok-4.3", 300, 1)
    assert "oauth" not in seen


def test_grok_bridge_routes_to_oauth_when_cli_missing(monkeypatch):
    monkeypatch.setattr(sifta_mcp_server, "_resolve_grok_cli_bin", lambda: None)

    seen = {}

    def fake_cli(prompt, model="", timeout_s=300, max_turns=1):
        seen["cli"] = True
        return {"ok": True, "reply": "cli"}

    def fake_oauth(prompt, model="grok-4", image_paths=None, timeout_s=180):
        seen["oauth"] = (prompt, model, image_paths, timeout_s)
        return {"ok": True, "reply": "oauth"}

    monkeypatch.setattr(sifta_mcp_server, "_grok_build_cli", fake_cli)
    monkeypatch.setattr(sifta_mcp_server, "_grok_oauth_chat", fake_oauth)

    result = sifta_mcp_server._grok_bridge("code the test", lane="auto", model="grok-4")

    assert result["ok"] is True
    assert result["lane"] == "oauth"
    assert result["tool"] == "grok.oauth_chat"
    assert seen["oauth"] == ("code the test", "grok-4", [], 300)
    assert "cli" not in seen


def test_mcp_server_dispatches_grok_bridge(tmp_path, monkeypatch):
    monkeypatch.setenv("SIFTA_MCP_SKIP_MANIFEST_ENFORCE", "1")
    monkeypatch.setattr(sifta_mcp_server, "_REPO", tmp_path)
    monkeypatch.setattr(sifta_mcp_server, "_grok_bridge", lambda *args, **kwargs: {"ok": True, "lane": "cli", "tool": "grok.build_cli"})

    called = sifta_mcp_server.process_request(
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "grok.bridge",
                "arguments": {"prompt": "code the bridge test"},
            },
        }
    )

    assert called["result"]["isError"] is False
    payload = json.loads(called["result"]["content"][0]["text"])
    assert payload["ok"] is True
    assert payload["tool"] == "grok.build_cli"


def test_world_touch_mcp_blocked_without_owner_nonce(tmp_path, monkeypatch):
    sd = tmp_path / ".sifta_state"
    sd.mkdir()
    monkeypatch.setattr(sifta_mcp_server, "_REPO", tmp_path)
    monkeypatch.chdir(tmp_path)

    called = sifta_mcp_server.process_request(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "propose_scar", "arguments": {"target_file": "x.py", "description": "test"}},
        }
    )
    assert called["result"]["isError"] is True
    payload = json.loads(called["result"]["content"][0]["text"])
    assert payload["blocked_by"] == "mcp_receipt_manifest"
    assert payload["reason"] == "mcp_world_touch_requires_owner_nonce"

    rows = [
        json.loads(line)
        for line in (sd / "effector_gate.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(r.get("action") == "refused" and r.get("effector") == "mcp:propose_scar" for r in rows)


def test_world_touch_mcp_allowed_after_owner_ingress(tmp_path, monkeypatch):
    from System.swarm_effector_gate import bind_owner_ingress

    sd = tmp_path / ".sifta_state"
    sd.mkdir()
    monkeypatch.setattr(sifta_mcp_server, "_REPO", tmp_path)
    monkeypatch.chdir(tmp_path)

    bind_owner_ingress(owner_text="close the tab", state_dir=sd)

    called = sifta_mcp_server.process_request(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "propose_scar", "arguments": {"target_file": "x.py", "description": "test"}},
        }
    )
    assert called["result"]["isError"] is False

    rows = [
        json.loads(line)
        for line in (sd / "effector_gate.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(r.get("action") == "allowed" and r.get("effector") == "mcp:propose_scar" for r in rows)
