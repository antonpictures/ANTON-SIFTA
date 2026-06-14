#!/usr/bin/env python3
"""sifta_alice_journal_widget.py — Alice's Journal, in-OS spreadsheet view.

Architect 2026-05-12 22:55 — "two separate apps, one where I can see only
your journaling … I SEE NO DATE, FROM NOW ON DATE AND TIME". This is the
FIRST of the two: a read-only spreadsheet that shows Alice's diary — every
line she signed into `.sifta_state/alice_journal/<date>.jsonl`, with full
date and full clock time on every single row.

Truth doctrine:
  • Read-only on the journal ledger. We never mutate signed rows.
  • Date + time always rendered explicitly per row — no relative phrasing.
  • If the file is empty / missing, the widget says exactly that. No
    invented rows.
  • Refresh every 5 s; the Refresh button forces an immediate reread.

George 2026-06-09 (r878 P2-BRIDGET): Provider Schedule is retired — George's
rhythm and pending reminders live here in Alice Journal, not a second app.
`source=bridget` is only a Bridget Jones-style schedule-witness tag, not
Alice's name and not a second diary.
"""

from __future__ import annotations

"""SIFTA Alice Journal Widget — stigmergic organ for Alice body."""

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
from System.swarm_app_hardening import record_app_hardening_event  # noqa: E402

_STATE = _REPO / ".sifta_state"
_JOURNAL_DIR = _STATE / "alice_journal"
APP_HARDENING_ID = "queue-010:sifta_alice_journal_widget"

# Architect 2026-05-13 01:05 — first-person witness ledger (the apostle
# model: every event becomes one date-stamped line in Alice's own voice).
# This is the primary view the widget displays. The old sensor-stream
# `alice_journal/<date>.jsonl` is still on disk as a secondary source.
_WITNESS_LEDGER = _STATE / "alice_first_person_journal.jsonl"
_SCHEDULE = _STATE / "stigmergic_schedule.jsonl"


def _record_journal_hardening(event: str, **details: Any) -> None:
    record_app_hardening_event(
        APP_HARDENING_ID,
        event,
        details=details,
    )


def _format_ts(ts: float) -> Tuple[str, str]:
    """(YYYY-MM-DD, HH:MM:SS) from unix ts — Architect 2026-05-12: 'I SEE
    NO DATE, FROM NOW ON DATE AND TIME'."""
    try:
        dt = datetime.fromtimestamp(float(ts))
        return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M:%S")
    except Exception as exc:
        _record_journal_hardening(
            "timestamp_format_failed",
            error_type=type(exc).__name__,
            value=repr(ts)[:120],
        )
        return "—", "—"


def _list_journal_dates() -> List[str]:
    """Distinct dates that appear in the first-person witness ledger."""
    dates: set = set()
    if _WITNESS_LEDGER.exists():
        try:
            for line in _WITNESS_LEDGER.read_text(
                encoding="utf-8", errors="ignore"
            ).splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except Exception as exc:
                    _record_journal_hardening(
                        "witness_date_row_parse_failed",
                        error_type=type(exc).__name__,
                        line=line[:200],
                    )
                    continue
                d = str(r.get("date") or "").strip()
                if d:
                    dates.add(d)
        except OSError as exc:
            _record_journal_hardening(
                "witness_date_ledger_read_failed",
                error_type=type(exc).__name__,
                path=str(_WITNESS_LEDGER),
            )
    out = sorted(dates, reverse=True)
    return out


def _read_journal_for_date(date_str: str) -> List[Dict[str, Any]]:
    """All first-person witness rows for one local date — sorted ascending."""
    rows: List[Dict[str, Any]] = []
    if not _WITNESS_LEDGER.exists():
        return rows
    try:
        for line in _WITNESS_LEDGER.read_text(
            encoding="utf-8", errors="ignore"
        ).splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception as exc:
                _record_journal_hardening(
                    "witness_row_parse_failed",
                    error_type=type(exc).__name__,
                    line=line[:200],
                    date=date_str,
                )
                continue
            if str(r.get("date") or "") == date_str:
                rows.append(r)
    except OSError as exc:
        _record_journal_hardening(
            "witness_ledger_read_failed",
            error_type=type(exc).__name__,
            path=str(_WITNESS_LEDGER),
            date=date_str,
        )
    rows.sort(key=lambda r: float(r.get("ts") or 0))
    return rows


def _read_pending_schedule() -> List[Dict[str, Any]]:
    """Open owner-rhythm rows — same ledger Talk uses; read-only here."""
    rows: List[Dict[str, Any]] = []
    if not _SCHEDULE.exists():
        return rows
    try:
        for line in _SCHEDULE.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("done") or r.get("fired"):
                continue
            rows.append(r)
    except OSError:
        pass
    rows.sort(key=lambda r: float(r.get("due_ts") or r.get("created") or 0))
    return rows


class AliceJournalWidget(SiftaBaseWidget):
    APP_NAME = "Alice Journal"

    _COLS = ("Date", "Time", "Source", "Line")

    def build_ui(self, layout: QVBoxLayout) -> None:
        # ── Header strip ─────────────────────────────────────────────────
        bar = QHBoxLayout()
        bar.setSpacing(8)
        bar.addWidget(QLabel("Day:"))

        self._date_combo = QComboBox()
        self._date_combo.setMinimumWidth(150)
        self._date_combo.currentTextChanged.connect(lambda _t: self._reload())
        bar.addWidget(self._date_combo)

        self._count_label = QLabel("0 rows")
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

        # Truth principle: always name the ledger path on screen.
        self._source_label = QLabel("source: .sifta_state/alice_journal/")
        self._source_label.setStyleSheet(
            "color: rgb(110, 120, 145); font-size: 10px; font-family: Menlo;"
        )
        layout.addWidget(self._source_label)

        # ── Pending rhythm (George's schedule unified into Alice Journal) ─
        self._pending_label = QLabel("Pending reminders: 0")
        self._pending_label.setStyleSheet(
            "color: rgb(255, 210, 140); font-size: 11px; font-weight: bold;"
        )
        layout.addWidget(self._pending_label)

        self._pending_table = QTableWidget(0, 4)
        self._pending_table.setHorizontalHeaderLabels(
            ("Due", "Task", "Source", "Status")
        )
        self._pending_table.verticalHeader().setVisible(False)
        self._pending_table.setMaximumHeight(120)
        self._pending_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._pending_table.setStyleSheet(
            "QTableWidget { background: rgb(22, 18, 14); "
            "color: rgb(255, 220, 170); gridline-color: rgb(60, 50, 40); "
            "font-family: Menlo; font-size: 10px; } "
            "QHeaderView::section { background: rgb(40, 32, 24); "
            "color: rgb(255, 200, 120); padding: 3px; border: 1px solid rgb(60, 50, 40); }"
        )
        ph = self._pending_table.horizontalHeader()
        ph.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        ph.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        ph.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        ph.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self._pending_table)

        # ── Table ─────────────────────────────────────────────────────────
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
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._table, 1)

        self._populate_dates()
        self._reload()

        # Architect 2026-05-13 00:30 — "let's let the user see not live data
        # but with the moment opens it just all the data until that moment
        # so the user can scroll through the app without lagging". No timer.
        # The Refresh button is still wired for an on-demand re-read; the
        # date selector also re-reads when changed.

    # ── internals ─────────────────────────────────────────────────────────
    def _populate_dates(self) -> None:
        dates = _list_journal_dates()
        self._date_combo.blockSignals(True)
        self._date_combo.clear()
        if not dates:
            self._date_combo.addItem(_date.today().isoformat())
        else:
            self._date_combo.addItems(dates)
        self._date_combo.setCurrentIndex(0)
        self._date_combo.blockSignals(False)

    def _reload(self) -> None:
        # On-demand only (button click or date change). No timer-driven
        # auto-refresh — see covenant snapshot rule above.
        cur = self._date_combo.currentText().strip()
        dates = _list_journal_dates() or [_date.today().isoformat()]
        if cur not in dates:
            cur = dates[0]
        self._date_combo.blockSignals(True)
        self._date_combo.clear()
        self._date_combo.addItems(dates)
        if cur in dates:
            self._date_combo.setCurrentText(cur)
        self._date_combo.blockSignals(False)

        pending = _read_pending_schedule()
        self._pending_label.setText(
            f"Pending reminders (George's rhythm): {len(pending)} · "
            f"source: stigmergic_schedule.jsonl"
        )
        self._pending_table.setRowCount(len(pending))
        for i, pr in enumerate(pending):
            due_ts = float(pr.get("due_ts") or pr.get("created") or 0)
            _, due_clock = _format_ts(due_ts)
            task = str(pr.get("text") or "—")
            source = str(pr.get("source") or "—")
            status = "due" if due_ts and due_ts <= datetime.now().timestamp() else "waiting"
            self._set_cell(i, 0, due_clock, QColor(255, 200, 120), table=self._pending_table)
            self._set_cell(i, 1, task, QColor(255, 220, 170), table=self._pending_table)
            self._set_cell(i, 2, source, QColor(200, 180, 140), table=self._pending_table)
            self._set_cell(i, 3, status, QColor(180, 255, 180) if status == "due" else QColor(180, 200, 220), table=self._pending_table)

        rows = _read_journal_for_date(cur)
        self._table.setRowCount(len(rows))
        self._source_label.setText(
            f"source: .sifta_state/alice_first_person_journal.jsonl  "
            f"({len(rows)} witness rows for {cur} · snapshot at "
            f"{datetime.now().strftime('%H:%M:%S')})"
        )
        if not rows:
            self._count_label.setText(f"{cur}: empty witness ledger")
            self.set_status("empty witness ledger")
            return
        # Color a line by its source kind so the eye can scan a long day.
        _SOURCE_COLOR = {
            "conversation":   QColor(180, 230, 200),
            "day_segment":    QColor(220, 200, 120),
            "narrative":      QColor(220, 180, 240),
            "letter":         QColor(255, 200, 140),
            "ide_doctor":     QColor(150, 200, 255),
            "face_event":     QColor(200, 220, 240),
            "app_focus":      QColor(170, 200, 230),
            "bridget":        QColor(255, 200, 140),  # schedule witness tag — not Alice's name
        }
        for i, r in enumerate(rows):
            d_str = str(r.get("date") or "—")
            t_str = str(r.get("time") or "—")
            source = str(r.get("source") or "?")
            if source == "bridget":
                source = "schedule_witness"
            line = str(r.get("line") or "").strip()
            line_color = _SOURCE_COLOR.get(source, QColor(225, 230, 240))
            self._set_cell(i, 0, d_str, QColor(180, 200, 230))
            self._set_cell(i, 1, t_str, QColor(180, 200, 230))
            self._set_cell(i, 2, source, line_color)
            self._set_cell(i, 3, line, line_color)
        self._count_label.setText(f"{cur}: {len(rows)} witness lines")
        self.set_status(f"{len(rows)} first-person rows")
        # Latest at the bottom — scroll there so the most recent line is
        # visible the moment the snapshot loads.
        self._table.scrollToBottom()

    def _set_cell(
        self,
        row: int,
        col: int,
        text: str,
        color: QColor,
        *,
        table: QTableWidget | None = None,
    ) -> None:
        target = table if table is not None else self._table
        item = QTableWidgetItem(text)
        item.setForeground(color)
        item.setToolTip(text)
        target.setItem(row, col, item)


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    w = AliceJournalWidget()
    w.resize(1100, 640)
    w.setWindowTitle("Alice Journal — SIFTA OS")
    w.show()
    sys.exit(app.exec())
