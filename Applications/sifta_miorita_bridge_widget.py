#!/usr/bin/env python3
"""Miorița Bridge — Alice's project surface for life progress and Season 1.

The app reads the single Miorița project folder. It intentionally has no private
chat: Alice's global conversation remains the canonical conversation surface.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from System.sifta_base_widget import SiftaBaseWidget
from System.swarm_app_hardening import record_app_hardening_event


MIORITA_ROOT = Path("/Users/ioanganton/Documents/Miorita")
ACTION_BOARD = Path("Realitate/01_TABLOU_ACTIUNI_URMATOARE.json")
REGISTRY = Path("Organizare/30_REGISTRU_FISIERE_LA_SCENE.json")
ROUTING = Path("Episoade/scene_source_routing.json")
APP_HARDENING_ID = "miorita-bridge:v1"


def _read_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def load_miorita_snapshot(root: Path = MIORITA_ROOT) -> dict[str, Any]:
    """Read the two Miorița lanes without inferring missing evidence."""
    if not root.is_dir():
        return {
            "available": False,
            "root": str(root),
            "error": "Folderul Miorița nu este disponibil.",
            "tasks": [],
            "episodes": [],
            "registry": {},
        }

    board = _read_json(root / ACTION_BOARD, {"tasks": []})
    registry = _read_json(root / REGISTRY, {"summary": {}})
    routing = _read_json(root / ROUTING, {"items": []})
    episode_counts = Counter(int(row.get("episode") or 0) for row in routing.get("items", []))
    episode_titles: dict[int, str] = {}
    for row in routing.get("items", []):
        episode = int(row.get("episode") or 0)
        if episode:
            episode_titles[episode] = str(row.get("episode_title") or f"EP{episode:02d}")

    episodes = [
        {
            "number": episode,
            "title": episode_titles.get(episode, f"EP{episode:02d}"),
            "source_count": episode_counts.get(episode, 0),
        }
        for episode in range(1, 11)
    ]
    return {
        "available": True,
        "root": str(root),
        "tasks": list(board.get("tasks") or []),
        "episodes": episodes,
        "registry": dict(registry.get("summary") or {}),
        "registry_present": (root / REGISTRY).is_file(),
        "routing_present": (root / ROUTING).is_file(),
    }


def update_miorita_task_status(root: Path, task_id: str, status: str) -> bool:
    """Persist one visible action-board status; originals are never touched."""
    path = root / ACTION_BOARD
    board = _read_json(path, None)
    if not isinstance(board, dict):
        return False
    for task in board.get("tasks") or []:
        if task.get("id") == task_id:
            task["status"] = status
            path.write_text(json.dumps(board, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return True
    return False


class MioritaBridgeWidget(SiftaBaseWidget):
    APP_NAME = "Miorița Bridge"
    APP_LOCAL_CHAT_DISABLED = True
    STICKY_GLOBAL_CHAT_DISABLED = True

    def build_ui(self, layout: QVBoxLayout) -> None:
        intro = QLabel(
            "Un singur proiect, două suprafețe: pașii de viață reală și puntea lor către sezonul de ficțiune. "
            "Etichetele de adevăr rămân active."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: rgb(175, 190, 220); font-size: 11px; padding: 4px;")
        layout.addWidget(intro)

        bar = QHBoxLayout()
        self._summary = QLabel("Se citește proiectul Miorița...")
        self._summary.setStyleSheet("color: rgb(0,255,200); font-weight: bold;")
        bar.addWidget(self._summary)
        bar.addStretch()
        refresh = QPushButton("⟳ Reîmprospătează")
        refresh.clicked.connect(self._reload)
        bar.addWidget(refresh)
        layout.addLayout(bar)

        tabs = QTabWidget()
        tabs.addTab(self._build_life_tab(), "Viață reală")
        tabs.addTab(self._build_fiction_tab(), "Punte spre ficțiune")
        layout.addWidget(tabs, 1)

        self._reload()
        self.make_timer(30000, self._reload)

    def _build_life_tab(self) -> QFrame:
        frame = QFrame()
        body = QVBoxLayout(frame)
        label = QLabel(
            "Bifează numai pașii pe care i-ai făcut. Acțiunile scriu doar în tabloul Miorița, "
            "nu modifică documentele originale."
        )
        label.setWordWrap(True)
        label.setStyleSheet("color: rgb(255, 195, 115); padding: 4px;")
        body.addWidget(label)

        self._life_table = QTableWidget(0, 5)
        self._life_table.setHorizontalHeaderLabels(("Gata", "Prioritate", "Pasul următor", "Condiție / dovadă", "Punte în serial"))
        self._life_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._life_table.verticalHeader().setVisible(False)
        header = self._life_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        body.addWidget(self._life_table, 1)
        return frame

    def _build_fiction_tab(self) -> QFrame:
        frame = QFrame()
        body = QVBoxLayout(frame)
        self._fiction_boundary = QLabel()
        self._fiction_boundary.setWordWrap(True)
        self._fiction_boundary.setStyleSheet("color: rgb(165, 205, 255); padding: 4px;")
        body.addWidget(self._fiction_boundary)

        self._fiction_table = QTableWidget(0, 4)
        self._fiction_table.setHorizontalHeaderLabels(("Episod", "Titlu", "Surse media", "Funcție în sezon"))
        self._fiction_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._fiction_table.verticalHeader().setVisible(False)
        header = self._fiction_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        body.addWidget(self._fiction_table, 1)
        return frame

    def _reload(self) -> None:
        snapshot = load_miorita_snapshot()
        if not snapshot["available"]:
            self._summary.setText(snapshot["error"])
            self.set_status("Miorița indisponibilă")
            record_app_hardening_event(
                APP_HARDENING_ID,
                "miorita_root_missing",
                truth_label="OBSERVED",
                details={"root": snapshot["root"]},
            )
            return

        registry = snapshot["registry"]
        active = registry.get("active_files", "?")
        unlinked = registry.get("unlinked_active_files", "?")
        sources = sum(episode["source_count"] for episode in snapshot["episodes"])
        self._summary.setText(f"MIORIȚA: {active} fișiere legate · {sources} surse media · {unlinked} nelegate")
        self.set_status("Pod actualizat")
        self._populate_life(snapshot["tasks"])
        self._populate_fiction(snapshot["episodes"], registry)

    def _populate_life(self, tasks: list[dict[str, Any]]) -> None:
        self._life_table.setRowCount(len(tasks))
        for row, task in enumerate(tasks):
            check = QCheckBox()
            check.setChecked(task.get("status") == "done")
            check.stateChanged.connect(
                lambda state, task_id=str(task.get("id") or ""): self._set_task(task_id, state)
            )
            self._life_table.setCellWidget(row, 0, check)
            self._life_table.setItem(row, 1, QTableWidgetItem(str(task.get("priority") or "—")))
            title = str(task.get("title") or "—")
            title_item = QTableWidgetItem(title)
            title_item.setToolTip(str(task.get("next_step") or ""))
            self._life_table.setItem(row, 2, title_item)
            evidence = QTableWidgetItem(str(task.get("evidence") or "—"))
            evidence.setToolTip(str(task.get("next_step") or ""))
            self._life_table.setItem(row, 3, evidence)
            self._life_table.setItem(row, 4, QTableWidgetItem(str(task.get("fiction_bridge") or "—")))
            self._life_table.setRowHeight(row, 46)

    def _populate_fiction(self, episodes: list[dict[str, Any]], registry: dict[str, Any]) -> None:
        active = registry.get("active_files", "?")
        self._fiction_boundary.setText(
            f"Registrul leagă {active} fișiere active de cel puțin un episod. "
            "O legătură editorială nu face automat un transcript RAW, o afirmație sau o acuzație verificată."
        )
        self._fiction_table.setRowCount(len(episodes))
        for row, episode in enumerate(episodes):
            number = int(episode["number"])
            self._fiction_table.setItem(row, 0, QTableWidgetItem(f"EP{number:02d}"))
            self._fiction_table.setItem(row, 1, QTableWidgetItem(str(episode["title"])))
            self._fiction_table.setItem(row, 2, QTableWidgetItem(str(episode["source_count"])))
            function = "Motor și scene canonice + material nou"
            if number == 2:
                function = "Corpul mamei și cronologia îngrijirii"
            elif number == 5:
                function = "Dosar, plată, instituții și consecințe"
            elif number == 8:
                function = "Înregistrare, cameră, consimțământ"
            elif number == 9:
                function = "SIFTA, proiectul și separarea arhivei"
            elif number == 10:
                function = "Audit, drept la replică și final"
            self._fiction_table.setItem(row, 3, QTableWidgetItem(function))

    def _set_task(self, task_id: str, state: int) -> None:
        if not task_id:
            return
        status = "done" if state == int(Qt.CheckState.Checked.value) else "open"
        if update_miorita_task_status(MIORITA_ROOT, task_id, status):
            record_app_hardening_event(
                APP_HARDENING_ID,
                "miorita_task_status_changed",
                truth_label="OPERATIONAL",
                details={"task_id": task_id, "status": status},
            )
            self.set_status("Pas actualizat în Miorița")
        else:
            self.set_status("Nu am putut actualiza pasul")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = MioritaBridgeWidget()
    widget.resize(1220, 720)
    widget.show()
    sys.exit(app.exec())
