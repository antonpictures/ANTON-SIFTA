from __future__ import annotations


def test_topology_awareness_names_one_alice_relationship_graph(tmp_path):
    from System.swarm_topology_awareness import build_topology_awareness

    state = tmp_path / ".sifta_state"
    state.mkdir()
    (state / "alice_conversation.jsonl").write_text('{"ts": 1, "role": "user"}\n', encoding="utf-8")
    (state / "matrix_terminal_commands.jsonl").write_text('{"ts": 2, "action": "GROK_OPEN"}\n', encoding="utf-8")
    (state / "ide_stigmergic_trace.jsonl").write_text('{"ts": 3, "model": "codex"}\n', encoding="utf-8")
    (state / "work_receipts.jsonl").write_text('{"ts": 4, "kind": "TEST"}\n', encoding="utf-8")

    topo = build_topology_awareness(repo_root=tmp_path)

    assert topo["truth_label"] == "TOPOLOGY_AWARENESS_ORGAN_V1"
    nodes = {node["id"]: node for node in topo["nodes"]}
    for node_id in ("owner", "alice", "global_chat", "matrix_terminal", "local_cortex", "grok", "ide_doctors", "receipts"):
        assert node_id in nodes
    assert nodes["owner"]["label"]
    assert nodes["alice"]["boundary"] == "no surface owns Alice; all surfaces project Alice"
    assert "Grok is not Alice" in nodes["grok"]["boundary"]
    assert topo["ledgers"]["global_chat"]["exists"] is True
    assert topo["ledgers"]["matrix_terminal"]["latest_action"] == "GROK_OPEN"


def test_topology_prompt_block_preserves_grok_and_ide_boundaries(tmp_path):
    from System.swarm_topology_awareness import render_topology_prompt_block

    block = render_topology_prompt_block(repo_root=tmp_path)

    assert "TOPOLOGY AWARENESS" in block
    assert "owner" in block
    assert "Alice field -> tool/cortex organs -> external surfaces -> receipts" in block
    assert "George -> Alice field" not in block
    assert "Grok is external" in block
    assert "IDE doctors are surgical hands" in block
    assert "the global chat remains one shared Alice conversation" in block


def test_topology_awareness_tool_router_status():
    from System.swarm_tool_router import TOOL_REGISTRY, _EXECUTORS

    assert "topology_awareness_status" in TOOL_REGISTRY
    result = _EXECUTORS["topology_awareness_status"]({"focus_context": "Matrix Terminal"})

    assert result["ok"] is True
    assert result["status"] == "TOPOLOGY_AWARENESS_ORGAN_V1"
    assert "Grok is external" in result["alice_summary"]
    assert "prompt_block" in result
