#!/usr/bin/env python3
"""Applications/sifta_bonsai_image_app.py — Bonsai Image Studio (AI Vision).

A SIFTA OS surface over System.swarm_bonsai_image_organ. The owner types a
prompt + a stigmergic teaching label/meaning, hits Generate & Teach, and the
ternary MLX backend renders an image on Apple Silicon. The result is deposited
into Alice's visual_stigmergy lane tagged OBSERVED_AI_GENERATED (§7.16 — labeled
provenance, never a faked camera scene), with the owner's meaning attached so
Alice learns what the image IS.

Generation runs in a worker QThread, never on the GUI thread (the r150/r205
beachball lesson): a 512² render is ~6s and must not freeze the desktop.

Single-instance per §7.6.2.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QSpinBox, QFrame,
)

_REPO = Path(__file__).resolve().parent.parent
_IDLE_AFTER_ENV = "SIFTA_BONSAI_IDLE_AFTER_S"


def _idle_after_seconds() -> float:
    raw = os.environ.get(_IDLE_AFTER_ENV, "90").strip()
    try:
        return max(10.0, float(raw))
    except ValueError:
        return 90.0


class _BonsaiWorker(QThread):
    """Run generate_and_teach off the GUI thread."""
    done = pyqtSignal(dict)

    def __init__(self, prompt: str, owner_label: str, meaning: str, seed: int,
                 parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._prompt = prompt
        self._owner_label = owner_label
        self._meaning = meaning
        self._seed = seed

    def run(self) -> None:
        try:
            from System.swarm_bonsai_image_organ import generate_and_teach
            result = generate_and_teach(
                self._prompt, self._owner_label, self._meaning, seed=self._seed
            )
        except Exception as exc:  # noqa: BLE001
            result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        self.done.emit(result if isinstance(result, dict) else {"ok": False, "error": "no result"})


class _BonsaiComposeWorker(QThread):
    """Run ant+cortex prompt composition off the GUI thread."""
    done = pyqtSignal(dict)

    def __init__(self, seed: int, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._seed = seed

    def run(self) -> None:
        try:
            from System.swarm_bonsai_image_organ import compose_bonsai_ant_cortex
            result = compose_bonsai_ant_cortex(seed=self._seed, timeout_s=45)
        except Exception as exc:  # noqa: BLE001
            result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        self.done.emit(result if isinstance(result, dict) else {"ok": False, "error": "no result"})


class BonsaiImageStudioApp(QWidget):
    _live_instance: "Optional[BonsaiImageStudioApp]" = None
    _initialized_instance_ids: set[int] = set()

    def __new__(cls, *args, **kwargs):
        existing = cls._live_instance
        if existing is not None:
            try:
                _ = existing.isVisible()
                if id(existing) not in cls._initialized_instance_ids:
                    cls._live_instance = None
                else:
                    try:
                        existing.show(); existing.raise_(); existing.activateWindow()
                    except Exception:
                        pass
                    return existing
            except RuntimeError:
                cls._live_instance = None
        return super().__new__(cls)

    @classmethod
    def _clear_live_instance(cls, instance_id: int) -> None:
        cls._initialized_instance_ids.discard(instance_id)
        existing = cls._live_instance
        if existing is not None and id(existing) == instance_id:
            cls._live_instance = None

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        if id(self) in type(self)._initialized_instance_ids:
            return
        super().__init__(parent)
        type(self)._live_instance = self
        type(self)._initialized_instance_ids.add(id(self))
        self._worker: Optional[_BonsaiWorker] = None
        self._compose_worker: Optional[_BonsaiComposeWorker] = None
        self._idle_after_s = _idle_after_seconds()
        self._last_user_action_s = time.monotonic()

        self.setWindowTitle("Bonsai Image Studio")
        root = QVBoxLayout(self)

        title = QLabel("🌳 Bonsai Image Studio — generate AI images, teach Alice what they are")
        title.setStyleSheet("color: rgb(238,244,255); font-size: 15px; font-weight: bold;")
        root.addWidget(title)

        hint = QLabel(
            "Ternary MLX (on-device, Apple Silicon). The image lands in Alice's visual field "
            "tagged OBSERVED_AI_GENERATED with your meaning — she learns it, never mistakes it "
            "for a real camera scene."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: rgb(150,153,180); font-size: 11px;")
        root.addWidget(hint)

        self.prompt = QLineEdit()
        self.prompt.setPlaceholderText("Prompt — e.g. A bonsai tree in a quiet ceramic studio, soft morning light")
        root.addWidget(self.prompt)

        teach_row = QHBoxLayout()
        self.owner_label = QLineEdit()
        self.owner_label.setPlaceholderText("Stigmergic label — e.g. bonsai-in-studio")
        self.meaning = QLineEdit()
        self.meaning.setPlaceholderText("Meaning to teach — e.g. a small cultivated tree, calm, craft, patience")
        teach_row.addWidget(self.owner_label)
        teach_row.addWidget(self.meaning)
        root.addLayout(teach_row)

        ctl_row = QHBoxLayout()
        ctl_row.addWidget(QLabel("Seed:"))
        self.seed = QSpinBox()
        self.seed.setRange(0, 2_147_483_647)
        self.seed.setValue(42)
        ctl_row.addWidget(self.seed)
        self.compose_btn = QPushButton("Ant Cortex Compose")
        self.compose_btn.clicked.connect(self._on_compose)
        ctl_row.addWidget(self.compose_btn)
        self.generate_btn = QPushButton("Generate & Teach")
        self.generate_btn.clicked.connect(self._on_generate)
        ctl_row.addWidget(self.generate_btn)
        ctl_row.addStretch(1)
        root.addLayout(ctl_row)

        self.status = QLabel("Ready. Compose from the field, or type a prompt + meaning, then Generate & Teach.")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color: rgb(150,153,180); font-size: 11px;")
        root.addWidget(self.status)

        self.image = QLabel()
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image.setMinimumHeight(360)
        self.image.setFrameShape(QFrame.Shape.StyledPanel)
        self.image.setText("(generated image appears here)")
        self.image.setStyleSheet("color: rgb(112,122,150);")
        root.addWidget(self.image, stretch=1)

        self._idle_timer = QTimer(self)
        self._idle_timer.setInterval(15_000)
        self._idle_timer.timeout.connect(self._idle_tick)
        self._idle_timer.start()

    def _mark_active(self) -> None:
        self._last_user_action_s = time.monotonic()

    def _has_running_worker(self) -> bool:
        return bool(
            (self._worker is not None and self._worker.isRunning())
            or (self._compose_worker is not None and self._compose_worker.isRunning())
        )

    def _backend_preflight_error(self) -> str:
        try:
            from System.swarm_bonsai_image_organ import bonsai_backend_status

            status = bonsai_backend_status()
        except Exception as exc:  # noqa: BLE001
            return f"backend preflight failed: {type(exc).__name__}: {exc}"
        if status.get("ok"):
            return ""
        return str(status.get("error") or "Bonsai backend is not ready.")

    def _idle_tick(self) -> None:
        if self._worker is not None and not self._worker.isRunning():
            self._worker = None
        if self._compose_worker is not None and not self._compose_worker.isRunning():
            self._compose_worker = None
        if self._has_running_worker():
            return
        if (time.monotonic() - self._last_user_action_s) < self._idle_after_s:
            return
        if not self.status.text().startswith("Idle."):
            self.status.setText(
                "Idle. No Bonsai generation is running; Compose or Generate when you want work."
            )

    def mark_idle_from_desktop(
        self,
        *,
        reason: str = "",
        desktop_mode: str = "",
        app_name: str = "",
    ) -> Dict[str, Any]:
        """Called by the desktop when the owner returns to global chat."""
        running = self._has_running_worker()
        if running:
            self.status.setText(
                "Chat focus: Bonsai has background work running; it will settle to idle on completion."
            )
            return {"ok": True, "idle": False, "running": True, "reason": reason}
        self._worker = None
        self._compose_worker = None
        self._last_user_action_s = time.monotonic() - self._idle_after_s - 1.0
        self.status.setText(
            "Idle. Bonsai remains open in the background while the owner is in chat; no generation is running."
        )
        return {
            "ok": True,
            "idle": True,
            "running": False,
            "reason": reason,
            "desktop_mode": desktop_mode,
            "app_name": app_name,
        }

    def _on_compose(self) -> None:
        if self._compose_worker is not None and self._compose_worker.isRunning():
            return
        self._mark_active()
        self.compose_btn.setEnabled(False)
        self.status.setText("Ants sampling visual pheromones; Alice cortex selecting a teachable prompt…")
        self._compose_worker = _BonsaiComposeWorker(int(self.seed.value()), parent=self)
        self._compose_worker.done.connect(self._on_compose_done)
        self._compose_worker.start()

    def _on_compose_done(self, result: Dict[str, Any]) -> None:
        self._mark_active()
        self.compose_btn.setEnabled(True)
        self._compose_worker = None
        if not result.get("ok"):
            self.status.setText(f"Ant Cortex Compose did not select a prompt: {result.get('error', 'unknown error')}")
            return
        selected = result.get("selected", {}) if isinstance(result.get("selected"), dict) else {}
        prompt = str(selected.get("prompt") or "").strip()
        owner_label = str(selected.get("owner_label") or "").strip()
        meaning = str(selected.get("meaning") or "").strip()
        if prompt:
            self.prompt.setText(prompt)
        if owner_label:
            self.owner_label.setText(owner_label)
        if meaning:
            self.meaning.setText(meaning)
        rationale = str(selected.get("rationale") or "").strip()
        self.status.setText(
            "Ants sampled field → cortex selected/refined. "
            f"{rationale[:220]} Trace: {result.get('receipt_id', '?')}"
        )

    def _on_generate(self) -> None:
        self._mark_active()
        prompt = self.prompt.text().strip()
        if not prompt:
            self.status.setText("Type a prompt first.")
            return
        if self._worker is not None and self._worker.isRunning():
            return
        preflight_error = self._backend_preflight_error()
        if preflight_error:
            self.status.setText(f"Idle. Bonsai generation backend is not ready: {preflight_error}")
            return
        owner_label = self.owner_label.text().strip() or "untitled"
        meaning = self.meaning.text().strip()
        self.generate_btn.setEnabled(False)
        self.status.setText("Rendering on-device (ternary MLX, ~6s for 512²)… teaching Alice on landing.")
        self._worker = _BonsaiWorker(prompt, owner_label, meaning, int(self.seed.value()), parent=self)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, result: Dict[str, Any]) -> None:
        self._mark_active()
        self.generate_btn.setEnabled(True)
        self._worker = None
        if not result.get("ok"):
            self.status.setText(f"Did not generate: {result.get('error', 'unknown error')}")
            return
        path = result.get("image_path", "")
        trace = result.get("trace", {}) if isinstance(result.get("trace"), dict) else {}
        pix = QPixmap(path)
        if not pix.isNull():
            self.image.setPixmap(
                pix.scaled(self.image.width(), self.image.height(),
                           Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
            )
        self.status.setText(
            f"Taught Alice: '{trace.get('owner_label', '')}' — {trace.get('meaning', '')}  "
            f"(OBSERVED_AI_GENERATED, sha8={trace.get('sha8', '?')}). Saved: {path}"
        )

    def closeEvent(self, event) -> None:  # noqa: ANN001
        if hasattr(self, "_idle_timer"):
            self._idle_timer.stop()
        type(self)._clear_live_instance(id(self))
        super().closeEvent(event)
