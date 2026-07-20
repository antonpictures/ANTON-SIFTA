#!/usr/bin/env python3
"""Body-screen eye for Alice's own hardware display.

The USB camera can sit on Alice's laptop body and point at the laptop screen.
This organ turns that configuration into receipts:

1. capture/ingest a frame,
2. hash and describe the frame without pretending semantic certainty,
3. write a visual-confirmation row,
4. route the evidence into the truth-navigation field.

Truth label: SIFTA_BODY_SCREEN_EYE_V1
Ledger: .sifta_state/body_screen_eye_receipts.jsonl
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Mapping

try:
    from System.jsonl_file_lock import append_line_locked, read_text_locked
except ModuleNotFoundError:  # pragma: no cover - direct script fallback
    _SCRIPT_REPO = Path(__file__).resolve().parent.parent
    if str(_SCRIPT_REPO) not in sys.path:
        sys.path.insert(0, str(_SCRIPT_REPO))
    from System.jsonl_file_lock import append_line_locked, read_text_locked


_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

TRUTH_LABEL = "SIFTA_BODY_SCREEN_EYE_V1"
LEDGER_NAME = "body_screen_eye_receipts.jsonl"


def _state_dir(state_dir: Path | str | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else _STATE


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _image_metadata(path: Path) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "byte_size": path.stat().st_size if path.exists() else 0,
        "sha256": _sha256_file(path) if path.exists() else "",
        "width": 0,
        "height": 0,
        "mode": "",
        "format": "",
        "orientation": "unknown",
    }
    if not path.exists():
        return meta
    try:
        from PIL import Image

        with Image.open(path) as img:
            meta["width"], meta["height"] = int(img.width), int(img.height)
            meta["mode"] = str(img.mode)
            meta["format"] = str(img.format or "")
            if img.width > img.height:
                meta["orientation"] = "landscape"
            elif img.height > img.width:
                meta["orientation"] = "portrait"
            else:
                meta["orientation"] = "square"
    except Exception as exc:
        meta["image_error"] = f"{type(exc).__name__}: {exc}"
    return meta


def _frame_to_image_meta(frame: Any) -> dict[str, Any]:
    path = Path(str(getattr(frame, "file_path", "") or ""))
    if path.exists():
        meta = _image_metadata(path)
    else:
        meta = {
            "path": str(path) if str(path) != "." else "",
            "exists": False,
            "byte_size": int(getattr(frame, "byte_size", 0) or 0),
            "sha256": "",
            "width": int(getattr(frame, "width", 0) or 0),
            "height": int(getattr(frame, "height", 0) or 0),
            "mode": "",
            "format": "",
            "orientation": "unknown",
        }
    meta["iris_frame_id"] = str(getattr(frame, "frame_id", ""))
    meta["iris_capture_source"] = str(getattr(frame, "capture_source", ""))
    meta["iris_metadata"] = dict(getattr(frame, "metadata", {}) or {})
    return meta


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _build_evidence_packet(row: Mapping[str, Any]) -> dict[str, Any]:
    image = row.get("image") if isinstance(row.get("image"), dict) else {}
    return {
        "kind": "body_screen_eye_camera_visual_confirmation",
        "truth_label": TRUTH_LABEL,
        "observed": bool(row.get("observed")),
        "trace_id": row.get("trace_id"),
        "screenshot_hash": image.get("sha256"),
        "ledger": row.get("ledger"),
        "preview": row.get("scene_label", ""),
    }


def record_body_screen_eye(
    *,
    image_path: Path | str | None = None,
    source: str = "owner_attested_image",
    owner_claim: str = "",
    scene_label: str = "USB camera eye points at Alice laptop body screen",
    state_dir: Path | str | None = None,
    write: bool = True,
    now: float | None = None,
) -> dict[str, Any]:
    """Record one body-screen-eye observation from an existing image file."""
    state = _state_dir(state_dir)
    image_meta = _image_metadata(Path(image_path)) if image_path else {
        "path": "",
        "exists": False,
        "byte_size": 0,
        "sha256": "",
        "width": 0,
        "height": 0,
        "mode": "",
        "format": "",
        "orientation": "unknown",
    }
    observed = bool(image_meta.get("exists") and image_meta.get("sha256"))
    return _record_from_image_meta(
        image_meta=image_meta,
        source=source,
        owner_claim=owner_claim,
        scene_label=scene_label,
        observed=observed,
        state_dir=state,
        write=write,
        now=now,
    )


def capture_body_screen_eye(
    *,
    source: str = "webcam",
    owner_claim: str = "USB camera sitting on Alice hardware body eye points at laptop own body screen",
    scene_label: str = "USB camera eye points at Alice laptop body screen",
    state_dir: Path | str | None = None,
    write: bool = True,
    now: float | None = None,
) -> dict[str, Any]:
    """Capture one frame through swarm_iris and record it as body-screen-eye evidence."""
    try:
        from System.swarm_iris import SwarmIris

        frame = SwarmIris().blink_capture(source=source)
        image_meta = _frame_to_image_meta(frame)
    except Exception as exc:
        image_meta = {
            "path": "",
            "exists": False,
            "byte_size": 0,
            "sha256": "",
            "width": 0,
            "height": 0,
            "mode": "",
            "format": "",
            "orientation": "unknown",
            "capture_error": f"{type(exc).__name__}: {exc}",
        }
    observed = bool(image_meta.get("sha256") or image_meta.get("byte_size"))
    return _record_from_image_meta(
        image_meta=image_meta,
        source=f"iris_{source}",
        owner_claim=owner_claim,
        scene_label=scene_label,
        observed=observed,
        state_dir=_state_dir(state_dir),
        write=write,
        now=now,
    )


def _record_from_image_meta(
    *,
    image_meta: dict[str, Any],
    source: str,
    owner_claim: str,
    scene_label: str,
    observed: bool,
    state_dir: Path,
    write: bool,
    now: float | None,
) -> dict[str, Any]:
    ts = float(now if now is not None else time.time())
    row: dict[str, Any] = {
        "ts": ts,
        "trace_id": str(uuid.uuid4()),
        "schema": TRUTH_LABEL,
        "truth_label": TRUTH_LABEL,
        "kind": "BODY_SCREEN_EYE_RECEIPT",
        "source": source,
        "observed": bool(observed),
        "confidence": 0.82 if observed else 0.0,
        "scene_label": scene_label,
        "owner_claim_preview": _normalize_text(owner_claim)[:360],
        "image": image_meta,
        "ledger": str(state_dir / LEDGER_NAME),
    }

    try:
        from System.swarm_visual_confirmation import record_visual_confirmation

        visual = record_visual_confirmation(
            semantic_target=scene_label,
            stage="body_screen_eye",
            risk_tier="LOW",
            observed=bool(observed),
            confidence=row["confidence"],
            root=state_dir,
            action_trace_id=row["trace_id"],
            screenshot_hash=str(image_meta.get("sha256") or ""),
            notes=f"{source}: {row['owner_claim_preview']}",
            write_ledger=write,
        )
        row["visual_confirmation_trace_id"] = visual.get("trace_id")
    except Exception as exc:
        row["visual_confirmation_error"] = f"{type(exc).__name__}: {exc}"

    try:
        from System.swarm_truth_navigation_field import truth_navigation_assessment

        truth_nav = truth_navigation_assessment(
            owner_claim or scene_label,
            evidence_packets=[_build_evidence_packet(row)],
            state_dir=state_dir,
            write=write,
            now=ts,
        )
        row["truth_navigation_trace_id"] = truth_nav.get("trace_id")
        row["truth_navigation_verdict"] = truth_nav.get("verdict")
        row["truth_navigation_missing"] = truth_nav.get("missing_probe_dimensions", [])
    except Exception as exc:
        row["truth_navigation_error"] = f"{type(exc).__name__}: {exc}"

    row["sha256"] = hashlib.sha256(
        json.dumps({k: v for k, v in row.items() if k != "sha256"}, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()

    if write:
        append_line_locked(
            state_dir / LEDGER_NAME,
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return row


def latest_receipts(
    *,
    state_dir: Path | str | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    path = _state_dir(state_dir) / LEDGER_NAME
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        text = read_text_locked(path, encoding="utf-8", errors="replace")
    except Exception:
        return []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows[-max(1, int(limit)) :]


def summary_for_prompt(*, state_dir: Path | str | None = None) -> str:
    rows = latest_receipts(state_dir=state_dir, limit=1)
    if not rows:
        return ""
    row = rows[-1]
    image = row.get("image") if isinstance(row.get("image"), dict) else {}
    return (
        "BODY-SCREEN EYE:\n"
        f"- observed={row.get('observed')} source={row.get('source')} confidence={row.get('confidence')}\n"
        f"- scene={row.get('scene_label')}\n"
        f"- image={image.get('width')}x{image.get('height')} sha={str(image.get('sha256') or '')[:12]} "
        f"truth_nav={row.get('truth_navigation_verdict')}"
    )


def cli() -> int:
    parser = argparse.ArgumentParser(description="Alice body-screen eye receipt organ")
    sub = parser.add_subparsers(dest="cmd")
    ingest = sub.add_parser("ingest-image", help="Ingest an existing camera/photo image")
    ingest.add_argument("image_path")
    ingest.add_argument("--claim", default="USB camera sitting on Alice hardware body eye points at laptop own body screen")
    ingest.add_argument("--scene-label", default="USB camera eye points at Alice laptop body screen")
    capture = sub.add_parser("capture", help="Capture one frame through swarm_iris")
    capture.add_argument("--source", default="webcam", choices=("webcam", "ide_chrome_screenshot"))
    capture.add_argument("--claim", default="USB camera sitting on Alice hardware body eye points at laptop own body screen")
    capture.add_argument("--scene-label", default="USB camera eye points at Alice laptop body screen")
    sub.add_parser("summary", help="Print latest prompt summary")
    args = parser.parse_args()

    cmd = args.cmd or "summary"
    if cmd == "ingest-image":
        row = record_body_screen_eye(
            image_path=args.image_path,
            source="owner_attested_image",
            owner_claim=args.claim,
            scene_label=args.scene_label,
        )
        print(json.dumps(row, indent=2, ensure_ascii=False))
        return 0
    if cmd == "capture":
        row = capture_body_screen_eye(
            source=args.source,
            owner_claim=args.claim,
            scene_label=args.scene_label,
        )
        print(json.dumps(row, indent=2, ensure_ascii=False))
        return 0
    if cmd == "summary":
        print(summary_for_prompt())
        return 0
    parser.print_help()
    return 2


__all__ = [
    "LEDGER_NAME",
    "TRUTH_LABEL",
    "capture_body_screen_eye",
    "latest_receipts",
    "record_body_screen_eye",
    "summary_for_prompt",
]


if __name__ == "__main__":
    raise SystemExit(cli())
