#!/usr/bin/env python3
"""
System/swarm_physical_capture_daemon.py
=======================================

A live background daemon that captures webcam frames, runs face detection
using OpenCV Haar cascades, and appends the results to the stigmergic ledger
(`.sifta_state/face_detection_events.jsonl`).

This gives Alice's newly wired organs (E35, E45, E46) live physical
substrate data to consume via `PhysicalSpaceReport`.
"""

import cv2
import json
import os
import time
from pathlib import Path

_STATE = Path(".sifta_state")
_LEDGER = _STATE / "face_detection_events.jsonl"
_INTERVAL_S = 5.0  # legacy default — used only when SIFTA_FACE_ADAPTIVE_OFF=1

# ── Cowork 2026-05-12 · P1 surprise-driven face daemon ──────────────────────
# Same VAD pattern as the eye (P0) and the mic. Event = a face was detected.
# Fast schedule while attention is present; exponential back-off when nobody
# is in view. Env-tunable from launcher. Falls back to fixed _INTERVAL_S
# when SIFTA_FACE_ADAPTIVE_OFF=1.
_FACE_FAST_S      = float(os.environ.get("SIFTA_FACE_FAST_S",      "1.0"))   # face in view → sample fast
_FACE_SLOW_S      = float(os.environ.get("SIFTA_FACE_SLOW_S",      "15.0"))  # nobody for a while → sample slow
_FACE_BACKOFF_K   = float(os.environ.get("SIFTA_FACE_BACKOFF_K",   "1.6"))   # geometric growth factor when empty
_FACE_HYSTERESIS_N = int(os.environ.get("SIFTA_FACE_HYSTERESIS_N", "2"))     # consecutive empty cycles before slowing


def _append_event(event: dict) -> None:
    with _LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


def _resolve_camera_index() -> int:
    """Resolve the current camera from live topology, not a stale integer."""
    try:
        from System.swarm_camera_target import probe_camera_topology, resolve_index

        probe_camera_topology(write_receipt=True)
        idx = resolve_index()
        if idx >= 0:
            return int(idx)
    except Exception:
        pass
    try:
        from System.swarm_iris import _discover_real_camera_index

        idx = _discover_real_camera_index()
        if idx >= 0:
            return int(idx)
    except Exception:
        pass
    return 0


def _open_capture():
    try:
        from System.swarm_camera_target import live_camera_allowed

        if not live_camera_allowed():
            return None, -1
    except Exception:
        pass
    idx = _resolve_camera_index()
    if idx < 0:
        return None, idx
    cap = cv2.VideoCapture(idx)
    if cap.isOpened():
        return cap, idx
    try:
        cap.release()
    except Exception:
        pass
    # One immediate fallback probe per §7.1. This catches Logitech detach:
    # the old target may be gone, but the MacBook camera is still live.
    try:
        from System.swarm_iris import invalidate_camera_cache, _discover_real_camera_index

        invalidate_camera_cache()
        fallback_idx = _discover_real_camera_index()
    except Exception:
        fallback_idx = -1
    if fallback_idx >= 0 and fallback_idx != idx:
        cap = cv2.VideoCapture(int(fallback_idx))
        if cap.isOpened():
            return cap, int(fallback_idx)
        try:
            cap.release()
        except Exception:
            pass
    return None, idx


def _ensure_ledger():
    _STATE.mkdir(parents=True, exist_ok=True)
    if not _LEDGER.exists():
        _LEDGER.touch()

def run_daemon(once=False):
    print(f"Starting Physical Capture Daemon (Interval: {_INTERVAL_S}s)...")
    _ensure_ledger()
    
    # Load OpenCV Haar cascade for face detection
    cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    face_cascade = cv2.CascadeClassifier(cascade_path)
    
    if face_cascade.empty():
        print("Failed to load Haar cascade.")
        return

    # Try to open webcam through the live topology resolver. Never pin a stale
    # USB integer; cv2/AVFoundation indices renumber when devices hot-plug.
    cap, camera_idx = _open_capture()
    if cap is None or not cap.isOpened():
        _append_event({
            "ts": time.time(),
            "event": "FACE_DETECTION",
            "faces_detected": 0,
            "confidence": 0.0,
            "audience": "nobody",
            "bounding_boxes": [],
            "error": "open_failed",
            "source": "swarm_physical_capture_daemon",
            "camera_index": camera_idx,
            "wake_reason": "camera_open_failed",
        })
        print("Failed to open webcam.")
        return
        
    # Warm up camera
    for _ in range(5):
        cap.read()
        time.sleep(0.1)

    # Adaptive scheduling state (P1) — tracks empty cycles for hysteresis
    empty_cycles = 0
    current_sleep_s = _FACE_FAST_S
    adaptive_off = os.environ.get("SIFTA_FACE_ADAPTIVE_OFF", "").strip() in ("1", "true", "yes")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                _append_event({
                    "ts": time.time(),
                    "event": "FACE_DETECTION",
                    "faces_detected": 0,
                    "confidence": 0.0,
                    "audience": "nobody",
                    "bounding_boxes": [],
                    "error": "read_failed_reopening_camera",
                    "source": "swarm_physical_capture_daemon",
                    "camera_index": camera_idx,
                    "wake_reason": "camera_read_failed",
                })
                try:
                    cap.release()
                except Exception:
                    pass
                cap, camera_idx = _open_capture()
                if cap is None or not cap.isOpened():
                    time.sleep(max(1.0, _FACE_SLOW_S))
                    continue
                time.sleep(1.0)
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
            )

            # Normalize bounding boxes
            h_img, w_img = frame.shape[:2]
            bboxes = []
            for (x, y, w, h) in faces:
                bboxes.append([
                    round(x / w_img, 3),
                    round(y / h_img, 3),
                    round(w / w_img, 3),
                    round(h / h_img, 3)
                ])

            # ── Cowork P1: choose next sleep based on detection event ──────────
            if adaptive_off:
                next_sleep_s = _INTERVAL_S
                wake_reason = "fixed_interval_legacy"
            elif len(faces) > 0:
                # Face in view → fast schedule; reset hysteresis counter
                empty_cycles = 0
                current_sleep_s = _FACE_FAST_S
                next_sleep_s = current_sleep_s
                wake_reason = "face_present"
            else:
                empty_cycles += 1
                if empty_cycles < _FACE_HYSTERESIS_N:
                    # Still in grace window — keep sampling at last rate
                    next_sleep_s = current_sleep_s
                    wake_reason = "empty_grace"
                else:
                    # Truly empty — exponentially back off toward _FACE_SLOW_S
                    current_sleep_s = min(_FACE_SLOW_S, current_sleep_s * _FACE_BACKOFF_K)
                    next_sleep_s = current_sleep_s
                    wake_reason = "empty_backoff"

            event = {
                "ts": time.time(),
                "event": "FACE_DETECTION",
                "faces_detected": len(faces),
                "confidence": 0.9 if len(faces) > 0 else 0.0,
                "audience": "architect" if len(faces) == 1 else "unknown_face" if len(faces) > 1 else "nobody",
                "bounding_boxes": bboxes,
                "error": None,
                "source": "swarm_physical_capture_daemon",
                "schedule_ms": int(next_sleep_s * 1000),
                "wake_reason": wake_reason,
                "empty_cycles": empty_cycles,
                "camera_index": camera_idx,
            }

            _append_event(event)

            # Round 114 §2.G.1 — feed owner_somatic_state from every face
            # detection event so the camera lane reaches Alice's somatic
            # field instead of stopping at face_detection_events.jsonl.
            # Never raise — visibility must not break the daemon.
            try:
                from System.swarm_owner_somatic_state import update_from_frame as _update_somatic_frame

                _update_somatic_frame(
                    {
                        "faces_detected": len(faces),
                        "confidence": 0.9 if len(faces) > 0 else 0.0,
                        "movement": "steady",  # face daemon does not yet emit motion class
                        "posture_hint": "architect_present" if len(faces) == 1 else "unknown",
                    },
                    camera_id=f"physical_capture_daemon:idx={camera_idx}",
                )
            except Exception:
                pass

            print(f"[{time.strftime('%H:%M:%S')}] faces={len(faces)} → next in {next_sleep_s:.1f}s ({wake_reason})")
            if once:
                break
            time.sleep(next_sleep_s)
            
    except KeyboardInterrupt:
        print("Daemon stopped by user.")
    finally:
        cap.release()

if __name__ == "__main__":
    import sys
    run_daemon(once="--once" in sys.argv)
