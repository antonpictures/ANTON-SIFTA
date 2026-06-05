#!/usr/bin/env python3
"""
System/swarm_architect_face_recognition.py — Architect Face Recognition Organ
═══════════════════════════════════════════════════════════════════════════════
AG46 2026-05-07 | Covenant §7.11 | GTH4921YP3

WHAT THIS DOES:
  Extends swarm_face_detection.py with IDENTITY recognition:
  detection says "a face is present" — this says "that face is George."

  Two-phase architecture:
    Phase 1 (detection): Swift binary → Apple Vision → bounding boxes + confidence
    Phase 2 (recognition): Python OpenCV → face ROI → embedding compare → is_architect

TRAINING (one-time setup):
  python3 System/swarm_architect_face_recognition.py train
  → Captures a frame, extracts face ROI, saves embedding to:
    .sifta_state/architect_face_embedding.npy  (64×64 normalised face patch)
    .sifta_state/architect_face_meta.json      (training receipt)

RECOGNITION (per-frame, called by the talk widget context block):
  from System.swarm_architect_face_recognition import get_recognition_context
  block = get_recognition_context()
  → "[ARCHITECT VISION] George confirmed by face recognition (0.94 sim)"

RECEIPT TRAIL:
  .sifta_state/face_recognition_events.jsonl   (every recognition attempt)
  Every receipt: ts, is_architect, similarity, method, training_ts

METHOD:
  OpenCV Haar cascade for robust detection, normalised 64×64 patch,
  cosine similarity to stored reference. Threshold: 0.70.
  When camera TCC not authorised: falls back to detection-only heuristic.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

import numpy as np

_REPO        = Path(__file__).resolve().parent.parent
_STATE       = _REPO / ".sifta_state"
_FRAMES_DIR  = _STATE / "owner_body_vision_frames"
_EMBEDDING   = _STATE / "architect_face_embedding.npy"
_META        = _STATE / "architect_face_meta.json"
_BINARY      = _STATE / "sifta_face_detect"
_LEDGER      = _STATE / "face_recognition_events.jsonl"

# Recognition threshold — cosine similarity to stored embedding
_SIMILARITY_THRESHOLD = 0.70
_MAX_LIVE_FRAME_AGE_S = 60.0
_MAX_TRAINING_CAPTURE_AGE_S = 20.0

_CV2 = None


def _cv2_disabled_in_qt_desktop() -> bool:
    disabled = os.environ.get("SIFTA_DISABLE_CV2_IN_QT_DESKTOP", "").strip().lower()
    forced = os.environ.get("SIFTA_FORCE_CV2", "").strip().lower()
    return disabled in {"1", "true", "yes", "on"} and forced not in {"1", "true", "yes", "on"}


def _load_cv2():
    """Import OpenCV only when an explicit recognition action needs it.

    The PyQt desktop camera path uses AVFoundation through Qt. Importing cv2 in
    the same process can load a second libavdevice copy and trigger macOS
    Objective-C class collisions. Keep identity recognition available from CLI
    or worker contexts, but keep the desktop import path cv2-free by default.
    """
    global _CV2
    if _cv2_disabled_in_qt_desktop():
        raise RuntimeError(
            "cv2 disabled in Qt desktop process; run this recognition path in "
            "the physical capture daemon or set SIFTA_FORCE_CV2=1 explicitly"
        )
    if _CV2 is None:
        import cv2 as cv2_mod  # type: ignore

        _CV2 = cv2_mod
    return _CV2


# ── Image utilities ───────────────────────────────────────────────────────────

def _load_cascade():
    cv2 = _load_cv2()
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    cc = cv2.CascadeClassifier(cascade_path)
    if cc.empty():
        raise RuntimeError("Haar cascade not found in OpenCV data")
    return cc


def _extract_face_patch(img_bgr: np.ndarray, *, target_size: int = 64) -> Optional[np.ndarray]:
    """
    Detect a face in img_bgr. Return normalised grayscale 64×64 patch, or None.
    Uses Haar cascade — runs on CPU, no external models, privacy-preserving.
    """
    cv2 = _load_cv2()
    cascade = _load_cascade()
    gray    = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    # equalise for varied lighting — George's desk can be dark
    gray    = cv2.equalizeHist(gray)
    faces   = cascade.detectMultiScale(
        gray, scaleFactor=1.05, minNeighbors=2,
        minSize=(40, 40), flags=cv2.CASCADE_SCALE_IMAGE
    )
    if len(faces) == 0:
        return None
    # Take the largest face (closest to camera)
    x, y, w, h = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)[0]
    # Expand slightly for context
    pad = int(min(w, h) * 0.12)
    x1  = max(0, x - pad)
    y1  = max(0, y - pad)
    x2  = min(img_bgr.shape[1], x + w + pad)
    y2  = min(img_bgr.shape[0], y + h + pad)
    face_roi = gray[y1:y2, x1:x2]
    if face_roi.size == 0:
        return None
    face_resized = cv2.resize(face_roi, (target_size, target_size))
    # L2 normalise
    flat = face_resized.astype(np.float32).flatten()
    norm = np.linalg.norm(flat)
    if norm < 1e-6:
        return None
    return flat / norm


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity — 1.0 = identical, 0.0 = orthogonal."""
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom < 1e-9:
        return 0.0
    return float(np.dot(a, b) / denom)


# ── Latest frame loader ───────────────────────────────────────────────────────

# The camera capture appends frames forever; nothing pruned them, so
# owner_body_vision_frames/ grew to 9.8G / 84,709 files (r539). This read-path
# janitor keeps only the newest _MAX_KEPT_FRAMES and unlinks the rest, bounding
# the dir every time Alice looks. Newest are what recognition needs anyway.
_MAX_KEPT_FRAMES = 300


def _prune_frames(pngs: list[Path], keep: int = _MAX_KEPT_FRAMES) -> list[Path]:
    """Unlink all but the newest `keep` PNGs (pngs sorted oldest→newest)."""
    if len(pngs) <= keep:
        return pngs
    for stale in pngs[:-keep]:
        try:
            stale.unlink()
        except OSError:
            pass
    return pngs[-keep:]


def _latest_frame_path() -> Optional[Path]:
    _FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    pngs = sorted(_FRAMES_DIR.glob("*.png"), key=lambda p: p.stat().st_mtime)
    pngs = _prune_frames(pngs)
    if not pngs:
        return None
    return pngs[-1]


def _frame_age_s(path: Path) -> float:
    return max(0.0, time.time() - path.stat().st_mtime)


def _load_frame(path: Path) -> Optional[np.ndarray]:
    cv2 = _load_cv2()
    img = cv2.imread(str(path))
    return img  # may be None if imread fails


def _latest_frame(*, max_age_s: float | None = None) -> tuple[Optional[np.ndarray], Optional[Path], Optional[float]]:
    """Load the newest PNG frame, optionally requiring freshness."""
    path = _latest_frame_path()
    if path is None:
        return None, None, None
    age = _frame_age_s(path)
    if max_age_s is not None and age > max_age_s:
        return None, path, age
    return _load_frame(path), path, age


def _capture_fresh_frame(*, max_age_s: float = _MAX_TRAINING_CAPTURE_AGE_S) -> tuple[Optional[np.ndarray], Optional[Path], Optional[float], str]:
    """
    Try to grab a fresh frame by running the Swift face-detect binary and reading
    the most recent PNG (the binary captures to owner_body_vision_frames/).
    If the binary is unavailable or fails, do not use stale cached frames.
    """
    status = "binary_missing"
    if _BINARY.exists():
        try:
            proc = subprocess.run(
                [str(_BINARY)], cwd=str(_REPO), capture_output=True, text=True, timeout=5.0
            )
            status = "capture_ok" if proc.returncode == 0 else f"capture_failed:{proc.returncode}"
            if proc.stdout:
                try:
                    row = json.loads(proc.stdout.strip().splitlines()[-1])
                    frame_path = row.get("frame_path")
                    if frame_path:
                        p = Path(frame_path)
                        age = _frame_age_s(p)
                        if age <= max_age_s:
                            return _load_frame(p), p, age, status
                        return None, p, age, "captured_frame_stale"
                except Exception:
                    pass
        except Exception:
            status = "capture_exception"
    img, path, age = _latest_frame(max_age_s=max_age_s)
    if img is None and path is not None:
        return None, path, age, "latest_frame_stale"
    return img, path, age, status


# ── Training ──────────────────────────────────────────────────────────────────

def train(source_image: Optional[str] = None) -> dict[str, Any]:
    """
    Build the Architect face embedding.

    Args:
        source_image: Optional path to a specific image. If None, uses the
                      most recent frame in owner_body_vision_frames/.

    Returns a training receipt dict.
    """
    source_path = None
    frame_age = None
    capture_status = "explicit_source"
    if source_image:
        source_path = Path(source_image)
        cv2 = _load_cv2()
        img = cv2.imread(source_image)
    else:
        img, source_path, frame_age, capture_status = _capture_fresh_frame(
            max_age_s=_MAX_TRAINING_CAPTURE_AGE_S
        )

    if img is None:
        receipt = {"ok": False, "event": "FACE_TRAINING",
                   "ts": time.time(),
                   "truth_label": "ARCHITECT_FACE_EMBEDDING_V1",
                   "error": "no_fresh_frame_available",
                   "capture_status": capture_status,
                   "frame_path": str(source_path) if source_path else None,
                   "frame_age_s": round(frame_age, 2) if frame_age is not None else None,
                   "note": "No fresh camera frame found. Sit in front of camera and retry."}
        _append_ledger(receipt)
        return receipt

    patch = _extract_face_patch(img)
    if patch is None:
        receipt = {"ok": False, "event": "FACE_TRAINING",
                   "ts": time.time(),
                   "truth_label": "ARCHITECT_FACE_EMBEDDING_V1",
                   "error": "no_face_detected",
                   "capture_status": capture_status,
                   "source_image": str(source_path) if source_path else source_image or "latest_frame",
                   "frame_age_s": round(frame_age, 2) if frame_age is not None else None,
                   "note": "No face detected in frame. Look directly at camera."}
        _append_ledger(receipt)
        return receipt

    _STATE.mkdir(parents=True, exist_ok=True)
    np.save(str(_EMBEDDING), patch)

    receipt = {
        "ts":          time.time(),
        "event":       "FACE_TRAINING",
        "embedding_shape": list(patch.shape),
        "source_image": str(source_path) if source_path else source_image or "latest_frame",
        "frame_age_s": round(frame_age, 2) if frame_age is not None else None,
        "capture_status": capture_status,
        "truth_label": "ARCHITECT_FACE_EMBEDDING_V1",
        "signed_by":   "AG46",
        "covenant":    "§7.11",
    }
    _META.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    _append_ledger({"ok": True, **receipt})
    print(f"✅ Training complete. Embedding saved: {_EMBEDDING}")
    print(f"   Patch shape: {patch.shape}, norm: {np.linalg.norm(patch):.4f}")
    return {"ok": True, "receipt": receipt}


# ── Recognition ───────────────────────────────────────────────────────────────

def recognise(
    img: Optional[np.ndarray] = None,
    *,
    max_frame_age_s: float = _MAX_LIVE_FRAME_AGE_S,
) -> dict[str, Any]:
    """
    Attempt to recognise the Architect in a camera frame.

    Returns a receipt dict:
      {is_architect, similarity, method, ts, error?, alice_line}
    """
    ts = time.time()
    base = {"ts": ts, "event": "FACE_RECOGNITION",
            "truth_label": "ARCHITECT_FACE_RECOGNITION_V1"}

    # Load reference embedding
    if not _EMBEDDING.exists():
        result = {**base, "is_architect": False, "similarity": 0.0,
                  "method": "no_embedding",
                  "error": "no_training — run: python3 System/swarm_architect_face_recognition.py train",
                  "alice_line": ""}
        _append_ledger(result)
        return result

    reference = np.load(str(_EMBEDDING))

    # Get frame. If no explicit image is supplied, identity-grade recognition
    # requires a fresh camera frame; stale cached PNGs are not live presence.
    frame_path: Optional[Path] = None
    frame_age: Optional[float] = None
    if img is None:
        img, frame_path, frame_age = _latest_frame(max_age_s=max_frame_age_s)
        if img is None and frame_path is not None:
            result = {**base, "is_architect": False, "similarity": 0.0,
                      "threshold": _SIMILARITY_THRESHOLD,
                      "method": "stale_frame",
                      "frame_path": str(frame_path),
                      "frame_age_s": round(frame_age, 2) if frame_age is not None else None,
                      "error": "latest_frame_stale",
                      "alice_line": "[ARCHITECT VISION] Latest camera frame is stale; no live face identity receipt."}
            _append_ledger(result)
            return result
    if img is None:
        result = {**base, "is_architect": False, "similarity": 0.0,
                  "method": "no_frame", "error": "no_frame_available",
                  "alice_line": ""}
        _append_ledger(result)
        return result

    # Extract face patch
    patch = _extract_face_patch(img)
    if patch is None:
        result = {**base, "is_architect": False, "similarity": 0.0,
                  "method": "no_face_in_frame", "error": None,
                  "alice_line": "[ARCHITECT VISION] No face detected in camera frame."}
        _append_ledger(result)
        return result

    # Compare
    sim = _cosine_similarity(patch, reference)
    is_arch = sim >= _SIMILARITY_THRESHOLD

    alice_line = _build_alice_line(is_arch, sim)
    result = {**base,
              "is_architect":  is_arch,
              "similarity":    round(sim, 4),
              "threshold":     _SIMILARITY_THRESHOLD,
              "method":        "haar+cosine_v1",
              "frame_path":    str(frame_path) if frame_path else None,
              "frame_age_s":   round(frame_age, 2) if frame_age is not None else None,
              "error":         None,
              "alice_line":    alice_line}
    _append_ledger(result)
    return result


def _build_alice_line(is_arch: bool, sim: float) -> str:
    if is_arch:
        conf = f"{sim:.0%}"
        return f"[ARCHITECT VISION] George confirmed by face recognition ({conf} similarity)."
    elif sim > 0.45:
        return f"[ARCHITECT VISION] Face detected but identity uncertain ({sim:.0%} sim — below {_SIMILARITY_THRESHOLD:.0%} threshold)."
    else:
        return "[ARCHITECT VISION] Face in frame — not recognised as George."


def _append_ledger(row: dict) -> None:
    try:
        _STATE.mkdir(parents=True, exist_ok=True)
        with _LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ── Context block for Alice's prompt ─────────────────────────────────────────

_RECOGNITION_CACHE: dict = {}
_RECOGNITION_CACHE_AT: float = 0.0
_RECOGNITION_TTL_S   = 20.0   # re-recognise at most every 20 seconds


def get_recognition_context() -> str:
    """
    Returns the one-line context string for Alice's system prompt.
    Uses a 20-second cache to avoid hammering OpenCV every turn.
    """
    global _RECOGNITION_CACHE, _RECOGNITION_CACHE_AT
    now = time.time()
    if _RECOGNITION_CACHE and (now - _RECOGNITION_CACHE_AT) < _RECOGNITION_TTL_S:
        return _RECOGNITION_CACHE.get("alice_line", "")

    try:
        result = recognise()
        _RECOGNITION_CACHE    = result
        _RECOGNITION_CACHE_AT = now
        return result.get("alice_line", "")
    except Exception:
        return ""


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "recognise"

    if cmd == "train":
        src = sys.argv[2] if len(sys.argv) > 2 else None
        result = train(source_image=src)
        print(json.dumps(result, indent=2))

    elif cmd == "recognise" or cmd == "recognize":
        result = recognise()
        print(json.dumps(result, indent=2))
        print()
        print("Alice sees:")
        print(" ", result.get("alice_line", "(no line)"))

    elif cmd == "status":
        print(f"Embedding exists: {_EMBEDDING.exists()}")
        if _META.exists():
            meta = json.loads(_META.read_text())
            print(f"Training ts:     {meta.get('ts', '?')}")
            print(f"Training source: {meta.get('source_image', '?')}")
        print(f"Binary exists:   {_BINARY.exists()}")
        frames = list(_FRAMES_DIR.glob('*.png'))
        print(f"Latest frames:   {len(frames)}")
        latest = _latest_frame_path()
        if latest:
            print(f"Latest frame:    {latest.name}")
            print(f"Latest age_s:    {_frame_age_s(latest):.1f}")

    else:
        print(f"Usage: {sys.argv[0]} train [image_path] | recognise | status")
        sys.exit(1)
