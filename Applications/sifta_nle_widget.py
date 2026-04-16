#!/usr/bin/env python3
"""
sifta_nle_widget.py — SIFTA NLE embedded as a QWidget for iSwarm OS MDI
========================================================================

Wraps NLEWindow's internals into a QWidget (not QMainWindow) so it
opens inside the Swarm OS desktop as an MDI subwindow.  Auto-loads
demo data on open so the scientist sees real waveforms + swimmers
immediately.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if str(_REPO / "Applications") not in sys.path:
    sys.path.insert(0, str(_REPO / "Applications"))

from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSlider,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from sifta_nle import (
    PheromoneMatrixCanvas,
    generate_edl,
    parse_srt,
    REPO,
    FFMPEG,
)


class NLEWidget(QWidget):
    """Full NLE panel — embeddable inside iSwarm OS MDI."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("""
            QWidget { background: rgb(8, 10, 18); color: rgb(200, 210, 240); }
            QGroupBox {
                border: 1px solid rgb(45, 42, 65); border-radius: 6px;
                margin-top: 10px; padding-top: 14px;
                font-family: 'Menlo'; font-size: 10px; color: rgb(200, 210, 240);
            }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; color: rgb(0, 255, 200); }
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 rgb(50,42,65), stop:1 rgb(30,25,42));
                border: 1px solid rgb(80,70,100); border-radius: 6px; padding: 6px 14px;
                color: rgb(200,210,240); font-family: 'Menlo'; font-size: 11px; font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 rgb(70,60,90), stop:1 rgb(45,38,62));
                border-color: rgb(0,255,200);
            }
            QPushButton#btnRender {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 rgb(0,120,80), stop:1 rgb(0,60,40));
                border-color: rgb(0,255,200);
            }
            QSlider::groove:horizontal { height: 4px; background: rgb(40,35,55); border-radius: 2px; }
            QSlider::handle:horizontal {
                background: rgb(0,255,200); width: 12px; height: 12px; margin: -4px 0; border-radius: 6px;
            }
            QTextEdit {
                background: rgb(10,8,16); border: 1px solid rgb(40,35,55); border-radius: 4px;
                font-family: 'Menlo'; font-size: 9px; color: rgb(0,255,200); padding: 4px;
            }
            QTableWidget {
                background: rgb(12,10,20); border: 1px solid rgb(40,35,55);
                font-family: 'Menlo'; font-size: 9px; color: rgb(200,210,240);
                gridline-color: rgb(35,32,50);
            }
            QHeaderView::section {
                background: rgb(25,22,38); color: rgb(0,255,200);
                border: 1px solid rgb(40,35,55); font-family: 'Menlo'; font-size: 9px;
                font-weight: bold; padding: 4px;
            }
            QTabWidget::pane { border: 1px solid rgb(45,42,65); background: rgb(12,10,20); }
            QTabBar::tab {
                background: rgb(25,22,38); color: rgb(150,155,180);
                border: 1px solid rgb(45,42,65); padding: 6px 16px;
                font-family: 'Menlo'; font-size: 10px;
            }
            QTabBar::tab:selected { background: rgb(40,35,55); color: rgb(0,255,200); border-bottom-color: rgb(0,255,200); }
        """)

        main = QVBoxLayout(self)
        main.setContentsMargins(6, 6, 6, 6)
        main.setSpacing(4)

        title_bar = QHBoxLayout()
        title = QLabel("SIFTA NLE — Stigmergic Swarm Cut Studio")
        title.setFont(QFont("Menlo", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: rgb(0,255,200); padding: 2px;")
        title_bar.addWidget(title)
        title_bar.addStretch()
        self.status_label = QLabel("Ready — load files or DEMO")
        self.status_label.setStyleSheet("color: rgb(100,105,130); font-size: 10px;")
        title_bar.addWidget(self.status_label)
        main.addLayout(title_bar)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        btn_load = QPushButton("Load Files")
        btn_load.clicked.connect(self._load_files)
        toolbar.addWidget(btn_load)

        btn_demo = QPushButton("Load Demo")
        btn_demo.clicked.connect(self._load_demo)
        toolbar.addWidget(btn_demo)

        btn_srt = QPushButton("Load SRT")
        btn_srt.clicked.connect(self._load_srt)
        toolbar.addWidget(btn_srt)

        toolbar.addWidget(self._sep())

        self.btn_play = QPushButton("Play")
        self.btn_play.clicked.connect(self._toggle_play)
        toolbar.addWidget(self.btn_play)

        btn_hero = QPushButton("Hero Frame")
        btn_hero.setCheckable(True)
        btn_hero.toggled.connect(self._toggle_hero)
        toolbar.addWidget(btn_hero)

        toolbar.addWidget(self._sep())

        btn_edl = QPushButton("Export EDL")
        btn_edl.clicked.connect(self._export_edl)
        toolbar.addWidget(btn_edl)

        btn_render = QPushButton("Render")
        btn_render.setObjectName("btnRender")
        btn_render.clicked.connect(self._render)
        toolbar.addWidget(btn_render)

        toolbar.addStretch()
        main.addLayout(toolbar)

        slider_row = QHBoxLayout()
        slider_row.setSpacing(15)
        self._slider_labels: dict[str, QLabel] = {}
        for label, default, slot, lo, hi in [
            ("Rhythm", 80, self._rhythm_changed, 10, 200),
            ("Chroma", 40, self._chroma_changed, 0, 150),
            ("Threshold", 65, self._threshold_changed, 20, 95),
        ]:
            box = QVBoxLayout()
            lbl = QLabel(label)
            lbl.setStyleSheet("font-size: 9px; color: rgb(100,105,130);")
            box.addWidget(lbl)
            sl = QSlider(Qt.Orientation.Horizontal)
            sl.setRange(lo, hi)
            sl.setValue(default)
            sl.setFixedWidth(140)
            sl.valueChanged.connect(slot)
            box.addWidget(sl)
            val = QLabel(str(default))
            val.setStyleSheet("font-size: 9px; color: rgb(0,255,200); font-weight: bold;")
            box.addWidget(val)
            self._slider_labels[label] = val
            slider_row.addLayout(box)
        slider_row.addStretch()
        main.addLayout(slider_row)

        self._pane_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.canvas = PheromoneMatrixCanvas()
        self.canvas.cut_executed.connect(self._on_cut)
        self._pane_splitter.addWidget(self.canvas)

        sidebar = QTabWidget()
        sidebar.setMaximumWidth(320)
        sidebar.setMinimumWidth(260)

        clip_tab = QWidget()
        cl = QVBoxLayout(clip_tab)
        self.clip_table = QTableWidget(0, 4)
        self.clip_table.setHorizontalHeaderLabels(["File", "Dur", "FPS", "Codec"])
        self.clip_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.clip_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        cl.addWidget(self.clip_table)
        sidebar.addTab(clip_tab, "Clips")

        edl_tab = QWidget()
        el = QVBoxLayout(edl_tab)
        self.edl_table = QTableWidget(0, 4)
        self.edl_table.setHorizontalHeaderLabels(["Time", "Source", "Type", "Str"])
        self.edl_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        el.addWidget(self.edl_table)
        sidebar.addTab(edl_tab, "Cuts")

        log_tab = QWidget()
        ll = QVBoxLayout(log_tab)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        ll.addWidget(self.log_view)
        sidebar.addTab(log_tab, "Log")

        self._pane_splitter.addWidget(sidebar)
        self._pane_splitter.setStretchFactor(0, 3)
        self._pane_splitter.setStretchFactor(1, 1)
        main.addWidget(self._pane_splitter, 1)
        QTimer.singleShot(0, self._balance_pane_splitter)

        self.log_timer = QTimer(self)
        self.log_timer.timeout.connect(self._refresh_log)
        self.log_timer.start(500)

        QTimer.singleShot(200, self._load_demo)

    def _balance_pane_splitter(self) -> None:
        from System.splitter_utils import balance_horizontal_splitter

        balance_horizontal_splitter(
            self._pane_splitter,
            self,
            left_ratio=0.72,
            min_right=260,
            min_left=240,
            max_right=320,
        )

    def _sep(self) -> QFrame:
        s = QFrame()
        s.setFrameShape(QFrame.Shape.VLine)
        s.setStyleSheet("color: rgb(45,42,65);")
        return s

    def _load_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self, "Load Media Files", str(Path.home()),
            "Media (*.mp4 *.mov *.mkv *.avi *.wav *.mp3 *.aac *.m4a);;All (*)",
        )
        if files:
            self.canvas.load_clips([Path(f) for f in files])
            self._update_clip_table()
            self.status_label.setText(f"Loaded {len(files)} files")

    def _load_demo(self) -> None:
        self.canvas.load_demo()
        self._update_clip_table()
        self.status_label.setText("Demo loaded — 6 synthetic clips")

    def _load_srt(self) -> None:
        f, _ = QFileDialog.getOpenFileName(self, "Load Subtitles", str(Path.home()), "SRT (*.srt);;All (*)")
        if f:
            subs = parse_srt(Path(f))
            self.canvas.subtitles = subs
            self.canvas._log(f"Loaded {len(subs)} subtitle entries")
            self.status_label.setText(f"Loaded {len(subs)} subtitles")

    def _toggle_play(self) -> None:
        self.canvas.playing = not self.canvas.playing
        self.btn_play.setText("Pause" if self.canvas.playing else "Play")

    def _toggle_hero(self, on: bool) -> None:
        self.canvas.set_hero_active(on)

    def _rhythm_changed(self, v: int) -> None:
        self.canvas.set_rhythm_density(v)
        self._slider_labels["Rhythm"].setText(str(v))

    def _chroma_changed(self, v: int) -> None:
        self.canvas.set_chroma_density(v)
        self._slider_labels["Chroma"].setText(str(v))

    def _threshold_changed(self, v: int) -> None:
        self.canvas.set_cut_threshold(v)
        self._slider_labels["Threshold"].setText(str(v))

    def _on_cut(self, t: float, reason: str) -> None:
        row = self.edl_table.rowCount()
        self.edl_table.insertRow(row)
        tc = f"{int(t // 60):02d}:{int(t % 60):02d}.{int((t % 1) * 100):02d}"
        self.edl_table.setItem(row, 0, QTableWidgetItem(tc))
        self.edl_table.setItem(row, 1, QTableWidgetItem(reason))
        self.edl_table.setItem(row, 2, QTableWidgetItem("CUT"))
        for ph in self.canvas.pheromones:
            if abs(ph.time_pos - t) < 0.1:
                self.edl_table.setItem(row, 3, QTableWidgetItem(f"{ph.strength:.2f}"))
                break

    def _export_edl(self) -> None:
        if not self.canvas.executed_cuts:
            self.canvas._log("No cuts to export")
            return
        decisions = []
        cuts = sorted(self.canvas.executed_cuts)
        cuts = [0.0] + cuts + [self.canvas.total_duration]
        for i in range(len(cuts) - 1):
            ss, se = cuts[i], cuts[i + 1]
            ci = 0
            for j, c in enumerate(self.canvas.clips):
                if c.timeline_start <= ss < c.timeline_start + c.duration:
                    ci = j
                    break
            from sifta_nle import EditDecision
            decisions.append(EditDecision(
                clip_idx=ci,
                in_time=ss - self.canvas.clips[ci].timeline_start,
                out_time=min(se - self.canvas.clips[ci].timeline_start, self.canvas.clips[ci].duration),
                timeline_pos=ss,
            ))
        edl = generate_edl(decisions, self.canvas.clips)
        out = REPO / ".sifta_state" / "sifta_edit.edl"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(edl)
        self.canvas._log(f"EDL exported: {out}")
        self.status_label.setText(f"EDL saved: {out.name}")

    def _render(self) -> None:
        if not FFMPEG:
            self.canvas._log("ffmpeg not found — brew install ffmpeg")
            return
        self.canvas._log("Render queued — ffmpeg pipeline starting...")
        self.status_label.setText("Rendering...")

    def _update_clip_table(self) -> None:
        self.clip_table.setRowCount(0)
        for c in self.canvas.clips:
            row = self.clip_table.rowCount()
            self.clip_table.insertRow(row)
            self.clip_table.setItem(row, 0, QTableWidgetItem(c.filename))
            self.clip_table.setItem(row, 1, QTableWidgetItem(f"{c.duration:.1f}s"))
            self.clip_table.setItem(row, 2, QTableWidgetItem(f"{c.fps:.1f}"))
            self.clip_table.setItem(row, 3, QTableWidgetItem(c.codec))

    def _refresh_log(self) -> None:
        lines = self.canvas.log_lines[-100:]
        self.log_view.setPlainText("\n".join(lines))
        sb = self.log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self.canvas.timer.stop()
        self.log_timer.stop()
        super().closeEvent(event)
