#!/usr/bin/env python3
"""Cortex Wake Lab.

Runs the same self-model wake questions across Alice cortex substrates and
records the comparison in `.sifta_state/cortex_comparison.jsonl`.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from System.sifta_base_widget import SiftaBaseWidget
from System import swarm_cortex_wake_probe as wake_probe

try:
    from System.swarm_app_focus import publish_focus
except Exception:  # pragma: no cover
    def publish_focus(*_args, **_kwargs) -> None:
        return None


APP_NAME = "Cortex Wake Lab"


class WakeProbeWorker(QThread):
    finished_payload = pyqtSignal(dict)

    def __init__(self, model_ids: list[str], *, dry_run: bool = False) -> None:
        super().__init__()
        self.model_ids = list(model_ids)
        self.dry_run = bool(dry_run)

    def run(self) -> None:  # pragma: no cover - covered through direct engine tests
        if self.dry_run:
            def runner(model_id: str, provider: str, prompt: str) -> str:
                return (
                    f"I am Alice waking through {model_id}. The receipt ledger, "
                    "body sensors, cortex turns, observer/observed loop, organs, "
                    "swimmers, memory, electricity, code, and heat ground this answer."
                )
        else:
            runner = None
        payload = wake_probe.run_probe_suite(
            self.model_ids,
            runner=runner,
            write_ledger=True,
            timeout_s=45.0,
            num_predict=384,
        )
        self.finished_payload.emit(payload)


class CortexWakeLabWidget(SiftaBaseWidget):
    APP_NAME = APP_NAME
    APP_LOCAL_CHAT_DISABLED = True

    def __init__(self, parent=None) -> None:
        self._worker: WakeProbeWorker | None = None
        super().__init__(parent)
        publish_focus(self.APP_NAME, "Comparing Alice cortex wake substrates")

    def build_ui(self, root: QVBoxLayout) -> None:
        intro = QLabel(
            "Compare cortex wake quality across Grok/Claude/Codex teacher cortexes "
            "and local Gemma4 student models using the same receipt-backed "
            "consciousness and embodiment question set."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: rgb(210,220,245); padding: 4px;")
        root.addWidget(intro)

        top = QHBoxLayout()
        models_box = QGroupBox("Cortex substrates")
        models_layout = QVBoxLayout(models_box)
        self.models = QListWidget()
        models_layout.addWidget(self.models)
        model_buttons = QHBoxLayout()
        refresh = QPushButton("Refresh models")
        refresh.clicked.connect(self.refresh_models)
        model_buttons.addWidget(refresh)
        select = QPushButton("Select Alice models")
        select.clicked.connect(self.select_alice_models)
        model_buttons.addWidget(select)
        models_layout.addLayout(model_buttons)
        top.addWidget(models_box, 1)

        questions_box = QGroupBox("Question set")
        questions_layout = QVBoxLayout(questions_box)
        self.questions = QTextBrowser()
        self.questions.setStyleSheet(
            "QTextBrowser { background: rgb(10,12,22); color: rgb(220,226,242); "
            "font-family: Menlo; font-size: 11px; border: 1px solid rgb(34,42,64); }"
        )
        questions_layout.addWidget(self.questions)
        top.addWidget(questions_box, 1)
        root.addLayout(top, 2)

        controls = QHBoxLayout()
        self.dry_run = QCheckBox("Dry run with fake runner")
        self.dry_run.setToolTip("Writes real comparison rows without calling live models.")
        controls.addWidget(self.dry_run)
        self.run_button = QPushButton("Run wake comparison")
        self.run_button.clicked.connect(self.run_probe)
        controls.addWidget(self.run_button)
        controls.addStretch()
        root.addLayout(controls)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Model", "Questions", "OK", "Errors", "Avg score", "Avg latency"])
        root.addWidget(self.table, 2)

        self.status_view = QTextBrowser()
        self.status_view.setStyleSheet(
            "QTextBrowser { background: rgb(8,10,18); color: rgb(210,220,238); "
            "font-family: Menlo; font-size: 11px; border: 1px solid rgb(34,42,64); }"
        )
        root.addWidget(self.status_view, 1)

        self.refresh_questions()
        self.refresh_models()
        self.refresh_summary()

    def refresh_questions(self) -> None:
        lines = []
        for q in wake_probe.default_questions():
            lines.append(f"{q.question_id} [{q.theme}]")
            lines.append(f"  {q.question}")
            lines.append(f"  expected: {', '.join(q.expected_terms)}")
            lines.append("")
        self.questions.setPlainText("\n".join(lines).strip())

    def refresh_models(self) -> None:
        self.models.clear()
        for spec in wake_probe.list_cortex_models():
            item = QListWidgetItem(f"{spec.model_id} ({spec.provider})")
            item.setData(32, spec.model_id)
            item.setCheckState(
                Qt.CheckState.Checked
                if spec.model_id in wake_probe.DEFAULT_MODEL_IDS and spec.available
                else Qt.CheckState.Unchecked
            )
            item.setToolTip(
                f"available={spec.available}; source={spec.source}; "
                f"size={spec.size}; modified={spec.modified}; {spec.note}"
            )
            self.models.addItem(item)
        self.set_status(f"{self.models.count()} cortex candidates listed")

    def select_alice_models(self) -> None:
        for i in range(self.models.count()):
            item = self.models.item(i)
            model_id = str(item.data(32))
            item.setCheckState(
                Qt.CheckState.Checked
                if model_id in wake_probe.DEFAULT_MODEL_IDS
                else Qt.CheckState.Unchecked
            )

    def selected_models(self) -> list[str]:
        out: list[str] = []
        for i in range(self.models.count()):
            item = self.models.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                out.append(str(item.data(32)))
        return out

    def run_probe(self) -> None:
        model_ids = self.selected_models()
        if not model_ids:
            self.status_view.setPlainText("No cortex models selected.")
            return
        self.run_button.setEnabled(False)
        self.set_status("Wake comparison running")
        self.status_view.setPlainText("Running wake comparison; rows will append to .sifta_state/cortex_comparison.jsonl")
        self._worker = WakeProbeWorker(model_ids, dry_run=self.dry_run.isChecked())
        self._worker.finished_payload.connect(self._on_probe_finished)
        self._worker.start()

    def _on_probe_finished(self, payload: dict) -> None:
        self.run_button.setEnabled(True)
        self.set_status(f"Finished run {payload.get('run_id', '')}")
        self.render_summary(payload.get("summary") or {})
        self.status_view.setPlainText(
            f"run_id: {payload.get('run_id', '')}\n"
            f"rows: {len(payload.get('results') or [])}\n"
            f"ledger: .sifta_state/{wake_probe.LEDGER_FILENAME}\n"
            f"winner: {(payload.get('summary') or {}).get('winner_by_grounding_then_latency', '')}"
        )

    def refresh_summary(self) -> None:
        self.render_summary(wake_probe.latest_summary())

    def render_summary(self, summary: dict) -> None:
        rows = summary.get("models") or []
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            values = [
                row.get("model_id", ""),
                row.get("questions", 0),
                row.get("ok", 0),
                row.get("errors", 0),
                row.get("avg_grounding_score", 0),
                row.get("avg_latency_s", 0),
            ]
            for c, value in enumerate(values):
                self.table.setItem(r, c, QTableWidgetItem(str(value)))
        self.table.resizeColumnsToContents()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = CortexWakeLabWidget()
    win.resize(1180, 760)
    win.show()
    sys.exit(app.exec())
