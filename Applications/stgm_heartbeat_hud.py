"""Compact, receipt-driven STGM topbar indicator. No synthetic balance motion."""
from html import escape

from PyQt6.QtCore import Qt, QVariantAnimation, QEasingCurve
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QLabel


class StgmHeartbeatHud(QLabel):
    COLORS = {"HEALTHY": "#83d8b1", "FAULT": "#ff927f", "STALE": "#9299a7",
              "AWAITING": "#e5bc79", "UNAVAILABLE": "#9299a7"}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(42)
        self.setMinimumWidth(290)
        self.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.setStyleSheet("font-family: 'Helvetica Neue'; background: transparent; border: none; padding: 0 10px 0 26px;")
        self._last_heart = None
        self._last_event = None
        self._pulse = 0.0
        self._color = QColor(self.COLORS["AWAITING"])
        self._animation = QVariantAnimation(self)
        self._animation.setDuration(1200)
        self._animation.setStartValue(1.0)
        self._animation.setEndValue(0.0)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.valueChanged.connect(self._animate)

    def _animate(self, value):
        self._pulse = float(value)
        self.update()

    def show_observation(self, balance_text: str, evidence: dict):
        state = evidence.get("state", "UNAVAILABLE")
        color = self.COLORS.get(state, self.COLORS["AWAITING"])
        self._color = QColor(color)
        heart_id = evidence.get("heart_id")
        event_id = evidence.get("event_id")
        new_heart = heart_id and heart_id != self._last_heart
        new_event = event_id and self._last_event and event_id != self._last_event
        if new_heart or new_event:
            self._animation.stop()
            self._animation.start()
        elif not heart_id:
            self._animation.stop()
            self._pulse = 0.0
        self._last_heart, self._last_event = heart_id, event_id
        pending = " | sold in actualizare" if evidence.get("cache_stale") else ""
        detail = evidence.get("detail", "Fara date")
        if evidence.get("cache_stale"):
            detail += " | cache vechi"
        self.setText(
            f'<span style="font-size:12px;font-weight:600;color:#f3ede3">{escape(balance_text)}</span><br>'
            f'<span style="font-size:10px;color:{color}">{escape(detail)}</span>'
        )
        age = evidence.get("heart_age")
        age_line = f"Heartbeat primit acum {age:.0f}s." if age is not None else "Niciun heartbeat recent."
        self.setToolTip(f"{age_line}{pending}\nUltima tranzactie: {event_id or 'necunoscuta'}\n"
                        f"Erori: {', '.join(evidence.get('faults', [])) or 'niciuna in proba'}\n"
                        "Pulsul indica un receipt nou, nu bani creati de animatie. STGM nu este un curs EUR/USD.")
        self.setAccessibleName(f"{balance_text}. {detail}. {age_line}{pending}")

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        halo = QColor(self._color)
        halo.setAlpha(int(65 * self._pulse))
        painter.setBrush(halo)
        radius = int(5 + 5 * self._pulse)
        painter.drawEllipse(12 - radius, 21 - radius, radius * 2, radius * 2)
        painter.setBrush(self._color)
        painter.drawEllipse(9, 18, 6, 6)
