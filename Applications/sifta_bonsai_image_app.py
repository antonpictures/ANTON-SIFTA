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

import json
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

        # r746 — George's order: "leave only one button generate another export jpg
        # and only one box to type the text, simple." One box, two buttons.
        # The teach contract survives underneath: label + meaning derive from the
        # prompt, so every image still lands in Alice's field with her lesson.
        self.prompt = QLineEdit()
        self.prompt.setPlaceholderText("Type what you want to see — Generate does the rest")
        root.addWidget(self.prompt)

        self._seed = 42  # internal; the receipt still carries it
        self._last_image_path = ""
        self._last_trace_ts = 0.0  # r747: 0 on open → newest field render shows on first tick (§1.A history-is-identity)

        ctl_row = QHBoxLayout()
        self.generate_btn = QPushButton("Generate")
        self.generate_btn.clicked.connect(self._on_generate)
        ctl_row.addWidget(self.generate_btn)
        self.export_btn = QPushButton("Export JPG")
        self.export_btn.clicked.connect(self._on_export_jpg)
        ctl_row.addWidget(self.export_btn)
        ctl_row.addStretch(1)
        root.addLayout(ctl_row)

        self.status = QLabel("Ready. Type a prompt, hit Generate.")
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
        self._idle_timer.setInterval(5_000)  # r747: also polls the visual field; chat renders appear within ~5s
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

    def _check_field_for_new_renders(self) -> None:
        """r747 — the open app is a WINDOW into Alice's visual field (§1.A).

        When Cole (or any owner) crafts an image in conversation and tells
        Alice 'bonsai a photo of …', her chat hand fires the same organ this
        app's Generate button calls. This watch tails the organ's own ledger
        (bonsai_image_trace.jsonl) so that render appears HERE too — image on
        the glass, her prompt mirrored into the box, Export JPG live. One
        organ, many hands, one visible field.
        """
        try:
            trace_path = _REPO / ".sifta_state" / "bonsai_image_trace.jsonl"
            if not trace_path.exists():
                return
            with open(trace_path, "rb") as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                f.seek(max(0, size - 65536))
                lines = [ln for ln in f.read().decode("utf-8", "replace").splitlines() if ln.strip()]
            if not lines:
                return
            row = json.loads(lines[-1])
            ts = float(row.get("ts") or 0)
            path = str(row.get("image_path") or "")
            if ts <= self._last_trace_ts or not path or path == self._last_image_path:
                self._last_trace_ts = max(self._last_trace_ts, ts)
                return
            if not Path(path).exists():
                return
            pix = QPixmap(path)
            if pix.isNull():
                return
            self._last_trace_ts = ts
            self._last_image_path = path
            self.image.setPixmap(
                pix.scaled(self.image.width(), self.image.height(),
                           Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
            )
            prompt = str(row.get("prompt") or "")
            if prompt:
                self.prompt.setText(prompt)
            self.status.setText(
                f"Alice rendered this from the field: '{str(row.get('owner_label') or '')}' "
                f"(receipt {str(row.get('receipt_id') or '?')[:12]}). Export JPG is live."
            )
        except Exception:
            pass

    def _idle_tick(self) -> None:
        self._check_field_for_new_renders()
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
                "Idle. No Bonsai generation is running; Generate when you want work."
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
        # r746 — label + meaning derive from the prompt: Alice still learns
        # every image, George types one thing.
        words = [w.strip(".,!?\"'()[]") for w in prompt.split() if w.strip(".,!?\"'()[]")]
        owner_label = "-".join(words[:4]).lower() or "untitled"
        meaning = prompt
        self.generate_btn.setEnabled(False)
        self.status.setText("Rendering on-device (ternary MLX, ~6s for 512²)… teaching Alice on landing.")
        self._worker = _BonsaiWorker(prompt, owner_label, meaning, int(self._seed), parent=self)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_export_jpg(self) -> None:
        """r746 — Export the last generated image as JPG to the Desktop."""
        self._mark_active()
        src = str(self._last_image_path or "")
        if not src or not Path(src).exists():
            self.status.setText("Nothing to export yet — Generate first.")
            return
        pix = QPixmap(src)
        if pix.isNull():
            self.status.setText(f"Export failed: could not read {src}")
            return
        dest_dir = Path.home() / "Desktop"
        if not dest_dir.exists():
            dest_dir = Path(src).parent
        dest = dest_dir / f"bonsai_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
        if pix.save(str(dest), "JPG", 92):
            self.status.setText(f"Exported JPG: {dest}")
        else:
            self.status.setText(f"Export failed writing {dest}")

    def accept_generated_image_from_chat(
        self,
        *,
        prompt: str,
        image_path: str,
        trace: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Mirror a Talk-driven Bonsai generation into the open app surface.

        The real generation still happens through System.swarm_bonsai_image_organ,
        which writes the visual-field receipts. This method keeps the UI body in
        sync: one prompt box shows what Alice generated, the image panel displays
        it, and Export JPG becomes available without asking the owner to repeat.
        """
        self._mark_active()
        trace = trace if isinstance(trace, dict) else {}
        self.prompt.setText(str(prompt or ""))
        self._last_image_path = str(image_path or "")
        pix = QPixmap(self._last_image_path)
        if not pix.isNull():
            self.image.setPixmap(
                pix.scaled(self.image.width(), self.image.height(),
                           Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
            )
        self.status.setText(
            f"Talk generated and taught Alice: '{trace.get('owner_label', 'chat request')}' — "
            f"{trace.get('meaning', prompt)}  "
            f"(OBSERVED_AI_GENERATED, sha8={trace.get('sha8', '?')}). Export JPG is ready."
        )
        try:
            self.show(); self.raise_(); self.activateWindow()
        except Exception:
            pass
        return {"ok": True, "mirrored": True, "image_path": self._last_image_path}

    def _on_done(self, result: Dict[str, Any]) -> None:
        self._mark_active()
        self.generate_btn.setEnabled(True)
        self._worker = None
        if not result.get("ok"):
            self.status.setText(f"Did not generate: {result.get('error', 'unknown error')}")
            return
        path = result.get("image_path", "")
        self._last_image_path = str(path or "")
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
