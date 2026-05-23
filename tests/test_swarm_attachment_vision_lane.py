import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_attachment_vision_lane import (  # noqa: E402
    LEDGER_NAME,
    TRUTH_LABEL,
    describe_attachment_for_talk,
    inspect_attachment_image,
)
from System.swarm_organ_tokenizer import ATTACHMENT_VISUAL_TOKEN_LEDGER_NAME  # noqa: E402


PNG_2X1 = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x02\x00\x00\x00\x01\x08\x02\x00\x00\x00"
    b"\xfd\xd4\x9as"
)


def test_inspect_attachment_image_extracts_metadata_and_zone_labels(tmp_path):
    image = tmp_path / "screen.png"
    image.write_bytes(PNG_2X1)
    ocr_rows = [
        {"text": "Dr. Codex IDE", "x": 0.05, "w": 0.10, "confidence": 0.92},
        {"text": "SIFTA Alice chat", "x": 0.45, "w": 0.10, "confidence": 0.91},
        {"text": "Dr. Claude IDE", "x": 0.78, "w": 0.10, "confidence": 0.90},
    ]

    summary = inspect_attachment_image(
        image,
        user_text="can you tell from attachment?",
        state_dir=tmp_path,
        ocr_rows=ocr_rows,
        run_ocr=False,
    )

    assert summary.ok is True
    assert summary.truth_label == TRUTH_LABEL
    assert summary.image_format == "png"
    assert summary.width == 2
    assert summary.height == 1
    assert summary.zone_labels == {
        "left": ["Codex"],
        "middle": ["Alice/SIFTA"],
        "right": ["Claude/Cowork"],
    }
    assert summary.self_screenshot["ok"] is True
    assert summary.self_screenshot["surface_kind"] == "sifta_os_with_doctor_panes"
    assert "left: Codex" in summary.reply
    assert "middle: Alice/SIFTA" in summary.reply
    assert "right: Claude/Cowork" in summary.reply
    assert "screenshot of my own SIFTA OS surface" in summary.reply
    assert "not a full visual caption model" in summary.reply


def test_inspect_without_ocr_is_honest_limited(tmp_path):
    image = tmp_path / "screen.png"
    image.write_bytes(PNG_2X1)

    summary = inspect_attachment_image(
        image,
        state_dir=tmp_path,
        run_ocr=False,
    )

    assert summary.ok is True
    assert summary.zone_labels == {}
    assert "did not get OCR/layout text" in summary.reply


def test_bad_image_refuses_without_fabricating(tmp_path):
    fake = tmp_path / "fake.png"
    fake.write_text("not pixels", encoding="utf-8")

    reply = describe_attachment_for_talk(
        "can you describe this?",
        fake,
        state_dir=tmp_path,
    )

    assert "could not inspect" in reply
    assert "will not fabricate pixels" in reply


def test_write_receipt_round_trips(tmp_path):
    image = tmp_path / "screen.png"
    image.write_bytes(PNG_2X1)

    summary = inspect_attachment_image(
        image,
        state_dir=tmp_path,
        ocr_rows=[{"text": "Codex", "x": 0.1, "w": 0.1}],
        run_ocr=False,
        write=True,
        now=123.0,
    )

    ledger = tmp_path / LEDGER_NAME
    assert ledger.exists()
    row = json.loads(ledger.read_text(encoding="utf-8").strip())
    assert row["schema"] == "SIFTA_ATTACHMENT_VISION_LANE_RECEIPT_V1"
    assert row["trace_id"] == summary.trace_id
    assert row["zone_labels"] == {"left": ["Codex"]}
    assert row["self_screenshot"]["ok"] is False

    token_ledger = tmp_path / ATTACHMENT_VISUAL_TOKEN_LEDGER_NAME
    assert token_ledger.exists()
    token_row = json.loads(token_ledger.read_text(encoding="utf-8").strip())
    assert token_row["schema"] == "SIFTA_ATTACHMENT_VISUAL_TOKENS_RECEIPT_V1"
    assert token_row["payload"]["source_trace_id"] == summary.trace_id
    assert token_row["payload"]["token_count"] > 0
    assert token_row["payload"]["visual_mass"] > 0.0
