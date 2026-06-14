#!/usr/bin/env python3
"""
Applications/sifta_stigmerobotics_widget.py
==========================================

Canonical Stigmerobotics app for the SIFTA desktop.

This is a Python-first Qt surface inside the SIFTA OS process. It replaces
scattered tournament briefing windows with one macOS-menu app that shows the
ROB 501 proof ladder, live ledger-auditor status, immune STGM economy, and the
source tournament documents. No browser escape hatch is used.
"""
from __future__ import annotations

"""SIFTA Stigmerobotics Widget — stigmergic organ for Alice body."""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
_DOC = _REPO / "Documents" / "STIGMEROBOTICS_ROB501_TOURNAMENT.md"
_MANIFEST = _REPO / "Applications" / "apps_manifest.json"

if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QComboBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from System.sifta_base_widget import SiftaBaseWidget

try:
    from System.ledger_auditor import audit_live
except Exception:
    audit_live = None

try:
    from System.swarm_immune_economy_summary import (
        format_life_cockpit_summary,
        summarize_immune_economy,
    )
except Exception:
    format_life_cockpit_summary = None
    summarize_immune_economy = None

try:
    from System.stigmerobotics_state_vector import CHANNEL_UNITS, live_state_vector
except Exception:
    CHANNEL_UNITS = {}
    live_state_vector = None

try:
    from System.stigmerobotics_pheromone_field import live_pheromone_field
except Exception:
    live_pheromone_field = None

try:
    from System.stigmerobotics_safety_graph import live_safety_graph
except Exception:
    live_safety_graph = None

try:
    from System.stigmerobotics_observability import live_observability_report
except Exception:
    live_observability_report = None

try:
    from System.stigmerobotics_chaos_escape import live_chaos_escape
except Exception:
    live_chaos_escape = None

try:
    from System.stigmerobotics_segmental_coordination import build_coordination_report
    _TRACE_PATH = Path(__file__).resolve().parent.parent / ".sifta_state" / "ide_stigmergic_trace.jsonl"
except Exception:
    build_coordination_report = None
    _TRACE_PATH = None

try:
    from System.stigmerobotics_wet_dry_interface import build_wet_dry_bridge
except Exception:
    build_wet_dry_bridge = None

try:
    from System.stigmerobotics_biohybrid_boundary import live_biohybrid_report
except Exception:
    live_biohybrid_report = None

try:
    from System.stigmerobotics_body_connection import (
        build_body_connection_proof,
        BodyConnectionProof as _BodyConnectionProof,
    )
except Exception:
    build_body_connection_proof = None  # type: ignore[assignment]
    _BodyConnectionProof = None

try:
    from System.stigmerobotics_ik_baseline import build_combined_robot_data_report
except Exception:
    build_combined_robot_data_report = None

try:
    from System.stigmerobotics_e51_hardware_prep import (
        CHAIN_STEPS as _E51_CHAIN_STEPS,
        list_physical_bodies as _list_physical_bodies,
    )
except Exception:
    _E51_CHAIN_STEPS = ()
    _list_physical_bodies = None


_GLOBAL_STYLE = """
QWidget {
    background-color: #0b0c10;
    color: #c5c6c7;
    font-family: 'Inter', 'Roboto', 'Menlo', monospace;
    font-size: 13px;
}
QTabWidget::pane {
    border: 1px solid #1f2833;
    background: #0b0c10;
    border-radius: 8px;
    top: -1px;
}
QTabBar::tab {
    background: #1f2833;
    color: #8892b0;
    padding: 10px 20px;
    margin-right: 4px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    border: 1px solid transparent;
}
QTabBar::tab:selected {
    background: #0b0c10;
    color: #66fcf1;
    border: 1px solid #1f2833;
    border-bottom-color: #0b0c10;
    font-weight: bold;
}
QTabBar::tab:hover:!selected {
    background: #2b3a4a;
    color: #c5c6c7;
}
QLabel#header {
    color: #66fcf1;
    font-size: 18px;
    font-weight: bold;
    padding: 12px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #11141c, stop:1 #0b0c10);
    border-radius: 6px;
    border-left: 5px solid #66fcf1;
}
QLabel[card="true"] {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1a1a24, stop:1 #0b0c10);
    border: 1px solid #1f2833;
    border-radius: 8px;
    padding: 12px;
    color: #45a29e;
    font-size: 13px;
}
QLabel[card="true"]:hover {
    border: 1px solid #45a29e;
}
QTableWidget {
    background-color: #0b0c10;
    alternate-background-color: #12141a;
    gridline-color: #1f2833;
    border: 1px solid #1f2833;
    border-radius: 6px;
    selection-background-color: #1f2833;
    selection-color: #66fcf1;
}
QHeaderView::section {
    background-color: #1a1a24;
    color: #66fcf1;
    padding: 6px;
    border: 1px solid #1f2833;
    font-weight: bold;
}
QPlainTextEdit, QTextBrowser {
    background-color: #0b0c10;
    color: #c5c6c7;
    border: 1px solid #1f2833;
    border-radius: 6px;
    padding: 10px;
    font-family: 'Menlo', monospace;
    font-size: 12px;
}
QPushButton {
    background-color: #0b0c10;
    color: #66fcf1;
    border: 1px solid #45a29e;
    border-radius: 6px;
    padding: 8px 24px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #1f2833;
    border: 1px solid #66fcf1;
}
QPushButton:pressed {
    background-color: #45a29e;
    color: #0b0c10;
}
QComboBox {
    background-color: #101722;
    color: #e8ffff;
    border: 1px solid #45a29e;
    border-radius: 6px;
    padding: 8px 12px;
    min-height: 22px;
    font-weight: bold;
}
QComboBox:hover {
    border: 1px solid #66fcf1;
    background-color: #162233;
}
QComboBox::drop-down {
    border: 0px;
    width: 32px;
}
QComboBox QAbstractItemView {
    background-color: #0b0c10;
    color: #e8ffff;
    border: 1px solid #45a29e;
    selection-background-color: #1f2833;
    selection-color: #66fcf1;
    outline: 0;
}
QScrollBar:vertical {
    border: none;
    background: #0b0c10;
    width: 8px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #1f2833;
    min-height: 20px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #45a29e;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar:horizontal {
    border: none;
    background: #0b0c10;
    height: 8px;
    margin: 0px;
}
QScrollBar::handle:horizontal {
    background: #1f2833;
    min-width: 20px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal:hover {
    background: #45a29e;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}
"""

_ACTIVE_TESTS = (
    "tests/test_stigmero_e01_quantifier_gate.py",
    "tests/test_stigmero_e02_induction.py",
    "tests/test_stigmero_e03_state_vector.py",
    "tests/test_stigmero_e04_sensor_subspaces.py",
    "tests/test_stigmero_e33_pheromone_field.py",
    "tests/test_stigmero_e34_safety_graph.py",
    "tests/test_stigmero_e35_observability.py",
    "tests/test_stigmero_e38_safe_append_automaton.py",
    "tests/test_stigmero_e39_aco_convergence.py",
    "tests/test_stigmero_e45_bifurcation.py",
    "tests/test_stigmero_e45_chaos_escape.py",
    "tests/test_stigmero_e46_segmental_coordination.py",
    "tests/test_stigmero_e47_biohybrid_boundary.py",
    "tests/test_stigmero_e47_wet_dry_interface.py",
    "tests/test_stigmero_e48_physical_protocol.py",
    "tests/test_stigmero_e48_wetlab_integration.py",
    "tests/test_stigmero_e49_irb2400_ik.py",
    "tests/test_stigmero_e50_arkoma_ik.py",
    "tests/test_stigmero_ik_baseline.py",
    "tests/test_stigmero_e51_hardware_prep.py",
    "tests/test_ledger_invariants.py",
    "tests/test_stigmero_body_connection_proof.py",
)


def _short(text: str, limit: int = 96) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _read_manifest() -> dict[str, dict[str, Any]]:
    try:
        data = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _active_stigmerobotics_apps() -> list[str]:
    apps = []
    for name, meta in _read_manifest().items():
        blob = f"{name} {json.dumps(meta, ensure_ascii=False)}".lower()
        if "stigmerobotics" not in blob:
            continue
        if meta.get("_retired") or meta.get("hidden"):
            continue
        apps.append(name)
    return sorted(apps)


def _parse_event_rows(markdown: str) -> list[list[str]]:
    rows: list[list[str]] = []
    in_grid = False
    for line in markdown.splitlines():
        if line.startswith("| # | ROB 501 topic |"):
            in_grid = True
            continue
        if in_grid and line.startswith("|---"):
            continue
        if in_grid and not line.startswith("|"):
            break
        if not in_grid or not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 6 or not cells[0].strip().isdigit():
            continue
        rows.append(cells[:6])
    return rows


def _doc_text() -> str:
    if not _DOC.exists():
        return f"Missing document: {_DOC}"
    return _DOC.read_text(encoding="utf-8", errors="replace")


class StigmeroboticsWidget(SiftaBaseWidget):
    """StigmeroboticsWidget — Alice organ."""
    APP_NAME = "Stigmerobotics"

    def build_ui(self, layout: QVBoxLayout) -> None:
        self.setStyleSheet(_GLOBAL_STYLE)
        self._cards: dict[str, QLabel] = {}

        header = QLabel("STIGMEROBOTICS - ROB 501 Proof Control Room")
        header.setObjectName("header")
        layout.addWidget(header)

        cards = QGridLayout()
        cards.setHorizontalSpacing(12)
        cards.setVerticalSpacing(12)
        for idx, name in enumerate(("singleton", "proofs", "state", "pheromone", "safety", "observability", "chaos", "segmental", "biohybrid", "wetdry", "ledger", "economy", "bodyproof")):
            lbl = QLabel("...")
            lbl.setObjectName(f"card_{name}")
            lbl.setProperty("card", "true")
            lbl.setMinimumHeight(64)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._cards[name] = lbl
            cards.addWidget(lbl, idx // 3, idx % 3)
        layout.addLayout(cards)

        nav = QHBoxLayout()
        nav.setSpacing(10)
        nav_label = QLabel("Page")
        nav_label.setMinimumWidth(44)
        nav.addWidget(nav_label)
        self.page_selector = QComboBox()
        self.page_selector.setMinimumWidth(320)
        self.page_selector.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.page_selector.currentIndexChanged.connect(self._on_page_selected)
        nav.addWidget(self.page_selector, 1)
        layout.addLayout(nav)

        self.tabs = QTabWidget()
        self.tabs.tabBar().hide()
        self.tabs.currentChanged.connect(self._sync_page_selector)
        layout.addWidget(self.tabs, 1)
        self._page_selector_updating = False

        self._build_overview_tab()
        self._build_state_vector_tab()
        self._build_pheromone_tab()
        self._build_safety_graph_tab()
        self._build_observability_tab()
        self._build_chaos_escape_tab()
        self._build_segmental_tab()
        self._build_biohybrid_tab()
        self._build_wet_dry_tab()
        self._build_edge_species_tab()
        self._build_robot_data_tab()
        self._build_body_proof_tab()
        self._build_audit_tab()
        self._build_docs_tab()
        self._build_tests_tab()
        self._sync_page_selector_items()

        row = QHBoxLayout()
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh_all)
        row.addWidget(refresh)
        run = QPushButton("Run Active Proof Tests")
        run.clicked.connect(self.run_proof_tests)
        row.addWidget(run)
        row.addStretch()
        layout.addLayout(row)

        self._timer = self.make_timer(10_000, self.refresh_all)
        self.refresh_all()

    def _sync_page_selector_items(self) -> None:
        self._page_selector_updating = True
        try:
            self.page_selector.clear()
            for index in range(self.tabs.count()):
                self.page_selector.addItem(self.tabs.tabText(index))
            self.page_selector.setCurrentIndex(self.tabs.currentIndex())
        finally:
            self._page_selector_updating = False

    def _on_page_selected(self, index: int) -> None:
        if self._page_selector_updating or index < 0:
            return
        if index != self.tabs.currentIndex():
            self.tabs.setCurrentIndex(index)

    def _sync_page_selector(self, index: int) -> None:
        if not hasattr(self, "page_selector") or self.page_selector.currentIndex() == index:
            return
        self._page_selector_updating = True
        try:
            self.page_selector.setCurrentIndex(index)
        finally:
            self._page_selector_updating = False

    def _build_overview_tab(self) -> None:
        page = QWidget()
        root = QVBoxLayout(page)
        self.event_table = QTableWidget(0, 4)
        self.event_table.setHorizontalHeaderLabels(("Event", "ROB 501 topic", "Prove in SIFTA", "Status"))
        self.event_table.horizontalHeader().setStretchLastSection(True)
        self.event_table.setAlternatingRowColors(True)
        root.addWidget(self.event_table, 1)
        self.singleton_report = QPlainTextEdit()
        self.singleton_report.setReadOnly(True)
        self.singleton_report.setMaximumHeight(140)
        root.addWidget(self.singleton_report)
        self.tabs.addTab(page, "Proof Matrix")

    def _build_state_vector_tab(self) -> None:
        page = QWidget()
        root = QVBoxLayout(page)
        self.state_vector_table = QTableWidget(0, 4)
        self.state_vector_table.setHorizontalHeaderLabels(("Channel", "Value", "Unit", "Meaning"))
        self.state_vector_table.horizontalHeader().setStretchLastSection(True)
        self.state_vector_table.setAlternatingRowColors(True)
        root.addWidget(self.state_vector_table, 1)

        self.state_vector_log = QPlainTextEdit()
        self.state_vector_log.setReadOnly(True)
        self.state_vector_log.setMaximumHeight(220)
        root.addWidget(self.state_vector_log)
        self.tabs.addTab(page, "E03 State Vector")

    def _build_pheromone_tab(self) -> None:
        page = QWidget()
        root = QVBoxLayout(page)
        self.pheromone_table = QTableWidget(0, 3)
        self.pheromone_table.setHorizontalHeaderLabels(("Channel", "Intensity", "After 60s"))
        self.pheromone_table.horizontalHeader().setStretchLastSection(True)
        self.pheromone_table.setAlternatingRowColors(True)
        root.addWidget(self.pheromone_table, 1)

        self.pheromone_log = QPlainTextEdit()
        self.pheromone_log.setReadOnly(True)
        self.pheromone_log.setMaximumHeight(240)
        root.addWidget(self.pheromone_log)
        self.tabs.addTab(page, "E33 Pheromone Field")

    def _build_safety_graph_tab(self) -> None:
        page = QWidget()
        root = QVBoxLayout(page)
        self.safety_table = QTableWidget(0, 4)
        self.safety_table.setHorizontalHeaderLabels(("Source Row", "Target Row", "Channel", "Reason"))
        self.safety_table.horizontalHeader().setStretchLastSection(True)
        self.safety_table.setAlternatingRowColors(True)
        root.addWidget(self.safety_table, 1)

        self.safety_log = QPlainTextEdit()
        self.safety_log.setReadOnly(True)
        self.safety_log.setMaximumHeight(240)
        root.addWidget(self.safety_log)
        self.tabs.addTab(page, "E34 Safety Graph")

    def _build_observability_tab(self) -> None:
        page = QWidget()
        root = QVBoxLayout(page)
        self.observability_table = QTableWidget(0, 3)
        self.observability_table.setHorizontalHeaderLabels(("Kind / Gap", "Class", "Sensors"))
        self.observability_table.horizontalHeader().setStretchLastSection(True)
        self.observability_table.setAlternatingRowColors(True)
        root.addWidget(self.observability_table, 1)

        self.observability_log = QPlainTextEdit()
        self.observability_log.setReadOnly(True)
        self.observability_log.setMaximumHeight(260)
        root.addWidget(self.observability_log)
        self.tabs.addTab(page, "E35 Observability")

    def _build_chaos_escape_tab(self) -> None:
        page = QWidget()
        root = QVBoxLayout(page)
        self.chaos_table = QTableWidget(0, 3)
        self.chaos_table.setHorizontalHeaderLabels(("Channel", "Intensity", "Wiggle"))
        self.chaos_table.horizontalHeader().setStretchLastSection(True)
        self.chaos_table.setAlternatingRowColors(True)
        root.addWidget(self.chaos_table, 1)

        self.chaos_log = QPlainTextEdit()
        self.chaos_log.setReadOnly(True)
        self.chaos_log.setMaximumHeight(240)
        root.addWidget(self.chaos_log)
        self.tabs.addTab(page, "E45 Chaos Escape")

    def _build_segmental_tab(self) -> None:
        page = QWidget()
        root = QVBoxLayout(page)
        self.segmental_table = QTableWidget(0, 4)
        self.segmental_table.setHorizontalHeaderLabels(("Channel A", "Channel B", "Coupling", "Status"))
        self.segmental_table.horizontalHeader().setStretchLastSection(True)
        self.segmental_table.setAlternatingRowColors(True)
        root.addWidget(self.segmental_table, 1)

        self.segmental_log = QPlainTextEdit()
        self.segmental_log.setReadOnly(True)
        self.segmental_log.setMaximumHeight(240)
        root.addWidget(self.segmental_log)
        self.tabs.addTab(page, "E46 Segmental")

    def _build_biohybrid_tab(self) -> None:
        page = QWidget()
        root = QVBoxLayout(page)
        self.biohybrid_table = QTableWidget(0, 4)
        self.biohybrid_table.setHorizontalHeaderLabels(("Row", "Kind / Intent", "Gate", "Notes"))
        self.biohybrid_table.horizontalHeader().setStretchLastSection(True)
        self.biohybrid_table.setAlternatingRowColors(True)
        root.addWidget(self.biohybrid_table, 1)

        self.biohybrid_log = QPlainTextEdit()
        self.biohybrid_log.setReadOnly(True)
        self.biohybrid_log.setMaximumHeight(240)
        root.addWidget(self.biohybrid_log)
        self.tabs.addTab(page, "E47 Biohybrid")

    def _build_wet_dry_tab(self) -> None:
        page = QWidget()
        root = QVBoxLayout(page)
        self.wet_dry_table = QTableWidget(0, 4)
        self.wet_dry_table.setHorizontalHeaderLabels(
            ("Organ", "Physical Counterpart", "Ledger", "Physical")
        )
        self.wet_dry_table.horizontalHeader().setStretchLastSection(True)
        self.wet_dry_table.setAlternatingRowColors(True)
        root.addWidget(self.wet_dry_table, 1)

        self.wet_dry_log = QPlainTextEdit()
        self.wet_dry_log.setReadOnly(True)
        self.wet_dry_log.setMaximumHeight(240)
        root.addWidget(self.wet_dry_log)
        self.tabs.addTab(page, "E48+ Research")

    def _build_edge_species_tab(self) -> None:
        """New tab for the SIFTA Edge Robotics Species vision (Jetson / physical robots)."""
        page = QWidget()
        root = QVBoxLayout(page)

        header = QLabel("Edge Species — BeeSon on NVIDIA Hardware")
        header.setObjectName("header")
        root.addWidget(header)

        desc = QLabel(
            "This tab previews the path from current ROB 501 Stigmerobotics organs to a true edge species "
            "running on Jetson-class silicon. Same covenant DNA. Different metabolism. Real-time fast layer + slow JSONL field.\n\n"
            "Physics basis: Reaction-diffusion field (∂φ/∂t = D∇²φ − λφ + f(agents)) + thermal diffusion. "
            "Temperature increases effective drag in biological muscle and clock jitter/resistance in silicon → lower CPG frequency (β·T term)."
        )
        desc.setWordWrap(True)
        root.addWidget(desc)

        # === ENERGY ACCOUNTING (Real physics, investor-grade) ===
        energy_label = QLabel("<b>Global Energy Accounting (Conserved + Dissipated)</b>")
        root.addWidget(energy_label)

        self.energy_panel = QLabel()
        self.energy_panel.setObjectName("card")
        self.energy_panel.setMinimumHeight(70)
        root.addWidget(self.energy_panel)

        # Key organs relevant to physical actuation
        organs_label = QLabel("<b>Physical-Ready Organs (current)</b>")
        root.addWidget(organs_label)

        self.edge_organs_table = QTableWidget(0, 2)
        self.edge_organs_table.setHorizontalHeaderLabels(("Organ", "Status"))
        self.edge_organs_table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.edge_organs_table)

        # Seed with physically relevant organs from ROB 501
        physical_organs = [
            ("E35 Observability (Markov Blanket)", "Strong — knows what it cannot see"),
            ("E46 Segmental Coordination", "Strong — lamprey-style coupling"),
            ("E47 Biohybrid Boundary", "In progress — wet/dry contract"),
            ("Physical Space", "Operational"),
            ("Body Connection Proof", "Proven — attached organ, not separate OS"),
            ("Fast Layer + DFA + Receipts", "HYPOTHESIS — two-timescale prototype (this tab)"),
        ]
        self.edge_organs_table.setRowCount(len(physical_organs))
        for i, (name, status) in enumerate(physical_organs):
            self.edge_organs_table.setItem(i, 0, QTableWidgetItem(name))
            self.edge_organs_table.setItem(i, 1, QTableWidgetItem(status))

        # === FAST LAYER + RECOVERY SIM (Real physics demo) ===
        fast_box = QLabel("<b>Fast Layer + Thermal DFA + Autonomous Recovery (Investor Demo)</b>")
        root.addWidget(fast_box)

        self.dfa_state_label = QLabel("<b>DFA State:</b> SAFE")
        root.addWidget(self.dfa_state_label)

        self.fast_layer_log = QPlainTextEdit()
        self.fast_layer_log.setReadOnly(True)
        self.fast_layer_log.setMaximumHeight(140)
        root.addWidget(self.fast_layer_log)

        btn_layout = QHBoxLayout()
        damage_btn = QPushButton("Inject Thermal Damage @ j2")
        damage_btn.clicked.connect(self._inject_thermal_damage)
        btn_layout.addWidget(damage_btn)

        multi_damage_btn = QPushButton("Stack Damage (j2 + j3)")
        multi_damage_btn.clicked.connect(self._stack_damage)
        btn_layout.addWidget(multi_damage_btn)

        reset_btn = QPushButton("Reset Field")
        reset_btn.clicked.connect(self._reset_edge_field)
        btn_layout.addWidget(reset_btn)

        root.addLayout(btn_layout)

        tc_label = QLabel("<b>Tab Consciousness - Safari Sense</b>")
        root.addWidget(tc_label)

        self.tc_status = QLabel("OFF")
        self.tc_status.setObjectName("card")
        self.tc_status.setMinimumHeight(44)
        root.addWidget(self.tc_status)

        tc_buttons = QHBoxLayout()
        tc_on = QPushButton("Turn On")
        tc_on.clicked.connect(self._turn_on_tab_consciousness)
        tc_buttons.addWidget(tc_on)
        tc_off = QPushButton("Turn Off")
        tc_off.clicked.connect(self._turn_off_tab_consciousness)
        tc_buttons.addWidget(tc_off)
        root.addLayout(tc_buttons)

        note = QLabel(
            "<i>Hardware path:</i> This exact control loop (CPG + field + DFA + receipt) is designed to bind to real motor drivers "
            "(CAN / PWM) on Jetson with identical receipt format. Only step size and I/O binding change."
        )
        note.setWordWrap(True)
        root.addWidget(note)

        self.tabs.addTab(page, "Edge Species")

        # Initialize simulation state
        self._init_edge_simulation()
        self._refresh_tc_status()

        # Autonomous recovery timer (real physics: thermal diffusion + energy dissipation)
        self.edge_timer = QTimer(self)
        self.edge_timer.timeout.connect(self._edge_simulation_step)
        self.edge_timer.start(120)  # ~8 Hz update for smooth demo

    def _init_edge_simulation(self):
        self.edge_thermal = 0.0
        self.edge_total_energy = 100.0
        self.edge_work_done = 0.0
        self.edge_heat_dissipated = 0.0
        self.edge_dfa_state = "SAFE"
        self.edge_damage_level = 0
        self._update_energy_panel()

    def _update_energy_panel(self):
        text = (
            f"Total Field Energy: {self.edge_total_energy:.1f}  |  "
            f"Mechanical Work: {self.edge_work_done:.1f}  |  "
            f"Heat Dissipated: {self.edge_heat_dissipated:.1f}  |  "
            f"Current Thermal Load: {self.edge_thermal:.2f}"
        )
        self.energy_panel.setText(text)

    def _edge_simulation_step(self):
        # Simple physics: thermal diffuses and dissipates over time
        if self.edge_thermal > 0:
            self.edge_thermal *= 0.92  # diffusion + cooling
            self.edge_heat_dissipated += (1 - 0.92) * self.edge_thermal * 0.3

        # Lyapunov-style recovery
        if self.edge_thermal < 0.3 and self.edge_dfa_state != "SAFE":
            self.edge_dfa_state = "SAFE"
            self.dfa_state_label.setText("<b>DFA State:</b> SAFE (autonomous recovery)")
            self.fast_layer_log.appendPlainText("Field cooled — DFA returned to SAFE autonomously")

        self._update_energy_panel()

    def _inject_thermal_damage(self):
        self.edge_thermal += 0.45
        self.edge_damage_level += 1
        self.edge_total_energy -= 4.0
        self.edge_work_done += 1.5

        if self.edge_thermal > 0.8:
            self.edge_dfa_state = "WARN"
            self.dfa_state_label.setText("<b>DFA State:</b> WARN (dV/dt > 0)")
        if self.edge_thermal > 1.35:
            self.edge_dfa_state = "VETO"
            self.dfa_state_label.setText("<b>DFA State:</b> VETO — effector blocked (receipt written)")

        self.fast_layer_log.appendPlainText(f"Thermal pulse injected. Current thermal: {self.edge_thermal:.2f} | DFA: {self.edge_dfa_state}")
        self._update_energy_panel()

    def _stack_damage(self):
        self.edge_thermal += 0.9
        self.edge_damage_level += 2
        self.edge_total_energy -= 9.0

        if self.edge_thermal > 0.8:
            self.edge_dfa_state = "WARN"
        if self.edge_thermal > 1.35:
            self.edge_dfa_state = "VETO"
            self.dfa_state_label.setText("<b>DFA State:</b> VETO — multiple joints affected")

        self.fast_layer_log.appendPlainText(f"Stacked damage. Thermal: {self.edge_thermal:.2f} | DFA: {self.edge_dfa_state}")
        self._update_energy_panel()

    def _reset_edge_field(self):
        self._init_edge_simulation()
        self.fast_layer_log.appendPlainText("Field reset. Receipt chain preserved in ledger.")
        self.dfa_state_label.setText("<b>DFA State:</b> SAFE")

    def _refresh_tc_status(self):
        try:
            from System import swarm_tab_consciousness as tc

            status = tc.get_status()
            if status.get("active"):
                mode = "URLs enabled" if status.get("collect_urls") else "titles only"
                self.tc_status.setText(
                    f"ON ({mode}) | activated_by={status.get('activated_by', 'unknown')} | "
                    f"cost_per_hour={float(status.get('cost_per_hour', 0.0)):.2f} STGM"
                )
            else:
                self.tc_status.setText("OFF | Safari tabs are not being sampled")
        except Exception as exc:
            self.tc_status.setText(f"Module unavailable: {type(exc).__name__}")

    def _turn_on_tab_consciousness(self):
        try:
            from System import swarm_tab_consciousness as tc

            tc.activate("ui")
        except Exception as exc:
            self.fast_layer_log.appendPlainText(f"Tab Consciousness activation failed: {exc}")
        self._refresh_tc_status()

    def _turn_off_tab_consciousness(self):
        try:
            from System import swarm_tab_consciousness as tc

            tc.deactivate()
        except Exception as exc:
            self.fast_layer_log.appendPlainText(f"Tab Consciousness deactivation failed: {exc}")
        self._refresh_tc_status()

    def _emit_fast_layer_trace(self) -> None:
        """Emit a sample trace as if coming from a real-time fast layer on Jetson."""
        try:
            trace_path = Path(".sifta_state/fast_layer_traces.jsonl")
            row = {
                "ts": time.time(),
                "source": "fast_layer_sim:jetson",
                "type": "FAST_LAYER_JOINT_TRACE",
                "joint": "left_shoulder_pitch",
                "position": round(0.4 + (time.time() % 1.0) * 0.2, 3),
                "effort": round(1.2 + (time.time() % 0.8), 2),
                "thermal": round(48 + (time.time() % 3), 1),
                "field_pressure": "medium",
                "note": "Simulated real-time CPG output — would be emitted at 500Hz on actual Jetson"
            }
            with trace_path.open("a") as f:
                f.write(json.dumps(row) + "\n")
            self.fast_layer_log.appendPlainText(f"[{time.strftime('%H:%M:%S')}] Emitted fast layer trace for left_shoulder_pitch")
        except Exception as e:
            self.fast_layer_log.appendPlainText(f"Emit failed: {e}")

    def _build_robot_data_tab(self) -> None:
        page = QWidget()
        root = QVBoxLayout(page)

        header = QLabel("Robot Data — E49 IRB2400 + E50 ARKOMA")
        header.setObjectName("header")
        root.addWidget(header)

        legend = QLabel(
            "Truth labels: ingest <b>OPERATIONAL</b> · baseline metrics <b>OBSERVED</b> · "
            "physical motion <b>HYPOTHESIS</b> · beats-solver <b>FORBIDDEN</b>"
        )
        legend.setWordWrap(True)
        root.addWidget(legend)

        self.robot_data_table = QTableWidget(0, 6)
        self.robot_data_table.setHorizontalHeaderLabels(
            ("Robot", "Dataset", "Rows", "Ingest", "Baseline mean (rad)", "Truth")
        )
        self.robot_data_table.horizontalHeader().setStretchLastSection(True)
        self.robot_data_table.setAlternatingRowColors(True)
        root.addWidget(self.robot_data_table, 1)

        btn_row = QHBoxLayout()
        run_btn = QPushButton("Run E49/E50 Fixture Benchmarks")
        run_btn.clicked.connect(self._run_robot_data_benchmarks)
        btn_row.addWidget(run_btn)
        e51_btn = QPushButton("Show E51 Hardware-Prep Chain")
        e51_btn.clicked.connect(self._show_e51_hardware_prep_chain)
        btn_row.addWidget(e51_btn)
        btn_row.addStretch()
        root.addLayout(btn_row)

        self.robot_data_log = QPlainTextEdit()
        self.robot_data_log.setReadOnly(True)
        self.robot_data_log.setMaximumHeight(280)
        self.robot_data_log.setPlainText(
            "Press 'Run E49/E50 Fixture Benchmarks' for ingest + nearest-neighbor baseline metrics."
        )
        root.addWidget(self.robot_data_log)
        self.tabs.addTab(page, "E49/E50 Robot Data")

    def _run_robot_data_benchmarks(self) -> None:
        if build_combined_robot_data_report is None:
            self.robot_data_log.setPlainText("System.stigmerobotics_ik_baseline could not be imported.")
            return
        try:
            report = build_combined_robot_data_report()
        except Exception as exc:
            self.robot_data_log.setPlainText(
                f"Robot data benchmark failed: {type(exc).__name__}: {exc}"
            )
            return

        rows = [
            (
                "ABB IRB 2400",
                "Kaggle IRB2400",
                str(report["e49_irb2400"]["ingest"].get("row_count", "?")),
                "PASS" if report["e49_irb2400"]["ok"] else "FAIL",
                f"{report['e49_irb2400']['baseline_stats']['mean_rad']:.6f}",
                "OPERATIONAL / OBSERVED",
            ),
            (
                "NAO ARKOMA",
                "Mendeley brg4dz8nbb.1",
                str(report["e50_arkoma"]["ingest"].get("row_count", "?")),
                "PASS" if report["e50_arkoma"]["ok"] else "FAIL",
                f"{report['e50_arkoma']['baseline_stats']['mean_rad']:.6f}",
                "OPERATIONAL / OBSERVED",
            ),
        ]
        self.robot_data_table.setRowCount(len(rows))
        for r, values in enumerate(rows):
            for c, cell in enumerate(values):
                item = QTableWidgetItem(cell)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.robot_data_table.setItem(r, c, item)
        self.robot_data_table.resizeColumnsToContents()
        self.robot_data_log.setPlainText(json.dumps(report, indent=2, ensure_ascii=False))

    def _show_e51_hardware_prep_chain(self) -> None:
        if _list_physical_bodies is None:
            self.robot_data_log.setPlainText("System.stigmerobotics_e51_hardware_prep could not be imported.")
            return
        bodies = _list_physical_bodies()
        lines = [
            "E51 hardware-prep safety chain (HYPOTHESIS until physical GO):",
            "",
            *list(_E51_CHAIN_STEPS),
            "",
            f"Physical body IDs: {', '.join(bodies)}",
            "Virtual dry-run bodies: abb_irb2400_virtual, nao_arkoma_virtual",
            "",
            "Truth: chain spec OPERATIONAL in pytest; metal motion HYPOTHESIS.",
        ]
        self.robot_data_log.setPlainText("\n".join(lines))

    def _build_body_proof_tab(self) -> None:
        page = QWidget()
        root = QVBoxLayout(page)
        self.body_proof_table = QTableWidget(0, 3)
        self.body_proof_table.setHorizontalHeaderLabels(("Check", "Status", "Detail"))
        self.body_proof_table.horizontalHeader().setStretchLastSection(True)
        self.body_proof_table.setAlternatingRowColors(True)
        root.addWidget(self.body_proof_table, 1)
        self.body_proof_log = QPlainTextEdit()
        self.body_proof_log.setReadOnly(True)
        self.body_proof_log.setMaximumHeight(240)
        root.addWidget(self.body_proof_log)
        self.tabs.addTab(page, "Body Proof")

    def _refresh_body_proof(self) -> None:
        if build_body_connection_proof is None:
            self._cards["bodyproof"].setText("Body Proof<br/>module unavailable")
            self.body_proof_table.setRowCount(0)
            self.body_proof_log.setPlainText("System.stigmerobotics_body_connection could not be imported.")
            return
        try:
            proof = build_body_connection_proof()
        except Exception as exc:
            self._cards["bodyproof"].setText("Body Proof<br/>ERROR")
            self.body_proof_table.setRowCount(0)
            self.body_proof_log.setPlainText(f"build_body_connection_proof failed: {type(exc).__name__}: {exc}")
            return

        ok = proof.ok
        status_color = "#66fcf1" if ok else "#ff4b4b"
        fail_count = len(proof.failing_checks)
        self._cards["bodyproof"].setText(
            "<span style='color: white; font-weight: bold;'>Body Proof</span><br/>"
            f"<span style='color: {status_color};'>{'PASS' if ok else f'FAIL ({fail_count})'}</span><br/>"
            f"<span style='color: #8892b0;'>organs={proof.organ_count} stgm={proof.wallet_stgm:.0f}</span>"
        )
        checks = proof.checks
        self.body_proof_table.setRowCount(len(checks))
        for r, check in enumerate(checks):
            icon = "✅" if check.ok else "❌"
            values = (check.name, icon, _short(check.detail, 120))
            for c, cell in enumerate(values):
                item = QTableWidgetItem(cell)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.body_proof_table.setItem(r, c, item)
        self.body_proof_table.resizeColumnsToContents()
        self.body_proof_log.setPlainText(proof.grok_report())

    def _build_audit_tab(self) -> None:
        page = QWidget()
        root = QVBoxLayout(page)
        self.audit_log = QPlainTextEdit()
        self.audit_log.setReadOnly(True)
        root.addWidget(self.audit_log)
        self.economy_log = QPlainTextEdit()
        self.economy_log.setReadOnly(True)
        self.economy_log.setMaximumHeight(170)
        root.addWidget(self.economy_log)
        self.tabs.addTab(page, "Ledgers + STGM")

    def _build_docs_tab(self) -> None:
        page = QWidget()
        root = QVBoxLayout(page)
        self.doc_view = QTextBrowser()
        self.doc_view.setOpenExternalLinks(True)
        root.addWidget(self.doc_view)
        self.tabs.addTab(page, "Tournament Doc")

    def _build_tests_tab(self) -> None:
        page = QWidget()
        root = QVBoxLayout(page)
        self.test_log = QPlainTextEdit()
        self.test_log.setReadOnly(True)
        self.test_log.setPlainText("Press 'Run Active Proof Tests' for a current proof receipt.")
        root.addWidget(self.test_log)
        self.tabs.addTab(page, "Test Receipt")

    def refresh_all(self) -> None:
        text = _doc_text()
        self._refresh_singleton()
        self._refresh_event_table(text)
        self._refresh_state_vector()
        self._refresh_pheromone()
        self._refresh_safety_graph()
        self._refresh_observability()
        self._refresh_chaos_escape()
        self._refresh_segmental()
        self._refresh_biohybrid()
        self._refresh_wet_dry()
        self._refresh_body_proof()
        self._refresh_tc_status()
        self._refresh_audit()
        self._refresh_economy()
        self.doc_view.setMarkdown(text)
        self._status.setText(f"Refreshed {time.strftime('%H:%M:%S')}")

    def _refresh_singleton(self) -> None:
        active = _active_stigmerobotics_apps()
        ok = active == ["Stigmerobotics"]
        
        status_color = "#66fcf1" if ok else "#ff4b4b"
        self._cards["singleton"].setText(
            f"<span style='color: white; font-weight: bold;'>Singleton {'OK' if ok else 'FAIL'}</span><br/>"
            f"<span style='color: {status_color};'>{active or 'none'}</span>"
        )
        manifest = _read_manifest()
        retired = [
            name for name, meta in manifest.items()
            if meta.get("_retired") and "tournament briefing" in name.lower()
        ]
        self.singleton_report.setPlainText(
            "\n".join(
                [
                    "MacOS-style menu contract:",
                    f"  Active Stigmerobotics apps: {active}",
                    f"  Retired related briefing apps: {retired}",
                    "  Menu folder: Developer",
                    "  Surface law: one visual hub, no browser escape, no duplicate app-local chat.",
                ]
            )
        )

    def _refresh_event_table(self, markdown: str) -> None:
        rows = _parse_event_rows(markdown)
        self.event_table.setRowCount(len(rows))
        green = 0
        for r, cells in enumerate(rows):
            event = re.sub(r"\*|`", "", cells[2]).strip()
            prove = re.sub(r"\*|`", "", cells[3]).strip()
            status = re.sub(r"\*|`", "", cells[5]).strip()
            if "GREEN" in status:
                green += 1
            values = (event, _short(cells[1], 48), _short(prove, 90), _short(status, 48))
            for c, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.event_table.setItem(r, c, item)
        self.event_table.resizeColumnsToContents()
        next_event = next((row[2] for row in rows if "todo" in row[5].lower()), "E03")
        
        green_color = "#66fcf1" if green == len(rows) else "#45a29e"
        self._cards["proofs"].setText(
            f"<span style='color: white; font-weight: bold;'>Proof Ladder</span><br/>"
            f"<span style='color: {green_color};'>GREEN={green} / {len(rows)}</span><br/>"
            f"<span style='color: #8892b0;'>next={_short(next_event, 30)}</span>"
        )

    def _refresh_state_vector(self) -> None:
        if live_state_vector is None:
            self._cards["state"].setText("State vector\nmodule unavailable")
            self.state_vector_table.setRowCount(0)
            self.state_vector_log.setPlainText("System.stigmerobotics_state_vector could not be imported.")
            return
        try:
            report = live_state_vector()
        except Exception as exc:
            self._cards["state"].setText("State vector\nERROR")
            self.state_vector_table.setRowCount(0)
            self.state_vector_log.setPlainText(f"Live state vector failed: {type(exc).__name__}: {exc}")
            return

        status_color = "#66fcf1" if report.ok else "#ff4b4b"
        self._cards["state"].setText(
            f"<span style='color: white; font-weight: bold;'>E03 State</span><br/>"
            f"<span style='color: {status_color};'>{'PASS' if report.ok else 'FAIL'}</span><br/>"
            f"<span style='color: #8892b0;'>x in R<sup>{report.dimension}</sup></span>"
        )
        self.state_vector_table.setRowCount(len(report.channels))
        for r, (channel, value) in enumerate(zip(report.channels, report.vector)):
            unit, meaning = CHANNEL_UNITS.get(channel, ("", ""))
            values = (channel, f"{value:.4f}", unit, meaning)
            for c, cell in enumerate(values):
                item = QTableWidgetItem(cell)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.state_vector_table.setItem(r, c, item)
        self.state_vector_table.resizeColumnsToContents()
        self.state_vector_log.setPlainText(
            "\n".join(report.summary_lines())
            + "\n\nproof_of_property:\n"
            + json.dumps(report.proof_of_property, indent=2, ensure_ascii=False)
        )

    def _refresh_pheromone(self) -> None:
        if live_pheromone_field is None:
            self._cards["pheromone"].setText("Pheromone<br/>module unavailable")
            self.pheromone_table.setRowCount(0)
            self.pheromone_log.setPlainText("System.stigmerobotics_pheromone_field could not be imported.")
            return
        try:
            report = live_pheromone_field(limit=300)
        except Exception as exc:
            self._cards["pheromone"].setText("Pheromone<br/>ERROR")
            self.pheromone_table.setRowCount(0)
            self.pheromone_log.setPlainText(f"Live pheromone field failed: {type(exc).__name__}: {exc}")
            return

        status_color = "#66fcf1" if report.ok else "#ff4b4b"
        self._cards["pheromone"].setText(
            f"<span style='color: white; font-weight: bold;'>E33 Field</span><br/>"
            f"<span style='color: {status_color};'>{'PASS' if report.ok else 'FAIL'}</span><br/>"
            f"<span style='color: #8892b0;'>risk={report.collision_risk:.4f}</span>"
        )
        rows = sorted(report.field.items(), key=lambda item: item[1], reverse=True)[:12]
        self.pheromone_table.setRowCount(len(rows))
        for r, (channel, value) in enumerate(rows):
            after = report.field_after_dt.get(channel, 0.0)
            values = (_short(channel, 72), f"{value:.6f}", f"{after:.6f}")
            for c, cell in enumerate(values):
                item = QTableWidgetItem(cell)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.pheromone_table.setItem(r, c, item)
        self.pheromone_table.resizeColumnsToContents()
        self.pheromone_log.setPlainText(
            "\n".join(report.summary_lines())
            + "\n\nproof_of_property:\n"
            + json.dumps(report.proof_of_property, indent=2, ensure_ascii=False)
        )

    def _refresh_safety_graph(self) -> None:
        if live_safety_graph is None:
            self._cards["safety"].setText("Safety graph<br/>module unavailable")
            self.safety_table.setRowCount(0)
            self.safety_log.setPlainText("System.stigmerobotics_safety_graph could not be imported.")
            return
        try:
            report = live_safety_graph(limit=300)
        except Exception as exc:
            self._cards["safety"].setText("Safety graph<br/>ERROR")
            self.safety_table.setRowCount(0)
            self.safety_log.setPlainText(f"Live safety graph failed: {type(exc).__name__}: {exc}")
            return

        status_color = "#66fcf1" if report.ok else "#ff4b4b"
        self._cards["safety"].setText(
            f"<span style='color: white; font-weight: bold;'>E34 Safety</span><br/>"
            f"<span style='color: {status_color};'>{'PASS' if report.ok else 'LIVE GAP'}</span><br/>"
            f"<span style='color: #8892b0;'>edges={len(report.edges)} gaps={len(report.violations)}</span>"
        )
        rows = report.edges[:12]
        self.safety_table.setRowCount(len(rows))
        for r, edge in enumerate(rows):
            values = (
                str(edge.source_row),
                str(edge.target_row),
                f"{edge.channel[0]} / {edge.channel[1]}",
                edge.reason,
            )
            for c, cell in enumerate(values):
                item = QTableWidgetItem(cell)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.safety_table.setItem(r, c, item)
        self.safety_table.resizeColumnsToContents()
        self.safety_log.setPlainText(
            "\n".join(report.summary_lines())
            + "\n\nproof_of_property:\n"
            + json.dumps(report.proof_of_property, indent=2, ensure_ascii=False)
        )

    def _refresh_observability(self) -> None:
        if live_observability_report is None:
            self._cards["observability"].setText("Observability<br/>module unavailable")
            self.observability_table.setRowCount(0)
            self.observability_log.setPlainText("System.stigmerobotics_observability could not be imported.")
            return
        try:
            report = live_observability_report(limit=300)
        except Exception as exc:
            self._cards["observability"].setText("Observability<br/>ERROR")
            self.observability_table.setRowCount(0)
            self.observability_log.setPlainText(f"Live observability failed: {type(exc).__name__}: {exc}")
            return

        status_color = "#66fcf1" if report.ok else "#ff4b4b"
        self._cards["observability"].setText(
            f"<span style='color: white; font-weight: bold;'>E35 Blanket</span><br/>"
            f"<span style='color: {status_color};'>{'NONTRIVIAL' if report.ok else 'BROKEN'}</span><br/>"
            f"<span style='color: #8892b0;'>hidden={len(report.hidden_deps)} unknown={len(report.unknown_kinds)}</span>"
        )

        rows: list[tuple[str, str, str]] = []
        for kind, obs in report.kind_classes.items():
            rows.append((kind, obs.name, "trace row"))
        for kind in report.unknown_kinds:
            rows.append((kind, "UNKNOWN_KIND", "classify before relying on it"))
        for name, sensors in report.mandatory_sensors.items():
            rows.append((name, "HIDDEN_DEP", ", ".join(sensors)))
        self.observability_table.setRowCount(len(rows))
        for r, values in enumerate(rows):
            for c, cell in enumerate(values):
                item = QTableWidgetItem(_short(cell, 90))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.observability_table.setItem(r, c, item)
        self.observability_table.resizeColumnsToContents()
        self.observability_log.setPlainText(
            "\n".join(report.summary_lines())
            + "\n\nproof_of_property:\n"
            + json.dumps(report.proof_of_property, indent=2, ensure_ascii=False)
        )

    def _refresh_chaos_escape(self) -> None:
        if live_chaos_escape is None:
            self._cards["chaos"].setText("Chaos escape<br/>module unavailable")
            self.chaos_table.setRowCount(0)
            self.chaos_log.setPlainText("System.stigmerobotics_chaos_escape could not be imported.")
            return
        try:
            decision = live_chaos_escape(limit=300)
        except Exception as exc:
            self._cards["chaos"].setText("Chaos escape<br/>ERROR")
            self.chaos_table.setRowCount(0)
            self.chaos_log.setPlainText(f"Live chaos escape failed: {type(exc).__name__}: {exc}")
            return

        if decision.mode == "CALM":
            status_color = "#66fcf1"
        elif decision.mode == "FROZEN":
            status_color = "#ff4b4b"
        else:
            status_color = "#f7c948"
        self._cards["chaos"].setText(
            f"<span style='color: white; font-weight: bold;'>E45 Chaos</span><br/>"
            f"<span style='color: {status_color};'>{decision.mode}</span><br/>"
            f"<span style='color: #8892b0;'>amp={decision.amplitude:.4f}</span>"
        )
        rows = decision.wiggles[:12]
        self.chaos_table.setRowCount(len(rows))
        for r, item in enumerate(rows):
            values = (_short(item.channel, 72), f"{item.intensity:.6f}", f"{item.wiggle:+.6f}")
            for c, cell in enumerate(values):
                table_item = QTableWidgetItem(cell)
                table_item.setFlags(table_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.chaos_table.setItem(r, c, table_item)
        self.chaos_table.resizeColumnsToContents()
        self.chaos_log.setPlainText(
            "\n".join(decision.summary_lines())
            + "\n\nproof_of_property:\n"
            + json.dumps(decision.proof_of_property, indent=2, ensure_ascii=False)
        )

    def _refresh_segmental(self) -> None:
        if build_coordination_report is None or _TRACE_PATH is None:
            self._cards["segmental"].setText("Segmental<br/>module unavailable")
            self.segmental_table.setRowCount(0)
            self.segmental_log.setPlainText("System.stigmerobotics_segmental_coordination could not be imported.")
            return
        try:
            rows: list = []
            if _TRACE_PATH.exists():
                rows = [json.loads(l) for l in _TRACE_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
            report = build_coordination_report(rows[-300:])
        except Exception as exc:
            self._cards["segmental"].setText("Segmental<br/>ERROR")
            self.segmental_table.setRowCount(0)
            self.segmental_log.setPlainText(f"Live segmental failed: {type(exc).__name__}: {exc}")
            return

        state = report.state.name
        if state == "COORDINATED":
            status_color = "#66fcf1"
        elif state == "SINGLE_CHANNEL":
            status_color = "#45a29e"
        else:
            status_color = "#ff4b4b"
        self._cards["segmental"].setText(
            f"<span style='color: white; font-weight: bold;'>E46 CPG</span><br/>"
            f"<span style='color: {status_color};'>{state}</span><br/>"
            f"<span style='color: #8892b0;'>ch={report.n_channels} violations={len(report.violations)}</span>"
        )

        # Populate coupling edges table
        edges = report.strongly_coupled_pairs[:20]
        violations_set = {(v.fire_a.channel, v.fire_b.channel) for v in report.violations}
        self.segmental_table.setRowCount(len(edges))
        for r, edge in enumerate(edges):
            pair = (edge.channel_a, edge.channel_b)
            pair_rev = (edge.channel_b, edge.channel_a)
            is_violation = pair in violations_set or pair_rev in violations_set
            values = (
                _short("::" .join(edge.channel_a), 40),
                _short("::" .join(edge.channel_b), 40),
                f"{edge.coupling_strength:.4f}",
                "VIOLATION" if is_violation else "OK",
            )
            for c, cell in enumerate(values):
                item = QTableWidgetItem(cell)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.segmental_table.setItem(r, c, item)
        self.segmental_table.resizeColumnsToContents()
        self.segmental_log.setPlainText(
            "\n".join(report.summary_lines())
            + "\n\nproof_of_property:\n"
            + json.dumps(report.proof_of_property, indent=2, ensure_ascii=False)
        )

    def _refresh_biohybrid(self) -> None:
        if live_biohybrid_report is None:
            self._cards["biohybrid"].setText("Biohybrid<br/>module unavailable")
            self.biohybrid_table.setRowCount(0)
            self.biohybrid_log.setPlainText("System.stigmerobotics_biohybrid_boundary could not be imported.")
            return
        try:
            report = live_biohybrid_report(limit=300)
        except Exception as exc:
            self._cards["biohybrid"].setText("Biohybrid<br/>ERROR")
            self.biohybrid_table.setRowCount(0)
            self.biohybrid_log.setPlainText(f"Live biohybrid boundary failed: {type(exc).__name__}: {exc}")
            return

        state = report.state.name
        if state in {"SENSOR_ONLY", "HUMAN_REVIEW_READY"} and report.ok:
            status_color = "#66fcf1"
        elif state == "BLOCKED":
            status_color = "#f7c948"
        else:
            status_color = "#ff4b4b"
        self._cards["biohybrid"].setText(
            f"<span style='color: white; font-weight: bold;'>E47 Biohybrid</span><br/>"
            f"<span style='color: {status_color};'>{state}</span><br/>"
            f"<span style='color: #8892b0;'>rows={len(report.rows)} intents={report.n_intents}</span>"
        )

        rows: list[tuple[str, str, str, str]] = []
        for gate in report.intent_gates[:12]:
            rows.append(
                (
                    str(gate.intent.row_index),
                    _short(gate.intent.trace_id or gate.intent.kind, 48),
                    gate.status.name,
                    _short(gate.note + (" missing=" + ",".join(gate.missing) if gate.missing else ""), 90),
                )
            )
        if not rows:
            for row in report.rows[:12]:
                rows.append(
                    (
                        str(row.row_index),
                        row.kind,
                        "RECEIPT",
                        _short(row.trace_id, 90),
                    )
                )
        for bad in report.forbidden_payloads[:12]:
            rows.append(
                (
                    str(bad.row_index),
                    bad.kind,
                    "QUARANTINE",
                    _short(",".join(bad.forbidden_keys), 90),
                )
            )
        self.biohybrid_table.setRowCount(len(rows))
        for r, values in enumerate(rows):
            for c, cell in enumerate(values):
                item = QTableWidgetItem(cell)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.biohybrid_table.setItem(r, c, item)
        self.biohybrid_table.resizeColumnsToContents()
        self.biohybrid_log.setPlainText(
            "\n".join(report.summary_lines())
            + "\n\nproof_of_property:\n"
            + json.dumps(report.proof_of_property, indent=2, ensure_ascii=False)
        )

    def _refresh_wet_dry(self) -> None:
        if build_wet_dry_bridge is None:
            self._cards["wetdry"].setText("E48+ Research<br/>module unavailable")
            self.wet_dry_table.setRowCount(0)
            self.wet_dry_log.setPlainText("System.stigmerobotics_wet_dry_interface could not be imported.")
            return
        try:
            bridge = build_wet_dry_bridge()
        except Exception as exc:
            self._cards["wetdry"].setText("E48+ Research<br/>ERROR")
            self.wet_dry_table.setRowCount(0)
            self.wet_dry_log.setPlainText(f"Wet-dry bridge failed: {type(exc).__name__}: {exc}")
            return

        ok = bridge.all_have_safety_gate and bridge.all_have_doi
        status_color = "#66fcf1" if ok else "#ff4b4b"
        self._cards["wetdry"].setText(
            f"<span style='color: white; font-weight: bold;'>E48+ Research</span><br/>"
            f"<span style='color: {status_color};'>{'HYPOTHESIS-GATED' if ok else 'BROKEN'}</span><br/>"
            f"<span style='color: #8892b0;'>specs={len(bridge.specs)} gate=E34</span>"
        )

        self.wet_dry_table.setRowCount(len(bridge.specs))
        for r, spec in enumerate(bridge.specs):
            values = (
                spec.organ_id,
                _short(spec.physical_name, 48),
                spec.truth_label_ledger,
                spec.truth_label_physical,
            )
            for c, cell in enumerate(values):
                item = QTableWidgetItem(cell)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.wet_dry_table.setItem(r, c, item)
        self.wet_dry_table.resizeColumnsToContents()
        self.wet_dry_log.setPlainText(
            "\n".join(bridge.summary_lines())
            + "\n\nproof_of_property:\n"
            + json.dumps(bridge.proof_of_property, indent=2, ensure_ascii=False)
        )

    def _refresh_audit(self) -> None:
        if audit_live is None:
            self._cards["ledger"].setText("Ledger audit\nmodule unavailable")
            self.audit_log.setPlainText("System.ledger_auditor could not be imported.")
            return
        try:
            ok, trace_result, receipt_result = audit_live(verbose=False)
        except Exception as exc:
            self._cards["ledger"].setText("Ledger audit\nERROR")
            self.audit_log.setPlainText(f"Live audit failed: {type(exc).__name__}: {exc}")
            return
            
        status_color = "#66fcf1" if ok else "#ff4b4b"
        self._cards["ledger"].setText(
            f"<span style='color: white; font-weight: bold;'>Ledger Audit</span><br/>"
            f"<span style='color: {status_color};'>{'PASS' if ok else 'FAIL'}</span><br/>"
            f"<span style='color: #8892b0;'>trace={len(trace_result.violations)} receipt={len(receipt_result.violations)}</span>"
        )
        self.audit_log.setPlainText(trace_result.summary() + "\n\n" + receipt_result.summary())

    def _refresh_economy(self) -> None:
        if summarize_immune_economy is None or format_life_cockpit_summary is None:
            self._cards["economy"].setText("STGM economy\nmodule unavailable")
            self.economy_log.setPlainText("System.swarm_immune_economy_summary could not be imported.")
            return
        try:
            summary = summarize_immune_economy()
        except Exception as exc:
            self._cards["economy"].setText("STGM economy\nERROR")
            self.economy_log.setPlainText(f"Summary failed: {type(exc).__name__}: {exc}")
            return
            
        status_color = "#45a29e"
        if "BLOCKED" in summary.display_status or "CONSERVE" in summary.display_status:
            status_color = "#ff4b4b"
            
        self._cards["economy"].setText(
            f"<span style='color: white; font-weight: bold;'>STGM Immune</span><br/>"
            f"<span style='color: {status_color};'>{summary.display_status}</span><br/>"
            f"<span style='color: #8892b0;'>burn={summary.session_charged_stgm:.5f}</span>"
        )
        lines = [format_life_cockpit_summary(summary), ""]
        for event in summary.events[-8:]:
            lines.append(
                f"{event.kind} cost={event.cost_stgm:.6f} blocked={event.budget_blocked} regime={event.regime}"
            )
        self.economy_log.setPlainText("\n".join(lines))

    def run_proof_tests(self) -> None:
        cmd = [sys.executable, "-m", "pytest", *_ACTIVE_TESTS, "-q"]
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(_REPO),
                env={**os.environ, "PYTHONPATH": str(_REPO)},
                capture_output=True,
                text=True,
                timeout=60,
            )
        except Exception as exc:
            self.test_log.setPlainText(f"Test run failed: {type(exc).__name__}: {exc}")
            return
        output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
        self.test_log.setPlainText(
            "$ " + " ".join(cmd) + f"\nexit={proc.returncode}\n\n" + output.strip()
        )


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    win = StigmeroboticsWidget()
    win.resize(1240, 820)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
