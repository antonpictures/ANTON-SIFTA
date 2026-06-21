from __future__ import annotations

import gzip
import json
from pathlib import Path

from System.canonical_schemas import LEDGER_SCHEMAS
from System.swarm_ledger_rotation import (
    DEFAULT_POLICIES,
    RotationPolicy,
    fast_rotate_ledger_by_bytes,
    rotate_ledger,
)


def test_rotate_ledger_archives_evicted_rows_and_keeps_tail(tmp_path: Path):
    state = tmp_path / "state"
    archive = tmp_path / "archive"
    audit = state / "ledger_rotation.jsonl"
    state.mkdir()
    ledger = state / "visual_stigmergy.jsonl"
    ledger.write_text("".join(json.dumps({"i": i}) + "\n" for i in range(6)), encoding="utf-8")
    policy = RotationPolicy("visual_stigmergy.jsonl", keep_last=2, min_bytes=1, reason="test")

    row = rotate_ledger(
        policy,
        state_dir=state,
        archive_dir=archive,
        rotation_ledger=audit,
        now=123.0,
    )

    assert set(row.keys()) == LEDGER_SCHEMAS["ledger_rotation.jsonl"]
    assert row["archived_lines"] == 4
    assert row["kept_lines"] == 2
    assert [json.loads(line)["i"] for line in ledger.read_text().splitlines()] == [4, 5]
    with gzip.open(row["archive_path"], "rt", encoding="utf-8") as f:
        assert [json.loads(line)["i"] for line in f.read().splitlines()] == [0, 1, 2, 3]
    written = json.loads(audit.read_text(encoding="utf-8").strip())
    assert written["archive_sha256"] == row["archive_sha256"]


def test_dry_run_does_not_mutate_source_or_write_audit(tmp_path: Path):
    state = tmp_path / "state"
    state.mkdir()
    ledger = state / "pheromone_log.jsonl"
    original = "".join(json.dumps({"i": i}) + "\n" for i in range(6))
    ledger.write_text(original, encoding="utf-8")
    policy = RotationPolicy("pheromone_log.jsonl", keep_last=2, min_bytes=1, reason="test")

    row = rotate_ledger(policy, state_dir=state, archive_dir=tmp_path / "archive", dry_run=True)

    assert row["dry_run"] is True
    assert "would keep" in row["reason"]
    assert ledger.read_text(encoding="utf-8") == original
    assert not (state / "ledger_rotation.jsonl").exists()


def test_small_ledger_skips_without_audit(tmp_path: Path):
    state = tmp_path / "state"
    state.mkdir()
    ledger = state / "network_topology.jsonl"
    ledger.write_text("{}\n", encoding="utf-8")
    policy = RotationPolicy("network_topology.jsonl", keep_last=1, min_bytes=10_000, reason="test")

    row = rotate_ledger(policy, state_dir=state, archive_dir=tmp_path / "archive")

    assert row["archived_lines"] == 0
    assert row["archive_path"] == ""
    assert row["reason"].startswith("skip:")


def test_fast_rotate_by_bytes_moves_full_file_and_keeps_recent_tail(tmp_path: Path):
    state = tmp_path / "state"
    archive = tmp_path / "archive"
    audit = state / "ledger_rotation.jsonl"
    state.mkdir()
    ledger = state / "kernel_process_table.jsonl"
    original = "".join(json.dumps({"i": i, "payload": "x" * 20}) + "\n" for i in range(20))
    ledger.write_text(original, encoding="utf-8")

    row = fast_rotate_ledger_by_bytes(
        "kernel_process_table.jsonl",
        state_dir=state,
        archive_dir=archive,
        rotation_ledger=audit,
        max_bytes=1,
        keep_bytes=180,
        now=456.0,
    )

    assert set(row.keys()) == LEDGER_SCHEMAS["ledger_rotation.jsonl"]
    assert row["archive_bytes"] == len(original.encode("utf-8"))
    assert Path(str(row["archive_path"])).exists()
    kept = [json.loads(line)["i"] for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert kept
    assert kept[-1] == 19
    assert min(kept) > 0
    written = json.loads(audit.read_text(encoding="utf-8").strip())
    assert written["archive_path"] == row["archive_path"]


def test_default_policies_cover_owner_protection_hot_ledgers():
    required = {
        "sensory_attention_ledger.jsonl",
        "sensor_lane_journal.jsonl",
        "journal_schedule_receipts.jsonl",
        "motor_pulses.jsonl",
        "alice_first_person_journal.jsonl",
        "camera_unified_field_proof.jsonl",
        "architect_screen_gaze_balance.jsonl",
        "active_eye_identity_frames.jsonl",
    }

    assert required <= set(DEFAULT_POLICIES)


def test_giant_policies_include_state_pressure_ledgers():
    assert "fractal_pheromone_field.jsonl" in DEFAULT_POLICIES
    assert "browser_page_state.jsonl" in DEFAULT_POLICIES


def test_rotate_frame_directory_archives_oldest_files(tmp_path: Path):
    from System.swarm_ledger_rotation import rotate_frame_directory

    state = tmp_path / "state"
    archive = tmp_path / "archive"
    audit = state / "ledger_rotation.jsonl"
    frames = state / "iris_frames"
    frames.mkdir(parents=True)
    for i in range(5):
        (frames / f"frame_{i}.jpg").write_bytes(b"x" * 200)
    row = rotate_frame_directory(
        "iris_frames",
        state_dir=state,
        archive_dir=archive,
        rotation_ledger=audit,
        keep_files=2,
        min_bytes=1,
        now=999.0,
    )
    assert row["archived_lines"] == 3
    assert len(list(frames.glob("*.jpg"))) == 2
    assert Path(str(row["archive_path"])).exists()
