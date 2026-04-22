"""
sifta_gasstation_meter.py — Token & cost gauge for cloud brain calls
═══════════════════════════════════════════════════════════════════

Authored by C47H, 2026-04-20, on AG31's request:

    "have an app like a gasstation meter and i will too in google
     console api logs"

What this is
────────────
A small Qt app that tails `.sifta_state/brain_token_ledger.jsonl`
(written by `System.swarm_gemini_brain.record_usage`) and renders a
live "fuel pump"-style readout:

    ┌─ TODAY ──────────────┐  ┌─ LIFETIME ───────────┐
    │  $ 0.0123             │  │  $ 0.4711             │
    │  in:  12,400 tok      │  │  in:  882,113 tok     │
    │  out:  3,221 tok      │  │  out:  91,402 tok     │
    │  calls: 17            │  │  calls: 412           │
    └───────────────────────┘  └───────────────────────┘

    LAST PUMP — gemini:gemini-2.5-flash · req-tag c2f8a91e
    in 412 / out 188 tok · $0.000610 · 2,140 ms

    BY MODEL                     CALLS   IN tok   OUT tok    USD
    gemini-2.5-flash               14    11,200    2,890    0.0094
    gemini-2.5-pro                  3     1,200      331    0.0029

    [ open ledger ]   [ refresh now ]   [ pause auto ]

How to cross-check against Google Cloud Console
───────────────────────────────────────────────
Every call SIFTA fires at Gemini stamps two custom HTTP headers:

    x-goog-api-client: sifta-swarm/c47h-2026-04-20
    x-goog-request-tag: <short-uuid>

The `request_tag` shown after each call in this gauge is the same one
on the wire and stored in the ledger row. In console.cloud.google.com
→ "API & Services" → "Generative Language API" → traffic, you can
filter by user-agent prefix `sifta-swarm/` (or grep request logs for
the tag) to confirm one-for-one that what the meter shows is what
Google billed you for.

Run modes
─────────
    • Standalone: `python3 Applications/sifta_gasstation_meter.py`
    • Inside the SIFTA OS desktop via `apps_manifest.json`
      (widget_class = "GasStationMeterWidget").
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QPalette
from PyQt6.QtWidgets import (
    QApplication, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel,
    QLCDNumber, QPushButton, QSizePolicy, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from System.sifta_base_widget import SiftaBaseWidget

# Lazy import — the meter must run even if the gemini module is broken,
# because its only job is to *report* on the ledger that already exists
# on disk. We re-resolve the ledger path here so the meter has zero
# runtime coupling to the brain backend.
try:
    from System.swarm_gemini_brain import (
        TOKEN_LEDGER as _LEDGER, summarize_ledger, read_ledger,
    )
except Exception:
    _LEDGER = _REPO / ".sifta_state" / "brain_token_ledger.jsonl"

    def summarize_ledger() -> Dict[str, Any]:                       # type: ignore
        return {"lifetime": {"calls": 0, "in": 0, "out": 0, "cost_usd": 0.0},
                "today":    {"calls": 0, "in": 0, "out": 0, "cost_usd": 0.0},
                "last_24h": {"calls": 0, "in": 0, "out": 0, "cost_usd": 0.0},
                "by_model": {}, "last": None}

    def read_ledger(limit: Optional[int] = None) -> List[Dict[str, Any]]:  # type: ignore
        return []


_TICK_MS = 1500
_LCD_DIGITS = 9
_RECENT_ROWS = 25


# ─────────────────────────────────────────────────────────────────────
# Styling helpers
# ─────────────────────────────────────────────────────────────────────
_PUMP_BG = "background-color: rgb(8,12,18);"
_PUMP_AMBER = "color: rgb(255,176,0);"
_PUMP_GREEN = "color: rgb(50,255,160);"
_PUMP_DIM = "color: rgb(110,118,140);"


def _money(v: float) -> str:
    """Format USD with enough precision to see sub-cent calls move."""
    return f"${v:,.4f}" if v < 1.0 else f"${v:,.2f}"


def _tok(v: int) -> str:
    return f"{int(v):,}"


def _styled_lcd(parent: QWidget, color_css: str) -> QLCDNumber:
    """A pump-style LCD with amber/green segments on near-black."""
    lcd = QLCDNumber(parent)
    lcd.setDigitCount(_LCD_DIGITS)
    lcd.setSegmentStyle(QLCDNumber.SegmentStyle.Flat)
    lcd.setFrameShape(QFrame.Shape.NoFrame)
    pal = lcd.palette()
    rgb_str = color_css.split("rgb(")[1].split(")")[0]
    rgb = rgb_str.split(",")
    pal.setColor(QPalette.ColorRole.WindowText,
                 QColor(int(rgb[0]), int(rgb[1]), int(rgb[2])))
    lcd.setPalette(pal)
    lcd.setMinimumHeight(46)
    return lcd


def _label(text: str, css: str = _PUMP_DIM, point: int = 9,
           bold: bool = False) -> QLabel:
    lab = QLabel(text)
    f = QFont("Menlo", point)
    if bold:
        f.setBold(True)
    lab.setFont(f)
    lab.setStyleSheet(css)
    return lab


# ─────────────────────────────────────────────────────────────────────
# A single pump panel: TODAY or LIFETIME
# ─────────────────────────────────────────────────────────────────────
class _PumpPanel(QFrame):
    """One column of the gauge — title, big $ readout, token rows."""

    def __init__(self, title: str, color_css: str = _PUMP_AMBER,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(_PUMP_BG + " border: 1px solid rgb(38,42,55);"
                           " border-radius: 6px;")
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Expanding)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 10)
        root.setSpacing(6)

        head = QHBoxLayout()
        head.addWidget(_label(title, _PUMP_DIM, point=9, bold=True))
        head.addStretch()
        self._calls_lab = _label("calls 0", _PUMP_DIM, point=9)
        head.addWidget(self._calls_lab)
        root.addLayout(head)

        self._lcd = _styled_lcd(self, color_css)
        self._lcd.display("0.0000")
        root.addWidget(self._lcd)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(2)
        grid.addWidget(_label("in", _PUMP_DIM), 0, 0)
        grid.addWidget(_label("out", _PUMP_DIM), 1, 0)
        self._in_lab = _label("0 tok", _PUMP_GREEN, point=11, bold=True)
        self._out_lab = _label("0 tok", _PUMP_GREEN, point=11, bold=True)
        grid.addWidget(self._in_lab, 0, 1)
        grid.addWidget(self._out_lab, 1, 1)
        grid.setColumnStretch(1, 1)
        root.addLayout(grid)

    def update_with(self, bucket: Dict[str, Any]) -> None:
        cost = float(bucket.get("cost_usd") or 0.0)
        # LCD only does numerics — strip the leading "$" but keep enough
        # decimals for sub-cent calls to be visible.
        self._lcd.display(f"{cost:.4f}" if cost < 1.0 else f"{cost:.2f}")
        self._in_lab.setText(f"{_tok(bucket.get('in', 0))} tok")
        self._out_lab.setText(f"{_tok(bucket.get('out', 0))} tok")
        self._calls_lab.setText(f"calls {_tok(bucket.get('calls', 0))}")


# ─────────────────────────────────────────────────────────────────────
# Main widget
# ─────────────────────────────────────────────────────────────────────
class GasStationMeterWidget(SiftaBaseWidget):
    """A live fuel-pump gauge for the brain-token ledger.

    Reads `.sifta_state/brain_token_ledger.jsonl`, polls every 1.5 s,
    and renders TODAY + LIFETIME + LAST CALL + per-model breakdown.
    Pure read; never writes. Safe to leave open for days.
    """

    APP_NAME = "Brain Gas-Station Meter"

    def build_ui(self, layout: QVBoxLayout) -> None:
        # ── Pumps ────────────────────────────────────────────────
        pumps = QHBoxLayout()
        pumps.setSpacing(8)
        self._today = _PumpPanel("TODAY (USD)", _PUMP_AMBER)
        self._life = _PumpPanel("LIFETIME (USD)", _PUMP_GREEN)
        self._24h  = _PumpPanel("LAST 24H (USD)", _PUMP_AMBER)
        pumps.addWidget(self._today, 1)
        pumps.addWidget(self._24h, 1)
        pumps.addWidget(self._life, 1)
        layout.addLayout(pumps)

        # ── Last pump card (most recent call) ────────────────────
        self._last_card = _label("LAST PUMP — (no calls yet)",
                                 _PUMP_DIM, point=10, bold=True)
        self._last_detail = _label("", _PUMP_GREEN, point=11, bold=True)
        layout.addWidget(self._last_card)
        layout.addWidget(self._last_detail)

        # ── Per-model breakdown table ────────────────────────────
        layout.addWidget(_label("BY MODEL", _PUMP_DIM, point=9, bold=True))
        self._table = QTableWidget(0, 5, self)
        self._table.setHorizontalHeaderLabels(
            ["Model", "Calls", "In tok", "Out tok", "USD"]
        )
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in range(1, 5):
            hdr.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setStyleSheet(
            "QTableWidget { background: rgb(12,16,22);"
            " gridline-color: rgb(38,42,55);"
            " color: rgb(220,222,228); font-family: Menlo; font-size: 11px; }"
            "QHeaderView::section { background: rgb(20,24,32);"
            " color: rgb(160,168,184); padding: 4px;"
            " border: 0px; border-right: 1px solid rgb(38,42,55); }"
        )
        self._table.setMaximumHeight(180)
        layout.addWidget(self._table)

        # ── Recent calls (compact log) ───────────────────────────
        layout.addWidget(_label("RECENT CALLS (last "
                                f"{_RECENT_ROWS})", _PUMP_DIM, point=9, bold=True))
        self._recent = QTableWidget(0, 6, self)
        self._recent.setHorizontalHeaderLabels(
            ["When", "Model", "In", "Out", "USD", "ms"]
        )
        rhdr = self._recent.horizontalHeader()
        rhdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        rhdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for c in range(2, 6):
            rhdr.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        self._recent.verticalHeader().setVisible(False)
        self._recent.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._recent.setStyleSheet(self._table.styleSheet())
        layout.addWidget(self._recent, 1)

        # ── Controls ─────────────────────────────────────────────
        ctl = QHBoxLayout()
        self._auto = True
        self._pause_btn = QPushButton("Pause auto-refresh")
        self._pause_btn.clicked.connect(self._toggle_auto)
        self._refresh_btn = QPushButton("Refresh now")
        self._refresh_btn.clicked.connect(self._refresh)
        self._open_btn = QPushButton("Open ledger file")
        self._open_btn.clicked.connect(self._open_ledger)
        for b in (self._refresh_btn, self._pause_btn, self._open_btn):
            b.setStyleSheet(
                "QPushButton { padding: 5px 12px;"
                " background: rgb(20,24,32); color: rgb(0,255,200);"
                " border: 1px solid rgb(38,42,55); border-radius: 4px; }"
                "QPushButton:hover { background: rgb(30,36,46); }"
            )
            ctl.addWidget(b)
        ctl.addStretch()
        self._ledger_path_lab = _label(f"ledger: {_LEDGER}",
                                       _PUMP_DIM, point=9)
        ctl.addWidget(self._ledger_path_lab)
        layout.addLayout(ctl)

        # ── Tick ─────────────────────────────────────────────────
        self.make_timer(_TICK_MS, self._refresh)
        self._refresh()

    # ── Behaviour ──────────────────────────────────────────────

    def _toggle_auto(self) -> None:
        self._auto = not self._auto
        self._pause_btn.setText(
            "Resume auto-refresh" if not self._auto else "Pause auto-refresh"
        )

    def _open_ledger(self) -> None:
        """Reveal the ledger file in Finder (macOS); harmless elsewhere."""
        import subprocess
        try:
            subprocess.Popen(["open", "-R", str(_LEDGER)])
        except Exception:
            self.set_status(f"ledger at {_LEDGER}")

    def _refresh(self) -> None:
        if not self._auto and self.sender() is not self._refresh_btn:
            # Auto tick suppressed; manual refresh button still works.
            return
        try:
            summary = summarize_ledger()
        except Exception as exc:
            self.set_status(f"ledger read failed: {exc}")
            return
        self._today.update_with(summary["today"])
        self._24h.update_with(summary["last_24h"])
        self._life.update_with(summary["lifetime"])

        last = summary.get("last")
        if last:
            tag = last.get("request_tag") or "—"
            model = last.get("model") or "?"
            self._last_card.setText(
                f"LAST PUMP — {model}  ·  req-tag {tag}  "
                f"·  {last.get('ts_iso','')}"
            )
            self._last_detail.setText(
                f"in {_tok(last.get('prompt_tokens',0))} / "
                f"out {_tok(last.get('completion_tokens',0))} tok  ·  "
                f"{_money(float(last.get('cost_usd') or 0.0))}  ·  "
                f"{int(last.get('latency_ms') or 0):,} ms"
            )
        else:
            self._last_card.setText("LAST PUMP — (no calls yet)")
            self._last_detail.setText(
                "Switch the brain dropdown in Talk-to-Alice to a "
                "gemini:* model to start filling the tank."
            )

        self._populate_by_model(summary.get("by_model") or {})
        self._populate_recent(read_ledger(limit=_RECENT_ROWS))
        self.set_status(
            f"lifetime {summary['lifetime']['calls']} calls · "
            f"{_money(summary['lifetime']['cost_usd'])} · "
            f"updated {time.strftime('%H:%M:%S')}"
        )

    def _populate_by_model(self, by_model: Dict[str, Dict[str, Any]]) -> None:
        rows = sorted(by_model.items(),
                      key=lambda kv: float(kv[1].get("cost_usd") or 0.0),
                      reverse=True)
        self._table.setRowCount(len(rows))
        for r, (model, b) in enumerate(rows):
            cells = [
                model,
                _tok(b.get("calls", 0)),
                _tok(b.get("in", 0)),
                _tok(b.get("out", 0)),
                _money(float(b.get("cost_usd") or 0.0)),
            ]
            for c, val in enumerate(cells):
                item = QTableWidgetItem(val)
                if c >= 1:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight |
                                          Qt.AlignmentFlag.AlignVCenter)
                self._table.setItem(r, c, item)

    def _populate_recent(self, rows: List[Dict[str, Any]]) -> None:
        # Newest at top.
        rows = list(reversed(rows))
        self._recent.setRowCount(len(rows))
        for r, row in enumerate(rows):
            ts = float(row.get("ts") or 0.0)
            when = time.strftime("%H:%M:%S", time.localtime(ts)) if ts else "—"
            cells = [
                when,
                str(row.get("model") or "?"),
                _tok(row.get("prompt_tokens", 0)),
                _tok(row.get("completion_tokens", 0)),
                _money(float(row.get("cost_usd") or 0.0)),
                f"{int(row.get('latency_ms') or 0):,}",
            ]
            for c, val in enumerate(cells):
                item = QTableWidgetItem(val)
                if c >= 2:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight |
                                          Qt.AlignmentFlag.AlignVCenter)
                self._recent.setItem(r, c, item)


# ─────────────────────────────────────────────────────────────────────
# Standalone runner
# ─────────────────────────────────────────────────────────────────────
def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    w = GasStationMeterWidget()
    w.setWindowTitle("Brain Gas-Station Meter — SIFTA")
    w.resize(1000, 720)
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
