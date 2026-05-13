#!/usr/bin/env python3
"""sifta_provider_schedule_widget.py — Provider Schedule, in-OS spreadsheet view.

Architect 2026-05-12 22:55 — "another app where I can see only my
schedule, everything that I have done plus anything that I will be doing
in the future if I schedule something … I SEE NO DATE, FROM NOW ON DATE
AND TIME". This is the SECOND of the two apps: a read-only spreadsheet of
the owner's day — every signed segment from `architect_day_segments.jsonl`
PLUS any future pending tasks from `stigmergic_schedule.jsonl`.

Truth doctrine:
  • Read-only on both ledgers. We never mutate signed rows.
  • Date + time on every row — explicit, never relative.
  • If the file is empty / missing, the widget says exactly that.
  • Refresh every 5 s; Refresh button forces an immediate reread.

Sibling: sifta_alice_journal_widget.py is the first app — Alice's diary.

Architect 2026-05-13 00:30 — renamed from "Owner Schedule" to
"Provider Schedule" because the human IS the provider of electricity
and hardware to the SIFTA organism. Matches kernel cascade label
`owner_provider_label()` ("AGI Provider").
"""

from __future__ import annotations

import json
import sys
from datetime import date as _date, datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.sifta_base_widget import SiftaBaseWidget  # noqa: E402

_STATE = _REPO / ".sifta_state"
_SEGMENTS = _STATE / "architect_day_segments.jsonl"
_SCHEDULE = _STATE / "stigmergic_schedule.jsonl"


def _format_ts(ts: float) -> Tuple[str, str]:
    try:
        dt = datetime.fromtimestamp(float(ts))
        return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M:%S")
    except Exception:
        return "—", "—"


def _list_segment_dates() -> List[str]:
    """Distinct local_dates in architect_day_segments.jsonl, plus today."""
    dates = set()
    if _SEGMENTS.exists():
        try:
            for line in _SEGMENTS.read_text(
                encoding="utf-8", errors="ignore"
            ).splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                d = str(r.get("local_date") or "").strip()
                if d:
                    dates.add(d)
        except OSError:
            pass
    dates.add(_date.today().isoformat())
    out = sorted(dates, reverse=True)
    return out


def _read_segments_for_date(date_str: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not _SEGMENTS.exists():
        return rows
    try:
        for line in _SEGMENTS.read_text(
            encoding="utf-8", errors="ignore"
        ).splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if str(r.get("local_date") or "") == date_str:
                rows.append(r)
    except OSError:
        pass
    # Sort by start_minute_of_day ascending so the day reads top→bottom.
    rows.sort(key=lambda r: int(r.get("start_minute_of_day") or 0))
    return rows


def _read_pending_future_tasks() -> List[Dict[str, Any]]:
    """Return rows from stigmergic_schedule.jsonl that look like
    user-scheduled future events (have a due_ts / future timestamp)."""
    rows: List[Dict[str, Any]] = []
    if not _SCHEDULE.exists():
        return rows
    try:
        for line in _SCHEDULE.read_text(
            encoding="utf-8", errors="ignore"
        ).splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("done"):
                continue
            rows.append(r)
    except OSError:
        pass
    return rows


class ProviderScheduleWidget(SiftaBaseWidget):
    APP_NAME = "Provider Schedule"

    _COLS = (
        "Date",
        "Start",
        "End",
        "Min",
        "Label",
        "Loc",
        "Conf",
        "App / Context",
    )

    def build_ui(self, layout: QVBoxLayout) -> None:
        # ── Header strip ─────────────────────────────────────────────────
        bar = QHBoxLayout()
        bar.setSpacing(8)
        bar.addWidget(QLabel("Day:"))

        self._date_combo = QComboBox()
        self._date_combo.setMinimumWidth(150)
        self._date_combo.currentTextChanged.connect(lambda _t: self._reload())
        bar.addWidget(self._date_combo)

        self._count_label = QLabel("0 segments · 0 m")
        self._count_label.setStyleSheet(
            "color: rgb(145, 153, 180); font-size: 11px;"
        )
        bar.addWidget(self._count_label)
        bar.addStretch()

        self._refresh_btn = QPushButton("⟳ Refresh")
        self._refresh_btn.setFixedHeight(28)
        self._refresh_btn.setStyleSheet(
            "QPushButton { background: rgb(20, 40, 60); color: rgb(100, 200, 255); "
            "border: 1px solid rgb(40, 80, 120); border-radius: 6px; "
            "padding: 2px 12px; font-size: 12px; font-weight: bold; } "
            "QPushButton:hover { background: rgb(30, 55, 80); }"
        )
        self._refresh_btn.clicked.connect(self._reload)
        bar.addWidget(self._refresh_btn)
        layout.addLayout(bar)

        self._source_label = QLabel("source: .sifta_state/architect_day_segments.jsonl")
        self._source_label.setStyleSheet(
            "color: rgb(110, 120, 145); font-size: 10px; font-family: Menlo;"
        )
        layout.addWidget(self._source_label)

        # ── Observed segments table ──────────────────────────────────────
        observed_header = QLabel("Observed (past):")
        observed_header.setStyleSheet(
            "color: rgb(160, 210, 180); font-size: 11px; font-weight: bold; "
            "margin-top: 4px;"
        )
        layout.addWidget(observed_header)

        self._table = QTableWidget(0, len(self._COLS))
        self._table.setHorizontalHeaderLabels(self._COLS)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(True)
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setStyleSheet(
            "QTableWidget { background: rgb(14, 16, 24); "
            "alternate-background-color: rgb(18, 21, 30); "
            "color: rgb(220, 228, 240); gridline-color: rgb(40, 45, 60); "
            "font-family: Menlo; font-size: 11px; } "
            "QHeaderView::section { background: rgb(28, 32, 44); "
            "color: rgb(180, 200, 230); padding: 4px; "
            "border: 1px solid rgb(40, 45, 60); font-weight: bold; }"
        )
        hh = self._table.horizontalHeader()
        for i in range(len(self._COLS) - 1):
            hh.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(len(self._COLS) - 1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._table, 1)

        # ── Future / pending tasks table ─────────────────────────────────
        future_header = QLabel("Scheduled (future / pending):")
        future_header.setStyleSheet(
            "color: rgb(220, 200, 100); font-size: 11px; font-weight: bold; "
            "margin-top: 6px;"
        )
        layout.addWidget(future_header)

        self._future_table = QTableWidget(0, 4)
        self._future_table.setHorizontalHeaderLabels(
            ("Created", "Due", "Priority", "Task")
        )
        self._future_table.verticalHeader().setVisible(False)
        self._future_table.setShowGrid(True)
        self._future_table.setAlternatingRowColors(True)
        self._future_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._future_table.setStyleSheet(self._table.styleSheet())
        fh = self._future_table.horizontalHeader()
        fh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        fh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        fh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        fh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._future_table.setFixedHeight(180)
        layout.addWidget(self._future_table)

        self._populate_dates()
        self._reload()

        # Architect 2026-05-13 00:30 — "let's let the user see not live data
        # but with the moment opens it just all the data until that moment
        # so the user can scroll through the app without lagging". No timer.
        # The Refresh button is still wired for an on-demand re-read; the
        # date selector also re-reads when changed.

    # ── internals ─────────────────────────────────────────────────────────
    def _populate_dates(self) -> None:
        dates = _list_segment_dates()
        self._date_combo.blockSignals(True)
        self._date_combo.clear()
        self._date_combo.addItems(dates)
        self._date_combo.setCurrentIndex(0)
        self._date_combo.blockSignals(False)

    def _reload(self) -> None:
        # Keep date list fresh (new day might have appeared since last tick).
        cur = self._date_combo.currentText().strip()
        dates = _list_segment_dates()
        if cur not in dates:
            cur = dates[0]
        self._date_combo.blockSignals(True)
        self._date_combo.clear()
        self._date_combo.addItems(dates)
        self._date_combo.setCurrentText(cur)
        self._date_combo.blockSignals(False)

        rows = _read_segments_for_date(cur)
        total_m = sum(int(r.get("duration_minutes") or 0) for r in rows)
        self._table.setRowCount(len(rows))
        self._source_label.setText(
            "source: .sifta_state/architect_day_segments.jsonl  "
            f"({len(rows)} signed rows · {total_m} observed minutes · refreshed "
            f"{datetime.now().strftime('%H:%M:%S')})"
        )
        for i, r in enumerate(rows):
            d_str = str(r.get("local_date") or cur)
            start = str(r.get("start_time") or "—")
            end = str(r.get("end_time") or "—")
            dur = str(r.get("duration_minutes") or 0)
            label = str(r.get("label") or "?")
            loc = str(r.get("location") or "?")
            try:
                conf = f"{float(r.get('owner_activity_confidence') or 0):.2f}"
            except Exception:
                conf = "—"
            app = str(r.get("frontmost_app") or "")
            window = str(r.get("frontmost_window") or "")
            context = f"{app}: {window}" if window else app
            if not context:
                context = str(r.get("context_note") or "")
            label_color = {
                "coding": QColor(140, 220, 160),
                "researching": QColor(220, 200, 120),
                "file_browsing": QColor(190, 180, 220),
            }.get(label, QColor(200, 215, 235))
            self._set_cell(self._table, i, 0, d_str, QColor(180, 200, 230))
            self._set_cell(self._table, i, 1, start, QColor(180, 200, 230))
            self._set_cell(self._table, i, 2, end, QColor(180, 200, 230))
            self._set_cell(self._table, i, 3, dur, QColor(170, 180, 200))
            self._set_cell(self._table, i, 4, label, label_color)
            self._set_cell(self._table, i, 5, loc, QColor(160, 200, 200))
            self._set_cell(self._table, i, 6, conf, QColor(200, 200, 160))
            self._set_cell(self._table, i, 7, context, QColor(225, 230, 240))
        if rows:
            self._table.scrollToBottom()

        # Future / pending side
        future = _read_pending_future_tasks()
        self._future_table.setRowCount(len(future))
        for i, r in enumerate(future):
            cts = float(r.get("created") or r.get("ts") or 0)
            cd, ct = _format_ts(cts)
            created = f"{cd} {ct}" if cd != "—" else "—"
            due = ""
            due_ts = r.get("due_ts")
            if due_ts:
                dd, dt = _format_ts(float(due_ts))
                due = f"{dd} {dt}"
            else:
                due = "no due time"
            prio = str(r.get("priority") or "")
            task = str(r.get("text") or "")[:300].replace("\n", " ")
            self._set_cell(
                self._future_table, i, 0, created, QColor(180, 200, 230)
            )
            self._set_cell(
                self._future_table, i, 1, due, QColor(220, 200, 120)
            )
            self._set_cell(
                self._future_table, i, 2, prio, QColor(200, 200, 160)
            )
            self._set_cell(
                self._future_table, i, 3, task, QColor(225, 230, 240)
            )

        self._count_label.setText(
            f"{cur}: {len(rows)} segments · {total_m} observed minutes"
            + (f" · {len(future)} pending" if future else "")
        )
        self.set_status(f"{len(rows)} observed · {len(future)} pending")

    def _set_cell(
        self,
        table: QTableWidget,
        row: int,
        col: int,
        text: str,
        color: QColor,
    ) -> None:
        item = QTableWidgetItem(text)
        item.setForeground(color)
        item.setToolTip(text)
        table.setItem(row, col, item)


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    w = OwnerScheduleWidget()
    w.resize(1180, 720)
    w.setWindowTitle("Provider Schedule — SIFTA OS")
    w.show()
    sys.exit(app.exec())
