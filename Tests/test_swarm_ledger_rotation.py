from __future__ import annotations

import gzip
import json
from pathlib import Path

from System.canonical_schemas import LEDGER_SCHEMAS
from System.swarm_ledger_rotation import RotationPolicy, rotate_ledger


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
