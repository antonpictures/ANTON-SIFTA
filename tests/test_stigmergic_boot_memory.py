from __future__ import annotations

from System.swarm_stigmergic_boot_memory import append_linked_record, boot_context, validate_graph


def test_boot_context_is_root_and_does_not_invent_pose(tmp_path):
    first = boot_context(state_dir=tmp_path, epoch=1000)
    second = boot_context(state_dir=tmp_path, epoch=1001)
    assert first["record_id"] == second["record_id"]
    assert first["clock"]["epoch"] == 1000
    assert first["pose"] is None
    assert first["source_ids"] == []


def test_graph_reports_dangling_links_and_cycles():
    assert not validate_graph([{"record_id": "a", "source_ids": ["missing"]}])["ok"]
    result = validate_graph([
        {"record_id": "a", "source_ids": ["b"]},
        {"record_id": "b", "source_ids": ["a"]},
    ])
    assert not result["ok"] and result["cycles"]


def test_linked_record_points_to_boot_root(tmp_path):
    row = append_linked_record("decision", state_dir=tmp_path, payload={"action": "open_tab"})
    root = boot_context(state_dir=tmp_path)
    assert row["source_ids"] == [root["record_id"]]
    assert row["boot_record_id"] == root["record_id"]
