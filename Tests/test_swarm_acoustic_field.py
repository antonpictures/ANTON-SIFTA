from __future__ import annotations

import json
import time

from System.swarm_acoustic_field import (
    SwarmAcousticField,
    _classify_ambient,
    _compute_rms,
    _compute_zcr,
)
from System import swarm_field_self_regulator as regulator
from System.stigmergic_field import field_dashboard


def test_acoustic_classifiers_are_stable() -> None:
    assert _classify_ambient(0.001) == "silence"
    assert _classify_ambient(0.03, 0.2) == "speech"
    assert _classify_ambient(0.08, 0.1) == "music"
    assert _classify_ambient(0.3, 0.5) == "noise"
    assert abs(_compute_rms([1.0, -1.0, 1.0, -1.0]) - 1.0) < 0.001
    assert _compute_zcr([1, -1, 1, -1]) == 1.0


def test_acoustic_salience_decays_and_feeds_dashboard(tmp_path) -> None:
    salience_path = tmp_path / "audio_salience_field.json"
    field = SwarmAcousticField(
        fields_dir=tmp_path / "acoustic_fields",
        pheromones_ledger=tmp_path / "acoustic_pheromones.jsonl",
        salience_path=salience_path,
    )

    source = "mic_test"
    silence = [0.0] * 128
    noise = [1.0] * 128
    field.ingest_audio(source, silence)
    time.sleep(0.002)
    energy = field.ingest_audio(source, noise)
    before = field.get_salience_field().get("noise", 0.0)

    assert energy > 0.0
    assert before > 0.0

    for _ in range(5):
        time.sleep(0.001)
        field.ingest_audio(source, silence)

    after = field.get_salience_field().get("noise", 0.0)
    assert after < before

    dashboard = field_dashboard(tmp_path)
    assert "audio_salience" in dashboard["fields"]
    assert dashboard["fields"]["audio_salience"]["ambient_categories"] >= 1


def test_meta_regulator_reads_audio_salience(tmp_path, monkeypatch) -> None:
    (tmp_path / "audio_salience_field.json").write_text(json.dumps({"speech": 1.5}))
    monkeypatch.setattr(regulator, "_STATE_DIR", tmp_path)
    monkeypatch.setattr(regulator, "_REGULATION_LOG", tmp_path / "field_regulation_log.jsonl")
    monkeypatch.setattr(regulator, "_REGULATION_STATE", tmp_path / "field_regulation_state.json")
    monkeypatch.setattr(regulator, "_FIELD_TRENDS", tmp_path / "field_trends.jsonl")

    reports = regulator.read_all_fields()

    assert "audio_salience" in reports
    assert reports["audio_salience"].top_keys[0][0] == "speech"

