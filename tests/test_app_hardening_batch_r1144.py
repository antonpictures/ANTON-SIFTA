from __future__ import annotations

import importlib.util
import json
import py_compile
from pathlib import Path

from System.swarm_app_hardening import (
    APP_HARDENING_LEDGER,
    record_app_hardening_event,
    recent_app_hardening_events,
)


REPO = Path(__file__).resolve().parents[1]

BATCH = [
    (1, "Applications/sifta_artificial_general_intelligence.py", "AGIWindow", "queue-001:sifta_artificial_general_intelligence"),
    (2, "Applications/fold_swarm_pouw_sim.py", "PredatorSimWindow", "queue-002:fold_swarm_pouw_sim"),
    (3, "Applications/sifta_primordial_field.py", "PrimordialFieldWidget", "queue-003:sifta_primordial_field"),
    (4, "Applications/sifta_pacman_stigmergic.py", "PacManGame", "queue-004:sifta_pacman_stigmergic"),
    (5, "Applications/sifta_agi_cognition_dashboard.py", "AGICognitionDashboard", "queue-005:sifta_agi_cognition_dashboard"),
]


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_r1144_batch_matches_first_five_queue_rows() -> None:
    queue = json.loads((REPO / "Documents/APP_HARDENING_QUEUE_2026-06-14.json").read_text())
    rows = queue["rows"][:5]
    assert [row["entry_point"] for row in rows] == [entry for _, entry, _, _ in BATCH]
    assert [row["widget_class"] for row in rows] == [widget for _, _, widget, _ in BATCH]


def test_r1144_first_five_apps_compile_import_and_expose_hardening_ids() -> None:
    for queue_num, rel, widget, hardening_id in BATCH:
        path = REPO / rel
        py_compile.compile(str(path), doraise=True)
        module = _load_module(path)
        assert getattr(module, "APP_HARDENING_ID") == hardening_id
        assert hasattr(module, widget), f"queue #{queue_num} missing widget {widget}"


def test_r1144_known_silent_paths_are_replaced_with_hardening_events() -> None:
    sources = {rel: (REPO / rel).read_text(encoding="utf-8") for _, rel, _, _ in BATCH}

    assert "except ImportError:\n    pass" not in sources["Applications/sifta_artificial_general_intelligence.py"]
    assert "pouw_integration_unavailable" in sources["Applications/sifta_artificial_general_intelligence.py"]

    assert "def _publish_focus(*a, **kw): pass" not in sources["Applications/fold_swarm_pouw_sim.py"]
    assert "focus_publisher_unavailable" in sources["Applications/fold_swarm_pouw_sim.py"]

    assert "doctor_sigil_paint_failed" in sources["Applications/sifta_primordial_field.py"]
    assert "organ_receipt_parse_failed" in sources["Applications/sifta_pacman_stigmergic.py"]
    assert "jsonl_row_parse_failed" in sources["Applications/sifta_agi_cognition_dashboard.py"]


def test_app_hardening_event_ledger_helper_writes_and_reads(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    row = record_app_hardening_event(
        "queue-test",
        "visible_error",
        details={"why": "test"},
        state_dir=state,
    )
    assert row["write_status"] == "ok"
    assert (state / APP_HARDENING_LEDGER).exists()
    recent = recent_app_hardening_events(state_dir=state)
    assert recent[0]["event_id"] == row["event_id"]
    assert recent[0]["details"] == {"why": "test"}
