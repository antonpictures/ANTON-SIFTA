#!/usr/bin/env python3
"""sifta_organism_doctor.py — MDI widget that renders SIFTA's
organism health on demand and on a 30-second auto-refresh.

Architect 2026-05-14 ~19:00 PDT — "for organism you need a doctor like
I need a doctor". Single page, 13 probe rows, color-coded status. The
2026-05-30 matrix includes the Body Consciousness Index.

The probe logic lives in :mod:`System.swarm_organism_doctor` (no Qt,
testable headless). This widget is the renderer + the refresh
controller — nothing more.

§7.6.2 single-instance pattern (TSP-style ``_initialized_instance_ids``
set guard) so a double-click never builds two doctors.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

from System.swarm_organism_doctor import (  # noqa: E402
    OVERALL_CRITICAL,
    OVERALL_HEALTHY,
    OVERALL_WARNING,
    compose_health_report,
    render_html_report,
)


_DOCTOR_QSS = """
QWidget#OrganismDoctorRoot {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #0d101e, stop:1 #06070f);
}
QPushButton#DoctorRefreshBtn {
    background: rgba(168, 107, 255, 50);
    color: #f1f4ff;
    border: 1px solid #a86bff;
    border-radius: 8px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.4px;
}
QPushButton#DoctorRefreshBtn:hover {
    background: #a86bff;
    color: #06070f;
}
QTextEdit#DoctorReport {
    background: rgba(20, 23, 38, 220);
    border: 1px solid rgba(140, 150, 200, 50);
    border-radius: 12px;
    padding: 14px;
    color: #f1f4ff;
}
QLabel#DoctorStatusBadge {
    border-radius: 10px;
    padding: 4px 12px;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 1.2px;
}
"""


class OrganismDoctorWidget(QWidget):
    """SIFTA's single-page organism health report. Calls the probe
    library, renders the HTML, refreshes every 30s."""

    _live_instance: "Optional[OrganismDoctorWidget]" = None
    _initialized_instance_ids: set[int] = set()

    def __new__(cls, *args, **kwargs):
        existing = cls._live_instance
        if existing is not None:
            try:
                _ = existing.isVisible()
                try:
                    existing.show()
                    existing.raise_()
                    existing.activateWindow()
                except Exception:
                    pass
                return existing
            except RuntimeError:
                cls._live_instance = None
        return super().__new__(cls)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        # §7.6.2 sip-safe guard: never probe instance attrs before super().__init__.
        if id(self) in type(self)._initialized_instance_ids:
            return
        super().__init__(parent)
        self.setObjectName("OrganismDoctorRoot")
        self.setWindowTitle("Organism Doctor")
        self.resize(900, 640)
        self.setStyleSheet(_DOCTOR_QSS)

        # ── Header ────────────────────────────────────────────────
        header_row = QHBoxLayout()
        title = QLabel("🩺  Organism Doctor")
        title.setFont(QFont("SF Pro Display", 18, QFont.Weight.DemiBold))
        title.setStyleSheet("color: #f1f4ff; padding: 2px 0;")
        header_row.addWidget(title)

        self._status_badge = QLabel("READING…")
        self._status_badge.setObjectName("DoctorStatusBadge")
        self._status_badge.setStyleSheet(
            "background: #8e94ad; color: #06070f;"
        )
        header_row.addWidget(self._status_badge)
        header_row.addStretch(1)

        self._refresh_btn = QPushButton("↻  Refresh now")
        self._refresh_btn.setObjectName("DoctorRefreshBtn")
        self._refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_btn.clicked.connect(self._refresh)
        header_row.addWidget(self._refresh_btn)

        # ── Report body (HTML) ────────────────────────────────────
        self._report = QTextEdit()
        self._report.setObjectName("DoctorReport")
        self._report.setReadOnly(True)
        self._report.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        # ── Footer ────────────────────────────────────────────────
        self._footer = QLabel("auto-refresh every 30 s · receipts in .sifta_state/")
        self._footer.setStyleSheet("color: #565f89; font-size: 11px; padding-top: 4px;")

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 14)
        root.setSpacing(10)
        root.addLayout(header_row)
        root.addWidget(self._report, 1)
        root.addWidget(self._footer)

        # ── Auto-refresh timer ────────────────────────────────────
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(30_000)  # 30 s
        self._refresh_timer.timeout.connect(self._refresh)
        self._refresh_timer.start()

        # First read happens right after mount so the panel is never empty
        QTimer.singleShot(50, self._refresh)

        type(self)._live_instance = self
        type(self)._initialized_instance_ids.add(id(self))

    def _refresh(self) -> None:
        """Run the nine probes + render the HTML report."""
        try:
            health = compose_health_report()
        except Exception as exc:
            self._status_badge.setText("UNKNOWN")
            self._status_badge.setStyleSheet(
                "background: #8e94ad; color: #06070f;"
            )
            self._report.setHtml(
                f"<div style='color:#ff5a6e;font-family:Menlo;font-size:12px;'>"
                f"probe error: {type(exc).__name__}: {exc}</div>"
            )
            return
        # Status badge color
        color = {
            OVERALL_HEALTHY: "#2fd16b",
            OVERALL_WARNING: "#ffb53d",
            OVERALL_CRITICAL: "#ff5a6e",
        }.get(health.overall, "#8e94ad")
        self._status_badge.setText(health.overall)
        self._status_badge.setStyleSheet(
            f"background: {color}; color: #06070f;"
        )
        self._report.setHtml(render_html_report(health))
        self._footer.setText(
            f"auto-refresh every 30 s · {len(health.sections)} probes · node {health.node_serial}"
        )

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        try:
            self._refresh_timer.stop()
        except Exception:
            pass
        try:
            if type(self)._live_instance is self:
                type(self)._live_instance = None
            type(self)._initialized_instance_ids.discard(id(self))
        except Exception:
            pass
        super().closeEvent(event)


def main() -> int:
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    w = OrganismDoctorWidget()
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
