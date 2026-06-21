#!/usr/bin/env python3
"""
Applications/sifta_youtube_shazam.py
═══════════════════════════════════════════════════════════════
Stigmergic Unified Shazam (Event 121 / Architect Drop)
═══════════════════════════════════════════════════════════════
Pipeline:
  1. Tail media_ingress_gate.jsonl (ambient media STT, already immune-gated)
  2. Acoustic Scene Classifier pre-labels the audio: CINEMATIC / NEWS / MUSIC / SPORTS / ...
  3. LLM Shazam prompt is SCENE-AWARE (narrowed prior)
  4. Guess + receipt written to cowatch_shazam_ledger.jsonl

Research spine:
  Wang (2003) ISMIR — landmark fingerprinting
  Grassé (1959) — stigmergy as environment-encoded coordination
  DCASE (2013-) — acoustic scene classification benchmarks
"""

import json
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTextEdit, QFrame
)

try:
    from System.sifta_inference_defaults import resolve_ollama_model
    _MODEL = resolve_ollama_model()
except ImportError:
    _MODEL = "llama3"

try:
    from System.swarm_acoustic_scene_classifier import classify_scene
    _SCENE_AVAILABLE = True
except ImportError:
    _SCENE_AVAILABLE = False
    def classify_scene(**_kw):  # type: ignore
        class _F:
            scene = "UNKNOWN"; confidence = 0.0; scores = {}
        return _F()

try:
    from System.jsonl_file_lock import append_line_locked
    _LOCK_AVAILABLE = True
except ImportError:
    _LOCK_AVAILABLE = False
    def append_line_locked(path, line):  # type: ignore
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)

_STATE_DIR = Path(__file__).resolve().parent.parent / ".sifta_state"
_MEDIA_LOG  = _STATE_DIR / "media_ingress_gate.jsonl"
_LEDGER     = _STATE_DIR / "cowatch_shazam_ledger.jsonl"

# Scene → YouTube categories for prompt narrowing
_SCENE_HINT: dict = {
    "CINEMATIC": "movie, TV show, anime, or film documentary",
    "NEWS":      "news broadcast, political commentary, documentary narration, or news channel (CNN, BBC, Fox, etc.)",
    "MUSIC":     "song, music video, live concert, or artist",
    "SPORTS":    "sports broadcast, match commentary, or sports channel",
    "GAMING":    "video game, esports broadcast, or gaming video",
    "PODCAST":   "podcast, interview, or conversation-style video",
    "AMBIENT":   "ASMR, lo-fi, nature sounds, or background ambience",
    "UNKNOWN":   "movie, TV show, music, news, or any YouTube content",
}


class ShazamThread(QThread):
    result_ready = pyqtSignal(str, str, float)  # guess, scene, confidence

    def __init__(self, transcript: str, scene: str, confidence: float):
        super().__init__()
        self.transcript = transcript
        self.scene = scene
        self.confidence = confidence

    def run(self):
        hint = _SCENE_HINT.get(self.scene, _SCENE_HINT["UNKNOWN"])
        scene_ctx = (
            f"Acoustic scene pre-classifier detected: {self.scene} (confidence={self.confidence:.0%}). "
            f"Focus your guess on: {hint}.\n\n"
            if self.scene != "UNKNOWN" else ""
        )
        prompt = (
            "You are a Stigmergic Shazam engine. The Architect is watching a YouTube video.\n"
            f"{scene_ctx}"
            "Based on the STT transcript below, name the exact movie, show, song, artist, or news network. "
            "Reply with ONE short line only (e.g., 'Trainspotting (1996)'). "
            "If unrecognisable, reply 'Unknown Media'.\n\n"
            f"Transcript:\n{self.transcript[:800]}"
        )
        try:
            res = subprocess.run(
                ["ollama", "run", _MODEL, prompt],
                capture_output=True, text=True, timeout=12
            )
            guess = res.stdout.strip().splitlines()[0] if res.stdout.strip() else "Unknown Media"
        except Exception as e:
            guess = f"Error: {e}"

        self.result_ready.emit(guess, self.scene, self.confidence)


# ── Scene badge colours ────────────────────────────────────────────────────────
_SCENE_COLOUR = {
    "CINEMATIC": "#c678dd",
    "NEWS":      "#e06c75",
    "MUSIC":     "#66fcf1",
    "SPORTS":    "#e5c07b",
    "GAMING":    "#98c379",
    "PODCAST":   "#56b6c2",
    "AMBIENT":   "#61afef",
    "UNKNOWN":   "#5c6370",
}


class SiftaYoutubeShazam(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🎵 Stigmergic Shazam")
        self.resize(560, 380)
        self.setStyleSheet("""
            QWidget { background-color: #0b0c10; color: #c5c6c7; font-family: 'SF Pro Display', 'Helvetica Neue', sans-serif; }
            QTextEdit { background-color: #1f2833; border: 1px solid #2e3c4e; border-radius: 6px; padding: 6px; color: #a8b2bf; font-family: 'Menlo', monospace; font-size: 11px; }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(14, 14, 14, 14)

        # ── Header row ──────────────────────────────────────────────────────
        h_row = QHBoxLayout()
        header = QLabel("🎵 Stigmergic Unified Shazam")
        header.setFont(QFont("SF Pro Display", 17, QFont.Weight.Bold))
        header.setStyleSheet("color: #66fcf1;")
        h_row.addWidget(header)
        h_row.addStretch()

        self.scene_badge = QLabel("● LISTENING")
        self.scene_badge.setFont(QFont("Menlo", 11, QFont.Weight.Bold))
        self.scene_badge.setStyleSheet("color: #5c6370;")
        h_row.addWidget(self.scene_badge)
        layout.addLayout(h_row)

        # ── Separator ───────────────────────────────────────────────────────
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #2e3c4e;")
        layout.addWidget(sep)

        # ── Transcript ──────────────────────────────────────────────────────
        self.transcript_box = QTextEdit()
        self.transcript_box.setReadOnly(True)
        self.transcript_box.setPlaceholderText("Waiting for ambient media via STT gate…")
        self.transcript_box.setFixedHeight(140)
        layout.addWidget(self.transcript_box)

        # ── Guess ───────────────────────────────────────────────────────────
        self.guess_label = QLabel("Guess: —")
        self.guess_label.setFont(QFont("SF Pro Display", 15, QFont.Weight.Medium))
        self.guess_label.setStyleSheet("color: #45a29e; margin-top: 4px;")
        self.guess_label.setWordWrap(True)
        layout.addWidget(self.guess_label)

        # ── Receipt status ───────────────────────────────────────────────────
        self.receipt_label = QLabel("")
        self.receipt_label.setFont(QFont("Menlo", 9))
        self.receipt_label.setStyleSheet("color: #3d5a6e;")
        layout.addWidget(self.receipt_label)

        # ── State ────────────────────────────────────────────────────────────
        self.last_pos = 0
        self.buffer = ""
        self.last_update = time.time()
        self.current_scene = "UNKNOWN"
        self.current_scene_conf = 0.0
        self.shazam_thread: Optional[ShazamThread] = None

        # Fast-forward past existing log
        if _MEDIA_LOG.exists():
            self.last_pos = _MEDIA_LOG.stat().st_size

        # ── Timers ───────────────────────────────────────────────────────────
        self.poll_timer = QTimer(self); self.poll_timer.timeout.connect(self.poll_media_gate); self.poll_timer.start(800)
        self.scene_timer = QTimer(self); self.scene_timer.timeout.connect(self.update_scene); self.scene_timer.start(3000)

    # ── Scene classification refresh ─────────────────────────────────────────
    def update_scene(self):
        if not _SCENE_AVAILABLE:
            return
        try:
            frame = classify_scene()
            self.current_scene = frame.scene
            self.current_scene_conf = frame.confidence
            colour = _SCENE_COLOUR.get(frame.scene, "#5c6370")
            self.scene_badge.setText(f"● {frame.scene}  {frame.confidence:.0%}")
            self.scene_badge.setStyleSheet(f"color: {colour};")
        except Exception:
            pass

    # ── Media gate polling ────────────────────────────────────────────────────
    def poll_media_gate(self):
        if not _MEDIA_LOG.exists():
            return
        try:
            current_size = _MEDIA_LOG.stat().st_size
            if current_size < self.last_pos:
                self.last_pos = 0
            if current_size > self.last_pos:
                with _MEDIA_LOG.open("r", encoding="utf-8") as f:
                    f.seek(self.last_pos)
                    new_data = f.read()
                    self.last_pos = f.tell()
                for line in new_data.splitlines():
                    if not line.strip():
                        continue
                    try:
                        row = json.loads(line)
                        if row.get("route") == "ambient_media":
                            preview = row.get("text_preview", "").strip()
                            if preview:
                                self.buffer += " " + preview
                                self.last_update = time.time()
                                self._refresh_transcript()
                    except json.JSONDecodeError:
                        pass

            # Trigger guess after 5s of silence
            if self.buffer.strip() and (time.time() - self.last_update) > 5.0:
                if self.shazam_thread is None or not self.shazam_thread.isRunning():
                    self._trigger_shazam()
        except Exception as e:
            print(f"[Shazam] poll error: {e}")

    def _refresh_transcript(self):
        self.transcript_box.setPlainText(self.buffer.strip())
        self.transcript_box.moveCursor(self.transcript_box.textCursor().MoveOperation.End)

    def _trigger_shazam(self):
        self.guess_label.setText("Guess: 🧠 Thinking…")
        self.guess_label.setStyleSheet("color: #f2a900; margin-top: 4px;")
        transcript = self.buffer.strip()
        self.buffer = ""
        self.shazam_thread = ShazamThread(transcript, self.current_scene, self.current_scene_conf)
        self.shazam_thread.result_ready.connect(self._on_result)
        self.shazam_thread.start()

    def _on_result(self, guess: str, scene: str, confidence: float):
        colour = _SCENE_COLOUR.get(scene, "#66fcf1")
        self.guess_label.setText(f"Guess: {guess}")
        self.guess_label.setStyleSheet(f"color: {colour}; margin-top: 4px;")

        # ── Stigmergic receipt ───────────────────────────────────────────────
        rid = str(uuid.uuid4())
        receipt = {
            "kind": "cowatch_shazam_guess",
            "receipt_id": rid,
            "ts": time.time(),
            "guess": guess,
            "scene": scene,
            "scene_confidence": round(confidence, 4),
            "model": _MODEL,
            "truth_label": "COWATCH_SHAZAM_V1",
        }
        try:
            append_line_locked(_LEDGER, json.dumps(receipt, sort_keys=True) + "\n")
            self.receipt_label.setText(f"receipt {rid[:8]}… → cowatch_shazam_ledger.jsonl")
        except Exception:
            pass


def main():
    app = QApplication(sys.argv)
    win = SiftaYoutubeShazam()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
