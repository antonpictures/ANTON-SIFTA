#!/usr/bin/env python3
"""
Applications/sifta_voice_identity_widget.py
═══════════════════════════════════════════
Stigmergic Voice Identity Training Panel

The primary operator clicks RECORD → speaks (or lets audio play) → clicks STOP → 
picks a label → SAVE → receipt written to voice_identity_ledger.jsonl

Alice's swimmer chorus reads the ledger and learns in real time.

UI:
  ┌─────────────────────────────────────────┐
  │  🎙 Voice Identity Organ                │
  │  [●  RECORD]  [■  STOP]  [↺ CLEAR]     │
  │  ┌─────────────────────────────────────┐│
  │  │  waveform / level bar               ││
  │  └─────────────────────────────────────┘│
  │  Label:                                 │
  │  [🧑 Owner] [📺 YouTube] [📱 Phone]    │
  │  [🌿 Room]   [⌨️ Keyboard] [❓ Other]    │
  │  Note: ________________________  [SAVE] │
  │  ─────────────────────────────────────  │
  │  Exemplar bank:  Owner×4  YouTube×2…   │
  │  Live classification: [Owner  87%]      │
  └─────────────────────────────────────────┘
"""
from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path
from typing import Optional

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from PyQt6.QtCore import QThread, QTimer, pyqtSignal, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from System.swarm_voice_identity_organ import (
    LABELS,
    classify,
    exemplar_counts,
    extract_features,
    load_exemplars,
    write_exemplar,
)

_SAMPLE_RATE = 16000
_CHUNK = 1024


# ── Waveform display ─────────────────────────────────────────────────────────

class WaveformWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._levels: list[float] = [0.0] * 80
        self._recording = False
        self.setFixedHeight(60)
        self.setMinimumWidth(300)

    def push_level(self, level: float) -> None:
        self._levels.append(level)
        self._levels = self._levels[-80:]
        self.update()

    def set_recording(self, state: bool) -> None:
        self._recording = state

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#0d1117"))

        w, h = self.width(), self.height()
        cx = h // 2
        bar_w = w / len(self._levels)

        color = QColor("#ff3860") if self._recording else QColor("#00e5ff")
        pen = QPen(color, 1)
        p.setPen(pen)

        for i, level in enumerate(self._levels):
            x = int(i * bar_w)
            bar_h = int(level * cx * 0.9)
            p.drawLine(x, cx - bar_h, x, cx + bar_h)

        p.end()


# ── Audio recorder thread ─────────────────────────────────────────────────────

class RecorderThread(QThread):
    level_update = pyqtSignal(float)
    finished = pyqtSignal(object)  # emits np.ndarray

    def __init__(self):
        super().__init__()
        self._stop = False
        self._chunks: list[np.ndarray] = []

    def stop(self):
        self._stop = True

    def run(self):
        try:
            import sounddevice as sd
            from System.audio_ingress import resolve_default_owner_microphone

            mic_idx, _mic_name = resolve_default_owner_microphone(sd)
            mic_device = mic_idx if mic_idx >= 0 else None
            self._stop = False
            self._chunks = []

            def callback(indata, frames, time_info, status):
                chunk = indata[:, 0].copy() if indata.ndim > 1 else indata.copy()
                self._chunks.append(chunk)
                rms = float(np.sqrt(np.mean(chunk ** 2)))
                self.level_update.emit(min(rms * 8.0, 1.0))

            with sd.InputStream(device=mic_device, samplerate=_SAMPLE_RATE, channels=1,
                                 dtype="float32", blocksize=_CHUNK,
                                 callback=callback):
                while not self._stop:
                    time.sleep(0.05)

        except Exception as e:
            print(f"[VoiceIdentity] Recorder error: {e}")

        if self._chunks:
            audio = np.concatenate(self._chunks)
        else:
            audio = np.zeros(100, dtype=np.float32)
        self.finished.emit(audio)


# ── Live classifier thread ────────────────────────────────────────────────────

class LiveClassifierThread(QThread):
    result = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self._running = True

    def stop(self):
        self._running = False

    def run(self):
        try:
            import sounddevice as sd
        except Exception as e:
            print(f"[VoiceIdentity] sounddevice unavailable: {e}")
            return

        try:
            from System.audio_ingress import resolve_default_owner_microphone

            mic_idx, _mic_name = resolve_default_owner_microphone(sd)
            mic_device = mic_idx if mic_idx >= 0 else None
        except Exception:
            mic_device = None

        while self._running:
            try:
                with sd.InputStream(device=mic_device, samplerate=_SAMPLE_RATE, channels=1,
                                    dtype="float32", blocksize=0) as stream:
                    frames_needed = int(_SAMPLE_RATE * 1.5)
                    data, _ = stream.read(frames_needed)
                if not self._running:
                    break
                chunk = data[:, 0] if data.ndim > 1 else data.flatten()
                exemplars = load_exemplars()
                if len(exemplars) >= 2:
                    features = extract_features(chunk.astype(np.float32))
                    result = classify(features, exemplars)
                    self.result.emit(result)
            except Exception as e:
                # Don't crash if another stream is active (SIFTA audio pipeline)
                pass
            # Sleep between classification windows
            for _ in range(30):
                if not self._running:
                    return
                time.sleep(0.1)


# ── Label button ─────────────────────────────────────────────────────────────

class LabelButton(QPushButton):
    def __init__(self, key: str, info: dict, parent=None):
        emoji = info["emoji"]
        display = info["display"]
        super().__init__(f"{emoji}  {display}", parent)
        self._key = key
        self._color = info["color"]
        self._selected = False
        self._base_style = f"""
            QPushButton {{
                background: #1a1f2e;
                color: #8892a4;
                border: 1px solid #2a3040;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
                text-align: left;
            }}
            QPushButton:hover {{
                background: #1e2435;
                color: #b8c2d4;
                border: 1px solid {self._color}44;
            }}
        """
        self._selected_style = f"""
            QPushButton {{
                background: {self._color}22;
                color: {self._color};
                border: 2px solid {self._color};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
                font-weight: bold;
                text-align: left;
            }}
        """
        self.setStyleSheet(self._base_style)

    def set_selected(self, state: bool) -> None:
        self._selected = state
        self.setStyleSheet(self._selected_style if state else self._base_style)

    @property
    def key(self) -> str:
        return self._key


# ── Main widget ───────────────────────────────────────────────────────────────

class VoiceIdentityWidget(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🎙 Voice Identity Organ")
        self.setMinimumWidth(640)
        self.setMinimumHeight(720)
        self.resize(660, 760)

        self._recorder: Optional[RecorderThread] = None
        self._classifier: Optional[LiveClassifierThread] = None
        self._current_audio: Optional[np.ndarray] = None
        self._selected_label: str = "primary_operator"
        self._label_buttons: dict[str, LabelButton] = {}
        self._blink_state = False

        self._setup_ui()
        self._apply_style()
        self._refresh_counts()
        self._start_live_classifier()

        # Blink timer for recording indicator
        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._blink)
        self._blink_timer.start(500)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # ── Title ───────────────────────────────────────────────────────────
        title = QLabel("🎙  Voice Identity Organ")
        title.setObjectName("title")
        root.addWidget(title)

        subtitle = QLabel("Record audio → tag the source → Alice learns stigmergically")
        subtitle.setObjectName("subtitle")
        root.addWidget(subtitle)

        # ── Waveform ─────────────────────────────────────────────────────────
        self._waveform = WaveformWidget()
        root.addWidget(self._waveform)

        # ── Record controls ──────────────────────────────────────────────────
        ctrl = QHBoxLayout()
        self._rec_btn = QPushButton("●  RECORD")
        self._rec_btn.setObjectName("recBtn")
        self._rec_btn.clicked.connect(self._start_recording)
        ctrl.addWidget(self._rec_btn)

        self._stop_btn = QPushButton("■  STOP")
        self._stop_btn.setObjectName("stopBtn")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop_recording)
        ctrl.addWidget(self._stop_btn)

        self._clear_btn = QPushButton("↺  Clear")
        self._clear_btn.clicked.connect(self._clear)
        ctrl.addWidget(self._clear_btn)
        root.addLayout(ctrl)

        # ── Status ────────────────────────────────────────────────────────────
        self._status_label = QLabel("Ready — click RECORD and speak or let room audio play")
        self._status_label.setObjectName("status")
        self._status_label.setWordWrap(True)
        root.addWidget(self._status_label)

        # ── Label picker ──────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("sep")
        root.addWidget(sep)

        lbl_title = QLabel("2  Tag the audio source:")
        lbl_title.setObjectName("sectionTitle")
        root.addWidget(lbl_title)

        grid1 = QHBoxLayout()
        grid2 = QHBoxLayout()
        label_keys = list(LABELS.keys())
        for i, key in enumerate(label_keys):
            btn = LabelButton(key, LABELS[key])
            btn.clicked.connect(lambda checked, k=key: self._select_label(k))
            self._label_buttons[key] = btn
            if i < 3:
                grid1.addWidget(btn)
            else:
                grid2.addWidget(btn)
        root.addLayout(grid1)
        root.addLayout(grid2)
        self._select_label("primary_operator")

        # ── Note + Save ───────────────────────────────────────────────────────
        note_row = QHBoxLayout()
        note_lbl = QLabel("Note:")
        note_lbl.setFixedWidth(36)
        note_row.addWidget(note_lbl)
        self._note_edit = QLineEdit()
        self._note_edit.setPlaceholderText("optional note (e.g. 'noisy room', 'phone on desk')")
        note_row.addWidget(self._note_edit)
        root.addLayout(note_row)

        self._save_btn = QPushButton("✅  SAVE EXEMPLAR")
        self._save_btn.setObjectName("saveBtn")
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._save)
        root.addWidget(self._save_btn)

        # ── Exemplar bank ─────────────────────────────────────────────────────
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setObjectName("sep")
        root.addWidget(sep2)

        lbl3 = QLabel("Exemplar Bank (swimmer corpus)")
        lbl3.setObjectName("sectionTitle")
        root.addWidget(lbl3)

        self._counts_label = QLabel("No exemplars yet — record some samples!")
        self._counts_label.setObjectName("counts")
        self._counts_label.setWordWrap(True)
        root.addWidget(self._counts_label)

        # ── Live classification ───────────────────────────────────────────────
        sep3 = QFrame()
        sep3.setFrameShape(QFrame.Shape.HLine)
        sep3.setObjectName("sep")
        root.addWidget(sep3)

        lbl4 = QLabel("Live Room Classification (1.5 sec window)")
        lbl4.setObjectName("sectionTitle")
        root.addWidget(lbl4)

        self._live_label = QLabel("—  waiting for exemplars…")
        self._live_label.setObjectName("liveLabel")
        self._live_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._live_label)

        root.addStretch()

    def _apply_style(self):
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background: #0d1117;
                color: #c9d1d9;
                font-family: 'Menlo', 'JetBrains Mono', Consolas, monospace;
            }
            QLabel#title {
                font-size: 18px;
                font-weight: bold;
                color: #e6edf3;
            }
            QLabel#subtitle {
                font-size: 11px;
                color: #6e7681;
            }
            QLabel#sectionTitle {
                font-size: 12px;
                color: #8b949e;
                font-weight: bold;
                margin-top: 4px;
            }
            QLabel#status {
                font-size: 11px;
                color: #8b949e;
                padding: 6px;
                background: #161b22;
                border-radius: 6px;
            }
            QLabel#counts {
                font-size: 11px;
                color: #c9d1d9;
                padding: 8px;
                background: #161b22;
                border-radius: 6px;
            }
            QLabel#liveLabel {
                font-size: 16px;
                font-weight: bold;
                padding: 12px;
                background: #161b22;
                border-radius: 8px;
                border: 1px solid #30363d;
                color: #00e5ff;
            }
            QPushButton#recBtn {
                background: #1a1f2e;
                color: #ff3860;
                border: 2px solid #ff3860;
                border-radius: 8px;
                padding: 10px 16px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton#recBtn:hover { background: #ff386022; }
            QPushButton#stopBtn {
                background: #1a1f2e;
                color: #8892a4;
                border: 2px solid #30363d;
                border-radius: 8px;
                padding: 10px 16px;
                font-size: 13px;
            }
            QPushButton#stopBtn:enabled {
                color: #ffa500;
                border-color: #ffa500;
            }
            QPushButton#saveBtn {
                background: #1a3320;
                color: #3fb950;
                border: 2px solid #3fb950;
                border-radius: 8px;
                padding: 10px 16px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton#saveBtn:disabled {
                background: #161b22;
                color: #3d4249;
                border-color: #30363d;
            }
            QPushButton#saveBtn:hover:enabled { background: #3fb95022; }
            QPushButton {
                background: #1a1f2e;
                color: #8892a4;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
            }
            QPushButton:hover { color: #c9d1d9; border-color: #484f58; }
            QLineEdit {
                background: #161b22;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }
            QLineEdit:focus { border-color: #388bfd; }
            QFrame#sep { color: #21262d; }
        """)

    def _select_label(self, key: str):
        self._selected_label = key
        for k, btn in self._label_buttons.items():
            btn.set_selected(k == key)

    def _start_recording(self):
        self._current_audio = None
        self._save_btn.setEnabled(False)
        self._rec_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._status_label.setText("🔴  Recording… click STOP when done")
        self._waveform.set_recording(True)

        self._recorder = RecorderThread()
        self._recorder.level_update.connect(self._waveform.push_level)
        self._recorder.finished.connect(self._on_recording_done)
        self._recorder.start()

    def _stop_recording(self):
        if self._recorder:
            self._recorder.stop()
        self._stop_btn.setEnabled(False)
        self._status_label.setText("⏳  Processing audio…")

    def _on_recording_done(self, audio: np.ndarray):
        self._waveform.set_recording(False)
        self._rec_btn.setEnabled(True)
        dur = len(audio) / _SAMPLE_RATE
        if dur < 0.3:
            self._status_label.setText("⚠️  Too short — record at least 0.5 seconds")
            return
        self._current_audio = audio
        self._save_btn.setEnabled(True)
        self._status_label.setText(
            f"✅  Recorded {dur:.1f}s — now pick a label and click SAVE EXEMPLAR"
        )

    def _save(self):
        if self._current_audio is None:
            return
        features = extract_features(self._current_audio)
        note = self._note_edit.text().strip()
        row = write_exemplar(features, self._selected_label, note=note)
        label_info = LABELS.get(self._selected_label, LABELS["unknown"])
        dur = features.get("duration_s", 0.0)
        self._status_label.setText(
            f"💾  Saved {label_info['emoji']} {label_info['display']} exemplar "
            f"({dur:.1f}s) → receipt in voice_identity_ledger.jsonl"
        )
        self._current_audio = None
        self._save_btn.setEnabled(False)
        self._note_edit.clear()
        self._refresh_counts()

    def _clear(self):
        self._current_audio = None
        self._save_btn.setEnabled(False)
        self._waveform._levels = [0.0] * 80
        self._waveform.update()
        self._status_label.setText("Cleared — ready to record")

    def _refresh_counts(self):
        counts = exemplar_counts()
        if not counts:
            self._counts_label.setText("No exemplars yet — record some samples!")
            return
        parts = []
        for key, info in LABELS.items():
            if key == "unknown":
                continue
            n = counts.get(key, 0)
            if n > 0:
                parts.append(f"{info['emoji']} {info['display']}: {n}")
            else:
                parts.append(f"  {info['display']}: 0")
        total = sum(counts.values())
        self._counts_label.setText("  ·  ".join(parts) + f"\n  Total: {total} exemplars")

    def _start_live_classifier(self):
        self._classifier = LiveClassifierThread()
        self._classifier.result.connect(self._on_live_result)
        self._classifier.start()

    def _on_live_result(self, result: dict):
        label = result.get("label", "unknown")
        conf = result.get("confidence", 0.0)
        n = result.get("n_exemplars", 0)
        if n == 0:
            self._live_label.setText("—  no exemplars yet")
            return
        info = LABELS.get(label, LABELS["unknown"])
        votes = result.get("votes", {})
        vote_str = "  ".join(
            f"{LABELS.get(k, LABELS['unknown'])['emoji']} {int(v*100)}%"
            for k, v in list(votes.items())[:3]
        )
        pct = int(conf * 100)
        color = info["color"]
        self._live_label.setText(
            f"{info['emoji']}  {info['display']}  —  {pct}% confident\n{vote_str}"
        )
        self._live_label.setStyleSheet(
            f"font-size: 15px; font-weight: bold; padding: 12px; "
            f"background: {color}18; border-radius: 8px; "
            f"border: 2px solid {color}88; color: {color};"
        )

    def _blink(self):
        if self._recorder and self._recorder.isRunning():
            self._blink_state = not self._blink_state
            if self._blink_state:
                self._rec_btn.setStyleSheet(
                    "QPushButton { background: #ff3860; color: white; "
                    "border: 2px solid #ff3860; border-radius: 8px; "
                    "padding: 10px 16px; font-size: 13px; font-weight: bold; }"
                )
            else:
                self._rec_btn.setStyleSheet(
                    "QPushButton { background: #ff386022; color: #ff3860; "
                    "border: 2px solid #ff3860; border-radius: 8px; "
                    "padding: 10px 16px; font-size: 13px; font-weight: bold; }"
                )

    def closeEvent(self, event):
        if self._recorder:
            self._recorder.stop()
        if self._classifier:
            self._classifier.stop()
        super().closeEvent(event)


# ── App manifest entry ────────────────────────────────────────────────────────
APP_MANIFEST = {
    "app_id": "sifta_voice_identity_widget",
    "name": "Voice Identity Organ",
    "description": "Stigmergic voice tagging: record audio → label source → Alice learns (owner/YouTube/Phone/Room)",
    "emoji": "🎙",
    "category": "Sensing",
    "autostart": False,
}

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = VoiceIdentityWidget()
    w.show()
    sys.exit(app.exec())
