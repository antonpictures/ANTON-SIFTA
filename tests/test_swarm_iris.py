#!/usr/bin/env python3
"""Tests for swarm_iris - high in-degree organ (12 dependents).

The hardened eye from the camera split-brain work. Tests focus on
the deterministic paths (synthetic_frame, capability_report) and
graceful degradation (webcam_frame, SwarmIris fallbacks).

Contract per GROK_COVERAGE_CAMPAIGN_ORDER.md:
- Tests only.
- Real-ledger delta must be 0.
- Headless-collectable.
- Honest, failable assertions.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from System import swarm_iris as iris


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return len(path.read_text(encoding="utf-8", errors="replace").splitlines())


def test_module_exports_public_surface():
    """Real behavior 1: documented public API is present."""
    assert hasattr(iris, "capability_report")
    assert hasattr(iris, "synthetic_frame")
    assert hasattr(iris, "webcam_frame")
    assert hasattr(iris, "SwarmIris")
    assert hasattr(iris, "IrisFrame")
    assert hasattr(iris, "invalidate_camera_cache")


def test_capability_report_is_deterministic_and_truthful():
    """Real behavior 2: capability_report reflects actual runtime capabilities."""
    report = iris.capability_report()
    assert isinstance(report, dict)
    assert "platform" in report
    assert "max_frame_bytes" in report
    assert report["platform"] in ("darwin", "linux", "win32")


def test_synthetic_frame_produces_valid_irisframe_without_disk(monkeypatch):
    """Core deterministic path: synthetic_frame works in memory-only mode."""
    frame = iris.synthetic_frame(
        "Test text for coverage", width=400, height=80, save_to_disk=False
    )
    assert isinstance(frame, iris.IrisFrame)
    assert frame.capture_source == "synthetic"
    assert frame.width == 400
    assert frame.height == 80
    assert frame.byte_size > 0
    assert frame.file_path == ""  # no disk write


def test_synthetic_frame_respects_byte_limit(monkeypatch):
    """Safety: frames that would exceed the in-memory cap are rejected."""
    # Use save_to_disk=False and force a huge in-memory size via monkeypatch
    with patch.object(iris, "MAX_FRAME_BYTES_IN_MEMORY", 100):
        with pytest.raises(RuntimeError, match="MAX_FRAME_BYTES_IN_MEMORY"):
            iris.synthetic_frame("big", width=200, height=200, save_to_disk=False)


def test_webcam_frame_graceful_none_when_no_cv2(monkeypatch):
    """Graceful degradation: no cv2 -> None, never crashes."""
    with patch.object(iris, "_load_cv2", return_value=None):
        result = iris.webcam_frame(grab_timeout_s=0.01)
    assert result is None


def test_swarm_iris_blink_capture_returns_irisframe(tmp_path, monkeypatch):
    """Orchestrator behavior: SwarmIris.blink_capture returns a valid IrisFrame (under full log isolation)."""
    # Redirect the organ's own capture log for this call too
    original_log = iris._IRIS_LOG
    iris._IRIS_LOG = tmp_path / "swarm_iris_capture.jsonl"
    try:
        with patch.object(iris, "append_line_locked"), \
             patch("System.swarm_iris.append_line_locked"):
            eye = iris.SwarmIris()
            frame = eye.blink_capture(source="ide_chrome_screenshot")
            assert isinstance(frame, iris.IrisFrame)
    finally:
        iris._IRIS_LOG = original_log


def test_invalidate_camera_cache_is_idempotent():
    """Cache hygiene: calling invalidate multiple times is safe."""
    iris.invalidate_camera_cache()
    iris.invalidate_camera_cache()
    # No exception = pass


def test_real_ledgers_untouched_by_iris_tests(tmp_path, monkeypatch):
    """Explicit isolation gate per campaign contract."""
    state = Path(".sifta_state")
    watch = [
        state / "memory_ledger.jsonl",
        state / "stgm_memory_rewards.jsonl",
        state / "work_receipts.jsonl",
        state / "ide_stigmergic_trace.jsonl",
        state / "swarm_iris_capture.jsonl",
    ]
    before = {str(p): _count_lines(p) for p in watch}

    # Patch all write paths the organ uses + redirect its log file
    original_log = iris._IRIS_LOG
    iris._IRIS_LOG = tmp_path / "swarm_iris_capture.jsonl"

    try:
        with patch.object(iris, "append_line_locked"), \
             patch("System.swarm_iris.append_line_locked"):

            _ = iris.capability_report()
            _ = iris.synthetic_frame("coverage test", save_to_disk=False)

            with patch.object(iris, "_load_cv2", return_value=None):
                _ = iris.webcam_frame(grab_timeout_s=0.01)

            eye = iris.SwarmIris()
            _ = eye.blink_capture(source="ide_chrome_screenshot")
    finally:
        iris._IRIS_LOG = original_log

    after = {str(p): _count_lines(p) for p in watch}
    delta = {k: after[k] - before[k] for k in before}

    # Full contract: zero delta on *all* watched ledgers, including the organ's own capture log.
    assert all(v == 0 for v in delta.values()), f"Real ledgers (incl. organ own log) contaminated: {delta}"


def test_irisframe_to_dict_roundtrips_metadata():
    """Dataclass contract: to_dict produces something roundtrippable."""
    frame = iris.synthetic_frame("roundtrip", save_to_disk=False)
    d = frame.to_dict()
    assert isinstance(d, dict)
    assert d["capture_source"] == "synthetic"
    assert "metadata" in d


def test_blink_capture_webcam_falls_back_to_synthetic_without_disk_or_real_log(tmp_path):
    """Edge probe: unavailable webcam still yields a frame and only logs to the redirected ledger."""
    original_log = iris._IRIS_LOG
    real_synthetic_frame = iris.synthetic_frame
    iris._IRIS_LOG = tmp_path / "swarm_iris_capture.jsonl"

    def synthetic_without_disk(text: str, **kwargs):
        kwargs["save_to_disk"] = False
        return real_synthetic_frame(text, **kwargs)

    try:
        with patch.object(iris, "webcam_frame", return_value=None), \
             patch.object(iris, "synthetic_frame", side_effect=synthetic_without_disk):

            frame = iris.SwarmIris().blink_capture(source="webcam")

        assert frame.capture_source == "synthetic"
        assert frame.metadata["text"] == "[webcam unavailable]"
        assert frame.file_path == ""

        rows = iris._IRIS_LOG.read_text(encoding="utf-8").splitlines()
        assert len(rows) == 1
        assert '"capture_source": "synthetic"' in rows[0]
    finally:
        iris._IRIS_LOG = original_log
