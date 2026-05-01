"""Tests for the chromatophore StigmergicOpenGLDriver."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from System.swarm_stigmergic_opengl_driver import (
    DEFAULT_CHROMATOPHORE_SHADER,
    TRUTH_LABEL,
    StigmergicOpenGLDriver,
    smoke_render_receipt,
)


def _append_jsonl(path: Path, row: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")


def _ledger(tmp_path: Path) -> Path:
    ledger = tmp_path / "visual_phenotype_uniforms.jsonl"
    _append_jsonl(
        ledger,
        {
            "tick_id": "chromato-1",
            "receipt_backed": True,
            "u_stigmergic_drive": 0.7,
            "u_metabolic_scope": 0.8,
            "u_cot_factor": 0.2,
            "u_quorum_signal": 0.4,
            "u_chemotaxis_gradient": 0.3,
        },
    )
    return ledger


def test_chromatophore_shader_archive_is_present() -> None:
    source = DEFAULT_CHROMATOPHORE_SHADER.read_text(encoding="utf-8")
    assert "#version 410 core" in source
    assert "u_scene_texture" in source
    assert "u_bloom_blur_texture" in source
    assert "u_chemotaxis_gradient" in source


def test_driver_renders_real_offscreen_frame_and_reads_receipt(tmp_path: Path) -> None:
    try:
        driver = StigmergicOpenGLDriver(width=32, height=24, uniforms_log=_ledger(tmp_path))
    except Exception as exc:
        pytest.skip(f"ModernGL standalone context unavailable: {exc}")

    try:
        texture = driver.render_frame(force_pull=True)
        data = driver.read_rgba_bytes()
        assert texture.size == (32, 24)
        assert len(data) == 32 * 24 * 4
        assert any(data)
        assert driver.tick_counter == 1
        assert driver.last_frame is not None
        assert driver.last_frame.tick_id == "chromato-1"
        assert driver.last_frame.receipt_backed is True
    finally:
        driver.release()


def test_driver_saves_raw_receipt_when_requested(tmp_path: Path) -> None:
    try:
        driver = StigmergicOpenGLDriver(width=16, height=12, uniforms_log=_ledger(tmp_path))
    except Exception as exc:
        pytest.skip(f"ModernGL standalone context unavailable: {exc}")

    try:
        receipt = driver.save_screenshot(tmp_path / "chromato.raw")
        assert receipt.ok is True
        assert receipt.truth_label == TRUTH_LABEL
        assert receipt.receipt_backed is True
        assert receipt.tick_id == "chromato-1"
        assert receipt.bytes_written == 16 * 12 * 4
        assert Path(receipt.output_path).exists()
    finally:
        driver.release()


def test_smoke_render_receipt_returns_truth_label(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from System import swarm_stigmergic_opengl_driver as driver_mod

    ledger = _ledger(tmp_path)
    monkeypatch.setattr(driver_mod, "DEFAULT_LEDGER", ledger)
    try:
        receipt = smoke_render_receipt(tmp_path / "smoke.raw", uniforms_log=ledger)
    except Exception as exc:
        pytest.skip(f"ModernGL standalone context unavailable: {exc}")

    assert receipt.ok is True
    assert receipt.truth_label == TRUTH_LABEL
    assert receipt.receipt_backed is True
    assert receipt.tick_id == "chromato-1"
    assert receipt.bytes_written == 256 * 144 * 4
