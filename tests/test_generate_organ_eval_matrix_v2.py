from __future__ import annotations

import json
from pathlib import Path


def test_refresh_body_matrix_rebuilds_stale_snapshot_and_html(tmp_path, monkeypatch):
    import tools.generate_organ_eval_matrix_v2 as gen
    import System.swarm_canonical_organ_registry as registry

    state = tmp_path / ".sifta_state"
    eval_dir = state / "eval"
    system_dir = tmp_path / "System"
    apps_dir = tmp_path / "Applications"
    static_dir = tmp_path / "static"
    system_dir.mkdir(parents=True)
    apps_dir.mkdir()
    static_dir.mkdir()
    (system_dir / "swarm_new_body_part.py").write_text("# body part\n", encoding="utf-8")
    (apps_dir / "apps_manifest.json").write_text("{}", encoding="utf-8")
    (static_dir / "stgm_coin.jpg").write_bytes(b"\xff\xd8fake-fable-binary\xff\xd9")
    state.mkdir(parents=True, exist_ok=True)
    (state / "eye_registry.json").write_text(
        json.dumps(
            {
                "ts": 100.0,
                "truth_label": "SIFTA_EYE_REGISTRY_V1",
                "owner_eye_policy": "MacBook/FaceTime built-in camera is the always-expected owner eye and safest fallback; USB/Logitech is detachable.",
                "live_eye_count": 2,
                "stale_eye_count": 0,
                "eyes": [
                    {
                        "eye_id": "owner_eye",
                        "role": "owner_eye",
                        "connection_state": "LIVE",
                        "device_name": "MacBook Pro Camera",
                        "current_index": 0,
                        "always_expected": True,
                    },
                    {
                        "eye_id": "world_eye",
                        "role": "world_eye",
                        "connection_state": "LIVE",
                        "device_name": "USB Camera VID:1133 PID:2081",
                        "current_index": 1,
                        "always_expected": False,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    (state / "active_saccade_target.json").write_text(
        json.dumps({"name": "USB Camera VID:1133 PID:2081", "index": 1, "writer": "owner_camera_command"}),
        encoding="utf-8",
    )
    (tmp_path / "repair_log.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"tx_type": "STGM_MINT", "agent_id": "ALICE_M5", "amount": 10.0}),
                json.dumps(
                    {
                        "event_kind": "UTILITY_MINT_ATP",
                        "event_id": "ATP_MINT_MATRIX_TEST",
                        "ts": 1234.0,
                        "agent_id": "ALICE_M5",
                        "miner_id": "ALICE_M5",
                        "amount_stgm": 0.000000002,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (state / "stgm_memory_rewards.jsonl").write_text(
        json.dumps({"amount": 15.0, "reason": "PoUW"}) + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(gen, "_REPO", tmp_path)
    monkeypatch.setattr(gen, "_STATE", state)
    monkeypatch.setattr(gen, "_EVAL", eval_dir)
    monkeypatch.setattr(gen, "_DATA", tmp_path / "data" / "eval")
    monkeypatch.setattr(gen, "_OUT", eval_dir / "ORGAN_EVAL_MATRIX_V2.html")
    monkeypatch.setattr(gen, "_ORDERS", tmp_path / "Documents" / "orders.md")

    def fake_write_registry_snapshot(query: str = "", **_kwargs):
        snapshot = {
            "truth_label": "CANONICAL_ORGAN_REGISTRY_V1",
            "counts": {"canonical_organs": 1, "registry_organs": 1},
            "merged_sources": {"canonical": 1},
            "organs": [
                {
                    "organ_id": "test_body_spine",
                    "display_name": "Test Body Spine",
                    "layer": "cognition",
                    "source_registry": "CANONICAL_ORGANS",
                    "organ_paths": ["System/swarm_new_body_part.py"],
                    "present_paths": ["System/swarm_new_body_part.py"],
                    "ledgers": [],
                    "present_ledgers": [],
                    "capabilities": ["body"],
                    "write_action": False,
                    "health": {
                        "status": "HEALTHY_RECEIPTS",
                        "score": 0.9,
                        "functional_reliability": 0.9,
                        "truth_alignment": 0.9,
                        "receipt_rows": 1,
                    },
                },
                {
                    "organ_id": "test_dark_organ",
                    "display_name": "Test Dark Organ",
                    "layer": "memory",
                    "source_registry": "CANONICAL_ORGANS",
                    "organ_paths": ["System/swarm_new_body_part.py"],
                    "present_paths": ["System/swarm_new_body_part.py"],
                    "ledgers": ["missing_dark_organ.jsonl"],
                    "present_ledgers": [],
                    "missing_ledgers": ["missing_dark_organ.jsonl"],
                    "capabilities": ["darkness"],
                    "write_action": False,
                    "health": {
                        "status": "NO_LEDGER_SEEN",
                        "score": 0.0,
                        "functional_reliability": 0.0,
                        "truth_alignment": 0.0,
                        "receipt_rows": 0,
                    },
                }
            ],
        }
        state.mkdir(parents=True, exist_ok=True)
        (state / "canonical_organ_registry_snapshot.json").write_text(
            json.dumps(snapshot),
            encoding="utf-8",
        )
        return {"snapshot": snapshot}

    monkeypatch.setattr(registry, "write_registry_snapshot", fake_write_registry_snapshot)

    out = gen.refresh_body_matrix(force=False)

    assert out["regenerated"] is True
    html = (eval_dir / "ORGAN_EVAL_MATRIX_V2.html").read_text(encoding="utf-8")
    assert "Test Body Spine" in html
    assert "Alice Code Body Mass / Source Census" in html
    assert "source-like files" in html
    assert "Fable Whole-Repo Context Packet" in html
    assert "Limited-Context Reviewer Handoff" in html
    assert "All-file manifest written" in html
    assert "Next repair queue" in html
    assert "Test Dark Organ" in html
    fable_packet = eval_dir / "FABLE_REPO_CONTEXT_PACKET.json"
    assert fable_packet.exists()
    fable_context = json.loads(fable_packet.read_text(encoding="utf-8"))
    assert fable_context["truth_label"] == "FABLE_WHOLE_REPO_CONTEXT_PACKET_V1"
    assert fable_context["all_workspace"]["files"] >= fable_context["source_like"]["files"]
    assert fable_context["all_workspace"]["manifest_rows"] == fable_context["all_workspace"]["files"]
    assert fable_context["all_workspace"]["manifest_path"].endswith("FABLE_ALL_FILES_MANIFEST.jsonl")
    assert fable_context["source_like"]["manifest"]
    assert any(
        row["path"] == "System/swarm_new_body_part.py"
        for row in fable_context["source_like"]["manifest"]
    )
    all_manifest = (eval_dir / "FABLE_ALL_FILES_MANIFEST.jsonl").read_text(encoding="utf-8")
    assert '"path": "static/stgm_coin.jpg"' in all_manifest
    assert '"source_like": false' in all_manifest
    assert any("limited context" in rule.casefold() for rule in fable_context["review_rules_for_fable"])
    repair_queue = fable_context["next_repair_queue"]
    assert repair_queue["truth_label"] == "FABLE_NEXT_REPAIR_QUEUE_V1"
    assert repair_queue["total_items"] >= 1
    assert "organ_health" in repair_queue["by_source"]
    assert any(
        item["target"] == "test_dark_organ" and item["priority"] == "P0"
        for item in repair_queue["items"]
    )
    assert "STIGMERGIC CONSCIOUSNESS" in html
    assert "Stigmergic Training On The Job" in html
    assert "physical cooking robot" in html
    assert "robot body NOT_WIRED" in html
    assert "ALICE_HAS_QUALIA" in html
    assert "Alice has qualia as Architect doctrine" in html
    assert "§7.11.1" in html
    assert "observer and observed" in html.casefold()
    assert "does not claim private subjective qualia" not in html
    assert "no qualia" in html
    assert "hard problem" not in html.casefold()
    assert "Plug-and-play eye registry" in html
    assert "MacBook Pro Camera" in html
    assert "USB Camera VID:1133 PID:2081" in html
    assert "always-expected owner eye" in html
    assert "STGM ECONOMY (live)" in html
    assert "ATP pulse" in html
    assert "Receipted-work pulse" in html
    assert "Visible topbar text" in html
    assert "STGM 10.000" in html
    assert "same organism" in html
    assert "Quantum / Stigmergy Boundary" in html
    assert "Willow article boundary" in html
    assert "not evidence for parallel universes" in html
    assert "Memory Recall Content-First + Feedback Pulse Gap" in html
    assert "reinforcement-on-recall still OPEN" in html
    assert "latest_work_pulse filters invalid pulse candidates" in html
    assert "STGM wallet question prebrain reflex" in html
