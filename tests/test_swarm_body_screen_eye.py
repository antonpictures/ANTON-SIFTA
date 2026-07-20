from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from System import swarm_iris as iris
from System.swarm_body_screen_eye import (
    LEDGER_NAME,
    capture_body_screen_eye,
    record_body_screen_eye,
    summary_for_prompt,
)


def _png(path: Path, size: tuple[int, int] = (320, 180)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color=(22, 88, 144)).save(path)
    return path


def test_ingest_owner_image_writes_body_eye_visual_and_truth_receipts(tmp_path: Path) -> None:
    image = _png(tmp_path / "body_eye.png")

    row = record_body_screen_eye(
        image_path=image,
        owner_claim="USB camera eye points at laptop own body screen",
        state_dir=tmp_path,
    )

    assert row["truth_label"] == "SIFTA_BODY_SCREEN_EYE_V1"
    assert row["observed"] is True
    assert row["image"]["width"] == 320
    assert row["image"]["height"] == 180
    assert row["visual_confirmation_trace_id"]
    assert row["truth_navigation_trace_id"]
    assert (tmp_path / LEDGER_NAME).exists()
    assert (tmp_path / "visual_confirmation_log.jsonl").exists()
    assert (tmp_path / "truth_navigation_receipts.jsonl").exists()


def test_summary_for_prompt_reports_latest_body_screen_eye(tmp_path: Path) -> None:
    image = _png(tmp_path / "body_eye.png")
    record_body_screen_eye(image_path=image, state_dir=tmp_path)

    summary = summary_for_prompt(state_dir=tmp_path)

    assert "BODY-SCREEN EYE" in summary
    assert "observed=True" in summary
    assert "USB camera eye points" in summary


def test_capture_body_screen_eye_uses_iris_frame_without_real_camera(tmp_path: Path) -> None:
    frame_path = _png(tmp_path / "iris_frame.png", size=(200, 120))
    frame = iris.IrisFrame(
        frame_id="frame-test",
        capture_source="webcam",
        ts_captured=1.0,
        file_path=str(frame_path),
        width=200,
        height=120,
        byte_size=frame_path.stat().st_size,
        metadata={"adapter": "test"},
    )

    with patch("System.swarm_iris.SwarmIris.blink_capture", return_value=frame):
        row = capture_body_screen_eye(state_dir=tmp_path)

    assert row["source"] == "iris_webcam"
    assert row["observed"] is True
    assert row["image"]["iris_frame_id"] == "frame-test"
    assert row["image"]["iris_capture_source"] == "webcam"


def test_missing_image_records_non_observed_without_crash(tmp_path: Path) -> None:
    row = record_body_screen_eye(
        image_path=tmp_path / "missing.png",
        state_dir=tmp_path,
    )

    assert row["observed"] is False
    assert row["confidence"] == 0.0


def test_talk_prompt_wires_body_screen_eye_summary() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "Applications"
        / "sifta_talk_to_alice_widget.py"
    ).read_text(encoding="utf-8", errors="replace")

    assert "from System.swarm_body_screen_eye import summary_for_prompt" in source
    assert "_body_screen_eye_summary(state_dir=_state_root())" in source
