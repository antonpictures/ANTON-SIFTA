from pathlib import Path

from System.swarm_canonical_organ_registry import (
    build_registry,
    route_query,
    write_registry_snapshot,
)


def test_registry_counts_and_routes_to_organs(tmp_path: Path) -> None:
    root = tmp_path
    state = tmp_path / ".sifta_state"
    (root / "System").mkdir()
    (root / "Applications").mkdir()
    (root / "System" / "swarm_tool_router.py").write_text("", encoding="utf-8")
    (root / "System" / "swarm_life_journal_consolidator.py").write_text("", encoding="utf-8")
    (root / "Applications" / "sifta_talk_to_alice_widget.py").write_text("", encoding="utf-8")
    state.mkdir()
    (state / "work_receipts.jsonl").write_text('{"ok": true}\n', encoding="utf-8")
    (state / "journal_schedule_receipts.jsonl").write_text('{"ok": true}\n', encoding="utf-8")

    snap = build_registry(root=root, state_dir=state)
    assert snap["truth_label"] == "CANONICAL_ORGAN_REGISTRY_V1"
    assert snap["counts"]["system_python_organs"] == 2
    assert snap["counts"]["application_surfaces"] == 1
    assert snap["counts"]["registry_organs"] >= snap["counts"]["canonical_organs"]
    assert snap["research_basis"]
    assert "health" in snap["organs"][0]
    assert "stgm_profitability" in snap["organs"][0]
    assert all(organ.get("stable_id", "").startswith("organ_") for organ in snap["organs"])

    routed = route_query("check schedule and execute a tool with receipt", registry=snap)
    ids = [m["organ_id"] for m in routed["matches"]]
    assert "schedule_journal" in ids
    assert "tool_truth_router" in ids
    assert routed["matches"][0]["health"]["status"]
    assert routed["matches"][0]["stable_id"].startswith("organ_")


def test_write_registry_snapshot_appends_query_receipt(tmp_path: Path) -> None:
    root = tmp_path
    state = tmp_path / ".sifta_state"
    (root / "System").mkdir()
    (root / "System" / "swarm_face_detection.py").write_text("", encoding="utf-8")

    out = write_registry_snapshot("camera face", root=root, state_dir=state)

    assert (state / "canonical_organ_registry_snapshot.json").exists()
    assert (state / "canonical_organ_query_map.jsonl").exists()
    assert out["query_map"]["matches"][0]["organ_id"] == "vision_lane"


def test_registry_merges_apps_manifest_and_alias_routes(tmp_path: Path) -> None:
    root = tmp_path
    state = tmp_path / ".sifta_state"
    (root / "System").mkdir()
    apps = root / "Applications"
    apps.mkdir()
    (apps / "apps_manifest.json").write_text(
        '{"SIFTA Lab": {"entry_point": "Applications/sifta_lab.py", "category": "Science", "description": "protein research"}}',
        encoding="utf-8",
    )
    (apps / "sifta_lab.py").write_text("", encoding="utf-8")

    snap = build_registry(root=root, state_dir=state)
    ids = {organ["organ_id"] for organ in snap["organs"]}

    assert "app_sifta_lab" in ids
    assert snap["merged_sources"]["apps_manifest"] == 1
    routed = route_query("open science protein research", registry=snap)
    assert any(match["organ_id"] == "app_sifta_lab" for match in routed["matches"])


def test_route_query_uses_aliases_and_profitability_fields(tmp_path: Path) -> None:
    root = tmp_path
    state = tmp_path / ".sifta_state"
    (root / "System").mkdir()
    state.mkdir()
    (root / "System" / "swarm_agent_arm_registry.py").write_text("", encoding="utf-8")
    (root / "System" / "swarm_agent_arm_decision.py").write_text("", encoding="utf-8")
    (state / "agent_arm_receipts.jsonl").write_text('{"ok": true}\n', encoding="utf-8")

    snap = build_registry(root=root, state_dir=state)
    routed = route_query("use octopus arm evidence pass", registry=snap)
    match = routed["matches"][0]

    assert match["organ_id"] == "agent_arms"
    assert "octopus arm" in match["matched_aliases"]
    assert "stgm_profitability" in match


def test_health_and_profitability_are_receipt_derived(tmp_path: Path) -> None:
    root = tmp_path
    state = tmp_path / ".sifta_state"
    (root / "System").mkdir()
    state.mkdir()
    (root / "System" / "swarm_metabolic_homeostasis.py").write_text("", encoding="utf-8")
    (state / "metabolic_homeostasis.jsonl").write_text(
        '{"ok": true, "receipt": "abc", "value_stgm": 2.0, "fee_stgm": 0.25}\n'
        '{"ok": false, "receipt": "def", "error": "timeout", "fee_stgm": 0.10}\n',
        encoding="utf-8",
    )

    snap = build_registry(root=root, state_dir=state)
    metabolism = next(organ for organ in snap["organs"] if organ["organ_id"] == "metabolism_stgm")
    health = metabolism["health"]
    profit = metabolism["stgm_profitability"]

    assert health["sample_rows"] == 2
    assert health["ok_rows"] == 1
    assert health["bad_rows"] == 1
    assert health["receipt_rows"] == 2
    assert "functional_reliability" in health
    assert "truth_alignment" in health
    assert "formula" in health
    assert profit["credit_stgm"] == 2.0
    assert profit["debit_stgm"] == 0.35
    assert profit["profitable"] is True
