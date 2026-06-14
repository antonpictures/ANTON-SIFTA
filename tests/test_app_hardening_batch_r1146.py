from __future__ import annotations

import importlib.util
import json
import py_compile
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]

BATCH = [
    (6, "Applications/sifta_teach_ace_to_read.py", "TeachAceToReadWidget", "queue-006:sifta_teach_ace_to_read"),
    (7, "Applications/sifta_alice_widget.py", "AliceWidget", "queue-007:sifta_alice_widget"),
    (8, "Applications/sifta_alice_browser_widget.py", "AliceBrowserWidget", "queue-008:sifta_alice_browser_widget"),
    (9, "Applications/sifta_gaze_monitor_widget.py", "GazeMonitorWidget", "queue-009:sifta_gaze_monitor_widget"),
    (10, "Applications/sifta_alice_journal_widget.py", "AliceJournalWidget", "queue-010:sifta_alice_journal_widget"),
    (11, "Applications/sifta_cartography_widget.py", "CartographyWidget", "queue-011:sifta_cartography_widget"),
    (12, "Applications/sifta_self_evaluation.py", "SelfEvaluationApp", "queue-012:sifta_self_evaluation"),
    (13, "Applications/sifta_app_manager.py", "AppManagerWidget", "queue-013:sifta_app_manager"),
    (14, "Applications/sifta_alice_wellbeing_panel.py", "WellbeingPanel", "queue-014:sifta_alice_wellbeing_panel"),
    (15, "Applications/sifta_legs_humanoid_app.py", "LegsHumanoidApp", "queue-015:sifta_legs_humanoid_app"),
]

EXPECTED_EVENTS = {
    "Applications/sifta_teach_ace_to_read.py": "focus_bridge_import_failed",
    "Applications/sifta_alice_widget.py": "child_mesh_sidebar_hide_failed",
    "Applications/sifta_alice_browser_widget.py": "pending_slideshow_stage_failed",
    "Applications/sifta_gaze_monitor_widget.py": "gaze_status_update_failed",
    "Applications/sifta_alice_journal_widget.py": "witness_row_parse_failed",
    "Applications/sifta_cartography_widget.py": "gps_trace_row_parse_failed",
    "Applications/sifta_self_evaluation.py": "matrix_regeneration_failed",
    "Applications/sifta_app_manager.py": "manifest_load_failed",
    "Applications/sifta_alice_wellbeing_panel.py": "wellbeing_pulse_failed",
    "Applications/sifta_legs_humanoid_app.py": "legs_status_read_failed",
}


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_r1146_batch_matches_queue_rows_six_through_fifteen() -> None:
    queue = json.loads((REPO / "Documents/APP_HARDENING_QUEUE_2026-06-14.json").read_text())
    rows = queue["rows"][5:15]
    assert [row["index"] for row in rows] == [num for num, _, _, _ in BATCH]
    assert [row["entry_point"] for row in rows] == [entry for _, entry, _, _ in BATCH]
    assert [row["widget_class"] for row in rows] == [widget for _, _, widget, _ in BATCH]


def test_r1146_next_ten_apps_compile_import_and_expose_hardening_ids() -> None:
    for queue_num, rel, widget, hardening_id in BATCH:
        path = REPO / rel
        py_compile.compile(str(path), doraise=True)
        module = _load_module(path)
        assert getattr(module, "APP_HARDENING_ID") == hardening_id
        assert hasattr(module, widget), f"queue #{queue_num} missing widget {widget}"


def test_r1146_next_ten_apps_replace_silent_paths_with_events() -> None:
    for _, rel, _, hardening_id in BATCH:
        src = (REPO / rel).read_text(encoding="utf-8")
        assert hardening_id in src
        assert "record_app_hardening_event" in src
        assert EXPECTED_EVENTS[rel] in src
