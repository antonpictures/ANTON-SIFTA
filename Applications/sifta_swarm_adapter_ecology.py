#!/usr/bin/env python3
"""SIFTA OS app: Swarm Adapter Ecology dashboard.

Read-only visibility into Alice's Stigmergic Epigenetic LoRA lane.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from System.sifta_base_widget import SiftaBaseWidget

STATE = _REPO / ".sifta_state"
ADAPTERS_DIR = STATE / "stigmergic_adapters"
REGISTRY = STATE / "stigmergic_adapter_registry.jsonl"
REPLAY_EVALS = STATE / "stigmergic_replay_evals.jsonl"
MERGE_RECIPE = STATE / "stigmergic_adapter_merge_recipe.json"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _tail_jsonl(path: Path, limit: int = 12) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
    except Exception:
        return []
    return rows[-limit:]


def _short(value: Any, width: int = 72) -> str:
    text = "" if value is None else str(value)
    return text if len(text) <= width else text[: width - 1] + "..."


class MetricCard(QFrame):
    def __init__(self, title: str) -> None:
        super().__init__()
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            "QFrame { background: rgb(12,10,20); border: 1px solid rgb(45,42,65); "
            "border-radius: 8px; padding: 8px; }"
        )
        box = QVBoxLayout(self)
        title_label = QLabel(title.upper())
        title_label.setStyleSheet("color: rgb(100,108,140); font-size: 10px; border: none;")
        self.value = QLabel("--")
        self.value.setFont(QFont("Menlo", 16, QFont.Weight.Bold))
        self.value.setStyleSheet("color: rgb(0,255,200); border: none;")
        self.detail = QLabel("")
        self.detail.setStyleSheet("color: rgb(170,176,210); font-size: 10px; border: none;")
        box.addWidget(title_label)
        box.addWidget(self.value)
        box.addWidget(self.detail)

    def set_metric(self, value: str, detail: str = "") -> None:
        self.value.setText(value)
        self.detail.setText(detail)


class SwarmAdapterEcologyWidget(SiftaBaseWidget):
    APP_NAME = "Swarm Adapter Ecology"

    def build_ui(self, layout: QVBoxLayout) -> None:
        intro = QLabel(
            "Gemma 4 Stigmergic Epigenetic LoRA: OS use -> adapter -> pheromone -> replay gate -> merge recipe"
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: rgb(200,210,240); font-size: 11px;")
        layout.addWidget(intro)

        row = QHBoxLayout()
        self.card_base = MetricCard("Base")
        self.card_status = MetricCard("Merge Status")
        self.card_pheromone = MetricCard("Pheromone")
        self.card_adapters = MetricCard("Adapters")
        for card in (self.card_base, self.card_status, self.card_pheromone, self.card_adapters):
            row.addWidget(card)
        layout.addLayout(row)

        buttons = QHBoxLayout()
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        buttons.addWidget(refresh)
        buttons.addStretch()
        layout.addLayout(buttons)

        self.registry_table = QTableWidget(0, 6)
        self.registry_table.setHorizontalHeaderLabels(
            ["Adapter", "Base", "Eval", "Risk", "Pheromone", "Task"]
        )
        self.registry_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.registry_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(QLabel("Adapter Registry"))
        layout.addWidget(self.registry_table, 2)

        self.replay_table = QTableWidget(0, 5)
        self.replay_table.setHorizontalHeaderLabels(["Adapter", "Verdict", "Replay", "Counter", "Base"])
        self.replay_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.replay_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(QLabel("Hippocampal Replay Gate"))
        layout.addWidget(self.replay_table, 1)

        self.recipe = QPlainTextEdit()
        self.recipe.setReadOnly(True)
        layout.addWidget(QLabel("Current Merge Recipe / How To Run"))
        layout.addWidget(self.recipe, 2)

        self.make_timer(5000, self.refresh)
        self.refresh()

    def refresh(self) -> None:
        recipe = _read_json(MERGE_RECIPE)
        registry = _tail_jsonl(REGISTRY, 20)
        replay = _tail_jsonl(REPLAY_EVALS, 20)

        try:
            from System.swarm_adapter_pheromone_scorer import calculate_swarm_pheromone_strength

            pheromone = calculate_swarm_pheromone_strength()
        except Exception:
            pheromone = 0.0

        base = str(recipe.get("base_model") or "google/gemma-4")
        adapters = recipe.get("adapters") if isinstance(recipe.get("adapters"), list) else []
        status = str(recipe.get("status") or ("READY" if adapters else "WAITING_FOR_GEMMA4_ADAPTER"))

        self.card_base.set_metric(base, "Gemma 4 only")
        self.card_status.set_metric(status, f"{len(adapters)} selected for merge")
        self.card_pheromone.set_metric(f"{float(pheromone):.4f}", "from work, IDE, and repair ledgers")
        self.card_adapters.set_metric(str(len(registry)), f"{ADAPTERS_DIR}")

        self._fill_registry(registry)
        self._fill_replay(replay)
        self._fill_recipe(recipe, pheromone)
        self.set_status(f"Updated {time.strftime('%H:%M:%S')}")

    def _fill_registry(self, rows: list[dict[str, Any]]) -> None:
        self.registry_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            values = [
                row.get("adapter_id"),
                row.get("base_model"),
                row.get("eval_score"),
                row.get("risk_score"),
                row.get("pheromone_strength"),
                row.get("task"),
            ]
            for c, value in enumerate(values):
                item = QTableWidgetItem(_short(value, 44))
                if c in (2, 3, 4):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.registry_table.setItem(r, c, item)
        self.registry_table.resizeColumnsToContents()

    def _fill_replay(self, rows: list[dict[str, Any]]) -> None:
        self.replay_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            values = [
                row.get("adapter_id"),
                row.get("verdict"),
                row.get("replay_score", row.get("invariant_score")),
                row.get("counter_score"),
                row.get("base_model"),
            ]
            for c, value in enumerate(values):
                item = QTableWidgetItem(_short(value, 44))
                if str(value).upper() == "QUARANTINE":
                    item.setForeground(Qt.GlobalColor.red)
                elif str(value).upper() == "PROMOTE":
                    item.setForeground(Qt.GlobalColor.green)
                self.replay_table.setItem(r, c, item)
        self.replay_table.resizeColumnsToContents()

    def _fill_recipe(self, recipe: dict[str, Any], pheromone: float) -> None:
        command = (
            "Run a real Gemma 4 cycle:\n"
            "  SIFTA_GEMMA4_BASE=<exact-gemma4-hf-repo-or-local-safetensors> "
            "python3 scripts/execute_epigenetic_cycle.py\n\n"
            "Safety gate:\n"
            "  - non-Gemma4 bases are refused\n"
            "  - GGUF is refused for training\n"
            "  - old non-Gemma adapters are not selected\n\n"
        )
        payload = {
            "pheromone_strength": round(float(pheromone), 4),
            "merge_recipe": recipe or {"status": "WAITING_FOR_GEMMA4_ADAPTER"},
        }
        self.recipe.setPlainText(command + json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = SwarmAdapterEcologyWidget()
    w.resize(1180, 760)
    w.show()
    sys.exit(app.exec())
