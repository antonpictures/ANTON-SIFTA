from __future__ import annotations

import json
from pathlib import Path

import pytest

from System.swarm_calibrated_decision import (
    CALIBRATED_STATUS,
    RAW_STATUS,
    CalibrationArtifact,
    CalibratedDecisionEngine,
    DecisionError,
)


class FakeBackend:
    model_id = "local-test-model"
    model_artifact_digest = "sha256:test-artifact"
    prompt_template = "Message: {message}\nOptions: {labels_block}\nLabel:"

    def __init__(self, logits=None):
        self.logits = logits or {"complaint": 3.0, "question": 1.0, "other": -1.0}
        self.calls = 0

    def score(self, message, labels):
        self.calls += 1
        return {"logits": {label: self.logits[label] for label in labels}, "backend": "fake-local"}


def test_raw_choice_is_typed_and_explicitly_uncalibrated(tmp_path: Path):
    backend = FakeBackend()
    result = CalibratedDecisionEngine(backend, receipt_path=tmp_path / "decisions.jsonl").decide(
        "the parcel arrived broken", ["complaint", "question", "other"]
    )

    assert result.choice == "complaint"
    assert set(result.probabilities) == {"complaint", "question", "other"}
    assert abs(sum(result.probabilities.values()) - 1.0) < 1e-9
    assert result.status == RAW_STATUS
    assert result.calibration_artifact_id is None
    assert result.abstained is False
    row = json.loads((tmp_path / "decisions.jsonl").read_text().splitlines()[0])
    assert row["truth_label"] == "OBSERVED_LOCAL_DECISION"
    assert row["message_sha256"].startswith("sha256:")


def test_low_margin_abstains_without_dropping_the_distribution(tmp_path: Path):
    backend = FakeBackend({"a": 1.0, "b": 0.99, "c": -2.0})
    result = CalibratedDecisionEngine(backend, min_margin=0.1, receipt_path=tmp_path / "r.jsonl").decide(
        "ambiguous", ["a", "b", "c"]
    )

    assert result.choice is None
    assert result.abstained is True
    assert result.reason_code == "SMALL_MARGIN"
    assert len(result.probabilities) == 3


def test_measured_calibration_artifact_changes_status_but_is_named(tmp_path: Path):
    artifact = CalibrationArtifact("j2-fit-20260922", temperature=2.0, fitted_on="holdout-fit-v1")
    result = CalibratedDecisionEngine(
        FakeBackend(), calibration=artifact, receipt_path=tmp_path / "r.jsonl"
    ).decide("hello", ["complaint", "question", "other"])

    assert result.status == CALIBRATED_STATUS
    assert result.calibration_artifact_id == "j2-fit-20260922"
    assert result.confidence < 0.9  # temperature softened the raw distribution


def test_cache_key_includes_message_model_template_and_label_order(tmp_path: Path):
    backend = FakeBackend()
    engine = CalibratedDecisionEngine(backend, receipt_path=tmp_path / "r.jsonl")
    first = engine.decide("same", ["complaint", "question", "other"])
    cached = engine.decide("same", ["complaint", "question", "other"])
    reordered = engine.decide("same", ["question", "complaint", "other"])
    changed = engine.decide("different", ["complaint", "question", "other"])

    assert first.cache_hit is False
    assert cached.cache_hit is True
    assert reordered.cache_hit is False
    assert changed.cache_hit is False
    assert backend.calls == 3
    assert first.label_order_sha256 != reordered.label_order_sha256
    assert len((tmp_path / "r.jsonl").read_text().splitlines()) == 4


def test_backend_must_return_every_finite_declared_option(tmp_path: Path):
    class Bad(FakeBackend):
        def score(self, message, labels):
            return {"logits": {labels[0]: float("nan")}}

    with pytest.raises(DecisionError, match="INVALID_LOGITS"):
        CalibratedDecisionEngine(Bad(), receipt_path=tmp_path / "r.jsonl").decide("x", ["a", "b"])


def test_invalid_labels_and_calibration_are_refused():
    with pytest.raises(DecisionError, match="INVALID_LABELS"):
        CalibratedDecisionEngine(FakeBackend(), receipt_path=None).decide("x", ["a", "a"])
    with pytest.raises(ValueError, match="positive"):
        CalibrationArtifact("bad", temperature=0)


def test_backend_errors_are_not_cloud_fallbacks(tmp_path: Path):
    class Offline(FakeBackend):
        def score(self, message, labels):
            raise DecisionError("BACKEND_UNAVAILABLE", "local process is down")

    with pytest.raises(DecisionError) as exc:
        CalibratedDecisionEngine(Offline(), receipt_path=tmp_path / "r.jsonl").decide("x", ["a", "b"])
    assert exc.value.code == "BACKEND_UNAVAILABLE"
    row = json.loads((tmp_path / "r.jsonl").read_text().splitlines()[0])
    assert row["status"] == "decision_error"
    assert row["reason_code"] == "BACKEND_UNAVAILABLE"
