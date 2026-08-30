#!/usr/bin/env python3
"""SIFTA Model Silicon Foundry pre-silicon development app."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

from PyQt6.QtCore import QSize, Qt, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from System.swarm_model_silicon_foundry import (  # noqa: E402
    DEFAULT_MODEL,
    ModelEvidence,
    export_development_package,
    probe_ollama_model,
    readiness_stages,
)


_INK = "#e8e3d7"
_MUTED = "#9a9b98"
_GOLD = "#d7aa4d"
_GREEN = "#79c99e"
_RED = "#e27d69"
_BLUE = "#71a9c4"
_PANEL = "#171b1d"
_BORDER = "#343a3d"


class ModelSiliconFoundryWidget(QWidget):
    """Inspect one local model and export an honest foundry intake package."""

    OPEN_MAXIMIZED = True

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._evidence = ModelEvidence(model=DEFAULT_MODEL, installed=False)
        self._last_folder = ""
        self._build_ui()
        QTimer.singleShot(0, self.refresh_model)

    def _build_ui(self) -> None:
        self.setStyleSheet(
            f"""
            QWidget {{ background: #101315; color: {_INK}; font-family: 'Avenir Next'; font-size: 14px; }}
            QFrame#panel {{ background: {_PANEL}; border: 1px solid {_BORDER}; border-radius: 14px; }}
            QLineEdit, QTextEdit, QListWidget {{ background: #0d1011; border: 1px solid {_BORDER};
                border-radius: 9px; padding: 9px; selection-background-color: #6f5628; }}
            QPushButton {{ background: #252b2e; border: 1px solid #4a5256; border-radius: 9px;
                padding: 9px 15px; font-weight: 600; }}
            QPushButton:hover {{ border-color: {_GOLD}; color: #f7d98e; }}
            QPushButton#primary {{ background: #6b4f20; border-color: {_GOLD}; color: #fff0c4; }}
            QPushButton:disabled {{ color: #666; border-color: #333; background: #191c1e; }}
            QListWidget::item {{ padding: 7px; border-bottom: 1px solid #24292b; }}
            """
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        eyebrow = QLabel("SIFTA / MODEL-SPECIFIC HARDWARE")
        eyebrow.setStyleSheet(f"color: {_GOLD}; font-size: 12px; font-weight: 700; letter-spacing: 2px;")
        title = QLabel("Model Silicon Foundry")
        title.setStyleSheet("font-size: 30px; font-weight: 750;")
        subtitle = QLabel("Prepare one exact model for a hardware partner. Evidence first; fabrication claims never inferred.")
        subtitle.setStyleSheet(f"color: {_MUTED}; font-size: 15px;")
        root.addWidget(eyebrow)
        root.addWidget(title)
        root.addWidget(subtitle)

        boundary = QLabel(
            "THIS APP BUILDS A PRE-SILICON PACKAGE. It does not burn the model into your Mac, produce RTL, "
            "order wafers, tape out a design, or fabricate a physical chip."
        )
        boundary.setWordWrap(True)
        boundary.setStyleSheet(
            f"background: #2a2115; color: #f4d690; border: 1px solid #6e5427; "
            "border-radius: 10px; padding: 12px; font-weight: 650;"
        )
        root.addWidget(boundary)

        model_row = QHBoxLayout()
        self.model_edit = QLineEdit(DEFAULT_MODEL)
        self.model_edit.setPlaceholderText("Local Ollama model tag")
        scan_button = QPushButton("Verify local model")
        scan_button.clicked.connect(self.refresh_model)
        self.export_button = QPushButton("Build development package")
        self.export_button.setObjectName("primary")
        self.export_button.clicked.connect(self.export_package)
        self.export_button.setEnabled(False)
        model_row.addWidget(self.model_edit, 1)
        model_row.addWidget(scan_button)
        model_row.addWidget(self.export_button)
        root.addLayout(model_row)

        body = QHBoxLayout()
        body.setSpacing(16)
        facts_panel = self._panel()
        facts_layout = QVBoxLayout(facts_panel)
        facts_title = QLabel("Observed model body")
        facts_title.setStyleSheet("font-size: 18px; font-weight: 700;")
        facts_layout.addWidget(facts_title)
        self.facts_grid = QGridLayout()
        self.fact_values: dict[str, QLabel] = {}
        for row, (key, label) in enumerate(
            [
                ("status", "Local status"),
                ("architecture", "Architecture"),
                ("parameters", "Parameters"),
                ("quantization", "Quantization"),
                ("size", "Stored size"),
                ("context", "Context"),
                ("capabilities", "Capabilities"),
                ("digest", "Weight fingerprint"),
                ("license", "License evidence"),
            ]
        ):
            name = QLabel(label.upper())
            name.setStyleSheet(f"color: {_MUTED}; font-size: 10px; font-weight: 700;")
            value = QLabel("-")
            value.setWordWrap(True)
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.fact_values[key] = value
            self.facts_grid.addWidget(name, row, 0, Qt.AlignmentFlag.AlignTop)
            self.facts_grid.addWidget(value, row, 1)
        self.facts_grid.setColumnStretch(1, 1)
        facts_layout.addLayout(self.facts_grid)
        facts_layout.addStretch(1)

        stage_panel = self._panel()
        stage_layout = QVBoxLayout(stage_panel)
        stage_title = QLabel("Path to physical silicon")
        stage_title.setStyleSheet("font-size: 18px; font-weight: 700;")
        stage_help = QLabel("Only observed evidence can turn a stage green.")
        stage_help.setStyleSheet(f"color: {_MUTED};")
        self.stage_list = QListWidget()
        self.stage_list.setWordWrap(True)
        self.stage_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        stage_layout.addWidget(stage_title)
        stage_layout.addWidget(stage_help)
        stage_layout.addWidget(self.stage_list, 1)

        body.addWidget(facts_panel, 1)
        body.addWidget(stage_panel, 1)
        root.addLayout(body, 1)

        receipt_row = QHBoxLayout()
        self.status_label = QLabel("Waiting for local verification.")
        self.status_label.setStyleSheet(f"color: {_MUTED};")
        copy_button = QPushButton("Copy package path")
        copy_button.clicked.connect(self.copy_package_path)
        receipt_row.addWidget(self.status_label, 1)
        receipt_row.addWidget(copy_button)
        root.addLayout(receipt_row)

        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.setMaximumHeight(125)
        self.details.setPlaceholderText("Receipted package details appear here.")
        root.addWidget(self.details)

    @staticmethod
    def _panel() -> QFrame:
        panel = QFrame()
        panel.setObjectName("panel")
        return panel

    def refresh_model(self) -> None:
        model = self.model_edit.text().strip() or DEFAULT_MODEL
        self.status_label.setText("Reading the live local Ollama model body...")
        QApplication.processEvents()
        self._evidence = probe_ollama_model(model)
        self._render_evidence()

    def _render_evidence(self) -> None:
        evidence = self._evidence
        size_gb = evidence.size_bytes / 1_000_000_000 if evidence.size_bytes else 0.0
        self.fact_values["status"].setText("VERIFIED LOCAL" if evidence.installed else "NOT VERIFIED")
        self.fact_values["status"].setStyleSheet(f"color: {_GREEN if evidence.installed else _RED}; font-weight: 700;")
        self.fact_values["architecture"].setText(evidence.architecture or "unknown")
        self.fact_values["parameters"].setText(evidence.parameter_size or "unknown")
        self.fact_values["quantization"].setText(evidence.quantization or "unknown")
        self.fact_values["size"].setText(f"{size_gb:.3f} GB" if size_gb else "unknown")
        self.fact_values["context"].setText(f"{evidence.context_length:,} tokens" if evidence.context_length else "unknown")
        self.fact_values["capabilities"].setText(", ".join(evidence.capabilities) or "not reported")
        digest = evidence.digest or "not observed"
        self.fact_values["digest"].setText(f"{digest[:27]}..." if len(digest) > 30 else digest)
        self.fact_values["license"].setText("ATTACHED" if evidence.license_text else "MISSING - clearance blocked")
        self.fact_values["license"].setStyleSheet(f"color: {_GREEN if evidence.license_text else _RED}; font-weight: 650;")

        self.stage_list.clear()
        colors = {"READY": _GREEN, "BLOCKED": _RED, "PENDING": _GOLD, "EXTERNAL_REQUIRED": _BLUE, "NOT_DONE": _RED}
        for index, stage in enumerate(readiness_stages(evidence), 1):
            item = QListWidgetItem(f"{index}. {stage['label']}\n{stage['state']}  |  {stage['evidence']}")
            item.setForeground(QColor(colors.get(stage["state"], _INK)))
            item.setSizeHint(QSize(0, 72))
            item.setToolTip(stage["evidence"])
            self.stage_list.addItem(item)

        self.export_button.setEnabled(evidence.installed and bool(evidence.digest))
        if evidence.installed:
            self.status_label.setText("Model verified. Pre-silicon package can be built; physical chip remains NOT FABRICATED.")
        else:
            self.status_label.setText(evidence.error or "Model could not be verified.")
        self.details.setPlainText(json.dumps(asdict(evidence), indent=2, default=list))

    def export_package(self) -> None:
        if not self._evidence.installed or not self._evidence.digest:
            self.status_label.setText("Verify an exact installed model before exporting.")
            return
        try:
            result = export_development_package(self._evidence)
        except Exception as exc:
            self.status_label.setText(f"Package export failed: {type(exc).__name__}: {exc}")
            return
        self._last_folder = result["folder"]
        receipt_id = result["package"]["receipt_id"]
        self.status_label.setText(f"Development package ready. Receipt {receipt_id}. Physical chip: NOT FABRICATED.")
        self.details.setPlainText(
            f"Package folder:\n{result['folder']}\n\n"
            f"Vendor brief:\n{result['brief_path']}\n\n"
            f"Body ledger:\n{result['ledger_path']}"
        )

    def copy_package_path(self) -> None:
        if not self._last_folder:
            self.status_label.setText("Build a development package first.")
            return
        QApplication.clipboard().setText(self._last_folder)
        self.status_label.setText("Package path copied.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = ModelSiliconFoundryWidget()
    widget.resize(1200, 820)
    widget.show()
    raise SystemExit(app.exec())
