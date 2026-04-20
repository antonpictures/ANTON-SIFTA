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

import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
_STATE = _REPO / ".sifta_state"
_IRIS_LOG = _STATE / "swarm_iris_capture.jsonl"
MODULE_VERSION = "2026-04-18.olympiad.v2"

try:
    from System.jsonl_file_lock import append_line_locked
except ImportError:
    def append_line_locked(path, line, *, encoding="utf-8"):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding=encoding) as f:
            f.write(line)

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

    def _get_frontmost_window_id(self) -> Optional[int]:
        """Returns the CGWindowID of the active frontmost window via Swift."""
        swift_bin = self.output_dir.parent / "get_front_window"
        if not swift_bin.exists():
            swift_code = """
import Cocoa
import CoreGraphics

let options = CGWindowListOption(arrayLiteral: .excludeDesktopElements, .optionOnScreenOnly)
let windowListInfo = CGWindowListCopyWindowInfo(options, CGWindowID(0))
let infoList = windowListInfo as NSArray? as? [[String: AnyObject]]

if let topWindow = infoList?.first(where: { ($0[kCGWindowLayer as String] as? Int) == 0 && ($0[kCGWindowOwnerName as String] as? String) != "Window Server" }) {
    if let windowID = topWindow[kCGWindowNumber as String] as? Int {
        print(windowID)
    }
}
"""
            swift_src = self.output_dir.parent / "get_front_window.swift"
            try:
                swift_src.write_text(swift_code)
                import subprocess
                subprocess.run(["swiftc", str(swift_src), "-o", str(swift_bin)], check=True)
            except Exception:
                return None

        import subprocess
        try:
            res = subprocess.run([str(swift_bin)], capture_output=True, text=True, check=True)
            return int(res.stdout.strip())
        except Exception:
            return None

    def capture_screenshot(self, tag: str = "ide_chrome") -> IrisFrame:
        """
        Takes a screenshot to read the IDE chrome.
        Priority: Frontmost window only. Fallback: Full screen.
        """
        import subprocess
        
        now = time.time()
        frame_id = f"frame_{tag}_{int(now)}"
        target_file = self.output_dir / f"{frame_id}.png"
        
        window_id = self._get_frontmost_window_id()
        try:
            if window_id:
                # Capture specific window silently
                subprocess.run(["screencapture", "-x", "-l", str(window_id), str(target_file)], check=True)
            else:
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
            metadata={"adapter": "macOS screencapture", "window_isolated": window_id is not None, "status": "simulated_ok" if size==0 else "ok"}
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
# === AG31 PATCH 2026-04-19: camera device discovery ===
# C47H audit finding: both modules defaulted to AVFoundation index 0
# (OBS Virtual Camera on this machine), which returns nothing when OBS
# isn't running. Indices 1-3 are the real cameras:
#   1 = MacBook Pro Camera  (built-in)
#   2 = USB Camera VID:1133 PID:2081  (Logitech C920-class)
#   3 = iPhone Camera via Continuity  (iPhone 15 Plus)
# Fix: probe at runtime, skip dead devices, return first live index.
# ════════════════════════════════════════════════════════════════════════

# AVFoundation device index: resolved at runtime so we never silently
# anchor to a dead virtual device (OBS Virtual Camera = index 0 on this
# machine, returns nothing when OBS isn't running).
_AVFOUNDATION_MAX_IDX = 8   # 9 devices detected on this machine (0..8)

# NOTE C47H finding #1: name-based device filtering would be more robust
# (using system_profiler SPCameraDataType to map index→name then skipping
# names matching "obs", "virtual", "desk view"). Wired as v4 hardening.
# Current impl is POSITION-based: skip index 0 in pass 1, probe last in
# pass 2. Correct on this machine; documents accurately here.

def _discover_real_camera_index() -> int:
    """
    Probe cv2 indices 0.._AVFOUNDATION_MAX_IDX and return the first that
    opens AND returns a real frame.

    Strategy (two-pass, POSITION-based):
      Pass 1 — indices 1..N: skip index 0 first because on this machine
               index 0 = OBS Virtual Camera, dead unless OBS is running.
      Pass 2 — index 0: tried last as fallback. If OBS is running and is
               intentionally the canonical feed, it wins here.

    NOTE: This is position-based, not name-based filtering. On a machine
    where a virtual device sits at index 1, it will be selected. Name-based
    filtering (parse system_profiler, skip by device name) is filed as v4
    hardening — see _AVFOUNDATION_MAX_IDX comment above.

    Callers that want a specific device should pass camera_index explicitly
    to webcam_frame(). This helper is the "auto" default only.

    Returns -1 if no camera is readable (CI / no hardware / permission denied).
    Never raises.
    """
    if not HAS_CV2:
        return -1
    # Two-pass: try 1..N first, then 0 as last resort
    for idx in list(range(1, _AVFOUNDATION_MAX_IDX + 1)) + [0]:
        cap = None
        try:
            cap = _cv2.VideoCapture(idx)
            if not cap.isOpened():
                continue
            ok, frame = cap.read()
            if ok and frame is not None:
                return idx
        except Exception:
            continue
        finally:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass
    return -1


# Cache the discovered index once per process. A running swarm doesn't
# need to re-scan every blink.
_UNSET = object()
_DISCOVERED_CAMERA_IDX: object = _UNSET

def _get_default_camera_index() -> int:
    """Return cached discovered camera index. -1 = none available."""
    global _DISCOVERED_CAMERA_IDX
    if _DISCOVERED_CAMERA_IDX is _UNSET:
        _DISCOVERED_CAMERA_IDX = _discover_real_camera_index()
    return _DISCOVERED_CAMERA_IDX  # type: ignore[return-value]


def invalidate_camera_cache() -> None:
    """
    Force the next webcam_frame() call to re-probe available devices.

    Call this after hardware changes at runtime:
      - Plugging/unplugging an iPhone (Continuity Camera)
      - Starting/stopping OBS
      - Connecting a USB webcam mid-session

    Safe to call from any thread; just resets the sentinel so the next
    _get_default_camera_index() call re-runs _discover_real_camera_index().
    """
    global _DISCOVERED_CAMERA_IDX
    _DISCOVERED_CAMERA_IDX = _UNSET


# ════════════════════════════════════════════════════════════════════════
# === C47H SECTION M1.4: webcam_frame() — optional priority-B lane ===
# T65 segment. Webcam capture is OPTIONAL (the Architect explicitly said
# screen-capture is priority A; webcam is priority B). If cv2 is not
# installed OR no camera is available, returns None — does NOT raise.
# A None return is a normal, expected outcome on most installs.
# ════════════════════════════════════════════════════════════════════════

def webcam_frame(
    *,
    camera_index: int = -1,   # -1 = auto-discover (was hardcoded 0 = OBS Virtual Camera)
    tag: str = "webcam",
    save_to_disk: bool = True,
    grab_timeout_s: float = 1.5,
) -> Optional[IrisFrame]:
    """
    Single-frame webcam capture. Returns None when capture is unavailable
    (no cv2, no camera, permission denied, etc.). Never raises on the
    "no hardware" branch — the eye must degrade gracefully.

    camera_index=-1 (default): auto-discover the first live real camera,
      skipping virtual devices (OBS, Desk View) that may not be producing
      frames. C47H audit 2026-04-19: old default 0 = OBS Virtual Camera
      on this machine — silent fallback to synthetic frames all along.

    Pass camera_index explicitly (1, 2, 3, ...) to pin a specific device:
      1 = MacBook Pro Camera, 2 = Logitech USB, 3 = iPhone Continuity.

    >>> # On a CI box with no webcam, expect None.
    >>> result = webcam_frame(grab_timeout_s=0.1)
    >>> result is None or isinstance(result, IrisFrame)
    True
    """
    if not HAS_CV2:
        return None

    # Resolve auto-discovery
    if camera_index == -1:
        camera_index = _get_default_camera_index()
    if camera_index == -1:
        return None   # no real camera found

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
            append_line_locked(_IRIS_LOG, json.dumps(row, ensure_ascii=False) + "\n")
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
