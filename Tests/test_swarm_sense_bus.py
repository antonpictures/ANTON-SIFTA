from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from System.swarm_franken_senses import (
    ble_shark_electric_proximity_from_network,
    camera_predator_motion_from_visual,
    collect_live_readings,
    power_bear_interoception_from_body,
    primate_face_presence_from_ledger,
    sample_and_deposit,
)
from System.swarm_sense_bus import SenseReading, StigmergicSenseBus, proof_of_property


def _write_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")


def test_truth_weights_are_signed_and_bounded(tmp_path):
    bus = StigmergicSenseBus(tmp_path / "sense_bus.jsonl")
    readings = [
        SenseReading("vision", "hawk", "camera", 0.8, 0.5, "REAL", "test"),
        SenseReading("mag", "bird", "magnetometer", 1.0, 1.0, "DEMO", "test"),
        SenseReading("voc", "moth", "VOC", 1.0, 1.0, "UNKNOWN", "test"),
        SenseReading("audio", "bat", "mic", 0.2, 0.5, "BROKEN", "test"),
    ]

    assert readings[0].contribution == pytest.approx(0.4)
    assert readings[1].contribution == pytest.approx(0.25)
    assert readings[2].contribution == pytest.approx(0.0)
    assert readings[3].contribution == pytest.approx(-0.1)
    assert bus.field_value(readings) == pytest.approx(0.55)
    assert all(proof_of_property().values())


def test_deposit_and_snapshot_keep_latest_per_sense(tmp_path):
    bus_path = tmp_path / "sense_bus.jsonl"
    bus = StigmergicSenseBus(bus_path)
    bus.deposit(SenseReading("vision", "hawk", "camera", 0.1, 1.0, "REAL", "old"), writer="test")
    bus.deposit(SenseReading("vision", "hawk", "camera", 0.8, 1.0, "REAL", "new"), writer="test")
    bus.deposit(SenseReading("mag", "bird", "magnetometer", 1.0, 1.0, "DEMO", "demo"), writer="test")

    recent = bus.read_recent(limit=10)
    assert len(recent) == 3
    snapshot = bus.field_snapshot(max_age_s=60)
    assert snapshot["truth_counts"]["REAL"] == 1
    assert snapshot["truth_counts"]["DEMO"] == 1
    assert snapshot["field_value"] == pytest.approx(1.05)
    assert {row["name"] for row in snapshot["readings"]} == {"vision", "mag"}


def test_camera_and_face_adapters_use_real_recent_ledgers(tmp_path):
    ts = time.time()
    _write_jsonl(
        tmp_path / "visual_stigmergy.jsonl",
        {"ts": ts, "motion_mean": 0.42, "saliency_peak": 0.9, "w": 640, "h": 480},
    )
    _write_jsonl(
        tmp_path / "face_detection_events.jsonl",
        {"ts": ts, "faces_detected": 1, "confidence": 0.81, "audience": "owner_candidate"},
    )

    vision = camera_predator_motion_from_visual(state_dir=tmp_path, max_age_s=30)
    face = primate_face_presence_from_ledger(state_dir=tmp_path, max_age_s=30)

    assert vision.truth == "REAL"
    assert vision.value == pytest.approx(0.765)
    assert face.truth == "REAL"
    assert face.value == pytest.approx(0.81)
    assert face.metadata["audience"] == "owner_candidate"


def test_missing_stale_and_broken_sensors_do_not_become_real(tmp_path):
    missing = camera_predator_motion_from_visual(state_dir=tmp_path)
    assert missing.truth == "UNKNOWN"

    _write_jsonl(tmp_path / "face_detection_events.jsonl", {"ts": time.time(), "error": "camera denied"})
    broken = primate_face_presence_from_ledger(state_dir=tmp_path)
    assert broken.truth == "BROKEN"
    assert broken.contribution <= 0.0

    _write_jsonl(tmp_path / "network_topology.jsonl", {"ts": time.time() - 999, "neighbors": 4})
    stale = ble_shark_electric_proximity_from_network(state_dir=tmp_path, max_age_s=30)
    assert stale.truth == "UNKNOWN"


def test_sample_and_deposit_writes_seven_truth_labeled_receipts(tmp_path, monkeypatch):
    ts = time.time()
    _write_jsonl(tmp_path / "visual_stigmergy.jsonl", {"ts": ts, "motion_mean": 0.5, "saliency_peak": 0.2})
    _write_jsonl(tmp_path / "face_detection_events.jsonl", {"ts": ts, "faces_detected": 0, "confidence": 0.9})
    _write_jsonl(tmp_path / "network_topology.jsonl", {"ts": ts, "neighbors": ["m5", "m1", "phone"]})

    def fake_scan():
        class Economy:
            def as_dict(self):
                return {"canonical_wallet_sum": 37.0}

        return Economy()

    import System.swarm_franken_senses as senses

    monkeypatch.setattr("System.stgm_economy.scan_economy", fake_scan, raising=False)
    monkeypatch.setattr(senses.random, "random", lambda: 0.5)

    out = sample_and_deposit(
        bus_path=tmp_path / "sense_bus.jsonl",
        state_dir=tmp_path,
        writer="test_writer",
    )

    rows = (tmp_path / "sense_bus.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(rows) == 7
    assert len(out["readings"]) == 7
    assert out["truth_counts"]["DEMO"] == 1
    assert all(json.loads(row)["writer"] == "test_writer" for row in rows)


def test_malformed_network_score_is_safe_zero_real_when_ledger_is_live(tmp_path):
    _write_jsonl(tmp_path / "network_topology.jsonl", {"ts": time.time(), "score": "not-a-number"})

    reading = ble_shark_electric_proximity_from_network(state_dir=tmp_path)

    assert reading.truth == "REAL"
    assert reading.value == 0.0


def test_collect_live_readings_has_fixed_animal_map(tmp_path, monkeypatch):
    def fake_scan():
        class Economy:
            def as_dict(self):
                return {"canonical_wallet_sum": 1.0}

        return Economy()

    monkeypatch.setattr("System.stgm_economy.scan_economy", fake_scan, raising=False)

    readings = collect_live_readings(state_dir=tmp_path)

    assert [r.name for r in readings] == [
        "predator_vision",
        "face_presence",
        "echolocation_audio",
        "electric_proximity",
        "chemosense",
        "metabolic_interoception",
        "magnetoreception",
    ]
    assert readings[-1].truth == "DEMO"
