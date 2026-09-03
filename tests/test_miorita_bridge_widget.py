from __future__ import annotations

import json
from pathlib import Path

from Applications.sifta_miorita_bridge_widget import (
    ACTION_BOARD,
    REGISTRY,
    ROUTING,
    load_miorita_snapshot,
    update_miorita_task_status,
)


def test_snapshot_reads_two_miorita_lanes(tmp_path: Path) -> None:
    (tmp_path / ACTION_BOARD.parent).mkdir(parents=True)
    (tmp_path / REGISTRY.parent).mkdir(parents=True)
    (tmp_path / ROUTING.parent).mkdir(parents=True)
    (tmp_path / ACTION_BOARD).write_text(
        json.dumps({"tasks": [{"id": "one", "status": "open"}]}), encoding="utf-8"
    )
    (tmp_path / REGISTRY).write_text(
        json.dumps({"summary": {"active_files": 9, "unlinked_active_files": 0}}), encoding="utf-8"
    )
    (tmp_path / ROUTING).write_text(
        json.dumps({"items": [{"episode": 1, "episode_title": "LA 3:47"}]}), encoding="utf-8"
    )

    snapshot = load_miorita_snapshot(tmp_path)

    assert snapshot["available"] is True
    assert snapshot["tasks"][0]["id"] == "one"
    assert snapshot["episodes"][0]["source_count"] == 1
    assert snapshot["registry"]["unlinked_active_files"] == 0


def test_update_task_status_only_changes_action_board(tmp_path: Path) -> None:
    (tmp_path / ACTION_BOARD.parent).mkdir(parents=True)
    (tmp_path / ACTION_BOARD).write_text(
        json.dumps({"tasks": [{"id": "one", "status": "open"}]}), encoding="utf-8"
    )

    assert update_miorita_task_status(tmp_path, "one", "done") is True
    board = json.loads((tmp_path / ACTION_BOARD).read_text(encoding="utf-8"))
    assert board["tasks"][0]["status"] == "done"
