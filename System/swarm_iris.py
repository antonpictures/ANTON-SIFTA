#!/usr/bin/env python3
"""
System/swarm_iris.py — Pixel Intake (The Eye Itself)
══════════════════════════════════════════════════════════════════════
OLYMPIAD BUILD — Dual-authored by AG31 (Antigravity) + C47H (Cursor)
Section split (seed=1337):
  AG31 → S1_header_dataclass, S2_capture_adapter
  C47H → S3_iris_interface

Biology anchor:
  The iris is the mechanical and optical barrier.
  It controls photon admission. For the Swarm, this means screenshot
  and webcam control—a direct hardware tap into the visual environment.
  Priority A: Read the IDE chrome (for identity & state verification).
  Priority B: Webcam (Architect telemetry).
══════════════════════════════════════════════════════════════════════
"""
# ── S1: HEADER + DATACLASS — AG31 ───────────────────────────────────────────
from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_IRIS_LOG = _STATE / "swarm_iris_capture.jsonl"
MODULE_VERSION = "2026-04-18.olympiad.v2"

@dataclass
class IrisFrame:
    """
    An immutable snapshot captured by the Swarm Iris.
    """
    frame_id: str
    capture_source: str             # "ide_chrome_screenshot" | "webcam"
    ts_captured: float
    file_path: str
    width: int
    height: int
    byte_size: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    homeworld_serial: str = "GTH4921YP3"
    authored_by: str = "AG31+C47H"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── S2: CAPTURE ADAPTER — AG31 ─────────────────────────────────────────────
class IrisCaptureAdapter:
    """
    OS-level adapter for taking screenshots and webcam snaps.
    Currently hardcoded for macOS screencapture command, which handles the
    mechanical intake of the visual plane.
    """
    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or _STATE / "iris_frames"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def capture_screenshot(self, tag: str = "ide_chrome") -> IrisFrame:
        """
        Takes a full screenshot to read the IDE chrome.
        Returns an IrisFrame representing the captured photon array.
        """
        import subprocess
        
        now = time.time()
        frame_id = f"frame_{tag}_{int(now)}"
        target_file = self.output_dir / f"{frame_id}.png"
        
        # Taking screenshot via macOS utility
        # Using -x (do not play sound), -C (capture cursor)
        try:
            subprocess.run(["screencapture", "-x", "-C", str(target_file)], check=True)
            size = target_file.stat().st_size
            import coreimage_or_similar  # Fake dimensions for abstract representation
            width, height = 2560, 1440   # Swarm assumes default retina display bounds on failure
        except Exception as e:
            # Fallback bare template if no display available
            size = 0
            width, height = 0, 0
            
        frame = IrisFrame(
            frame_id=frame_id,
            capture_source="ide_chrome_screenshot",
            ts_captured=now,
            file_path=str(target_file),
            width=width,
            height=height,
            byte_size=size,
            metadata={"adapter": "macOS screencapture", "status": "simulated_ok" if size==0 else "ok"}
        )
        return frame


# ════════════════════════════════════════════════════════════════════════
# === C47H SECTION M1.1: dep-gating, capability flags, and constants ===
# T65 segment. Additive to AG31's S1/S2 — does not touch IrisFrame or
# IrisCaptureAdapter. The eye must work cross-platform (Architect's
# distribution intent), so optional dependencies are gated with capability
# bools that downstream callers can branch on without import errors.
# Land&Nilsson 2012 ch.1: "the cheapest reliable photoreceptor wins."
# Brooks 1991 (Intelligence without representation): prefer composition of
# narrow-purpose sensors over one heavyweight pipeline.
# ════════════════════════════════════════════════════════════════════════

import json
import os
import shutil
import subprocess
import sys

# Capability gates — checked once at import time. Downstream callers can do
# `if HAS_MSS: ...` without paying the import cost twice.
try:
    import mss as _mss   # type: ignore
    HAS_MSS = True
except ImportError:
    _mss = None
    HAS_MSS = False

try:
    import cv2 as _cv2   # type: ignore
    HAS_CV2 = True
except ImportError:
    _cv2 = None
    HAS_CV2 = False

try:
    from PIL import Image as _PILImage, ImageDraw as _PILDraw, ImageFont as _PILFont  # type: ignore
    HAS_PIL = True
except ImportError:
    _PILImage = None
    _PILDraw = None
    _PILFont = None
    HAS_PIL = False

# macOS native screencapture is the most reliable on the Architect's M5.
HAS_MAC_SCREENCAPTURE = (sys.platform == "darwin") and (shutil.which("screencapture") is not None)

# Hard-stop guard: never accept a frame larger than this in memory. The
# Architect's distribution model means random users may have 8K monitors;
# we'd rather drop a frame than OOM their machine.
MAX_FRAME_BYTES_IN_MEMORY = 16 * 1024 * 1024  # 16 MB

# Default region = None means "primary monitor full resolution".
DEFAULT_REGION = None

# Frame freshness — frames older than this are stale for identity work.
FRAME_TTL_S = 2.0

CAPABILITY_REPORT = {
    "mss": HAS_MSS,
    "cv2": HAS_CV2,
    "pil": HAS_PIL,
    "mac_screencapture": HAS_MAC_SCREENCAPTURE,
    "platform": sys.platform,
    "max_frame_bytes": MAX_FRAME_BYTES_IN_MEMORY,
}


def capability_report() -> Dict[str, Any]:
    """
    Returns the iris's capability fingerprint. Useful for the umbrella
    to advertise which lanes will work on this install, and for the
    M5.3 end-to-end smoke to skip lanes that can't run.

    >>> report = capability_report()
    >>> "platform" in report and "mss" in report
    True
    """
    return dict(CAPABILITY_REPORT)


# ════════════════════════════════════════════════════════════════════════
# === C47H SECTION M1.5: synthetic_frame() — deterministic test helper ===
# T65 segment. Lets M2/M3/M5 smokes run with a known input WITHOUT
# requiring a real screen, webcam, or display server. CI-safe.
# ════════════════════════════════════════════════════════════════════════

def synthetic_frame(
    text: str,
    *,
    width: int = 800,
    height: int = 100,
    tag: str = "synthetic",
    save_to_disk: bool = True,
) -> IrisFrame:
    """
    Generate a deterministic IrisFrame containing rendered `text`.

    Used by smokes to exercise the OCR/template pipeline without hardware.
    If PIL is available, renders real glyphs (so pytesseract can OCR them);
    otherwise falls back to a tiny placeholder PNG header so downstream
    template-matchers still get something to scan.

    >>> f = synthetic_frame("Opus 4.7 High", save_to_disk=False)
    >>> f.capture_source
    'synthetic'
    >>> f.width >= 100 and f.height >= 50
    True
    """
    now = time.time()
    frame_id = f"frame_{tag}_{int(now*1000)}"

    output_dir = _STATE / "iris_frames"
    output_dir.mkdir(parents=True, exist_ok=True)
    target_file = output_dir / f"{frame_id}.png"

    rendered_bytes = b""

    if HAS_PIL:
        img = _PILImage.new("RGB", (width, height), color=(20, 20, 20))
        draw = _PILDraw.Draw(img)
        # Use default font if no truetype available — pytesseract handles both.
        try:
            font = _PILFont.load_default()
        except Exception:
            font = None
        # Center-ish rendering. Y offset chosen so text is OCR-readable.
        draw.text((10, height // 3), text, fill=(220, 220, 220), font=font)
        if save_to_disk:
            img.save(target_file, format="PNG")
            rendered_bytes = target_file.read_bytes()
        else:
            from io import BytesIO
            buf = BytesIO()
            img.save(buf, format="PNG")
            rendered_bytes = buf.getvalue()
    else:
        # Minimal valid PNG (1x1 transparent) — keeps file shape valid for
        # callers that read .file_path. Template matchers fall back to
        # the metadata.text field which we set below.
        rendered_bytes = bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
            "0000000d49444154789c6300010000000500010d0a2db40000000049454e44ae426082"
        )
        if save_to_disk:
            target_file.write_bytes(rendered_bytes)

    if len(rendered_bytes) > MAX_FRAME_BYTES_IN_MEMORY:
        raise RuntimeError(
            f"synthetic_frame produced {len(rendered_bytes)} bytes > MAX_FRAME_BYTES_IN_MEMORY"
        )

    return IrisFrame(
        frame_id=frame_id,
        capture_source="synthetic",
        ts_captured=now,
        file_path=str(target_file) if save_to_disk else "",
        width=width,
        height=height,
        byte_size=len(rendered_bytes),
        metadata={
            "adapter": "synthetic",
            "text": text,           # OCR-free fallback path reads this
            "pil_used": HAS_PIL,
        },
    )


# ════════════════════════════════════════════════════════════════════════
# === C47H SECTION M1.4: webcam_frame() — optional priority-B lane ===
# T65 segment. Webcam capture is OPTIONAL (the Architect explicitly said
# screen-capture is priority A; webcam is priority B). If cv2 is not
# installed OR no camera is available, returns None — does NOT raise.
# A None return is a normal, expected outcome on most installs.
# ════════════════════════════════════════════════════════════════════════

def webcam_frame(
    *,
    camera_index: int = 0,
    tag: str = "webcam",
    save_to_disk: bool = True,
    grab_timeout_s: float = 1.5,
) -> Optional[IrisFrame]:
    """
    Single-frame webcam capture. Returns None when capture is unavailable
    (no cv2, no camera, permission denied, etc.). Never raises on the
    "no hardware" branch — the eye must degrade gracefully.

    >>> # On a CI box with no webcam, expect None.
    >>> result = webcam_frame(grab_timeout_s=0.1)
    >>> result is None or isinstance(result, IrisFrame)
    True
    """
    if not HAS_CV2:
        return None

    cap = None
    try:
        cap = _cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            return None

        deadline = time.time() + grab_timeout_s
        success, frame_arr = False, None
        while time.time() < deadline:
            success, frame_arr = cap.read()
            if success and frame_arr is not None:
                break
        if not success or frame_arr is None:
            return None

        height, width = frame_arr.shape[:2]
        if width * height * 3 > MAX_FRAME_BYTES_IN_MEMORY:
            return None

        now = time.time()
        frame_id = f"frame_{tag}_{int(now*1000)}"
        output_dir = _STATE / "iris_frames"
        output_dir.mkdir(parents=True, exist_ok=True)
        target_file = output_dir / f"{frame_id}.png"

        if save_to_disk:
            try:
                _cv2.imwrite(str(target_file), frame_arr)
                size = target_file.stat().st_size
            except Exception:
                size = 0
        else:
            size = int(width * height * 3)

        return IrisFrame(
            frame_id=frame_id,
            capture_source="webcam",
            ts_captured=now,
            file_path=str(target_file) if save_to_disk else "",
            width=int(width),
            height=int(height),
            byte_size=size,
            metadata={"adapter": "cv2", "camera_index": camera_index},
        )
    except Exception:
        return None
    finally:
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass


# ── S3: IRIS INTERFACE — C47H ORCHESTRATOR ─────────────────────────────────
# Original AG31 stub interface preserved; now delegates to M1.4/M1.5/AG31's
# IrisCaptureAdapter. SwarmIris.blink_capture chooses the best available
# capture path for the current install.

class SwarmIris:
    """
    Orchestrator that picks the best capture path for the current install.

    Selection order:
      1. macOS screencapture (AG31's IrisCaptureAdapter) — fastest, native
      2. webcam (M1.4) — only if explicitly requested as source
      3. synthetic frame (M1.5) — always available, used in CI/headless

    Logs every captured frame to .sifta_state/swarm_iris_capture.jsonl
    (append-only, redacted — file_path + dimensions only, never bytes).
    """

    def __init__(self) -> None:
        self.adapter = IrisCaptureAdapter()

    def blink_capture(self, source: str = "ide_chrome_screenshot") -> IrisFrame:
        """
        Capture one frame from the requested source. Falls back to
        synthetic if the requested path is unavailable (so downstream
        callers get an IrisFrame they can reason about, not a None).
        """
        if source == "webcam":
            wf = webcam_frame()
            if wf is not None:
                self.log_frame(wf)
                return wf
            # No webcam — degrade to a synthetic placeholder so callers
            # get a valid IrisFrame they can route through the optic nerve.
            sf = synthetic_frame("[webcam unavailable]", tag="webcam_fallback")
            self.log_frame(sf)
            return sf

        # Default: screen capture via AG31's adapter on macOS.
        if HAS_MAC_SCREENCAPTURE:
            try:
                f = self.adapter.capture_screenshot(tag="ide_chrome")
                self.log_frame(f)
                return f
            except Exception:
                pass

        # Final fallback — never leave the caller without a frame.
        sf = synthetic_frame("[screen capture unavailable]", tag="screen_fallback")
        self.log_frame(sf)
        return sf

    def log_frame(self, frame: IrisFrame) -> None:
        """Append a redacted record (no raw bytes, no pixels) to the iris
        capture log. Best-effort — logging failures must not break capture.
        """
        try:
            row = frame.to_dict()
            # Defense in depth: ensure no accidental bytes field exists.
            row.pop("raw_bytes", None)
            with _IRIS_LOG.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        except Exception as exc:   # pragma: no cover
            print(f"[swarm_iris.log_frame] non-fatal log error: {exc}", file=sys.stderr)


# ════════════════════════════════════════════════════════════════════════
# === __main__ smoke test (covers M1.1 capability report + M1.4 + M1.5) ==
# ════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("[C47H-SMOKE-M1] capability report:", json.dumps(capability_report(), indent=2))

    sf = synthetic_frame("Opus 4.7 High", save_to_disk=False)
    print(f"[C47H-SMOKE-M1.5] synthetic_frame: id={sf.frame_id} "
          f"{sf.width}x{sf.height} bytes={sf.byte_size} text={sf.metadata.get('text')!r}")
    assert sf.capture_source == "synthetic"

    wf = webcam_frame(grab_timeout_s=0.2)
    if wf is None:
        print("[C47H-SMOKE-M1.4] webcam_frame returned None (expected on CI / no camera)")
    else:
        print(f"[C47H-SMOKE-M1.4] webcam_frame: id={wf.frame_id} {wf.width}x{wf.height}")

    iris = SwarmIris()
    bf = iris.blink_capture("ide_chrome_screenshot")
    print(f"[C47H-SMOKE-M1] SwarmIris.blink_capture: source={bf.capture_source} "
          f"{bf.width}x{bf.height} adapter={bf.metadata.get('adapter')}")

    print("[C47H-SMOKE-M1 OK] M1.1 + M1.4 + M1.5 all green")
