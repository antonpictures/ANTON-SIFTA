import json

import sifta_mcp_server


def _request(method, request_id=1, params=None):
    return sifta_mcp_server.process_request(
        {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}
    )


def test_ollama_only_mode_exposes_only_local_model_tools(monkeypatch):
    monkeypatch.setattr(sifta_mcp_server, "_OLLAMA_ONLY", True)
    monkeypatch.setattr(
        sifta_mcp_server,
        "_ollama_list_local_models",
        lambda: {"ok": True, "models": ["ornith-1.5:9b"]},
    )
    monkeypatch.setattr(
        sifta_mcp_server,
        "_ollama_running_models",
        lambda: {"ok": True, "models": []},
    )

    initialized = _request("initialize")
    assert initialized["result"]["serverInfo"]["name"] == "SIFTA_OLLAMA_MODELS_MCP"

    listed = _request("tools/list", request_id=2)
    assert [tool["name"] for tool in listed["result"]["tools"]] == [
        "ollama.list_local_models",
        "ollama.running_models",
        "ollama.chat_local",
    ]

    called = _request(
        "tools/call",
        request_id=3,
        params={"name": "ollama.list_local_models", "arguments": {}},
    )
    assert json.loads(called["result"]["content"][0]["text"])["models"] == ["ornith-1.5:9b"]


def test_ollama_only_mode_rejects_non_ollama_tools(monkeypatch):
    monkeypatch.setattr(sifta_mcp_server, "_OLLAMA_ONLY", True)
    response = _request(
        "tools/call",
        params={"name": "computer_use.open_app", "arguments": {"app_name": "Xcode"}},
    )
    assert response["error"]["code"] == -32601


def test_full_mode_tools_list_remains_valid(monkeypatch):
    monkeypatch.setattr(sifta_mcp_server, "_OLLAMA_ONLY", False)
    listed = _request("tools/list")
    names = [tool["name"] for tool in listed["result"]["tools"]]
    assert "ollama.list_local_models" in names
    assert "sifta.swimmers.census" in names
