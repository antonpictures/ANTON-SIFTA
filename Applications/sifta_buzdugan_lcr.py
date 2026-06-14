#!/usr/bin/env python3
"""Buzdugan LCR app: visual, receipt-backed long-context retrieval proof."""
from __future__ import annotations

"""SIFTA Buzdugan Lcr — stigmergic organ for Alice body."""

import json
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from PyQt6.QtCore import QPointF, QRectF, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from System.sifta_base_widget import SiftaBaseWidget
from System import swarm_buzdugan_lcr as lcr


APP_NAME = "Buzdugan LCR"


class LcrWorker(QThread):
    finished_payload = pyqtSignal(dict)

    def __init__(self, *, token_target: int, force: bool) -> None:
        super().__init__()
        self.token_target = int(token_target)
        self.force = bool(force)

    def run(self) -> None:  # pragma: no cover - exercised through engine tests
        try:
            payload = lcr.run_lcr_benchmark(token_target=self.token_target, force=self.force)
        except Exception as exc:
            payload = {"error": f"{type(exc).__name__}: {exc}", "all_verified": False}
        self.finished_payload.emit(payload)


class LcrCanvas(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.receipt: dict[str, Any] | None = None
        self.setMinimumHeight(250)

    def set_receipt(self, receipt: dict[str, Any] | None) -> None:
        self.receipt = receipt
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(14, 14, -14, -14)
        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(0.0, QColor(7, 13, 26))
        grad.setColorAt(0.55, QColor(14, 25, 39))
        grad.setColorAt(1.0, QColor(8, 14, 22))
        p.fillRect(rect, grad)
        p.setPen(QPen(QColor(42, 64, 85), 1))
        p.drawRoundedRect(rect, 10, 10)

        p.setFont(QFont("Menlo", 16, QFont.Weight.Bold))
        p.setPen(QColor(235, 241, 255))
        p.drawText(
            rect.adjusted(18, 16, -18, -18),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            "Buzdugan LCR: body retrieval before cortex",
        )

        if not self.receipt:
            p.setFont(QFont("Menlo", 11))
            p.setPen(QColor(150, 165, 190))
            p.drawText(
                rect.adjusted(18, 62, -18, -18),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                "No receipt yet. Run the benchmark.",
            )
            p.end()
            return

        facts = self.receipt.get("retrievals") or []
        max_tok = max(
            [int(self.receipt.get("token_equivalent_est") or 1)]
            + [int(row.get("token_at_est") or 0) for row in facts]
        )
        pass_rate = float(self.receipt.get("pass_rate") or 0.0)
        ok = bool(self.receipt.get("all_verified"))

        bar = QRectF(rect.left() + 40, rect.top() + 104, rect.width() - 80, 18)
        bar_grad = QLinearGradient(bar.topLeft(), bar.topRight())
        bar_grad.setColorAt(0.0, QColor(55, 87, 120))
        bar_grad.setColorAt(0.5, QColor(27, 194, 161))
        bar_grad.setColorAt(1.0, QColor(255, 203, 107))
        p.fillRect(bar, bar_grad)
        p.setPen(QPen(QColor(180, 200, 220), 1))
        p.drawRoundedRect(bar, 8, 8)

        body_y = rect.top() + 174
        p.setPen(QPen(QColor(65, 220, 190), 2))
        p.drawLine(QPointF(bar.left(), body_y), QPointF(bar.right(), body_y))
        p.setFont(QFont("Menlo", 10, QFont.Weight.Bold))
        p.setPen(QColor(165, 236, 216))
        p.drawText(
            QRectF(bar.left(), body_y + 12, bar.width(), 22),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "SIFTA body index: file + line + byte + sha256",
        )

        for row in facts:
            token = int(row.get("token_at_est") or 0)
            x = bar.left() + (token / max(1, max_tok)) * bar.width()
            verified = bool(row.get("ok"))
            color = QColor(88, 255, 187) if verified else QColor(255, 85, 110)
            p.setPen(QPen(color, 2))
            p.drawLine(QPointF(x, bar.bottom()), QPointF(x, body_y))
            p.setBrush(color)
            p.drawEllipse(QPointF(x, bar.center().y()), 5, 5)
            p.drawEllipse(QPointF(x, body_y), 4, 4)

        target = self.receipt.get("target_retrieval") or {}
        p.setFont(QFont("Menlo", 11, QFont.Weight.Bold))
        p.setPen(QColor(88, 255, 187) if ok else QColor(255, 203, 107))
        p.drawText(
            QRectF(rect.left() + 18, rect.top() + 58, rect.width() - 36, 30),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            f"Verified {self.receipt.get('pass_count')}/{self.receipt.get('fact_count')} facts "
            f"from ~{self.receipt.get('token_equivalent_est')} token-equivalent corpus "
            f"({pass_rate:.0%})",
        )
        p.setFont(QFont("Menlo", 10))
        p.setPen(QColor(220, 226, 242))
        p.drawText(
            QRectF(rect.left() + 18, rect.bottom() - 44, rect.width() - 36, 24),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            f"Target: {target.get('key')} -> {target.get('value')} | line {target.get('line_no')} | sha {str(target.get('line_hash'))[:14]}",
        )
        p.end()


class BuzduganLCRWidget(SiftaBaseWidget):
    APP_NAME = APP_NAME
    APP_LOCAL_CHAT_DISABLED = True
    OPEN_MAXIMIZED = True

    def __init__(self, parent=None) -> None:
        self._worker: LcrWorker | None = None
        self._receipt: dict[str, Any] | None = None
        super().__init__(parent)

    def build_ui(self, root: QVBoxLayout) -> None:
        title = QLabel(
            "Measure SIFTA's retrieval-first answer: body trace -> exact receipt -> cortex. "
            "This is not a fake 1M-context model score."
        )
        title.setWordWrap(True)
        title.setStyleSheet("color: rgb(220,230,246); font-size: 13px; padding: 4px;")
        root.addWidget(title)

        self.canvas = LcrCanvas()
        root.addWidget(self.canvas, 2)

        controls = QHBoxLayout()
        self.quick_btn = QPushButton("Run 80k quick proof")
        self.quick_btn.clicked.connect(lambda: self.run_benchmark(80_000, True))
        controls.addWidget(self.quick_btn)
        self.full_btn = QPushButton("Run 820k body proof")
        self.full_btn.clicked.connect(lambda: self.run_benchmark(820_000, True))
        controls.addWidget(self.full_btn)
        self.refresh_btn = QPushButton("Refresh receipt")
        self.refresh_btn.clicked.connect(self.refresh_receipt)
        controls.addWidget(self.refresh_btn)
        controls.addStretch()
        root.addLayout(controls)

        stats = QHBoxLayout()
        self.metric_verified = self._metric("verified", "-")
        self.metric_tokens = self._metric("token-equivalent", "-")
        self.metric_target = self._metric("target token", "-")
        self.metric_latency = self._metric("elapsed", "-")
        for card in (self.metric_verified, self.metric_tokens, self.metric_target, self.metric_latency):
            stats.addWidget(card)
        root.addLayout(stats)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["Needle", "Key", "Value", "Token est", "Line", "Byte", "Hash ok"])
        root.addWidget(self.table, 2)

        self.receipt_text = QPlainTextEdit()
        self.receipt_text.setReadOnly(True)
        self.receipt_text.setStyleSheet("font-family: Menlo; font-size: 10px;")
        root.addWidget(self.receipt_text, 1)

        self.claim_text = QPlainTextEdit()
        self.claim_text.setReadOnly(True)
        self.claim_text.setMaximumHeight(82)
        self.claim_text.setStyleSheet("font-family: Menlo; font-size: 10px; color: rgb(127,255,212);")
        root.addWidget(self.claim_text)

        self.refresh_receipt()

    def _metric(self, label: str, value: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame { background: rgb(13,18,29); border: 1px solid rgb(38,60,80); border-radius: 8px; }"
        )
        layout = QVBoxLayout(frame)
        top = QLabel(label.upper())
        top.setStyleSheet("color: rgb(130,160,190); font-size: 10px;")
        val = QLabel(value)
        val.setObjectName("metricValue")
        val.setStyleSheet("color: rgb(92,255,190); font-size: 18px; font-weight: bold;")
        layout.addWidget(top)
        layout.addWidget(val)
        frame.value_label = val  # type: ignore[attr-defined]
        return frame

    def run_benchmark(self, token_target: int, force: bool) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        self._set_buttons(False)
        self.receipt_text.setPlainText(f"Running real Buzdugan LCR corpus at {token_target} token-equivalent target...")
        self._worker = LcrWorker(token_target=token_target, force=force)
        self._worker.finished_payload.connect(self._on_finished)
        self._worker.start()

    def _on_finished(self, payload: dict) -> None:
        self._set_buttons(True)
        self._receipt = payload
        self.render_receipt(payload)

    def _set_buttons(self, enabled: bool) -> None:
        self.quick_btn.setEnabled(enabled)
        self.full_btn.setEnabled(enabled)
        self.refresh_btn.setEnabled(enabled)

    def refresh_receipt(self) -> None:
        self._receipt = lcr.latest_receipt()
        self.render_receipt(self._receipt)

    def render_receipt(self, receipt: dict | None) -> None:
        self.canvas.set_receipt(receipt)
        self.receipt_text.setPlainText(lcr.format_receipt(receipt))
        self.claim_text.setPlainText(lcr.retweet_claim(receipt))

        facts = (receipt or {}).get("retrievals") or []
        self.table.setRowCount(len(facts))
        for r, row in enumerate(facts):
            vals = [
                row.get("needle_id"),
                row.get("key"),
                row.get("value"),
                row.get("token_at_est"),
                row.get("line_no"),
                row.get("byte_offset"),
                "yes" if row.get("ok") else "no",
            ]
            for c, val in enumerate(vals):
                item = QTableWidgetItem(str(val))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(r, c, item)
        self.table.resizeColumnsToContents()

        target = (receipt or {}).get("target_retrieval") or {}
        self.metric_verified.value_label.setText(  # type: ignore[attr-defined]
            f"{(receipt or {}).get('pass_count', 0)}/{(receipt or {}).get('fact_count', 0)}"
        )
        self.metric_tokens.value_label.setText(str((receipt or {}).get("token_equivalent_est") or "-"))  # type: ignore[attr-defined]
        self.metric_target.value_label.setText(str(target.get("target_token") or "-"))  # type: ignore[attr-defined]
        self.metric_latency.value_label.setText(f"{(receipt or {}).get('elapsed_s', '-') }s")  # type: ignore[attr-defined]


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = BuzduganLCRWidget()
    w.resize(1120, 760)
    w.show()
    sys.exit(app.exec())
