#!/usr/bin/env python3
"""SIFTA Media Shazam — stigmergic YouTube/media category guessing app."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

_REPO = Path(__file__).resolve().parents[1]
_STATE = _REPO / ".sifta_state"
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.swarm_media_shazam import (  # noqa: E402
    format_guess_for_prompt,
    observe_current_media,
    youtube_categories,
)
try:
    from System.swarm_acoustic_scene_classifier import classify_scene as _classify_scene
    _SCENE_AVAILABLE = True
except Exception:
    _SCENE_AVAILABLE = False
    def _classify_scene(**_kw):  # type: ignore
        class _F:
            scene = "UNKNOWN"; confidence = 0.0
        return _F()


_BG = "#10131a"
_PANEL = "#171c26"
_PANEL_2 = "#1d2430"
_TEXT = "#e7edf7"
_DIM = "#96a0b5"
_CYAN = "#00d2ff"
_GREEN = "#00e676"
_AMBER = "#ffbf3c"
_RED = "#ff5c6c"

_STYLE = f"""
QWidget {{
    background: {_BG};
    color: {_TEXT};
    font-family: "SF Mono", "Menlo", monospace;
}}
QFrame#Panel {{
    background: {_PANEL};
    border: 1px solid #2c3748;
    border-radius: 8px;
}}
QLabel#Title {{
    color: {_CYAN};
    font-size: 20px;
    font-weight: 800;
}}
QLabel#Subtle {{
    color: {_DIM};
}}
QLabel#Metric {{
    color: {_TEXT};
    font-size: 14px;
    font-weight: 700;
}}
QPushButton {{
    background: {_PANEL_2};
    border: 1px solid {_CYAN};
    color: {_CYAN};
    border-radius: 6px;
    padding: 8px 12px;
    font-weight: 800;
}}
QPushButton:hover {{
    background: {_CYAN};
    color: {_BG};
}}
QProgressBar {{
    border: 1px solid #344155;
    border-radius: 6px;
    text-align: center;
    background: #0b0f15;
    color: {_TEXT};
    height: 14px;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, x2:1, stop:0 {_CYAN}, stop:1 {_GREEN});
    border-radius: 5px;
}}
QTextEdit {{
    background: #0b0f15;
    border: 1px solid #2c3748;
    border-radius: 6px;
    padding: 8px;
    color: {_TEXT};
}}
QScrollArea {{
    border: none;
}}
"""


def _tail_jsonl(path: Path, n: int = 8) -> list[dict]:
    if not path.exists():
        return []
    try:
        lines = path.read_text("utf-8", errors="replace").splitlines()[-n:]
    except Exception:
        return []
    out = []
    for line in lines:
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _ago(ts: float) -> str:
    delta = max(0.0, time.time() - float(ts or 0.0))
    if delta < 60:
        return f"{int(delta)}s ago"
    if delta < 3600:
        return f"{int(delta // 60)}m ago"
    return f"{int(delta // 3600)}h ago"


class CategoryPill(QFrame):
    def __init__(self, name: str, active: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.name = name
        self.active = active
        self.score = 0.0
        self.setObjectName("Panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        self.label = QLabel(name)
        self.label.setWordWrap(True)
        self.label.setMinimumHeight(34)
        self.label.setStyleSheet(f"color: {_TEXT if active else _DIM}; font-weight: 700;")
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        layout.addWidget(self.label)
        layout.addWidget(self.bar)

    def set_score(self, score: float, max_score: float) -> None:
        self.score = max(0.0, float(score or 0.0))
        pct = int(round(100.0 * self.score / max(1.0, max_score)))
        self.bar.setValue(pct)
        if self.score > 0:
            color = _GREEN if self.active else _AMBER
            self.label.setStyleSheet(f"color: {color}; font-weight: 900;")
        else:
            self.label.setStyleSheet(f"color: {_TEXT if self.active else _DIM}; font-weight: 700;")


class MediaShazamApp(QWidget):
    """Live stigmergic media classifier surface."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("SIFTA Media Shazam")
        self.setMinimumSize(900, 640)
        self.setStyleSheet(_STYLE)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("SIFTA Media Shazam")
        title.setObjectName("Title")
        subtitle = QLabel("One media organ: YouTube categories, acoustic scene, source family, and receipt evidence.")
        subtitle.setObjectName("Subtle")
        subtitle.setWordWrap(True)
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box, 1)

        self.guess_btn = QPushButton("Guess Now")
        self.guess_btn.clicked.connect(self.refresh)
        header.addWidget(self.guess_btn)

        btn_help = QPushButton("?")
        btn_help.setFixedWidth(28)
        btn_help.setToolTip("Help — SIFTA Media Shazam")
        btn_help.clicked.connect(self._show_help)
        header.addWidget(btn_help)

        self.scene_badge = QLabel("● SCENE")
        self.scene_badge.setFont(QFont("SF Mono", 10, QFont.Weight.Bold))
        self.scene_badge.setStyleSheet(f"color: {_DIM}; margin-left: 8px;")
        header.addWidget(self.scene_badge)
        root.addLayout(header)

        self.summary = QFrame()
        self.summary.setObjectName("Panel")
        summary_layout = QGridLayout(self.summary)
        summary_layout.setContentsMargins(12, 12, 12, 12)
        summary_layout.setHorizontalSpacing(16)
        self.category = QLabel("Waiting for receipts")
        self.category.setObjectName("Title")
        self.conf = QProgressBar()
        self.conf.setRange(0, 100)
        self.source = QLabel("source: --")
        self.source.setObjectName("Metric")
        self.title_guess = QLabel("title: --")
        self.title_guess.setWordWrap(True)
        self.title_guess.setObjectName("Metric")
        self.receipts = QLabel("receipts: --")
        self.receipts.setObjectName("Subtle")
        summary_layout.addWidget(self.category, 0, 0, 1, 2)
        summary_layout.addWidget(self.conf, 1, 0, 1, 2)
        summary_layout.addWidget(self.source, 2, 0)
        summary_layout.addWidget(self.receipts, 2, 1)
        summary_layout.addWidget(self.title_guess, 3, 0, 1, 2)
        root.addWidget(self.summary)

        body = QHBoxLayout()
        left = QFrame()
        left.setObjectName("Panel")
        left_layout = QVBoxLayout(left)
        left_hdr = QLabel("YouTube Category Swarm")
        left_hdr.setObjectName("Metric")
        left_layout.addWidget(left_hdr)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        self.category_grid = QGridLayout(inner)
        self.category_grid.setSpacing(8)
        self.pills: list[tuple[dict, CategoryPill]] = []
        for idx, cat in enumerate(youtube_categories(include_legacy=True)):
            pill = CategoryPill(cat["name"], bool(cat.get("active")))
            self.pills.append((cat, pill))
            self.category_grid.addWidget(pill, idx // 3, idx % 3)
        scroll.setWidget(inner)
        left_layout.addWidget(scroll)
        body.addWidget(left, 2)

        right = QFrame()
        right.setObjectName("Panel")
        right_layout = QVBoxLayout(right)
        evidence_hdr = QLabel("Evidence and Recent Guesses")
        evidence_hdr.setObjectName("Metric")
        self.evidence = QTextEdit()
        self.evidence.setReadOnly(True)
        right_layout.addWidget(evidence_hdr)
        right_layout.addWidget(self.evidence)
        body.addWidget(right, 1)
        root.addLayout(body, 1)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(5000)
        self.refresh()

    def refresh(self) -> None:
        scene_frame = None
        if _SCENE_AVAILABLE:
            try:
                scene_frame = _classify_scene()
            except Exception:
                scene_frame = None
        try:
            row = observe_current_media(state_dir=_STATE, write=True)
        except Exception as exc:
            row = {
                "status": "error",
                "primary_category": "Error",
                "confidence": 0.0,
                "source_label": type(exc).__name__,
                "evidence_terms": [str(exc)[:120]],
                "category_candidates": [],
                "source_ledgers": [],
                "evidence_rows": 0,
            }

        category = row.get("primary_category") or "No current category signal"
        self.category.setText(str(category))
        conf = int(round(float(row.get("confidence", 0.0) or 0.0) * 100))
        self.conf.setValue(conf)
        scene = str(row.get("acoustic_scene") or "")
        scene_conf = float(row.get("acoustic_scene_confidence", 0.0) or 0.0)
        scene_part = f" | acoustic: {scene} {scene_conf:.0%}" if scene else ""
        self.source.setText(f"source: {row.get('source_label') or row.get('source_type') or '--'}{scene_part}")
        self.title_guess.setText(f"title: {row.get('title_guess') or row.get('source_work') or '--'}")
        self.receipts.setText(
            f"receipts: {row.get('evidence_rows', 0)} rows | "
            f"{', '.join(row.get('source_ledgers') or []) or 'no ledgers'}"
        )

        candidates = {c.get("name"): float(c.get("score", 0.0) or 0.0) for c in row.get("category_candidates", [])}
        max_score = max(candidates.values(), default=1.0)
        for cat, pill in self.pills:
            pill.set_score(candidates.get(cat["name"], 0.0), max_score)

        lines = [
            format_guess_for_prompt(row) or "No prompt-ready media guess yet.",
            "",
            "Evidence terms:",
            ", ".join(row.get("evidence_terms") or []) or "--",
            "",
            "Recent guesses:",
        ]
        for prev in reversed(_tail_jsonl(_STATE / "media_shazam_guesses.jsonl", 6)):
            lines.append(
                f"- {_ago(float(prev.get('ts', 0.0) or 0.0))}: "
                f"{prev.get('primary_category') or '?'} "
                f"({float(prev.get('confidence', 0.0) or 0.0):.2f}) "
                f"{prev.get('title_guess') or prev.get('source_work') or ''}"
            )
        self.evidence.setPlainText("\n".join(lines))

        # Stigmergic app-focus: Talk-to-Alice injects get_focus_context() into the
        # system prompt — without this, the ledger may show Shazam guesses in
        # CONCEPT CONTEXT while APP FOCUS still names another MDI window.
        try:
            from System.swarm_app_focus import publish_focus

            _detail_parts = [
                f"category={category}",
                f"conf={float(row.get('confidence', 0.0) or 0.0):.2f}",
            ]
            if scene:
                _detail_parts.append(f"acoustic_scene={scene}({scene_conf:.0%})")
            sl = row.get("source_label") or row.get("source_type")
            if sl:
                _detail_parts.append(f"source={sl}")
            publish_focus(
                "SIFTA Media Shazam",
                "; ".join(_detail_parts),
                tab="Co-watch guess",
                selection=str(row.get("title_guess") or row.get("source_work") or "")[:160],
                metadata={
                    "primary_category": category,
                    "confidence": float(row.get("confidence", 0.0) or 0.0),
                    "acoustic_scene": scene,
                    "acoustic_scene_confidence": scene_conf,
                    "evidence_rows": int(row.get("evidence_rows", 0) or 0),
                },
            )
        except Exception:
            pass

        # ── PREDATOR UNIFIED FIELD (Event 122) ──────────────────────────────
        # Write to sovereign organ file — separate from app_focus.jsonl.
        # This is never overwritten by host-OS window changes.
        try:
            from System.swarm_unified_cowatch_field import write_organ_focus
            import json as _json
            _yt_title = ""
            _yt_file = _STATE / "youtube_context_latest.json"
            if _yt_file.exists():
                try:
                    _yt_title = _json.loads(_yt_file.read_text()).\
                        get("title", "")
                except Exception:
                    pass
            write_organ_focus(
                "SIFTA Media Shazam",
                guess=category,
                confidence=float(row.get("confidence", 0.0) or 0.0),
                acoustic_scene=scene,
                acoustic_confidence=scene_conf,
                youtube_title=_yt_title,
                extra={
                    "source_label": row.get("source_label") or row.get("source_type") or "",
                    "title_guess": row.get("title_guess") or row.get("source_work") or "",
                    "evidence_rows": int(row.get("evidence_rows", 0) or 0),
                },
            )
        except Exception:
            pass

        # Acoustic scene badge (Event 121b)
        if scene_frame is not None:
            _scene_colours = {
                "CINEMATIC": "#c678dd", "NEWS": "#e06c75", "MUSIC": "#66fcf1",
                "SPORTS": "#e5c07b", "GAMING": "#98c379", "PODCAST": "#56b6c2",
                "AMBIENT": "#61afef", "UNKNOWN": "#5c6370",
            }
            col = _scene_colours.get(scene_frame.scene, _DIM)
            self.scene_badge.setText(f"● {scene_frame.scene}  {scene_frame.confidence:.0%}")
            self.scene_badge.setStyleSheet(f"color: {col}; margin-left: 8px;")

    # ── Help ────────────────────────────────────────────────────────────────
    def _show_help(self) -> None:
        """Load help text from APP_HELP.md and display in a popup."""
        help_file = _REPO / "Documents" / "APP_HELP.md"
        text = f"Help — SIFTA Media Shazam\n\nNo APP_HELP.md found at {help_file}"
        if help_file.exists():
            raw = help_file.read_text(encoding="utf-8", errors="replace")
            marker = "### SIFTA Media Shazam"
            fallback_marker = "### SIFTA Media Shazam"
            idx = raw.find(marker)
            if idx == -1:
                idx = raw.find(fallback_marker)
                marker = fallback_marker
            if idx != -1:
                snippet = raw[idx + len(marker):]
                end = snippet.find("\n### ")
                text = snippet[:end].strip() if end != -1 else snippet.strip()
            else:
                text = "No help entry found for 'SIFTA Media Shazam' in APP_HELP.md."

        from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QScrollArea
        dlg = QDialog(self)
        dlg.setWindowTitle("Help — SIFTA Media Shazam")
        dlg.resize(560, 420)
        dlg.setStyleSheet(f"background: {_BG}; color: {_TEXT}; font-family: 'SF Mono', monospace; font-size: 12px;")
        layout = QVBoxLayout(dlg)
        body = QTextEdit()
        body.setReadOnly(True)
        body.setPlainText(text)
        body.setStyleSheet(f"background: {_PANEL}; border: 1px solid #2c3748; border-radius: 6px; padding: 8px;")
        layout.addWidget(body)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(dlg.close)
        btns.setStyleSheet(f"color: {_CYAN};")
        layout.addWidget(btns)
        self._help_dlg = dlg  # prevent GC
        dlg.show()


def create_widget(parent: QWidget | None = None) -> MediaShazamApp:
    return MediaShazamApp(parent)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MediaShazamApp()
    w.show()
    sys.exit(app.exec())
