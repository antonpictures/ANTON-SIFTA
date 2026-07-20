#!/usr/bin/env python3
"""Stigmergic Shared Experience Anchors — SIFTA Apps OS surface (r1370).

Lists every real person/celebrity/contact mentioned in shared George+Alice experiences.
Fiction personas (e.g. bare 'Joy' from a cooking thread) are explicitly rejected.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from System.sifta_base_widget import SiftaBaseWidget
from System.swarm_filename_time_anchor import seed_known_evidence_file_times
from System.swarm_stigmergic_shared_experience_anchors import (
    TRUTH_LABEL,
    confirm_shared_experience_anchor,
    edit_shared_experience_anchor,
    list_anchor_snapshots,
    record_anchor_scan_receipt,
    reject_shared_experience_anchor,
    scan_conversation_for_anchors,
    seed_fiction_rejections,
)


class StigmergicAnchorsWidget(SiftaBaseWidget):
    APP_NAME = "Stigmergic Shared Experience Anchors"

    def build_ui(self, layout: QVBoxLayout) -> None:
        header = QLabel(
            "Real people & shared experiences with Alice — fiction personas blocked "
            f"({TRUTH_LABEL})"
        )
        header.setStyleSheet("color: rgb(0,255,200); font-size: 13px; font-weight: bold;")
        header.setWordWrap(True)
        layout.addWidget(header)

        self.status = QLabel("Press Scan to read alice_conversation.jsonl")
        self.status.setStyleSheet("color: rgb(180,190,210); font-size: 11px;")
        layout.addWidget(self.status)

        btn_row = QHBoxLayout()
        scan_btn = QPushButton("Scan conversation ledger")
        scan_btn.clicked.connect(self.run_scan)
        btn_row.addWidget(scan_btn)
        refresh_btn = QPushButton("Refresh table")
        refresh_btn.clicked.connect(self.refresh_table)
        btn_row.addWidget(refresh_btn)
        confirm_btn = QPushButton("Confirm selected")
        confirm_btn.clicked.connect(self.confirm_selected)
        btn_row.addWidget(confirm_btn)
        reject_btn = QPushButton("Reject selected")
        reject_btn.clicked.connect(self.reject_selected)
        btn_row.addWidget(reject_btn)
        edit_btn = QPushButton("Edit selected")
        edit_btn.clicked.connect(self.edit_selected)
        btn_row.addWidget(edit_btn)
        pin_time_btn = QPushButton("Pin file times from evidence")
        pin_time_btn.clicked.connect(self.pin_file_times)
        btn_row.addWidget(pin_time_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels(
            [
                "Name",
                "Status",
                "Kind",
                "Mentions",
                "Last seen",
                "Evidence",
                "Concept",
                "Timeline",
                "Disambiguation",
                "Experience snippet",
            ]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(
            "QTableWidget { background: rgb(12,10,18); color: rgb(220,225,245); "
            "gridline-color: rgb(45,42,65); font-size: 11px; }"
            "QHeaderView::section { background: rgb(25,22,35); color: rgb(0,255,200); }"
        )
        layout.addWidget(self.table, 1)

        note = QLabel(
            "Living timeline pins: edit name, concept, and disambiguation here (George or Alice "
            "in-app). Timeline labels name where the pin lands in George+Alice history. Rejected "
            "fiction anchors stay blocked. CONFIRMED rows feed Talk; CANDIDATE rows stay app-only "
            "until confirmed."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: rgb(140,150,170); font-size: 10px;")
        layout.addWidget(note)

        seed_fiction_rejections()
        self._pin_file_times_quiet()
        self.refresh_table()

    def _pin_file_times_quiet(self) -> list[dict]:
        return seed_known_evidence_file_times()

    def pin_file_times(self) -> None:
        results = self._pin_file_times_quiet()
        ok = sum(1 for r in results if r.get("ok"))
        fail = len(results) - ok
        self.status.setText(
            f"Pinned file times: {ok} ok · {fail} skipped/missing · "
            "timeline labels updated from filename + file birthtime"
        )
        self.refresh_table()

    def run_scan(self) -> None:
        result = scan_conversation_for_anchors()
        record_anchor_scan_receipt(result)
        pin_results = self._pin_file_times_quiet()
        pin_ok = sum(1 for r in pin_results if r.get("ok"))
        self.status.setText(
            f"Scanned {result.get('conversation_rows_scanned', 0)} rows · "
            f"registered {result.get('anchors_registered_this_scan', 0)} mentions · "
            f"{result.get('anchor_count', 0)} anchors total · "
            f"{result.get('rejected_count', 0)} rejected fiction · "
            f"file-time pins {pin_ok}"
        )
        self.refresh_table()

    def _selected_name(self) -> str:
        row = self.table.currentRow()
        if row < 0:
            return ""
        item = self.table.item(row, 0)
        return item.text().strip() if item else ""

    def confirm_selected(self) -> None:
        name = self._selected_name()
        if not name:
            self.status.setText("Select an anchor row first.")
            return
        row = confirm_shared_experience_anchor(
            name,
            evidence_kind="owner_confirmation_in_app",
            evidence_status="owner_confirmed",
            evidence_source=self.APP_NAME,
            link_human=True,
        )
        self.status.setText(
            f"Confirmed {row.get('canonical_name') or name} · "
            f"human={row.get('human_identity_id') or row.get('human_identity_link_error') or 'linked'}"
        )
        self.refresh_table()

    def reject_selected(self) -> None:
        name = self._selected_name()
        if not name:
            self.status.setText("Select an anchor row first.")
            return
        row = reject_shared_experience_anchor(
            name,
            reason="owner_rejected_candidate_anchor_in_app",
            evidence_kind="owner_rejection_in_app",
            evidence_status="owner_rejected",
            evidence_source=self.APP_NAME,
        )
        self.status.setText(f"Rejected {row.get('canonical_name') or name}")
        self.refresh_table()

    def edit_selected(self) -> None:
        name = self._selected_name()
        if not name:
            self.status.setText("Select an anchor row first.")
            return
        snaps = {s.canonical_name: s for s in list_anchor_snapshots()}
        snap = snaps.get(name)
        if not snap:
            self.status.setText(f"No snapshot for {name}")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit anchor — living timeline pin")
        form = QFormLayout(dialog)
        name_edit = QLineEdit(snap.canonical_name)
        concept_edit = QLineEdit(snap.concept_label)
        timeline_edit = QLineEdit(snap.timeline_label)
        disamb_edit = QLineEdit(snap.disambiguation)
        form.addRow("Name", name_edit)
        form.addRow("Concept", concept_edit)
        form.addRow("Timeline", timeline_edit)
        form.addRow("Disambiguation", disamb_edit)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        row = edit_shared_experience_anchor(
            name,
            new_canonical_name=name_edit.text().strip(),
            concept_label=concept_edit.text().strip(),
            timeline_label=timeline_edit.text().strip(),
            disambiguation=disamb_edit.text().strip(),
            editor="alice_in_app",
            evidence_source=self.APP_NAME,
        )
        self.status.setText(
            f"Edited anchor -> {row.get('canonical_name')} · "
            f"concept={row.get('concept_label') or '—'} · "
            f"timeline={row.get('timeline_label') or '—'}"
        )
        self.refresh_table()

    def refresh_table(self) -> None:
        snapshots = list_anchor_snapshots()
        self.table.setRowCount(len(snapshots))
        for row_idx, snap in enumerate(snapshots):
            evidence = snap.evidence_status
            if snap.evidence_kind:
                evidence = f"{evidence} / {snap.evidence_kind}" if evidence else snap.evidence_kind
            items = [
                snap.canonical_name,
                snap.status,
                snap.anchor_kind,
                str(snap.mention_count),
                self._fmt_ts(snap.last_seen_ts),
                evidence,
                snap.concept_label,
                snap.timeline_label,
                snap.disambiguation,
                snap.experience_snippet or snap.rejection_reason,
            ]
            for col_idx, value in enumerate(items):
                item = QTableWidgetItem(value)
                if snap.status == "REJECTED_FICTION":
                    item.setForeground(Qt.GlobalColor.darkRed)
                elif snap.status == "REJECTED":
                    item.setForeground(Qt.GlobalColor.red)
                elif snap.status == "CONFIRMED":
                    item.setForeground(Qt.GlobalColor.green)
                elif snap.status == "CANDIDATE":
                    item.setForeground(Qt.GlobalColor.yellow)
                self.table.setItem(row_idx, col_idx, item)
        self.table.resizeColumnsToContents()

    @staticmethod
    def _fmt_ts(ts: float) -> str:
        if not ts:
            return "—"
        try:
            from datetime import datetime

            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
        except (OSError, OverflowError, ValueError):
            return "—"


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    win = StigmergicAnchorsWidget()
    win.resize(1000, 640)
    win.show()
    sys.exit(app.exec())
