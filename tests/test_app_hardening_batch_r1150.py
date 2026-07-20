from __future__ import annotations

import importlib.util
import json
import py_compile
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]

BATCH = [
    (16, "Applications/sifta_intrinsic_drive_monitor.py", "AliceWillApp", "queue-016:sifta_intrinsic_drive_monitor"),
    (17, "Applications/sifta_apex_predator_widget.py", "ApexPredatorWidget", "queue-017:sifta_apex_predator_widget"),
    (18, "Applications/sifta_app_manager.py", "AppManagerWidget", "queue-018:sifta_app_manager"),
    (19, "Applications/sifta_aquaculture_sentinel_widget.py", "AquacultureFieldSentinelWidget", "queue-019:sifta_aquaculture_sentinel_widget"),
    (20, "Applications/sifta_agi_cognition_dashboard.py", "AGICognitionDashboard", "queue-020:sifta_agi_cognition_dashboard"),
    (21, "Applications/sifta_awareness_mirror_widget.py", "AwarenessMirrorApp", "queue-021:sifta_awareness_mirror_widget"),
    (22, "Applications/sifta_factory_widget.py", "FactoryWidget", "queue-022:sifta_factory_widget"),
    (23, "Applications/sifta_bell_theorem_widget.py", "BellTheoremWidget", "queue-023:sifta_bell_theorem_widget"),
    (24, "Applications/sifta_biological_dashboard_qt.py", "BiologicalDashboardWidget", "queue-024:sifta_biological_dashboard_qt"),
    (25, "Applications/sifta_bonsai_image_app.py", "BonsaiImageStudioApp", "queue-025:sifta_bonsai_image_app"),
]

EXPECTED_EVENTS = {
    "Applications/sifta_intrinsic_drive_monitor.py": "intrinsic_receipt_parse_failed",
    "Applications/sifta_apex_predator_widget.py": "apex_jsonl_parse_failed",
    "Applications/sifta_app_manager.py": "manifest_load_failed",
    "Applications/sifta_aquaculture_sentinel_widget.py": "aquaculture_receipt_parse_failed",
    "Applications/sifta_agi_cognition_dashboard.py": "jsonl_row_parse_failed",
    "Applications/sifta_awareness_mirror_widget.py": "awareness_frame_missing",
    "Applications/sifta_factory_widget.py": "factory_mint_credit_failed",
    "Applications/sifta_bell_theorem_widget.py": "bell_proof_write_failed",
    "Applications/sifta_biological_dashboard_qt.py": "biology_tension_read_failed",
    "Applications/sifta_bonsai_image_app.py": "bonsai_field_sync_failed",
}


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)
    return module


def _hardening_ids(module) -> set[str]:
    ids = {str(getattr(module, "APP_HARDENING_ID", ""))}
    ids.update(str(item) for item in getattr(module, "APP_HARDENING_ALIASES", ()))
    return {item for item in ids if item}


def test_r1150_batch_matches_queue_rows_sixteen_through_twenty_five() -> None:
    queue = json.loads((REPO / "Documents/APP_HARDENING_QUEUE_2026-06-14.json").read_text())
    rows = queue["rows"][15:25]
    assert [row["index"] for row in rows] == [num for num, _, _, _ in BATCH]
    assert [row["entry_point"] for row in rows] == [entry for _, entry, _, _ in BATCH]
    assert [row["widget_class"] for row in rows] == [widget for _, _, widget, _ in BATCH]


def test_r1150_next_ten_apps_compile_import_and_expose_hardening_ids() -> None:
    for queue_num, rel, widget, hardening_id in BATCH:
        path = REPO / rel
        py_compile.compile(str(path), doraise=True)
        module = _load_module(path)
        assert hardening_id in _hardening_ids(module)
        assert hasattr(module, widget), f"queue #{queue_num} missing widget {widget}"


def test_r1150_next_ten_apps_replace_silent_paths_with_events() -> None:
    for _, rel, _, hardening_id in BATCH:
        src = (REPO / rel).read_text(encoding="utf-8")
        assert hardening_id in src
        assert "record_app_hardening_event" in src
        assert EXPECTED_EVENTS[rel] in src
