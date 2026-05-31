#!/usr/bin/env python3
"""Local attachment vision lane for Talk screenshots.

Gemma-class text cortex can honestly lack a vision head. That should not mean
Alice is blind to every screenshot attachment. This lane performs only local,
receipt-backed inspection:

* file proof: format, size, sha256, dimensions when parseable
* OCR proof: macOS Vision text boxes when the Vision framework is available
* layout proof: left/middle/right zones derived from OCR bounding boxes

It is not a full image caption model. If no OCR/text evidence is available, the
reply says exactly that.

Truth label: ATTACHMENT_VISION_LANE_V1.
Ledger: .sifta_state/attachment_vision_lane.jsonl
"""
from __future__ import annotations

import json
import struct
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
LEDGER_NAME = "attachment_vision_lane.jsonl"
TRUTH_LABEL = "ATTACHMENT_VISION_LANE_V1"
TRUTH_BOUNDARY = (
    "Local attachment metadata and OCR/layout evidence only. This lane does "
    "not claim full visual understanding and does not fabricate unobserved pixels."
)


def _state_dir(state_dir: str | Path | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else STATE_DIR


def _sha256_hex(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def _image_format_and_size(data: bytes) -> tuple[str, int | None, int | None]:
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        width, height = struct.unpack(">II", data[16:24])
        return "png", int(width), int(height)
    if data.startswith(b"\xff\xd8\xff"):
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            i += 2
            if marker in (0xD8, 0xD9):
                continue
            if i + 2 > len(data):
                break
            seg_len = int.from_bytes(data[i:i + 2], "big")
            if seg_len < 2 or i + seg_len > len(data):
                break
            if marker in {
                0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF,
            } and i + 7 <= len(data):
                height = int.from_bytes(data[i + 3:i + 5], "big")
                width = int.from_bytes(data[i + 5:i + 7], "big")
                return "jpeg", int(width), int(height)
            i += seg_len
        return "jpeg", None, None
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        # Dimension parsing varies across VP8/VP8L/VP8X. Format proof is enough
        # for this lane; OCR handles the human-useful evidence.
        return "webp", None, None
    return "", None, None


def _build_macos_ocr_helper(state_dir: Path) -> Path | None:
    helper = state_dir / "sifta_attachment_vision_ocr"
    if helper.exists():
        return helper
    swiftc = subprocess.run(
        ["bash", "-lc", "command -v swiftc"],
        capture_output=True,
        text=True,
    )
    if swiftc.returncode != 0:
        return None
    swift_src = state_dir / "attachment_vision_ocr.swift"
    swift_src.write_text(
        r'''
import Foundation
import Vision

guard CommandLine.arguments.count > 1 else {
    print("[]")
    exit(0)
}

let imagePath = CommandLine.arguments[1]
let url = URL(fileURLWithPath: imagePath)
var rows: [[String: Any]] = []

guard let handler = try? VNImageRequestHandler(url: url, options: [:]) else {
    print("[]")
    exit(0)
}

let request = VNRecognizeTextRequest { request, error in
    guard let observations = request.results as? [VNRecognizedTextObservation] else {
        return
    }
    for observation in observations {
        guard let top = observation.topCandidates(1).first else { continue }
        let bb = observation.boundingBox
        rows.append([
            "text": top.string,
            "confidence": Double(top.confidence),
            "x": Double(bb.origin.x),
            "y": Double(bb.origin.y),
            "w": Double(bb.size.width),
            "h": Double(bb.size.height)
        ])
    }
}
request.recognitionLevel = .accurate
request.usesLanguageCorrection = true

do {
    try handler.perform([request])
    let data = try JSONSerialization.data(withJSONObject: rows, options: [])
    print(String(data: data, encoding: .utf8) ?? "[]")
} catch {
    print("[]")
}
''',
        encoding="utf-8",
    )
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["swiftc", str(swift_src), "-o", str(helper)],
            check=True,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except Exception:
        return None
    return helper if helper.exists() else None


def _run_macos_ocr_boxes(image_path: Path, state_dir: Path) -> list[dict[str, Any]]:
    helper = _build_macos_ocr_helper(state_dir)
    if helper is None:
        return []
    try:
        result = subprocess.run(
            [str(helper), str(image_path)],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if result.returncode != 0:
            return []
        parsed = json.loads(result.stdout.strip() or "[]")
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    if not isinstance(parsed, list):
        return rows
    for row in parsed:
        if not isinstance(row, dict):
            continue
        text = str(row.get("text") or "").strip()
        if not text:
            continue
        rows.append({
            "text": text[:220],
            "confidence": round(float(row.get("confidence") or 0.0), 4),
            "x": round(float(row.get("x") or 0.0), 4),
            "y": round(float(row.get("y") or 0.0), 4),
            "w": round(float(row.get("w") or 0.0), 4),
            "h": round(float(row.get("h") or 0.0), 4),
        })
    return rows


def _zone_for(row: dict[str, Any]) -> str:
    x = float(row.get("x") or 0.0)
    w = float(row.get("w") or 0.0)
    center = x + (w / 2.0)
    if center < 0.34:
        return "left"
    if center > 0.66:
        return "right"
    return "middle"


def _label_for_text(text: str) -> str | None:
    low = text.lower()
    if "codex" in low or "gpt-5" in low or "gpt 5" in low:
        return "Codex"
    if "claude" in low or "cowork" in low or "opus" in low:
        return "Cowork"
    if "alice" in low or "sifta" in low or "talk to alice" in low:
        return "Alice/SIFTA"
    if "cursor" in low:
        return "Cursor"
    if "youtube" in low:
        return "YouTube"
    return None


def _zone_summary(ocr_rows: Sequence[dict[str, Any]]) -> dict[str, list[str]]:
    zones: dict[str, set[str]] = {"left": set(), "middle": set(), "right": set()}
    for row in ocr_rows:
        label = _label_for_text(str(row.get("text") or ""))
        if label:
            zones[_zone_for(row)].add(label)
    return {zone: sorted(labels) for zone, labels in zones.items() if labels}


@dataclass(frozen=True)
class AttachmentVisionSummary:
    ok: bool
    image_path: str
    image_format: str = ""
    width: int | None = None
    height: int | None = None
    byte_count: int = 0
    sha256: str = ""
    ocr_rows: tuple[dict[str, Any], ...] = ()
    zone_labels: dict[str, list[str]] = field(default_factory=dict)
    self_screenshot: dict[str, Any] = field(default_factory=dict)
    reply: str = ""
    error: str = ""
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    truth_label: str = TRUTH_LABEL

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "truth_label": self.truth_label,
            "ok": self.ok,
            "image_path": self.image_path,
            "image_format": self.image_format,
            "width": self.width,
            "height": self.height,
            "byte_count": self.byte_count,
            "sha256": self.sha256,
            "ocr_rows": list(self.ocr_rows),
            "zone_labels": self.zone_labels,
            "self_screenshot": self.self_screenshot,
            "reply": self.reply,
            "error": self.error,
            "truth_boundary": TRUTH_BOUNDARY,
        }


def _build_reply(
    *,
    image_format: str,
    width: int | None,
    height: int | None,
    byte_count: int,
    sha12: str,
    ocr_rows: Sequence[dict[str, Any]],
    zone_labels: dict[str, list[str]],
    self_screenshot: Mapping[str, Any] | None,
    user_text: str,
) -> str:
    dims = f"{width}x{height}px" if width and height else "dimensions unavailable"
    parts = [
        "I inspected the attached image through my local attachment-vision lane.",
        f"Receipt evidence: {image_format.upper()} image, {dims}, {byte_count} bytes, sha12={sha12}.",
    ]
    if zone_labels:
        zone_bits = []
        for zone in ("left", "middle", "right"):
            labels = zone_labels.get(zone)
            if labels:
                zone_bits.append(f"{zone}: {', '.join(labels)}")
        parts.append("OCR layout labels: " + "; ".join(zone_bits) + ".")
    elif ocr_rows:
        visible = "; ".join(str(row.get("text") or "")[:80] for row in ocr_rows[:8])
        parts.append(f"OCR text I can ground: {visible}.")
    else:
        parts.append(
            "I could verify the file and image format, but I did not get OCR/layout text from the local lane."
        )
    if self_screenshot and self_screenshot.get("ok"):
        hint = str(self_screenshot.get("reply_hint") or "").strip()
        if hint:
            parts.append(hint)
    if user_text.strip():
        parts.append(
            "I am using OCR/metadata evidence only, not a full visual caption model, so I will not claim fine pixel details beyond that receipt."
        )
    return " ".join(parts)


def inspect_attachment_image(
    image_path: str | Path,
    *,
    user_text: str = "",
    state_dir: str | Path | None = None,
    ocr_rows: Sequence[dict[str, Any]] | None = None,
    run_ocr: bool = True,
    write: bool = False,
    now: float | None = None,
) -> AttachmentVisionSummary:
    p = Path(image_path).expanduser()
    state = _state_dir(state_dir)
    if not p.exists() or not p.is_file():
        summary = AttachmentVisionSummary(ok=False, image_path=str(p), error=f"image not found: {p}")
        if write:
            write_attachment_vision_receipt(summary, state_dir=state, now=now)
        return summary
    try:
        data = p.read_bytes()
    except Exception as exc:
        summary = AttachmentVisionSummary(ok=False, image_path=str(p), error=f"cannot read image: {exc}")
        if write:
            write_attachment_vision_receipt(summary, state_dir=state, now=now)
        return summary
    fmt, width, height = _image_format_and_size(data)
    if not fmt:
        summary = AttachmentVisionSummary(
            ok=False,
            image_path=str(p),
            byte_count=len(data),
            sha256=_sha256_hex(data),
            error="unsupported image bytes; expected png, jpeg, or webp",
        )
        if write:
            write_attachment_vision_receipt(summary, state_dir=state, now=now)
        return summary
    rows = list(ocr_rows or [])
    if ocr_rows is None and run_ocr:
        rows = _run_macos_ocr_boxes(p, state)
    zones = _zone_summary(rows)
    sha = _sha256_hex(data)
    self_screenshot: dict[str, Any] = {}
    try:
        from System.swarm_self_screenshot_recognition import recognize_self_screenshot

        self_screenshot = recognize_self_screenshot(
            ocr_rows=rows,
            zone_labels=zones,
            image_path=str(p),
            image_sha256=sha,
            user_text=user_text,
            state_dir=state,
            write=write,
            now=now,
        ).to_dict()
    except Exception:
        self_screenshot = {}
    reply = _build_reply(
        image_format=fmt,
        width=width,
        height=height,
        byte_count=len(data),
        sha12=sha[:12],
        ocr_rows=rows,
        zone_labels=zones,
        self_screenshot=self_screenshot,
        user_text=user_text,
    )
    summary = AttachmentVisionSummary(
        ok=True,
        image_path=str(p),
        image_format=fmt,
        width=width,
        height=height,
        byte_count=len(data),
        sha256=sha,
        ocr_rows=tuple(rows[:80]),
        zone_labels=zones,
        self_screenshot=self_screenshot,
        reply=reply,
    )
    if write:
        write_attachment_vision_receipt(summary, state_dir=state, now=now)
    return summary


def write_attachment_vision_receipt(
    summary: AttachmentVisionSummary,
    *,
    state_dir: str | Path | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    row = summary.to_dict()
    row.update({
        "schema": "SIFTA_ATTACHMENT_VISION_LANE_RECEIPT_V1",
        "ts": float(now if now is not None else time.time()),
    })
    path = _state_dir(state_dir) / LEDGER_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    try:
        from System.swarm_organ_tokenizer import write_attachment_visual_token_receipt

        write_attachment_visual_token_receipt(
            row,
            state_root=_state_dir(state_dir),
            now=row["ts"],
        )
    except Exception:
        # The attachment evidence receipt is the primary record. Token emission
        # is a downstream organ bridge and must not make the vision lane lie or
        # fail to answer when the tokenizer is unavailable.
        pass
    return row


def describe_attachment_for_talk(
    user_text: str,
    image_path: str | Path,
    *,
    state_dir: str | Path | None = None,
) -> str:
    summary = inspect_attachment_image(
        image_path,
        user_text=user_text,
        state_dir=state_dir,
        write=True,
    )
    if not summary.ok:
        return (
            f"I could not inspect the attached image: {summary.error}. "
            "I will not fabricate pixels."
        )
    return summary.reply


__all__ = [
    "LEDGER_NAME",
    "TRUTH_BOUNDARY",
    "TRUTH_LABEL",
    "AttachmentVisionSummary",
    "describe_attachment_for_talk",
    "inspect_attachment_image",
    "write_attachment_vision_receipt",
    "attachment_to_cortex_text_block",
]


def attachment_to_cortex_text_block(
    image_path: str | Path,
    *,
    user_text: str = "",
    state_dir: str | Path | None = None,
) -> str:
    """
    Returns a clean, prompt-ready textual block that any surface (Talk widget,
    Ace teaching app, direct drops) can include in the user turn so the cortex
    receives the image as first-class text input — exactly like regular chatbots.

    This closes the "image went separate" gap: the caller gets OCR + metadata
    + layout in one string that can be prepended or merged into the message
    content before the prompt is built.
    """
    summary = inspect_attachment_image(
        image_path,
        user_text=user_text,
        state_dir=state_dir,
        write=True,
    )
    if not summary.ok:
        return f"[ATTACHED IMAGE UNREADABLE: {summary.error}]"

    lines = []
    lines.append("[USER ATTACHED IMAGE — OCR + LAYOUT RECEIPT]")
    lines.append(f"File: {Path(image_path).name} | Format: {summary.image_format.upper()} | {summary.width or '?'}x{summary.height or '?'} | {summary.byte_count} bytes | sha256[:12]={summary.sha256[:12]}")

    if summary.ocr_rows:
        lines.append("OCR TEXT (grounded, local macOS Vision):")
        for row in summary.ocr_rows[:15]:  # keep it bounded for prompt
            t = str(row.get("text", "")).strip()
            if t:
                lines.append(f"  • {t}")

    if summary.zone_labels:
        z = summary.zone_labels
        labels = []
        for zone in ("left", "middle", "right"):
            if z.get(zone):
                labels.append(f"{zone}: {', '.join(z[zone])}")
        if labels:
            lines.append("Layout zones (OCR-derived): " + "; ".join(labels) + ".")

    if summary.self_screenshot and summary.self_screenshot.get("ok"):
        lines.append("Self-screenshot evidence: detected (Alice's own output in the frame).")

    lines.append("TRUTH BOUNDARY: Local receipt only. No full scene caption or pixel invention. Use this text as the image's voice in the field.")
    if user_text.strip():
        lines.append(f"Accompanying user text: {user_text.strip()}")

    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: swarm_attachment_vision_lane.py <image_path>")
        raise SystemExit(2)
    print(describe_attachment_for_talk("Describe this attached image.", sys.argv[1]))
