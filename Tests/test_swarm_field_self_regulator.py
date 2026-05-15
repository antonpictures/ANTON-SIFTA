from __future__ import annotations

from pathlib import Path

import pytest

from System import swarm_field_self_regulator as regulator
from System.stigmergic_field import FieldConfig, StigmergicField


@pytest.fixture()
def isolated_regulator(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(regulator, "_STATE_DIR", tmp_path)
    monkeypatch.setattr(regulator, "_REGULATION_LOG", tmp_path / "field_regulation_log.jsonl")
    monkeypatch.setattr(regulator, "_REGULATION_STATE", tmp_path / "field_regulation_state.json")
    monkeypatch.setattr(regulator, "_FIELD_TRENDS", tmp_path / "field_trends.jsonl")
    return tmp_path


def test_reads_current_cortex_route_field_name(isolated_regulator: Path) -> None:
    field = StigmergicField(FieldConfig(n_bins=16, fast_decay=0.9, slow_decay=0.99))
    field.deposit(3, 0, amount=2.0)
    field.save(isolated_regulator / "cortex_route_field.json")

    reports = regulator.read_all_fields()

    assert "cortex_router" in reports
    assert reports["cortex_router"].deposits == 1
    assert reports["cortex_router"].energy > 0


def test_reads_current_hippocampus_memory_field_path(isolated_regulator: Path) -> None:
    memory_dir = isolated_regulator / "hippocampus"
    memory_dir.mkdir()
    (memory_dir / "memory_salience_field.json").write_text('{"owner_voice": 2.0, "ambient": 0.25}')

    reports = regulator.read_all_fields()

    assert "memory_salience" in reports
    assert reports["memory_salience"].deposits == 2
    assert reports["memory_salience"].top_keys[0][0] == "owner_voice"


def test_reads_audio_salience_field(isolated_regulator: Path) -> None:
    (isolated_regulator / "audio_salience_field.json").write_text('{"noise": 2.0, "silence": 0.1}')

    reports = regulator.read_all_fields()

    assert "audio_salience" in reports
    assert reports["audio_salience"].top_keys[0][0] == "noise"


def test_dominance_regulation_has_hysteresis(isolated_regulator: Path) -> None:
    report = regulator.FieldHealthReport(
        name="test_field",
        energy=101.0,
        deposits=2,
        top_keys=[("dominant", 10.0), ("runner", 1.0)],
        dominance_ratio=10.0,
        health="DOMINANT",
    )

    first = regulator.regulate_field("test_field", report, dry_run=False)
    second = regulator.regulate_field("test_field", report, dry_run=False)

    assert len(first) == 1
    assert second == []
