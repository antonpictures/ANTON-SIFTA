import json
from pathlib import Path

from System.swarm_episodic_diary import (
    APP_INVENTORY_TRUTH_LABEL,
    format_app_inventory_for_prompt,
    refresh_app_inventory_memory,
    write_episodic_diary,
)


def _jsonl_rows(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_refresh_app_inventory_memory_writes_numbered_idempotent_catalog(tmp_path):
    manifest = tmp_path / "apps_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "Stigmergic Sudoku": {
                    "category": "Games",
                    "entry_point": "Applications/sifta_sudoku_widget.py",
                    "widget_class": "StigmergicSudokuWidget",
                    "description": "ACO Sudoku solver.",
                },
                "Journal": {
                    "category": "Memory",
                    "entry_point": "Applications/sifta_alice_journal_widget.py",
                    "widget_class": "SiftaAliceJournalWidget",
                },
            }
        ),
        encoding="utf-8",
    )

    row = refresh_app_inventory_memory(state_dir=tmp_path, manifest_path=manifest, now=123.0)
    assert row is not None
    assert row["truth_label"] == APP_INVENTORY_TRUTH_LABEL
    assert row["app_count"] == 2
    assert [app["number"] for app in row["apps"]] == [1, 2]
    assert {app["title"] for app in row["apps"]} == {"Journal", "Stigmergic Sudoku"}

    second = refresh_app_inventory_memory(state_dir=tmp_path, manifest_path=manifest, now=124.0)
    assert second["manifest_hash"] == row["manifest_hash"]
    assert len(_jsonl_rows(tmp_path / "app_inventory_memory.jsonl")) == 1

    prompt = format_app_inventory_for_prompt(state_dir=tmp_path)
    assert "#001" in prompt
    assert "one global chat can discuss any app by name or number" in prompt
    assert "Stigmergic Sudoku" in prompt


def test_episodic_diary_metabolizes_app_focus_and_desktop_state(tmp_path):
    (tmp_path / "app_focus.jsonl").write_text(
        json.dumps(
            {
                "ts": 200.0,
                "app": "Stigmergic Sudoku",
                "detail": "The owner is testing the Sudoku swarm.",
                "tab": "Game",
                "selection": "hard puzzle",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "sifta_desktop_app_state.jsonl").write_text(
        json.dumps(
            {
                "ts": 201.0,
                "truth_label": "SIFTA_DESKTOP_APP_STATE_V1",
                "action": "open_app",
                "app_name": "Stigmergic Sudoku",
                "active_app": "Stigmergic Sudoku",
                "open_app_count": 1,
                "open_apps": ["Stigmergic Sudoku"],
                "desktop_mode": "launcher",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    written = write_episodic_diary(hours=24, state_dir=tmp_path, since_ts=0.0, now=300.0)
    assert written
    assert any("apps" in row.get("labels", []) for row in written)
    facts = " ".join(" ".join(row.get("facts", [])) for row in written)
    assert "app=Stigmergic Sudoku" in facts
    assert "action=open_app" in facts
