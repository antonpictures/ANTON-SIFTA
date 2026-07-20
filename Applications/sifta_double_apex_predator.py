#!/usr/bin/env python3
"""Double Apex Predator — one app for both predator surfaces + dual doctors.

Tabs:
  1. Perceiver  — Event 71 attention bottleneck (was Apex Predator Perceiver)
  2. Field      — Predator v7 organ canvas + status (was Apex Predator Background)
  3. Doctors    — Codex + Claude on one shared local Ollama cortex

One body. Two hunt modes. Dual doctor arms. Glass + receipts.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.sifta_base_widget import SiftaBaseWidget  # noqa: E402
from System.swarm_double_apex import (  # noqa: E402
    DEFAULT_LOCAL_MODEL,
    TRUTH_LABEL,
    doctor_status,
    launch_both,
    launch_doctor,
    list_local_models,
    pick_default_model,
)

try:
    from System.swarm_app_focus import publish_focus as _publish_focus
except Exception:
    _publish_focus = None  # type: ignore[assignment]

APP_TITLE = "Apex Predator"
APP_ID = "sifta_apex_predator"

_BG = "#050810"
_GOLD = "#ffe298"
_CYAN = "#00d4ff"
_GREEN = "#00ff88"
_DIM = "#8b98b0"
_CARD = "#0c1220"


def _focus(detail: str) -> None:
    if _publish_focus is None:
        return
    try:
        _publish_focus(APP_TITLE, detail, app_id=APP_ID)
    except Exception:
        pass


class _DoctorsPane(QWidget):
    """Launch Codex App + Claude Code against one local Ollama model."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            f"QWidget {{ background: {_BG}; color: #e8eef8; }}"
            f"QComboBox {{ background: {_CARD}; border: 1px solid #2a3548; "
            f"padding: 8px; border-radius: 6px; color: #e8eef8; }}"
            f"QPushButton {{ background: #141a28; color: #e8eef8; "
            f"border: 1px solid #3a4a63; padding: 10px 16px; border-radius: 6px; }}"
            f"QPushButton:hover {{ border-color: {_CYAN}; }}"
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(12)

        head = QLabel("DUAL APEX DOCTORS  ·  one local cortex, two arms")
        head.setFont(QFont("Menlo", 12, QFont.Weight.Bold))
        head.setStyleSheet(f"color: {_GOLD};")
        root.addWidget(head)

        blurb = QLabel(
            "Honest wiring (2026-07):\n"
            "• Claude Code + local Ollama = works (Anthropic-compatible messages API).\n"
            "• Codex App + local Ollama = often broken: Codex only speaks Responses API; "
            "Ollama /v1/responses hangs → you see 'high demand' / Reconnecting 5/5.\n"
            "• If Codex is stuck: run `ollama launch codex-app --restore` then fully quit & reopen Codex "
            "(cloud gpt-5.5). Prefer Claude Code for Nightshift Heretic locally.\n"
            "• Default model: Nightshift 27B if installed. Not cloud Claude unless you pick a cloud tag."
        )
        blurb.setWordWrap(True)
        blurb.setStyleSheet(f"color: {_DIM}; font-size: 11px;")
        root.addWidget(blurb)

        warn = QLabel(
            "Recommended local path: Launch Claude Code  ·  "
            "Keep Codex App on cloud (restore) unless Ollama gains working /v1/responses."
        )
        warn.setWordWrap(True)
        warn.setStyleSheet(f"color: {_GOLD}; font-size: 11px; font-weight: 700;")
        root.addWidget(warn)

        row = QHBoxLayout()
        row.addWidget(QLabel("Model"))
        self.model_box = QComboBox()
        self.model_box.setMinimumWidth(420)
        self.model_box.setEditable(True)
        row.addWidget(self.model_box, 1)
        refresh = QPushButton("Refresh models")
        refresh.clicked.connect(self.reload_models)
        row.addWidget(refresh)
        root.addLayout(row)

        btns = QHBoxLayout()
        b_codex = QPushButton("Launch Codex App")
        b_codex.setStyleSheet(
            f"QPushButton {{ border-color: {_CYAN}; color: {_CYAN}; font-weight: 700; }}"
        )
        b_codex.clicked.connect(lambda: self._launch("codex_app"))
        b_cli = QPushButton("Launch Codex CLI")
        b_cli.clicked.connect(lambda: self._launch("codex_cli"))
        b_claude = QPushButton("Launch Claude Code")
        b_claude.setStyleSheet(
            f"QPushButton {{ border-color: #f07178; color: #f07178; font-weight: 700; }}"
        )
        b_claude.clicked.connect(lambda: self._launch("claude"))
        b_both = QPushButton("Launch BOTH (double apex)")
        b_both.setStyleSheet(
            f"QPushButton {{ border-color: {_GOLD}; color: {_GOLD}; font-weight: 700; }}"
        )
        b_both.clicked.connect(self._launch_both)
        btns.addWidget(b_codex)
        btns.addWidget(b_cli)
        btns.addWidget(b_claude)
        btns.addWidget(b_both)
        root.addLayout(btns)

        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setStyleSheet(
            f"background: {_CARD}; color: {_GREEN}; border: 1px solid #1e2636; "
            "padding: 12px; border-radius: 8px; font-family: Menlo; font-size: 11px;"
        )
        root.addWidget(self.status)
        root.addStretch(1)

        self.reload_models()
        self._paint_status()

    def _selected_model(self) -> str:
        return (self.model_box.currentText() or DEFAULT_LOCAL_MODEL).strip()

    def reload_models(self) -> None:
        info = list_local_models()
        models = list(info.get("models") or [])
        cur = self._selected_model()
        self.model_box.blockSignals(True)
        self.model_box.clear()
        if models:
            self.model_box.addItems(models)
            pick = pick_default_model(models)
            idx = self.model_box.findText(pick)
            if idx >= 0:
                self.model_box.setCurrentIndex(idx)
            elif cur:
                self.model_box.setEditText(cur)
            else:
                self.model_box.setEditText(pick)
        else:
            self.model_box.setEditText(DEFAULT_LOCAL_MODEL)
        self.model_box.blockSignals(False)
        self._paint_status(extra=f"models ok={info.get('ok')} n={len(models)}")

    def _paint_status(self, extra: str = "", last: Optional[dict] = None) -> None:
        st = doctor_status()
        bits = [
            f"ollama={'✓' if st['ollama'] else '✗'}  "
            f"codex={'✓' if st['codex'] else '✗'}  "
            f"claude={'✓' if st['claude'] else '✗'}",
            f"model → {self._selected_model()}",
            f"truth {TRUTH_LABEL}",
        ]
        if extra:
            bits.append(extra)
        if last:
            bits.append(
                f"last: ok={last.get('ok')} arm={last.get('arm', last.get('event', '—'))} "
                f"pid={last.get('pid', '—')} reason={last.get('reason', '')}"
            )
        self.status.setText("\n".join(bits))

    def _launch(self, arm: str) -> None:
        model = self._selected_model()
        r = launch_doctor(arm, model=model, cwd=_REPO)
        color = _GREEN if r.get("ok") else "#f07178"
        self.status.setStyleSheet(
            f"background: {_CARD}; color: {color}; border: 1px solid #1e2636; "
            "padding: 12px; border-radius: 8px; font-family: Menlo; font-size: 11px;"
        )
        self._paint_status(last=r)
        _focus(f"launch {arm} · {model}")

    def _launch_both(self) -> None:
        model = self._selected_model()
        r = launch_both(model=model, cwd=_REPO)
        color = _GREEN if r.get("ok") else "#f07178"
        self.status.setStyleSheet(
            f"background: {_CARD}; color: {color}; border: 1px solid #1e2636; "
            "padding: 12px; border-radius: 8px; font-family: Menlo; font-size: 11px;"
        )
        self._paint_status(
            last={
                "ok": r.get("ok"),
                "arm": "both",
                "pid": (
                    f"codex={((r.get('codex_app') or {}).get('pid'))} "
                    f"claude={((r.get('claude') or {}).get('pid'))}"
                ),
                "reason": (
                    ""
                    if r.get("ok")
                    else f"codex={((r.get('codex_app') or {}).get('reason'))} "
                    f"claude={((r.get('claude') or {}).get('reason'))}"
                ),
            }
        )
        _focus(f"launch BOTH · {model}")


class _FieldPane(QWidget):
    """Predator v7 canvas + organ panel side by side."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        try:
            from Applications.sifta_predator_desktop_bg import (
                OrganStatusPanel,
                PredatorDesktopBg,
            )

            self.bg = PredatorDesktopBg(self)
            self.panel = OrganStatusPanel(self)
            root.addWidget(self.bg, 5)
            root.addWidget(self.panel, 1)
        except Exception as exc:
            err = QLabel(f"Field pane failed to load: {type(exc).__name__}: {exc}")
            err.setWordWrap(True)
            err.setStyleSheet(f"color: #f07178; padding: 20px;")
            root.addWidget(err)


class DoubleApexPredatorWidget(SiftaBaseWidget):
    """United predator surface — Perceiver + Field + Dual Doctors."""

    APP_NAME = APP_TITLE
    _live_instance: Optional["DoubleApexPredatorWidget"] = None
    _initialized_ids: set[int] = set()

    def __new__(cls, *args, **kwargs):
        existing = cls._live_instance
        if existing is not None:
            try:
                if id(existing) in cls._initialized_ids:
                    existing.show()
                    existing.raise_()
                    existing.activateWindow()
                    return existing
            except RuntimeError:
                cls._live_instance = None
        return super().__new__(cls)

    def __init__(self, parent=None) -> None:
        if id(self) in type(self)._initialized_ids:
            return
        # SiftaBaseWidget may call build_ui from super().__init__
        self._tabs_ready = False
        super().__init__(parent)
        type(self)._live_instance = self
        type(self)._initialized_ids.add(id(self))
        self.setWindowTitle(f"🦅 {APP_TITLE}")
        self.setMinimumSize(1000, 680)
        self.resize(1180, 760)
        _focus("double apex open — perceiver + field + doctors")

    def build_ui(self, layout: QVBoxLayout) -> None:
        if self._tabs_ready:
            return
        self._tabs_ready = True

        title = QLabel("🦅  APEX PREDATOR  ·  one body · Perceiver · Field · Doctors")
        title.setFont(QFont("Menlo", 12, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {_CYAN};")
        layout.addWidget(title)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(
            f"QTabWidget::pane {{ border: 1px solid #1e2636; border-radius: 6px; }}"
            f"QTabBar::tab {{ background: #0c1220; color: {_DIM}; padding: 8px 16px; }}"
            f"QTabBar::tab:selected {{ color: {_GOLD}; border-bottom: 2px solid {_GOLD}; }}"
        )

        # Tab 1 — Perceiver (Event 71)
        try:
            from Applications.sifta_apex_predator_widget import ApexPredatorWidget

            # Embed without singleton fights: construct as child
            perceiver = ApexPredatorWidget(self)
            # If ApexPredatorWidget is also a singleton-ish base, still embed UI
            self.tabs.addTab(perceiver, "Perceiver · Event 71")
        except Exception as exc:
            fail = QLabel(f"Perceiver load failed: {exc}")
            fail.setWordWrap(True)
            fail.setStyleSheet("color: #f07178; padding: 16px;")
            self.tabs.addTab(fail, "Perceiver · Event 71")

        # Tab 2 — Field
        self.tabs.addTab(_FieldPane(self), "Field · Predator v7")

        # Tab 3 — Doctors
        self.tabs.addTab(_DoctorsPane(self), "Doctors · Codex + Claude")

        layout.addWidget(self.tabs, 1)
        self.set_status(
            f"{TRUTH_LABEL} · united apex surfaces · local doctor launch ready"
        )

        # Soft status refresh
        self._status_timer = QTimer(self)
        self._status_timer.setInterval(8000)
        self._status_timer.timeout.connect(self._pulse_status)
        self._status_timer.start()

    def _pulse_status(self) -> None:
        st = doctor_status()
        n_models = len(list_local_models().get("models") or [])
        self.set_status(
            f"{TRUTH_LABEL} · ollama={'on' if st['ollama'] else 'off'} · "
            f"models={n_models} · codex={'✓' if st['codex'] else '—'} · "
            f"claude={'✓' if st['claude'] else '—'} · t={int(time.time()) % 100000}"
        )

    def closeEvent(self, event) -> None:  # noqa: N802
        if type(self)._live_instance is self:
            type(self)._live_instance = None
        type(self)._initialized_ids.discard(id(self))
        try:
            if hasattr(self, "_status_timer"):
                self._status_timer.stop()
        except Exception:
            pass
        super().closeEvent(event)


# Manifest / backward-compat aliases
ApexPredatorWidget = DoubleApexPredatorWidget  # type: ignore[misc,assignment]
PredatorDesktopBg = DoubleApexPredatorWidget  # type: ignore[misc,assignment]


if __name__ == "__main__":
    app = QApplication.instance() or QApplication(sys.argv)
    w = DoubleApexPredatorWidget()
    w.show()
    raise SystemExit(app.exec())
