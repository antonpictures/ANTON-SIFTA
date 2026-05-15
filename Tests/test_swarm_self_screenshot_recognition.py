from __future__ import annotations

import json
from pathlib import Path

from System.swarm_self_screenshot_recognition import (
    EVIDENCE_KIND,
    LEDGER_NAME,
    TRUTH_LABEL,
    recognize_self_screenshot,
)


def test_recognizes_sifta_screen_with_doctor_panes(tmp_path: Path) -> None:
    evidence = recognize_self_screenshot(
        ocr_rows=[
            {"text": "Dr. Codex IDE", "x": 0.05, "w": 0.10},
            {"text": "SIFTA Python GUI OS - Alice Alive", "x": 0.45, "w": 0.20},
            {"text": "Claude Opus 4.7", "x": 0.78, "w": 0.10},
        ],
        zone_labels={
            "left": ["Codex"],
            "middle": ["Alice/SIFTA"],
            "right": ["Claude/Cowork"],
        },
        image_path="/tmp/sifta-screen.png",
        image_sha256="abc123",
        user_text="can you tell from attachment?",
        state_dir=tmp_path,
    )

    assert evidence.ok is True
    assert evidence.evidence_kind == EVIDENCE_KIND
    assert evidence.truth_label == TRUTH_LABEL
    assert evidence.surface_kind == "sifta_os_with_doctor_panes"
    assert evidence.confidence >= 0.25
    assert "sifta_os" in evidence.self_labels
    assert "codex" in evidence.doctor_labels
    assert "claude" in evidence.doctor_labels
    assert "screenshot of my own SIFTA OS surface" in evidence.reply_hint
    assert "OCR/layout evidence only" in evidence.reply_hint
    assert evidence.sha256


def test_external_media_without_sifta_evidence_is_not_self_surface(tmp_path: Path) -> None:
    evidence = recognize_self_screenshot(
        ocr_rows=[
            {"text": "YouTube - subscribe - 1,204,330 views"},
            {"text": "Transcript Search transcript Chapter 1"},
        ],
        zone_labels={"middle": ["YouTube"]},
        image_path="/tmp/video.png",
        state_dir=tmp_path,
    )

    assert evidence.ok is False
    assert evidence.surface_kind == "unknown_image"
    assert evidence.confidence < 0.25
    assert "do not have enough OCR/layout proof" in evidence.reply_hint


def test_write_receipt_is_append_only_payload(tmp_path: Path) -> None:
    evidence = recognize_self_screenshot(
        ocr_rows=[{"text": "Alice Alive - SIFTA OS", "x": 0.5, "w": 0.1}],
        image_path="/tmp/alice.png",
        image_sha256="f00d",
        state_dir=tmp_path,
        write=True,
        now=123.0,
    )

    ledger = tmp_path / LEDGER_NAME
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    row = rows[0]
    assert row["schema"] == "SIFTA_SELF_SCREENSHOT_EVIDENCE_V1"
    assert row["kind"] == EVIDENCE_KIND
    assert row["truth_label"] == TRUTH_LABEL
    assert row["trace_id"] == evidence.trace_id
    assert row["sha256"] == evidence.sha256
    assert row["payload"]["ok"] is True
    assert row["payload"]["image_sha256"] == "f00d"
