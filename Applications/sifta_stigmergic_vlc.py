#!/usr/bin/env python3
"""
Stigmergic VLC Bridge — Utilities organ for SIFTA OS (macOS).

Deterministic handoff to VideoLAN VLC (separate install under /Applications/VLC.app).
Every launch attempt appends one row to `.sifta_state/stigmergic_vlc_effector.jsonl`
(effector truth per IDE_BOOT_COVENANT.md §6 / §7.2). Optional deposits on the
cross-IDE bus (`ide_stigmergic_bridge.deposit`) mark session boundaries.

This module does not vendor VLC source; it orchestrates the system player and
records receipts. libVLC remains LGPL-2.1+; VLC app is GPL-2.0+ — see Help.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import uuid
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QFont
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_EFFECTOR = _STATE / "stigmergic_vlc_effector.jsonl"

if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.ide_stigmergic_bridge import deposit  # noqa: E402
from System.ledger_append import append_jsonl_line  # noqa: E402
from System.swarm_kernel_identity import owner_silicon  # noqa: E402

_BG = "#141620"
_CARD = "#1c2230"
_TEXT = "#e8ecf4"
_DIM = "#8b95ab"
_CYAN = "#7dcfff"


_STYLE = f"""
QWidget {{ background: {_BG}; color: {_TEXT}; font-family: 'SF Pro Text', 'Helvetica Neue', sans-serif; }}
QLabel#Title {{ color: {_CYAN}; font-size: 18px; font-weight: 700; }}
QLabel#Dim {{ color: {_DIM}; font-size: 12px; }}
QPushButton {{
    background: {_CARD}; color: {_CYAN}; border: 1px solid #3b4261;
    border-radius: 6px; padding: 8px 14px; font-weight: 600;
}}
QPushButton:hover {{ background: #2a3042; border-color: {_CYAN}; }}
QLineEdit {{
    background: {_CARD}; color: {_TEXT}; border: 1px solid #3b4261;
    border-radius: 6px; padding: 8px;
}}
QListWidget {{
    background: {_CARD}; color: {_TEXT}; border: 1px solid #3b4261;
    border-radius: 6px;
}}
QTextEdit {{
    background: {_CARD}; color: {_TEXT}; border: 1px solid #3b4261;
    border-radius: 6px; font-family: 'SF Mono', Menlo, monospace; font-size: 11px;
}}
QMenuBar {{
    background: {_CARD}; color: {_TEXT}; border-bottom: 1px solid #3b4261;
    padding: 2px 4px;
}}
QMenuBar::item:selected {{ background: #2a3042; }}
"""


def _vlc_app_path() -> Path | None:
    p = Path("/Applications/VLC.app")
    return p if p.is_dir() else None


def _append_effector(row: dict) -> None:
    _STATE.mkdir(parents=True, exist_ok=True)
    row.setdefault("ts", time.time())
    row.setdefault("effector", "stigmergic_vlc")
    row.setdefault("homeworld_serial", owner_silicon())
    append_jsonl_line(_EFFECTOR, row)


def _tail_effector(n: int = 24) -> list[dict]:
    if not _EFFECTOR.exists():
        return []
    try:
        lines = _EFFECTOR.read_text("utf-8", errors="replace").strip().splitlines()
    except OSError:
        return []
    out: list[dict] = []
    for line in lines[-n:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


HELP_TEXT = """Stigmergic VLC Bridge — Help

What this is
  A SIFTA Utilities launcher that opens VideoLAN VLC on macOS and writes append-only
  rows to .sifta_state/stigmergic_vlc_effector.jsonl so Alice never has to claim she
  played media without a receipt.

VideoLAN / VLC (upstream)
  VLC is free software from the VideoLAN project. The desktop app is GPL-2.0 or
  later on many builds; the embeddable engine libVLC is LGPL-2.1 or later.
  Install the macOS app from https://www.videolan.org/vlc/

  Main development uses GitLab merge requests; the GitHub mirror does not accept
  pull requests (see upstream README).

SIFTA behavior
  • Open File / Play URL run: open -n -a /Applications/VLC.app [<target>]
  • Each attempt records ok, argv, and homeworld_serial on this node.
  • Session open posts a short row on ide_stigmergic_trace via deposit().

If VLC is missing
  The bridge will fall back to opening the URL in your default browser
  (macOS `open <url>`) so you never lose access to the media.
  Install VLC.app into /Applications for native playback and receipts.
  Download from https://www.videolan.org/vlc/
"""


class StigmergicVlcBridge(QWidget):
    """PyQt6 Utilities surface: VLC handoff + stigmergic receipts + Help menu."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(_STYLE)

        try:
            deposit(
                "stigmergic_vlc_bridge",
                "SESSION_OPEN: Stigmergic VLC Bridge widget constructed",
                kind="stigmergic_signin",
                meta={
                    "app": "Stigmergic VLC Bridge",
                    "homeworld_serial": owner_silicon(),
                },
            )
        except Exception:
            pass

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        mbar = QMenuBar(self)
        file_m = mbar.addMenu("File")
        act_open = QAction("Open File in VLC…", self)
        act_open.triggered.connect(self._pick_open_file)
        file_m.addAction(act_open)
        act_blank = QAction("Launch VLC (no media)", self)
        act_blank.triggered.connect(self._launch_blank)
        file_m.addAction(act_blank)
        file_m.addSeparator()
        act_refresh = QAction("Refresh Recent", self)
        act_refresh.triggered.connect(self._refresh_recent)
        file_m.addAction(act_refresh)

        help_m = mbar.addMenu("Help")
        act_help = QAction("Stigmergic VLC Bridge Help", self)
        act_help.triggered.connect(self._show_help)
        help_m.addAction(act_help)
        act_upstream = QAction("VideoLAN VLC Website", self)
        act_upstream.triggered.connect(self._open_videolan)
        help_m.addAction(act_upstream)

        root.addWidget(mbar)

        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(16, 14, 16, 14)
        bl.setSpacing(12)

        title = QLabel("Stigmergic VLC Bridge")
        title.setObjectName("Title")
        bl.addWidget(title)

        self._status = QLabel()
        self._status.setObjectName("Dim")
        self._status.setWordWrap(True)
        bl.addWidget(self._status)

        url_row = QHBoxLayout()
        self._url = QLineEdit()
        self._url.setPlaceholderText("https://… or file:///… or path")
        btn_url = QPushButton("Play URL in VLC")
        btn_url.clicked.connect(self._play_url)
        url_row.addWidget(self._url, 1)
        url_row.addWidget(btn_url)
        bl.addLayout(url_row)

        btn_file = QPushButton("Choose file…")
        btn_file.clicked.connect(self._pick_open_file)
        bl.addWidget(btn_file, alignment=Qt.AlignmentFlag.AlignLeft)

        bl.addWidget(QLabel("Recent effector rows (newest last in file; shown newest here):"))
        self._recent = QListWidget()
        self._recent.setMinimumHeight(140)
        bl.addWidget(self._recent)

        bl.addWidget(QLabel("Raw tail (debug):"))
        self._raw = QTextEdit()
        self._raw.setReadOnly(True)
        self._raw.setMaximumHeight(120)
        bl.addWidget(self._raw)

        root.addWidget(body, 1)

        self._refresh_status()
        self._refresh_recent()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_status)
        self._timer.start(8000)

    def _refresh_status(self) -> None:
        vlc = _vlc_app_path()
        if vlc:
            self._status.setText(f"VLC found: {vlc}  ·  Node {owner_silicon()}")
        else:
            self._status.setText(
                "VLC not found at /Applications/VLC.app — "
                "URLs will open in your default browser as fallback. "
                "Install from videolan.org for native playback."
            )

    def _show_help(self) -> None:
        QMessageBox.information(self, "Help — Stigmergic VLC Bridge", HELP_TEXT)

    def _open_videolan(self) -> None:
        subprocess.run(
            ["open", "https://www.videolan.org/vlc/"],
            check=False,
        )
        _append_effector(
            {
                "action": "open_help_url",
                "target": "https://www.videolan.org/vlc/",
                "ok": True,
                "truth_note": "system open videolan.org",
            }
        )

    def _refresh_recent(self) -> None:
        self._recent.clear()
        rows = _tail_effector(40)
        for r in reversed(rows[-16:]):
            action = str(r.get("action", "row"))
            tgt = str(r.get("target", ""))[:80]
            ok = r.get("ok")
            item = QListWidgetItem(f"{action}  ok={ok}  {tgt}")
            item.setData(Qt.ItemDataRole.UserRole, r)
            self._recent.addItem(item)
        try:
            tail = _EFFECTOR.read_text("utf-8", errors="replace").splitlines()[-6:]
            self._raw.setPlainText("\n".join(tail))
        except OSError:
            self._raw.clear()

    def _run_open_vlc(self, *targets: str) -> bool:
        vlc = _vlc_app_path()
        if not vlc:
            target_str = " ".join(targets) if targets else "(blank)"
            # ── SIFTA-INTERNAL BROWSER HANDOFF (AG46 2026-05-07) ─────────────
            # VLC is not installed. Per §7.5 we do NOT call macOS `open` (that
            # is a second OS — breaks single-process gaze, weakens tool truth).
            # Instead, write a stigmergic drop file that the Alice Browser
            # widget polls. The URL opens inside SIFTA OS, receipt included.
            is_url = any(
                str(t).startswith(("http://", "https://", "rtsp://", "rtmp://"))
                for t in targets
            )
            if is_url and targets:
                url = targets[0]
                drop_file = _STATE / "alice_browser_open_url.txt"
                drop_err = ""
                try:
                    _STATE.mkdir(parents=True, exist_ok=True)
                    drop_file.write_text(url, encoding="utf-8")
                    drop_ok = True
                except Exception as exc:
                    drop_ok = False
                    drop_err = str(exc)
                _append_effector(
                    {
                        "action": "browser_handoff",
                        "target": url,
                        "ok": drop_ok,
                        "truth_note": (
                            "VLC.app missing — wrote alice_browser_open_url.txt for Alice Browser"
                            if drop_ok
                            else f"VLC.app missing — drop file write failed: {drop_err}"
                        ),
                    }
                )
                try:
                    deposit(
                        "stigmergic_vlc_bridge",
                        f"BROWSER_HANDOFF ok={drop_ok} target={url}",
                        kind="message",
                        meta={
                            "effector_row_hint": str(uuid.uuid4()),
                            "homeworld_serial": owner_silicon(),
                            "handoff_reason": "vlc_missing",
                        },
                    )
                except Exception:
                    pass
                self._refresh_recent()
                if drop_ok:
                    self._status.setText(
                        "VLC missing — URL queued for Alice Browser. "
                        "Open Alice Browser from Programs to watch. "
                        f"Target: {url[:55]}"
                    )
                else:
                    QMessageBox.warning(
                        self,
                        "Handoff failed",
                        "VLC not installed and the Alice Browser drop file could not be written.\n"
                        "Open Alice Browser manually and paste the URL there.",
                    )
                return drop_ok
            # ── Non-URL targets (local files) — VLC required ─────────────────
            _append_effector(
                {
                    "action": "vlc_launch",
                    "target": target_str,
                    "ok": False,
                    "truth_note": "VLC.app missing — local file playback requires VLC",
                }
            )
            QMessageBox.warning(
                self,
                "VLC missing",
                "Install VLC to /Applications/VLC.app to play local files.\n"
                "Web/YouTube URLs open automatically in Alice Browser when VLC is missing.",
            )
            self._refresh_recent()
            return False

        # macOS: open a new VLC instance and pass media paths/URLs as trailing args.
        argv = ["open", "-n", "-a", str(vlc), *targets]

        try:
            proc = subprocess.run(argv, capture_output=True, text=True, timeout=30)
            ok = proc.returncode == 0
            _append_effector(
                {
                    "action": "vlc_launch",
                    "target": " ".join(targets) if targets else "(blank)",
                    "ok": ok,
                    "argv": argv,
                    "returncode": proc.returncode,
                    "stderr_tail": (proc.stderr or "")[-400:],
                    "truth_note": "subprocess open -n -a VLC.app",
                }
            )
        except Exception as exc:
            ok = False
            _append_effector(
                {
                    "action": "vlc_launch",
                    "target": " ".join(targets) if targets else "(blank)",
                    "ok": False,
                    "argv": argv,
                    "truth_note": f"exception: {type(exc).__name__}: {exc}",
                }
            )
        try:
            deposit(
                "stigmergic_vlc_bridge",
                f"VLC_HANDOFF ok={ok} target={targets[0] if targets else '(blank)'}",
                kind="message",
                meta={
                    "effector_row_hint": str(uuid.uuid4()),
                    "homeworld_serial": owner_silicon(),
                },
            )
        except Exception:
            pass
        self._refresh_recent()
        if not ok:
            QMessageBox.warning(self, "VLC launch", "Launch failed; see effector tail for stderr.")
        return ok

    def _pick_open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open in VLC",
            str(Path.home()),
            "Media files (*.mp4 *.mkv *.mov *.m4v *.webm *.mp3 *.wav *.aac *.flac);;All files (*)",
        )
        if not path:
            return
        self._run_open_vlc(path)

    def _play_url(self) -> None:
        raw = self._url.text().strip()
        if not raw:
            QMessageBox.information(self, "URL", "Enter a stream URL or file path first.")
            return
        self._run_open_vlc(raw)

    def _launch_blank(self) -> None:
        self._run_open_vlc()


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    w = StigmergicVlcBridge()
    w.setWindowTitle("Stigmergic VLC Bridge")
    w.resize(620, 520)
    w.show()
    sys.exit(app.exec())
