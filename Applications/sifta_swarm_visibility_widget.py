#!/usr/bin/env python3
"""
Applications/sifta_swarm_visibility_widget.py
=============================================
Native BeeSon Swarm Field widget.

This replaces the detached white-app visibility idea with one Qt surface inside
SIFTA OS. It renders the four useful quadrants: organ health, field roll, STGM
flow, and active IDE swimmers. It also publishes app_focus rows so Alice can
talk about what the owner is seeing.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

try:
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (
        QApplication,
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QTextBrowser,
        QVBoxLayout,
        QWidget,
    )
except Exception:  # pragma: no cover - import-time guard for non-Qt probes
    Qt = None  # type: ignore[assignment]
    QApplication = None  # type: ignore[assignment]
    QFrame = None  # type: ignore[assignment]
    QGridLayout = None  # type: ignore[assignment]
    QHBoxLayout = None  # type: ignore[assignment]
    QLabel = None  # type: ignore[assignment]
    QPushButton = None  # type: ignore[assignment]
    QTextBrowser = None  # type: ignore[assignment]
    QVBoxLayout = None  # type: ignore[assignment]
    QWidget = object  # type: ignore[assignment,misc]

try:
    from System.swarm_visibility import full_snapshot
except Exception:  # pragma: no cover
    from swarm_visibility import full_snapshot  # type: ignore

try:
    from System.swarm_app_focus import publish_focus as _publish_focus
except Exception:  # pragma: no cover
    _publish_focus = None

try:
    from System.swarm_behavior_clock import behavior_clock
except Exception:  # pragma: no cover
    behavior_clock = None  # type: ignore[assignment]


class SwarmFieldWidget(QWidget):  # type: ignore[misc]
    """One live visibility surface for SIFTA organs and swimmers."""

    _live_instance: "SwarmFieldWidget | None" = None
    _initialized_instance_ids: set[int] = set()

    def __new__(cls, *args: Any, **kwargs: Any) -> "SwarmFieldWidget":
        live = cls._live_instance
        if live is not None:
            try:
                if not live.isHidden():
                    live.raise_()
                    live.activateWindow()
                return live
            except RuntimeError:
                cls._live_instance = None
        inst = super().__new__(cls)
        cls._live_instance = inst
        return inst

    def __init__(self, parent: QWidget | None = None) -> None:  # type: ignore[valid-type]
        if id(self) in self._initialized_instance_ids:
            return
        super().__init__(parent)
        self._initialized_instance_ids.add(id(self))
        self._last_snapshot: dict[str, Any] = {}
        self._clock_connected = False

        self.setWindowTitle("Swarm Field")
        self.resize(1040, 720)
        self._build_ui()
        self._connect_behavior_clock()
        self._refresh("open")

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Swarm Field")
        title.setObjectName("swarmFieldTitle")
        title.setStyleSheet("font-size: 26px; font-weight: 700;")
        subtitle = QLabel("Organs, field traces, STGM flow, and active IDE swimmers in one BeeSon app.")
        subtitle.setStyleSheet("color: #6b7280;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box, 1)

        self._status = QLabel("Loading field...")
        self._status.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._status.setStyleSheet("color: #374151;")
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(lambda: self._refresh("manual"))
        header.addWidget(self._status)
        header.addWidget(refresh)
        root.addLayout(header)

        grid = QGridLayout()
        grid.setSpacing(12)
        self._organs = self._panel("Organs")
        self._field = self._panel("Field Roll")
        self._stgm = self._panel("STGM Flow")
        self._swimmers = self._panel("Active Swimmers")
        grid.addWidget(self._organs["frame"], 0, 0)
        grid.addWidget(self._field["frame"], 0, 1)
        grid.addWidget(self._stgm["frame"], 1, 0)
        grid.addWidget(self._swimmers["frame"], 1, 1)
        root.addLayout(grid, 1)

        self.setStyleSheet(
            """
            QWidget { background: #f8fafc; color: #111827; }
            QFrame#panel { background: #ffffff; border: 1px solid #d1d5db; border-radius: 8px; }
            QTextBrowser { background: #0f172a; color: #e5e7eb; border: 0; font-family: Menlo, Consolas, monospace; font-size: 12px; }
            QPushButton { padding: 7px 12px; border: 1px solid #9ca3af; border-radius: 6px; background: #ffffff; }
            QPushButton:hover { background: #eef2ff; }
            """
        )

    def _panel(self, title: str) -> dict[str, Any]:
        frame = QFrame()
        frame.setObjectName("panel")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 10, 10, 10)
        label = QLabel(title)
        label.setStyleSheet("font-weight: 700;")
        text = QTextBrowser()
        text.setOpenExternalLinks(False)
        text.setMinimumHeight(220)
        layout.addWidget(label)
        layout.addWidget(text, 1)
        return {"frame": frame, "label": label, "text": text}

    def _connect_behavior_clock(self) -> None:
        if behavior_clock is None or self._clock_connected:
            return
        try:
            behavior_clock().tick.connect(lambda source: self._refresh(f"behavior_clock:{source}"))
            self._clock_connected = True
        except Exception:
            self._clock_connected = False

    def _refresh(self, reason: str = "manual") -> None:
        try:
            snap = full_snapshot()
        except Exception as exc:
            snap = {
                "organs": [],
                "field": [],
                "stgm": {"entries": [], "current_balance": None},
                "swimmers": [],
                "snapshot_ts": time.time(),
                "error": str(exc),
            }
        self._last_snapshot = snap
        self._organs["text"].setPlainText(self._render_organs(snap.get("organs", [])))
        self._field["text"].setPlainText(self._render_field(snap.get("field", [])))
        self._stgm["text"].setPlainText(self._render_stgm(snap.get("stgm", {})))
        self._swimmers["text"].setPlainText(self._render_swimmers(snap.get("swimmers", [])))

        counts = {
            "organs": len(snap.get("organs", []) or []),
            "field": len(snap.get("field", []) or []),
            "swimmers": len(snap.get("swimmers", []) or []),
        }
        self._status.setText(
            f"{counts['organs']} organs | {counts['field']} rows | {counts['swimmers']} swimmers"
        )
        self._publish_focus_context(reason, snap, counts)

    def _render_organs(self, organs: list[dict[str, Any]]) -> str:
        if not organs:
            return "No organ ledgers found."
        lines = []
        for row in organs:
            age = row.get("age_s")
            age_text = "new" if age is None else f"{float(age):.1f}s"
            lines.append(
                f"{row.get('health', '?'):>6}  {row.get('organ', '?'):<14} "
                f"rows={row.get('row_count', 0):<5} age={age_text:<8} head={row.get('head', '')}"
            )
        return "\n".join(lines)

    def _render_field(self, rows: list[dict[str, Any]]) -> str:
        if not rows:
            return "No recent field rows."
        lines = []
        for row in rows[-32:]:
            ts = row.get("ts", row.get("timestamp", ""))
            trace = row.get("trace_id") or row.get("hash") or row.get("receipt_hash") or ""
            lines.append(
                f"{row.get('ledger', '?'):<30} {row.get('type', 'UNKNOWN'):<24} "
                f"{str(trace)[:12]:<12} {ts}"
            )
        return "\n".join(lines)

    def _render_stgm(self, flow: dict[str, Any]) -> str:
        balance = flow.get("current_balance")
        header = f"current_balance={balance}" if balance is not None else "current_balance=unknown"
        entries = flow.get("entries", []) or []
        if not entries:
            return header + "\nNo recent STGM rows."
        lines = [header]
        for row in entries[-20:]:
            lines.append(
                f"{row.get('type', 'STGM'):<18} amount={row.get('amount', ''):<8} "
                f"balance_after={row.get('balance_after', row.get('balance', '')):<8} {row.get('reason', '')}"
            )
        return "\n".join(lines)

    def _render_swimmers(self, swimmers: list[dict[str, Any]]) -> str:
        if not swimmers:
            return "No LLM_REGISTRATION rows found on the IDE bus."
        lines = []
        for row in swimmers:
            lines.append(
                f"{row.get('doctor', 'unknown'):<22} {row.get('model', ''):<18} "
                f"{row.get('lane', ''):<12} {row.get('trace_id', '')}"
            )
        return "\n".join(lines)

    def _publish_focus_context(self, reason: str, snap: dict[str, Any], counts: dict[str, int]) -> None:
        if _publish_focus is None:
            return
        try:
            detail = (
                f"Swarm Field refreshed by {reason}: {counts['organs']} organ summaries, "
                f"{counts['field']} recent field rows, {counts['swimmers']} active swimmers."
            )
            _publish_focus(
                "Swarm Field",
                detail,
                tab="Visibility",
                selection="field snapshot",
                metadata={
                    "source": "swarm_field_widget",
                    "salience_score": 1.2,
                    "organs": counts["organs"],
                    "field_rows": counts["field"],
                    "swimmers": counts["swimmers"],
                    "snapshot_ts": snap.get("snapshot_ts"),
                },
            )
        except Exception:
            pass

    def closeEvent(self, event: Any) -> None:
        type(self)._live_instance = None
        type(self)._initialized_instance_ids.discard(id(self))
        super().closeEvent(event)


def main() -> int:
    if QApplication is None:
        raise RuntimeError("PyQt6 is required to run Swarm Field")
    app = QApplication.instance() or QApplication(sys.argv)
    widget = SwarmFieldWidget()
    widget.show()
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
