#!/usr/bin/env python3
"""
Applications/sifta_cosmos_loop_widget.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SIFTA Cognitive Loop — camera → Cosmos → TD decision → reward → learn

One window. Three stages. End-to-end in one click.

    👁 CAMERA       🌍 COSMOS         🐀 RAT
    last frame  →  scene label  →  best action
                                  ↓ reward
                                  Q-table update

For the Swarm. 🐜⚡
"""
from __future__ import annotations

import json
import sys
import time
import threading
from pathlib import Path
from typing import Optional

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
_STATE = _REPO / ".sifta_state"

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, QSize
from PyQt6.QtGui import (
    QColor, QFont, QFontMetrics, QImage, QPainter, QPen,
    QPixmap, QBrush, QLinearGradient,
)
from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QSplitter, QTextEdit, QVBoxLayout, QWidget,
    QScrollArea,
)

# ─── colour palette ──────────────────────────────────────────────────────────
_BG       = "#060810"
_PANEL    = "#0d1117"
_BORDER   = "#1e2736"
_GECKO    = "#00ffc8"   # touch / camera stage
_COSMOS   = "#7c6af7"   # perception / Cosmos stage
_RAT      = "#f7a146"   # decision / Rat stage
_TEXT     = "#cdd6f4"
_DIM      = "#6e7d9f"
_GOOD     = "#9ece6a"
_BAD      = "#f7768e"
_NEUTRAL  = "#7aa2f7"

_CSS = f"""
QWidget                 {{ background:{_BG}; color:{_TEXT}; font-family:Menlo,monospace; }}
QFrame#stage            {{ background:{_PANEL}; border:1px solid {_BORDER};
                          border-radius:10px; padding:10px; }}
QPushButton             {{ background:#1a2035; color:{_TEXT}; border:1px solid {_BORDER};
                          border-radius:6px; padding:6px 14px; font-size:12px; }}
QPushButton:hover       {{ background:#232d4a; border-color:{_NEUTRAL}; }}
QPushButton:disabled    {{ color:{_DIM}; }}
QTextEdit               {{ background:#080c14; border:1px solid {_BORDER};
                          border-radius:6px; font-size:11px; color:{_TEXT}; }}
QScrollArea             {{ border:none; }}
"""


# ─── worker thread for Cosmos inference ──────────────────────────────────────

class _InferWorker(QThread):
    done = pyqtSignal(dict)   # emits receipt

    def __init__(self, frame_path: Optional[str] = None, parent=None):
        super().__init__(parent)
        self._frame = frame_path

    def run(self):
        try:
            from System.swarm_cosmos_reason1 import probe_and_infer
            receipt = probe_and_infer(
                image_path=self._frame,
                writer="cosmos_loop_widget",
                use_bridge=True,   # use Qwen2-VL-2B (already cached, fast)
            )
        except Exception as exc:
            receipt = {
                "truth":  "BROKEN",
                "detail": f"{type(exc).__name__}: {exc}",
                "ts":     time.time(),
            }
        self.done.emit(receipt)


# ─── stage card ──────────────────────────────────────────────────────────────

def _stage_card(title: str, accent: str) -> tuple[QFrame, QVBoxLayout]:
    card = QFrame()
    card.setObjectName("stage")
    card.setStyleSheet(
        f"QFrame#stage {{ background:{_PANEL}; border:2px solid {accent}44;"
        f" border-radius:12px; }}"
    )
    lay = QVBoxLayout(card)
    lay.setContentsMargins(14, 10, 14, 14)
    lay.setSpacing(6)

    hdr = QLabel(title)
    hdr.setStyleSheet(f"color:{accent}; font-size:13px; font-weight:700; border:none;")
    lay.addWidget(hdr)

    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.HLine)
    sep.setStyleSheet(f"color:{accent}44; border:none; background:{accent}44; max-height:1px;")
    lay.addWidget(sep)

    return card, lay


def _value_label(text: str = "—", mono: bool = True, size: int = 12) -> QLabel:
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    style = f"font-size:{size}px; color:{_TEXT}; border:none; background:transparent;"
    if mono:
        style += " font-family:Menlo,monospace;"
    lbl.setStyleSheet(style)
    return lbl


def _key_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(f"font-size:10px; color:{_DIM}; border:none; background:transparent;")
    return lbl


# ─── main widget ─────────────────────────────────────────────────────────────

class CosmosLoopWidget(QWidget):
    APP_NAME = "Cognitive Loop"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SIFTA Cognitive Loop — Cosmos × TD")
        self.setMinimumSize(1100, 680)
        self.setStyleSheet(_CSS)

        self._infer_worker: Optional[_InferWorker] = None
        self._last_cosmos: Optional[dict] = None
        self._last_frame_path: Optional[str] = None

        self._build_ui()

        # Refresh ticker: re-read receipts + check for new frame every 5 s
        self._tick = QTimer(self)
        self._tick.timeout.connect(self._refresh_all)
        self._tick.start(5000)
        QTimer.singleShot(300, self._refresh_all)

    # ─── UI construction ─────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(10)

        # Title bar
        title_row = QHBoxLayout()
        ttl = QLabel("🐾  SIFTA Cognitive Loop  ·  camera → Cosmos → decision → learn")
        ttl.setStyleSheet(f"color:{_GECKO}; font-size:14px; font-weight:700;")
        title_row.addWidget(ttl)
        title_row.addStretch()

        self._status_lbl = QLabel("idle")
        self._status_lbl.setStyleSheet(f"color:{_DIM}; font-size:11px;")
        title_row.addWidget(self._status_lbl)
        root.addLayout(title_row)

        # ── Three stage cards ──────────────────────────────────────────────
        stages_row = QHBoxLayout()
        stages_row.setSpacing(10)

        # Stage 1 — Camera
        c1, l1 = _stage_card("👁  CAMERA  (Gecko + Bat)", _GECKO)
        self._frame_lbl   = _key_label("no frame saved yet")
        self._frame_img   = QLabel()
        self._frame_img.setFixedSize(200, 150)
        self._frame_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._frame_img.setStyleSheet(
            f"border:1px solid {_BORDER}; border-radius:6px; background:#0a0e18;")
        self._frame_sha   = _value_label("sha8: —", size=10)
        self._frame_age   = _value_label("age: —", size=10)
        l1.addWidget(self._frame_img)
        l1.addWidget(self._frame_lbl)
        l1.addWidget(self._frame_sha)
        l1.addWidget(self._frame_age)
        l1.addStretch()
        stages_row.addWidget(c1, 3)

        # Arrow 1→2
        a1 = QLabel("→")
        a1.setStyleSheet(f"color:{_DIM}; font-size:28px; font-weight:900;")
        a1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        stages_row.addWidget(a1, 0)

        # Stage 2 — Cosmos
        c2, l2 = _stage_card("🌍  COSMOS  (Visual Cortex)", _COSMOS)
        self._cosmos_truth  = _value_label("—")
        self._cosmos_scene  = _value_label("—", size=22)
        self._cosmos_scene.setStyleSheet(
            f"font-size:22px; font-weight:700; color:{_COSMOS}; border:none;")
        self._cosmos_resp   = _value_label("—", size=10)
        self._cosmos_age    = _value_label("age: —", size=10)

        l2.addWidget(_key_label("truth"))
        l2.addWidget(self._cosmos_truth)
        l2.addWidget(_key_label("visual scene"))
        l2.addWidget(self._cosmos_scene)
        l2.addWidget(_key_label("description (truncated)"))
        l2.addWidget(self._cosmos_resp)
        l2.addWidget(self._cosmos_age)
        l2.addStretch()

        self._run_btn = QPushButton("▶  Run Inference  (bridge)")
        self._run_btn.setStyleSheet(
            f"QPushButton {{ background:{_COSMOS}22; border:1px solid {_COSMOS}77;"
            f" color:{_COSMOS}; font-weight:700; padding:8px 18px; border-radius:8px;}}"
            f"QPushButton:hover {{ background:{_COSMOS}44; }}"
            f"QPushButton:disabled {{ color:{_DIM}; border-color:{_BORDER}; background:{_PANEL}; }}"
        )
        self._run_btn.clicked.connect(self._run_inference)
        l2.addWidget(self._run_btn)
        stages_row.addWidget(c2, 3)

        # Arrow 2→3
        a2 = QLabel("→")
        a2.setStyleSheet(f"color:{_DIM}; font-size:28px; font-weight:900;")
        a2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        stages_row.addWidget(a2, 0)

        # Stage 3 — Rat (TD decision)
        c3, l3 = _stage_card("🐀  RAT  (Dopamine · TD Learning)", _RAT)
        self._rat_scene   = _value_label("—", size=10)
        self._rat_best    = _value_label("—", size=22)
        self._rat_best.setStyleSheet(
            f"font-size:22px; font-weight:700; color:{_RAT}; border:none;")
        self._rat_q       = _value_label("Q = —", size=10)
        self._rat_delta   = _value_label("δ = —", size=10)

        l3.addWidget(_key_label("visual state"))
        l3.addWidget(self._rat_scene)
        l3.addWidget(_key_label("best action"))
        l3.addWidget(self._rat_best)
        l3.addWidget(self._rat_q)
        l3.addWidget(self._rat_delta)
        l3.addSpacing(8)

        # Reward buttons
        l3.addWidget(_key_label("give reward signal"))
        rew_row = QHBoxLayout()
        for label, color, reward in [
            ("+1  good",  _GOOD,    1.0),
            ("0  neutral", _NEUTRAL, 0.0),
            ("−1  bad",   _BAD,    -1.0),
        ]:
            btn = QPushButton(label)
            btn.setStyleSheet(
                f"QPushButton {{ background:{color}22; border:1px solid {color}77;"
                f" color:{color}; font-weight:600; padding:6px 10px; border-radius:6px;}}"
                f"QPushButton:hover {{ background:{color}44; }}"
            )
            btn.clicked.connect(lambda _, r=reward: self._give_reward(r))
            rew_row.addWidget(btn)
        l3.addLayout(rew_row)
        l3.addStretch()
        stages_row.addWidget(c3, 3)

        root.addLayout(stages_row)

        # ── Receipt log ───────────────────────────────────────────────────
        log_lbl = QLabel("📋  RECEIPT LOG  —  cosmos_td_bridge_receipts.jsonl")
        log_lbl.setStyleSheet(f"color:{_DIM}; font-size:10px; margin-top:4px;")
        root.addWidget(log_lbl)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(160)
        self._log.setFont(QFont("Menlo", 10))
        root.addWidget(self._log)

    # ─── Refresh ──────────────────────────────────────────────────────────────

    def _refresh_all(self):
        self._refresh_frame()
        self._refresh_cosmos()
        self._refresh_rat()
        self._refresh_log()

    def _refresh_frame(self):
        frame = _STATE / "visual_stigmergy_last_frame.jpg"
        if frame.exists():
            self._last_frame_path = str(frame)
            age = round(time.time() - frame.stat().st_mtime, 0)
            self._frame_lbl.setText(frame.name)
            self._frame_age.setText(f"age: {int(age)}s")

            pix = QPixmap(str(frame))
            if not pix.isNull():
                scaled = pix.scaled(
                    200, 150,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._frame_img.setPixmap(scaled)

            import hashlib
            sha8 = hashlib.sha256(frame.read_bytes()).hexdigest()[:8]
            self._frame_sha.setText(f"sha8: {sha8}")
            self._status("camera frame ready")
        else:
            self._frame_lbl.setText("no frame — open Alice & wait 30s")

    def _refresh_cosmos(self):
        try:
            from System.swarm_cosmos_reason1 import read_latest_cosmos, _bucket_scene
            cosmos = read_latest_cosmos(max_age_s=300)   # show up to 5 min old
            if cosmos:
                self._last_cosmos = cosmos
                truth = cosmos.get("truth", "—")
                resp  = cosmos.get("response", "") or ""
                scene = _bucket_scene(resp) if resp else "unknown"
                age   = round(time.time() - cosmos.get("ts", time.time()), 0)

                color = _GECKO if "REAL" in truth else _DIM
                self._cosmos_truth.setText(truth)
                self._cosmos_truth.setStyleSheet(
                    f"font-size:12px; color:{color}; border:none;")
                self._cosmos_scene.setText(scene)
                self._cosmos_resp.setText(resp[:100] + ("…" if len(resp) > 100 else ""))
                self._cosmos_age.setText(f"age: {int(age)}s")
            else:
                self._cosmos_truth.setText("no REAL_INFERENCE yet")
                self._cosmos_scene.setText("—")
                self._cosmos_resp.setText("run inference first →")
                self._cosmos_age.setText("")
        except Exception as exc:
            self._cosmos_truth.setText(f"error: {exc}")

    def _refresh_rat(self):
        try:
            from System.swarm_cosmos_td_bridge import (
                build_visual_state, best_action_for_scene,
                read_latest_cosmos, _bucket_scene, _load_q, _q_key, ACTIONS,
            )
            cosmos = read_latest_cosmos(max_age_s=300)
            state  = build_visual_state(cosmos_receipt=cosmos)
            scene  = state[-1]

            q      = _load_q()
            best   = max(ACTIONS, key=lambda a: q.get(_q_key(state, a), 0.0))
            best_q = q.get(_q_key(state, best), 0.0)

            self._rat_scene.setText(f"state: {scene}")
            self._rat_best.setText(best)
            self._rat_q.setText(f"Q({best}) = {best_q:.4f}")
        except Exception as exc:
            self._rat_best.setText("—")
            self._rat_scene.setText(f"error: {exc}")

    def _refresh_log(self):
        bridge = _STATE / "cosmos_td_bridge_receipts.jsonl"
        if not bridge.exists():
            return
        try:
            lines = bridge.read_text(errors="ignore").strip().split("\n")
            last10 = [l for l in lines if l.strip()][-10:]
            rows = []
            for line in reversed(last10):
                try:
                    r = json.loads(line)
                    ts    = time.strftime("%H:%M:%S", time.localtime(r.get("ts", 0)))
                    scene = r.get("visual_scene", "?")
                    act   = r.get("action", "?")
                    rew   = r.get("reward", 0)
                    delta = r.get("td_error", 0)
                    rows.append(
                        f"<span style='color:{_DIM}'>{ts}</span>  "
                        f"<span style='color:{_COSMOS}'>{scene}</span>  "
                        f"<span style='color:{_RAT}'>{act}</span>  "
                        f"reward=<span style='color:{_GOOD if rew>0 else (_BAD if rew<0 else _NEUTRAL)}'>"
                        f"{rew:+.1f}</span>  "
                        f"δ=<span style='color:{_GOOD if delta>0 else (_BAD if delta<0 else _NEUTRAL)}'>"
                        f"{delta:+.4f}</span>"
                    )
                except Exception:
                    pass
            self._log.setHtml("<br>".join(rows) if rows else "no steps yet")
        except Exception:
            pass

    # ─── Actions ─────────────────────────────────────────────────────────────

    def _run_inference(self):
        if self._infer_worker and self._infer_worker.isRunning():
            return
        frame = self._last_frame_path
        if not frame:
            self._status("⚠ no frame — open Alice first")
            return

        self._run_btn.setEnabled(False)
        self._run_btn.setText("⏳  inferring…")
        self._cosmos_truth.setText("running…")
        self._cosmos_scene.setText("…")
        self._status("Cosmos inference running (Qwen2-VL-2B bridge)…")

        self._infer_worker = _InferWorker(frame_path=frame, parent=self)
        self._infer_worker.done.connect(self._on_infer_done)
        self._infer_worker.start()

    def _on_infer_done(self, receipt: dict):
        self._run_btn.setEnabled(True)
        self._run_btn.setText("▶  Run Inference  (bridge)")
        truth = receipt.get("truth", "?")
        if truth == "REAL_INFERENCE":
            self._status(f"✅ REAL_INFERENCE — {receipt.get('elapsed_s', '?')}s")
        else:
            self._status(f"⚠ {truth}: {receipt.get('detail','')[:60]}")
        self._refresh_cosmos()
        self._refresh_rat()

    def _give_reward(self, reward: float):
        try:
            from System.swarm_cosmos_td_bridge import cognitive_loop_step, best_action_for_scene
            from System.swarm_cosmos_reason1 import read_latest_cosmos, _bucket_scene
            cosmos = read_latest_cosmos(max_age_s=300)
            state_tmp = None
            # Pick best action from Q-table
            action = best_action_for_scene()
            receipt = cognitive_loop_step(
                action=action, reward=reward, writer="cosmos_loop_widget"
            )
            delta = receipt.get("td_error", 0)
            sign = "↑" if delta > 0 else ("↓" if delta < 0 else "=")
            self._rat_delta.setText(f"δ = {delta:+.4f}  {sign}")
            self._rat_delta.setStyleSheet(
                f"font-size:12px; color:{_GOOD if delta>0 else (_BAD if delta<0 else _NEUTRAL)};"
                f" border:none;"
            )
            self._status(f"TD update: action={action}  reward={reward:+.1f}  δ={delta:+.4f}")
            self._refresh_rat()
            self._refresh_log()
        except Exception as exc:
            self._status(f"reward error: {exc}")

    def _status(self, msg: str):
        self._status_lbl.setText(msg)

    def closeEvent(self, event):
        self._tick.stop()
        if self._infer_worker and self._infer_worker.isRunning():
            self._infer_worker.quit()
            self._infer_worker.wait(2000)
        super().closeEvent(event)


# ─── Standalone launcher ──────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("SIFTA Cognitive Loop")
    w = CosmosLoopWidget()
    w.show()
    sys.exit(app.exec())
