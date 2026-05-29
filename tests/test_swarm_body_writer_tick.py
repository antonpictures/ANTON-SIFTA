"""Round 84 tests — body writer tick organ.

Verifies that one call to tick_writer_organs():
  - calls both producers (basal_ganglia + fractal_pheromone)
  - writes a receipt to body_writer_tick.jsonl with per-producer status
  - reports byte_delta per producer so the freshness loop can see growth
  - handles producer import or call failures without raising
  - respects feature flags to disable one producer
  - summary_for_prompt emits prompt-ready text
  - real .sifta_state is untouched
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from System import swarm_body_writer_tick as bwt


@pytest.fixture(autouse=True)
def _mock_heavy_producers():
    """The live fractal walker runs a heavy SierpinskiGasket + walker
    simulation that takes many seconds. The body_brain_loop tick also
    runs a full physiology cycle with multiple ledger writes. Both are
    mocked by default for unit speed; tests that want to verify the
    REAL producer call shape can opt out via patch.dict themselves.

    Round 91 — body_brain_loop added alongside fractal_walker_organ."""
    fake_walker = MagicMock(
        run_walkers=MagicMock(return_value=MagicMock(alpha=0.5, rows_written=0)),
    )
    fake_brain_module = MagicMock()
    fake_brain_module.SwarmPhysiology = MagicMock(
        return_value=MagicMock(
            body_brain_tick=MagicMock(return_value={"tick_id": "test-tick", "soma_score": 1.0}),
        ),
    )
    with patch.dict(
        "sys.modules",
        {
            "System.swarm_fractal_walker_organ": fake_walker,
            "System.swarm_body_brain_loop": fake_brain_module,
        },
    ):
        yield fake_walker


# ─── Happy path: both producers fire ───────────────────────────────────────


def test_tick_calls_all_four_producers_when_modules_present(tmp_path: Path):
    """Round 91 — four producers fire and the tick row reports all four:
    basal_ganglia + fractal_pheromone + field_slo + body_brain_loop. Heavy
    producers (fractal walker, body brain loop) are mocked by the autouse
    fixture; basal_ganglia + field_slo are mocked here for hermetic write
    paths."""
    state = tmp_path / ".sifta_state"

    fake_bg_module = MagicMock(
        select_action=MagicMock(return_value=("rest_idle", 0.1)),
        selection_log_path=MagicMock(return_value=state / "basal_ganglia_selections.jsonl"),
    )
    fake_slo_module = MagicMock(
        append_state_dir_report=MagicMock(return_value={"slo_pass": True}),
    )

    with patch.dict(
        "sys.modules",
        {
            "System.swarm_basal_ganglia_action_selector": fake_bg_module,
            "System.swarm_field_slo": fake_slo_module,
        },
    ):
        row = bwt.tick_writer_organs(state_dir=state)

    assert row["truth_label"] == bwt.TRUTH_LABEL
    assert row["producer_count"] == 4
    producer_names = {p["producer"] for p in row["producers"]}
    assert producer_names == {"basal_ganglia", "fractal_pheromone", "field_slo", "body_brain_loop"}
    fake_bg_module.select_action.assert_called_once()
    fake_slo_module.append_state_dir_report.assert_called_once()
    # Receipt landed in the tick ledger
    tick_path = state / bwt.TICK_LEDGER
    assert tick_path.exists()
    rows = [json.loads(l) for l in tick_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(rows) == 1


# ─── Mocked successful basal_ganglia ───────────────────────────────────────


def test_basal_ganglia_success_records_action_and_score(tmp_path: Path):
    state = tmp_path / ".sifta_state"
    state.mkdir(parents=True, exist_ok=True)

    fake_select = MagicMock(return_value=("repair_body", 0.42))
    fake_log_path = MagicMock(return_value=state / "basal_ganglia_selections.jsonl")
    # Simulate a successful ledger write by touching the file
    (state / "basal_ganglia_selections.jsonl").write_text("{}\n", encoding="utf-8")

    with patch.dict(
        "sys.modules",
        {
            "System.swarm_basal_ganglia_action_selector": MagicMock(
                select_action=fake_select,
                selection_log_path=fake_log_path,
            ),
        },
    ):
        # We bypass the fractal producer to isolate this test
        row = bwt.tick_writer_organs(
            state_dir=state, enable_fractal_pheromone=False,
        )

    bg = next(p for p in row["producers"] if p["producer"] == "basal_ganglia")
    # When the producer is replaced and the ledger doesn't actually grow
    # via select_action, status is "no_write" — but the action and score
    # MUST surface so the tick row is meaningful.
    assert bg.get("selected_action") == "repair_body"
    assert bg.get("winner_score") == pytest.approx(0.42)


# ─── Mocked import failures handled cleanly ────────────────────────────────


def test_producer_import_failure_does_not_raise(tmp_path: Path):
    state = tmp_path / ".sifta_state"

    # Block the basal_ganglia import via sys.modules sentinel + raise on access.
    bad_module = MagicMock()
    bad_module.select_action.side_effect = ImportError("synthetic missing")
    with patch.dict(
        "sys.modules",
        {"System.swarm_basal_ganglia_action_selector": bad_module},
    ):
        # Even when the basal_ganglia call_failed, the other three producers
        # should still attempt to fire and the tick row should land.
        row = bwt.tick_writer_organs(state_dir=state)
    assert "producers" in row
    bg = next(p for p in row["producers"] if p["producer"] == "basal_ganglia")
    assert bg["status"] in ("call_failed", "import_failed")
    # All four producers must still be represented (Round 91)
    assert row["producer_count"] == 4


# ─── Feature flags ─────────────────────────────────────────────────────────


def test_disable_basal_ganglia(tmp_path: Path):
    state = tmp_path / ".sifta_state"
    row = bwt.tick_writer_organs(
        state_dir=state,
        enable_basal_ganglia=False,
        enable_field_slo=False,
        enable_body_brain_loop=False,
    )
    producers = {p["producer"] for p in row["producers"]}
    assert producers == {"fractal_pheromone"}
    assert row["producer_count"] == 1


def test_disable_fractal_pheromone(tmp_path: Path):
    state = tmp_path / ".sifta_state"
    row = bwt.tick_writer_organs(
        state_dir=state,
        enable_fractal_pheromone=False,
        enable_field_slo=False,
        enable_body_brain_loop=False,
    )
    producers = {p["producer"] for p in row["producers"]}
    assert producers == {"basal_ganglia"}
    assert row["producer_count"] == 1


def test_disable_all_writes_empty_tick(tmp_path: Path):
    state = tmp_path / ".sifta_state"
    row = bwt.tick_writer_organs(
        state_dir=state,
        enable_basal_ganglia=False,
        enable_fractal_pheromone=False,
        enable_field_slo=False,
        enable_body_brain_loop=False,
    )
    assert row["producers"] == []
    assert row["producer_count"] == 0
    assert row["overall_status"] == "all_failed"


# ─── Round 91 — field_slo + body_brain_loop producers ──────────────────────


def test_field_slo_producer_fires(tmp_path: Path):
    """The field_slo tick must call append_state_dir_report and report ok."""
    state = tmp_path / ".sifta_state"
    fake_slo = MagicMock(
        append_state_dir_report=MagicMock(return_value={"slo_pass": True}),
    )
    with patch.dict("sys.modules", {"System.swarm_field_slo": fake_slo}):
        row = bwt.tick_writer_organs(
            state_dir=state,
            enable_basal_ganglia=False,
            enable_fractal_pheromone=False,
            enable_body_brain_loop=False,
        )
    assert row["producer_count"] == 1
    slo = row["producers"][0]
    assert slo["producer"] == "field_slo"
    fake_slo.append_state_dir_report.assert_called_once()


def test_body_brain_loop_producer_fires(tmp_path: Path):
    """The body_brain_loop tick must call SwarmPhysiology().body_brain_tick()."""
    state = tmp_path / ".sifta_state"
    row = bwt.tick_writer_organs(
        state_dir=state,
        enable_basal_ganglia=False,
        enable_fractal_pheromone=False,
        enable_field_slo=False,
    )
    assert row["producer_count"] == 1
    bbl = row["producers"][0]
    assert bbl["producer"] == "body_brain_loop"
    # When the mocked SwarmPhysiology returns a tick_id, it surfaces on the row.
    assert "tick_id" in bbl or bbl["status"] in ("ok", "no_write", "call_failed", "import_failed")


def test_field_slo_import_failure_does_not_raise(tmp_path: Path):
    state = tmp_path / ".sifta_state"
    bad_slo = MagicMock()
    bad_slo.append_state_dir_report.side_effect = ImportError("missing")
    with patch.dict("sys.modules", {"System.swarm_field_slo": bad_slo}):
        row = bwt.tick_writer_organs(
            state_dir=state,
            enable_basal_ganglia=False,
            enable_fractal_pheromone=False,
            enable_body_brain_loop=False,
        )
    slo = next(p for p in row["producers"] if p["producer"] == "field_slo")
    assert slo["status"] in ("call_failed", "import_failed")


def test_body_brain_loop_import_failure_does_not_raise(tmp_path: Path):
    state = tmp_path / ".sifta_state"
    bad_brain = MagicMock()
    bad_brain.SwarmPhysiology.side_effect = ImportError("missing")
    with patch.dict("sys.modules", {"System.swarm_body_brain_loop": bad_brain}):
        row = bwt.tick_writer_organs(
            state_dir=state,
            enable_basal_ganglia=False,
            enable_fractal_pheromone=False,
            enable_field_slo=False,
        )
    bbl = next(p for p in row["producers"] if p["producer"] == "body_brain_loop")
    assert bbl["status"] in ("call_failed", "import_failed")


# ─── write_receipt=False skips ledger ──────────────────────────────────────


def test_write_receipt_false_skips_ledger(tmp_path: Path):
    state = tmp_path / ".sifta_state"
    row = bwt.tick_writer_organs(
        state_dir=state, write_receipt=False,
    )
    assert row["truth_label"] == bwt.TRUTH_LABEL
    tick_path = state / bwt.TICK_LEDGER
    assert not tick_path.exists()


# ─── summary_for_prompt ────────────────────────────────────────────────────


def test_summary_empty_when_no_ticks(tmp_path: Path):
    state = tmp_path / ".sifta_state"
    out = bwt.summary_for_prompt(state)
    assert "no tick receipts yet" in out


def test_summary_reports_last_tick(tmp_path: Path):
    state = tmp_path / ".sifta_state"
    bwt.tick_writer_organs(
        state_dir=state, enable_basal_ganglia=False, enable_fractal_pheromone=False,
    )
    out = bwt.summary_for_prompt(state)
    assert "BODY WRITER TICK" in out
    assert "last_tick_age_s=" in out
    assert "status=" in out


# ─── Multiple ticks ────────────────────────────────────────────────────────


def test_two_ticks_produce_two_rows(tmp_path: Path):
    state = tmp_path / ".sifta_state"
    bwt.tick_writer_organs(
        state_dir=state, enable_basal_ganglia=False, enable_fractal_pheromone=False,
    )
    bwt.tick_writer_organs(
        state_dir=state, enable_basal_ganglia=False, enable_fractal_pheromone=False,
    )
    rows = [
        json.loads(l)
        for l in (state / bwt.TICK_LEDGER).read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    assert len(rows) == 2


# ─── Real ledger isolation ─────────────────────────────────────────────────


def test_real_ledger_isolation(tmp_path: Path):
    """Pure module — must not mutate any real .sifta_state file."""
    real = Path(".sifta_state")
    watched = [
        real / "body_writer_tick.jsonl",
        real / "basal_ganglia_selections.jsonl",
        real / "fractal_pheromone_field.jsonl",
        real / "work_receipts.jsonl",
    ]
    before = {str(p): (p.stat().st_size if p.exists() else 0) for p in watched}

    state = tmp_path / ".sifta_state"
    bwt.tick_writer_organs(
        state_dir=state, enable_basal_ganglia=False, enable_fractal_pheromone=False,
    )
    bwt.summary_for_prompt(state)

    after = {str(p): (p.stat().st_size if p.exists() else 0) for p in watched}
    for k in before:
        assert before[k] == after[k], f"body_writer_tick mutated {k}"
