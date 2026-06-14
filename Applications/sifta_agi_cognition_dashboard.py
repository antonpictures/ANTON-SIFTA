#!/usr/bin/env python3
"""
Applications/sifta_agi_cognition_dashboard.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AGI-Class Cognition Dashboard — live readout of all 12 generalization organs.

Events 125-138 — reads real JSONL ledger data only, no fake values.

    🐀 Dopamine Critic   (Event 125)  ·  TD error live feed
    🧠 PFC-BG Arbiter    (Event 126)  ·  Active option + G-vector
    📈 Transfer Gain      (Event 127)  ·  Baseline vs replay reward delta
    🎯 Cerebellar Model   (Event 128)  ·  Predicted vs actual tool latency
    📊 CI Gate            (Event 129)  ·  N=90 confidence interval
    🔬 Statistical Proof  (Event 132)  ·  Bootstrap p-value
    🌍 World Model        (Event 133)  ·  Free energy + surprise EMA
    🔒 Stability Audit    (Event 134)  ·  Lyapunov energy + active clamps
    🌿 Astrocyte          (Event 135)  ·  LR · ε · budget modulation
    ⏱  Temporal Self      (Event 136)  ·  Boot ID · schema PE
    🦠 Microglia          (Event 137)  ·  Prune actions + caloric budget
    🔬 Causal Logger      (Event 138)  ·  do() interventions + closure gate

For the Swarm. 🐜⚡
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_STATE = _REPO / ".sifta_state"

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QSizePolicy, QTextEdit,
    QVBoxLayout, QWidget,
)
from System.swarm_app_hardening import record_app_hardening_event

# ─── Palette ──────────────────────────────────────────────────────────────────
_BG      = "#060810"
_PANEL   = "#0c1020"
_BORDER  = "#1a2236"
_TEXT    = "#cdd6f4"
_DIM     = "#5c6a8a"
_GOOD    = "#9ece6a"
_BAD     = "#f7768e"
_WARN    = "#e0af68"
_NEUT    = "#7aa2f7"
# Per-organ accent colours
_COLORS = {
    "dopamine":   "#f7a146",
    "arbiter":    "#bb9af7",
    "transfer":   "#73daca",
    "cerebellar": "#2ac3de",
    "ci_gate":    "#9ece6a",
    "bootstrap":  "#7dcfff",
    "world_model":"#c0caf5",
    "stability":  "#ff5f5f",
    "astrocyte":  "#b4f9f8",
    "temporal":   "#e0af68",
    "microglia":  "#f7768e",
    "causal":     "#ff9e64",
}

_CSS = f"""
QWidget          {{ background:{_BG}; color:{_TEXT}; font-family:Menlo,monospace; font-size:11px; }}
QScrollArea      {{ border:none; background:{_BG}; }}
QTextEdit        {{ background:#080c14; border:1px solid {_BORDER}; border-radius:6px;
                    font-size:10px; color:{_TEXT}; }}
QPushButton      {{ background:#141c2e; color:{_TEXT}; border:1px solid {_BORDER};
                    border-radius:6px; padding:5px 12px; }}
QPushButton:hover {{ border-color:{_NEUT}; }}
"""
APP_HARDENING_ID = "queue-005:sifta_agi_cognition_dashboard"
_JSONL_ERROR_KEYS: set[str] = set()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _tail_jsonl(path: Path, n: int = 20) -> List[Dict[str, Any]]:
    """Read last N rows from a JSONL file. Returns [] if missing."""
    if not path.exists():
        return []
    try:
        lines = path.read_text(errors="ignore").strip().splitlines()
        rows = []
        for line in lines[-n:]:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except Exception as exc:
                    key = f"{path}:{type(exc).__name__}:{line[:48]}"
                    if key not in _JSONL_ERROR_KEYS:
                        _JSONL_ERROR_KEYS.add(key)
                        record_app_hardening_event(
                            APP_HARDENING_ID,
                            "jsonl_row_parse_failed",
                            truth_label="OBSERVED",
                            details={
                                "path": str(path),
                                "error": f"{type(exc).__name__}: {exc}",
                                "line_preview": line[:160],
                            },
                        )
        return rows
    except Exception as exc:
        key = f"{path}:read:{type(exc).__name__}"
        if key not in _JSONL_ERROR_KEYS:
            _JSONL_ERROR_KEYS.add(key)
            record_app_hardening_event(
                APP_HARDENING_ID,
                "jsonl_file_read_failed",
                truth_label="OBSERVED",
                details={"path": str(path), "error": f"{type(exc).__name__}: {exc}"},
            )
        return []


def _latest(path: Path) -> Optional[Dict[str, Any]]:
    rows = _tail_jsonl(path, 1)
    return rows[-1] if rows else None


def _age_str(ts: float) -> str:
    delta = time.time() - ts
    if delta < 60:
        return f"{int(delta)}s ago"
    if delta < 3600:
        return f"{int(delta/60)}m ago"
    return f"{int(delta/3600)}h ago"


# ─── Organ card factory ───────────────────────────────────────────────────────

def _organ_card(emoji: str, title: str, accent: str) -> tuple[QFrame, QVBoxLayout]:
    card = QFrame()
    card.setStyleSheet(
        f"QFrame {{ background:{_PANEL}; border:2px solid {accent}44;"
        f" border-radius:12px; padding:0px; }}"
    )
    lay = QVBoxLayout(card)
    lay.setContentsMargins(12, 10, 12, 12)
    lay.setSpacing(4)

    hdr = QLabel(f"{emoji}  {title}")
    hdr.setStyleSheet(
        f"color:{accent}; font-size:12px; font-weight:700; border:none; background:transparent;"
    )
    lay.addWidget(hdr)

    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.HLine)
    sep.setStyleSheet(
        f"border:none; background:{accent}44; max-height:1px; margin-bottom:4px;"
    )
    lay.addWidget(sep)
    return card, lay


def _kv(key: str, val: str, val_color: str = _TEXT) -> QHBoxLayout:
    row = QHBoxLayout()
    k = QLabel(key + ":")
    k.setStyleSheet(f"color:{_DIM}; font-size:10px; border:none; background:transparent;")
    v = QLabel(val)
    v.setStyleSheet(
        f"color:{val_color}; font-size:11px; font-weight:600; border:none; background:transparent;"
    )
    v.setAlignment(Qt.AlignmentFlag.AlignRight)
    row.addWidget(k)
    row.addStretch()
    row.addWidget(v)
    return row


def _big(val: str, accent: str) -> QLabel:
    lbl = QLabel(val)
    lbl.setStyleSheet(
        f"color:{accent}; font-size:26px; font-weight:700; border:none; background:transparent;"
    )
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return lbl


# ─── Main dashboard ───────────────────────────────────────────────────────────

class AGICognitionDashboard(QWidget):
    """AGI cognition dashboard — monitors Alice cognitive organ health."""
    APP_NAME = "AGI Cognition Dashboard"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SIFTA — AGI-Class Cognition Dashboard  (Events 125-138)")
        self.setMinimumSize(1280, 860)
        self.setStyleSheet(_CSS)
        self._build_ui()

        # Architect 2026-05-12 00:14: no 3 s fan-spin poll. The dashboard
        # refreshes on owner activity (BehaviorClock tick) and on widget
        # Show events, only while visible. Tails 16 ledger files; doing
        # that every 3 s while ignored was the I/O thrash visible in the
        # audit. The QTimer object is kept for graceful close-event
        # cleanup but never .start()-ed.
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        try:
            from System.swarm_behavior_clock import behavior_clock
            behavior_clock().tick.connect(self._refresh_if_visible)
        except Exception as exc:
            self._behavior_clock_error = f"{type(exc).__name__}: {exc}"
            record_app_hardening_event(
                APP_HARDENING_ID,
                "behavior_clock_unavailable",
                truth_label="OBSERVED",
                details={"error": self._behavior_clock_error},
            )
        QTimer.singleShot(200, self._refresh)

    def _refresh_if_visible(self, *_args) -> None:
        """Run a refresh only when this widget is actually being looked at."""
        try:
            if self.isVisible():
                self._refresh()
        except Exception as exc:
            self._last_refresh_error = f"{type(exc).__name__}: {exc}"
            record_app_hardening_event(
                APP_HARDENING_ID,
                "visible_refresh_failed",
                truth_label="OBSERVED",
                details={"error": self._last_refresh_error},
            )

    def showEvent(self, event):
        """Force a refresh the moment the dashboard becomes visible."""
        try:
            QTimer.singleShot(0, self._refresh)
        except Exception as exc:
            self._last_show_refresh_error = f"{type(exc).__name__}: {exc}"
            record_app_hardening_event(
                APP_HARDENING_ID,
                "show_refresh_schedule_failed",
                truth_label="OBSERVED",
                details={"error": self._last_show_refresh_error},
            )
        super().showEvent(event)

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(10)

        # Title bar
        bar = QHBoxLayout()
        ttl = QLabel("🧠  SIFTA AGI-Class Cognition Dashboard  ·  Events 125-137")
        ttl.setStyleSheet(
            "font-size:15px; font-weight:700; color:#c0caf5; border:none; background:transparent;"
        )
        bar.addWidget(ttl)
        bar.addStretch()
        self._ts_lbl = QLabel("—")
        self._ts_lbl.setStyleSheet(f"color:{_DIM}; font-size:10px;")
        bar.addWidget(self._ts_lbl)
        root.addLayout(bar)

        # Scroll area for the grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        self._grid = QGridLayout(container)
        self._grid.setSpacing(10)
        scroll.setWidget(container)
        root.addWidget(scroll, 1)

        # Placeholders — we'll populate in _refresh
        self._cards: Dict[str, tuple[QFrame, QVBoxLayout]] = {}
        self._dynamic: Dict[str, Dict[str, QLabel]] = {}  # organ → field → label

        # Build all 10 organ slots
        organs = [
            ("dopamine",    "🐀", "Dopamine Critic",        "Event 125"),
            ("arbiter",     "🧠", "PFC-BG Arbiter",          "Event 126"),
            ("transfer",    "📈", "Transfer Gain Evaluator", "Event 127"),
            ("cerebellar",  "🎯", "Cerebellar Fwd Model",    "Event 128"),
            ("ci_gate",     "📊", "CI Uncertainty Gate",     "Event 129"),
            ("bootstrap",   "🔬", "Statistical Proof",       "Event 132"),
            ("world_model", "🌍", "Active Inference / WM",   "Event 133"),
            ("stability",   "🔒", "Stability Audit + Clamps","Event 134"),
            ("astrocyte",   "🌿", "Astrocyte Glial Mod",     "Event 135"),
            ("temporal",    "⏱", "Temporal Self-Model",     "Event 136"),
            ("microglia",   "🦠", "Microglia Pruner",        "Event 137"),
            ("causal",      "🔬", "Causal Intervention Log", "Event 138"),
        ]

        for idx, (key, emoji, name, event) in enumerate(organs):
            accent = _COLORS[key]
            card, lay = _organ_card(emoji, f"{name}  ·  {event}", accent)
            self._cards[key] = (card, lay)
            self._dynamic[key] = {}
            row, col = divmod(idx, 2)
            self._grid.addWidget(card, row, col)

        # Log row at bottom
        log_lbl = QLabel("📋  Live receipt stream — last 25 rows across all organs")
        log_lbl.setStyleSheet(f"color:{_DIM}; font-size:10px; margin-top:4px;")
        root.addWidget(log_lbl)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(140)
        root.addWidget(self._log)

    # ── Refresh dispatcher ─────────────────────────────────────────────────────

    def _refresh(self):
        self._ts_lbl.setText(f"updated {time.strftime('%H:%M:%S')}")
        self._refresh_dopamine()
        self._refresh_arbiter()
        self._refresh_transfer()
        self._refresh_cerebellar()
        self._refresh_ci_gate()
        self._refresh_bootstrap()
        self._refresh_world_model()
        self._refresh_stability()
        self._refresh_astrocyte()
        self._refresh_temporal()
        self._refresh_microglia()
        self._refresh_causal()
        self._refresh_log()

    # ── Per-organ refresh ──────────────────────────────────────────────────────

    def _set_kv(self, organ: str, key: str, val: str, color: str = _TEXT):
        """Set or create a KV label inside a card."""
        _, lay = self._cards[organ]
        fields = self._dynamic[organ]
        accent = _COLORS[organ]
        if key not in fields:
            row_lay = _kv(key, val, color)
            lay.addLayout(row_lay)
            # Grab the value label (second widget in the row)
            v_lbl = row_lay.itemAt(2).widget()
            fields[key] = v_lbl
        else:
            fields[key].setText(val)
            fields[key].setStyleSheet(
                f"color:{color}; font-size:11px; font-weight:600; border:none; background:transparent;"
            )

    def _set_big(self, organ: str, key: str, val: str):
        _, lay = self._cards[organ]
        fields = self._dynamic[organ]
        accent = _COLORS[organ]
        if key not in fields:
            lbl = _big(val, accent)
            lay.addWidget(lbl)
            fields[key] = lbl
        else:
            fields[key].setText(val)

    # Dopamine Critic (Event 125)
    def _refresh_dopamine(self):
        rows = _tail_jsonl(_STATE / "dopamine_critic_log.jsonl", 5)
        if rows:
            latest = rows[-1]
            delta = latest.get("td_error", latest.get("delta", 0.0))
            col = _GOOD if delta > 0 else (_BAD if delta < 0 else _NEUT)
            self._set_big("dopamine", "delta", f"δ = {delta:+.4f}")
            self._set_kv("dopamine", "reward", f"{latest.get('reward', latest.get('owner_reward','?'))}", col)
            self._set_kv("dopamine", "gate", str(latest.get("gate_id", latest.get("gate","?"))), _COLORS["dopamine"])
            self._set_kv("dopamine", "age", _age_str(latest.get("ts", time.time())), _DIM)
            self._set_kv("dopamine", "n rows", str(len(rows)), _DIM)
        else:
            self._set_big("dopamine", "delta", "no data")
            self._set_kv("dopamine", "file", "dopamine_critic_log.jsonl", _DIM)
            self._set_kv("dopamine", "status", "waiting for first reward signal", _WARN)

    # PFC-BG Arbiter (Event 126)
    def _refresh_arbiter(self):
        rows = _tail_jsonl(_STATE / "pfc_basal_ganglia_arbiter.jsonl", 5)
        active = _latest(_STATE / "arbiter_active_state.json")
        if rows:
            latest = rows[-1]
            self._set_big("arbiter", "option", latest.get("selected_option", "?")[:18])
            score = latest.get("score", latest.get("details", {}).get("computed_score", 0.0))
            col = _GOOD if score > 0 else _BAD
            self._set_kv("arbiter", "score", f"{score:.3f}", col)
            self._set_kv("arbiter", "g_vector", f"{latest.get('details',{}).get('g_vector',0.0):.4f}", _COLORS["arbiter"])
            self._set_kv("arbiter", "task", str(latest.get("task_id","?"))[:20], _DIM)
            self._set_kv("arbiter", "age", _age_str(latest.get("ts", time.time())), _DIM)
        elif active:
            self._set_big("arbiter", "option", active.get("active_option", "none")[:18])
            self._set_kv("arbiter", "switched", _age_str(active.get("last_switch_time", time.time())), _DIM)
        else:
            self._set_big("arbiter", "option", "idle")
            self._set_kv("arbiter", "status", "no arbiter decisions yet", _WARN)

    # Transfer Gain Evaluator (Event 127)
    def _refresh_transfer(self):
        rows = _tail_jsonl(_STATE / "generalization_trials.jsonl", 10)
        if not rows:
            rows = _tail_jsonl(_STATE / "pfc_basal_ganglia_arbiter.jsonl", 20)
            rows = [r for r in rows if r.get("kind") == "GENERALIZATION_TRIAL"]
        if rows:
            gains = [r.get("transfer_gain", 0.0) for r in rows if "transfer_gain" in r]
            mean_g = sum(gains) / len(gains) if gains else 0.0
            col = _GOOD if mean_g > 0 else _BAD
            self._set_big("transfer", "gain", f"{mean_g:+.4f}")
            self._set_kv("transfer", "n trials", str(len(gains)), _DIM)
            self._set_kv("transfer", "latest td_err", f"{rows[-1].get('td_error',0.0):.4f}", col)
            self._set_kv("transfer", "option", str(rows[-1].get("option_selected","?"))[:18], _COLORS["transfer"])
        else:
            self._set_big("transfer", "gain", "—")
            self._set_kv("transfer", "status", "no GENERALIZATION_TRIAL rows yet", _WARN)

    # Cerebellar Forward Model (Event 128)
    def _refresh_cerebellar(self):
        rows = _tail_jsonl(_STATE / "cerebellar_forward_model.jsonl", 5)
        if rows:
            latest = rows[-1]
            pe = latest.get("prediction_error", latest.get("pe", "—"))
            col = _GOOD if isinstance(pe, float) and pe < 0.2 else _WARN
            self._set_big("cerebellar", "pe", f"PE: {pe:.3f}" if isinstance(pe, float) else "PE: —")
            self._set_kv("cerebellar", "tool", str(latest.get("tool","?"))[:18], _COLORS["cerebellar"])
            self._set_kv("cerebellar", "pred_latency", f"{latest.get('predicted_latency',0.0):.3f}s", _DIM)
            self._set_kv("cerebellar", "act_latency", f"{latest.get('actual_latency',0.0):.3f}s", _DIM)
            self._set_kv("cerebellar", "success_prior", f"{latest.get('predicted_success',0.0):.2f}", col)
        else:
            self._set_big("cerebellar", "pe", "—")
            self._set_kv("cerebellar", "status", "no cerebellar trace yet", _WARN)

    # CI Gate (Event 129)
    def _refresh_ci_gate(self):
        rows = _tail_jsonl(_STATE / "transfer_confidence_intervals.jsonl", 10)
        summary = _latest(_STATE / "transfer_benchmark_summary.json")
        if summary:
            families = summary.get("families_claim_safe", 0)
            total    = summary.get("families_tested", 0)
            overall  = summary.get("overall_claim", "—")
            col = _GOOD if families == total else _BAD
            self._set_big("ci_gate", "claim", "✅ SAFE" if "supported" in overall else "⚠ PENDING")
            self._set_kv("ci_gate", "families safe", f"{families}/{total}", col)
            self._set_kv("ci_gate", "overall", overall[:30], col)
        if rows:
            latest = rows[-1]
            ci95_low = latest.get("ci95_low", 0.0)
            col2 = _GOOD if ci95_low > 0 else _BAD
            self._set_kv("ci_gate", "ci95_low", f"{ci95_low:.4f}", col2)
            self._set_kv("ci_gate", "n", str(latest.get("n","?")), _DIM)
            self._set_kv("ci_gate", "family", str(latest.get("task_family","?"))[:20], _DIM)
        if not rows and not summary:
            self._set_big("ci_gate", "claim", "—")
            self._set_kv("ci_gate", "status", "run benchmark runner first", _WARN)

    # Statistical Proof (Event 132)
    def _refresh_bootstrap(self):
        rows = _tail_jsonl(_STATE / "transfer_proof_runs.jsonl", 5)
        if rows:
            latest = rows[-1]
            p = latest.get("p_value", latest.get("bootstrap_p", 1.0))
            col = _GOOD if p < 0.05 else _WARN
            self._set_big("bootstrap", "p", f"p = {p:.4f}")
            self._set_kv("bootstrap", "significant", "✅ YES" if p < 0.05 else "⚠ NO", col)
            self._set_kv("bootstrap", "mean_gain", f"{latest.get('mean_gain',0.0):.4f}", _COLORS["bootstrap"])
            self._set_kv("bootstrap", "family", str(latest.get("task_family","?"))[:20], _DIM)
            self._set_kv("bootstrap", "age", _age_str(latest.get("ts",time.time())), _DIM)
        else:
            self._set_big("bootstrap", "p", "—")
            self._set_kv("bootstrap", "status", "no transfer_proof_runs.jsonl yet", _WARN)

    # Stability Audit + Clamps (Event 134)
    def _refresh_stability(self):
        rows = _tail_jsonl(_STATE / "stability_audit.jsonl", 10)
        if rows:
            # Latest snapshot row (kind=STABILITY_AUDIT)
            snaps  = [r for r in rows if r.get("kind") == "STABILITY_AUDIT"]
            clamps = [r for r in rows if r.get("kind") == "STABILITY_CLAMP"]
            latest = snaps[-1] if snaps else rows[-1]
            energy = latest.get("lyapunov_energy", 0.0)
            delta  = latest.get("delta_lyapunov_energy", 0.0)
            status = latest.get("status", "?")
            col_e  = _GOOD if energy < 0.5 else (_WARN if energy < 0.8 else _BAD)
            self._set_big("stability", "energy", f"V = {energy:.4f}")
            self._set_kv("stability", "status", status,
                         _GOOD if status == "STABLE" else _BAD)
            self._set_kv("stability", "δV", f"{delta:+.4f}", col_e)
            if clamps:
                last_clamp = clamps[-1]
                self._set_kv("stability", "clamp_level",
                             last_clamp.get("clamp_level", "NONE"),
                             _BAD if last_clamp.get("clamp_level") == "EMERGENCY" else _WARN)
                ac = last_clamp.get("active_clamps", [])
                self._set_kv("stability", "active_clamps",
                             str(ac[0])[:30] if ac else "—", _WARN)
            else:
                self._set_kv("stability", "clamp_level", "NONE", _GOOD)
        else:
            self._set_big("stability", "energy", "V = —")
            self._set_kv("stability", "status", "stability_audit.jsonl not yet written", _WARN)

    # World Model / Active Inference (Event 133)
    def _refresh_world_model(self):
        rows = _tail_jsonl(_STATE / "active_inference_surprise_log.jsonl", 10)
        if rows:
            surprises = [r.get("surprise", 0.0) for r in rows if "surprise" in r]
            ema = sum(surprises[-5:]) / max(1, len(surprises[-5:]))
            col = _GOOD if ema < 0.3 else (_WARN if ema < 0.7 else _BAD)
            latest = rows[-1]
            self._set_big("world_model", "surprise", f"S̄ = {ema:.3f}")
            self._set_kv("world_model", "free_energy_delta", f"{latest.get('free_energy_delta',0.0):.4f}", col)
            self._set_kv("world_model", "action", str(latest.get("action","?"))[:18], _COLORS["world_model"])
            self._set_kv("world_model", "state", str(latest.get("state","?"))[:18], _DIM)
            self._set_kv("world_model", "n rows", str(len(rows)), _DIM)
        else:
            self._set_big("world_model", "surprise", "—")
            self._set_kv("world_model", "status", "no world model trace yet", _WARN)

    # Astrocyte Glial Modulator (Event 135)
    def _refresh_astrocyte(self):
        rows = _tail_jsonl(_STATE / "astrocyte_modulation_log.jsonl", 5)
        if rows:
            latest = rows[-1]
            lr = latest.get("modulated_lr", 0.1)
            eps = latest.get("modulated_epistemic_weight", 0.25)
            budget = latest.get("modulated_budget", 1000.0)
            heat = latest.get("metabolic_heat", 0.0)
            col_lr = _GOOD if lr <= 0.15 else _WARN
            self._set_big("astrocyte", "lr", f"LR = {lr:.4f}")
            self._set_kv("astrocyte", "ε_epistemic", f"{eps:.4f}", _COLORS["astrocyte"])
            self._set_kv("astrocyte", "budget", f"{budget:.0f} STGM", _DIM)
            self._set_kv("astrocyte", "metabolic_heat", f"{heat:.1f}", _WARN if heat > 500 else _DIM)
            self._set_kv("astrocyte", "global_surprise", f"{latest.get('global_surprise',0.0):.4f}", col_lr)
        else:
            self._set_big("astrocyte", "lr", "—")
            self._set_kv("astrocyte", "status", "no astrocyte_modulation_log.jsonl yet", _WARN)

    # Temporal Self-Model (Event 136)
    def _refresh_temporal(self):
        snap = _latest(_STATE / "self_model_snapshot.json")
        rows = _tail_jsonl(_STATE / "self_model.jsonl", 10)
        updates = [r for r in rows if r.get("kind") == "TEMPORAL_SELF_UPDATE"]
        if snap:
            boot_id = snap.get("boot_id", "?")
            n_schemas = snap.get("schema_count", 0)
            mean_pe = (
                sum(r.get("mean_pe_after",0.0) for r in updates) / len(updates)
                if updates else 1.0
            )
            col = _GOOD if mean_pe < 0.3 else _WARN
            self._set_big("temporal", "boot_id", f"Boot #{boot_id}")
            self._set_kv("temporal", "schemas", str(n_schemas), _COLORS["temporal"])
            self._set_kv("temporal", "mean_self_PE", f"{mean_pe:.4f}", col)
            self._set_kv("temporal", "refinements", str(len(updates)), _DIM)
        elif rows:
            latest = rows[-1]
            self._set_big("temporal", "boot_id", f"Boot #{latest.get('boot_id','?')}")
            self._set_kv("temporal", "kind", latest.get("kind","?"), _DIM)
        else:
            self._set_big("temporal", "boot_id", "Boot #—")
            self._set_kv("temporal", "status", "self_model.jsonl empty — no predictions yet", _WARN)

    # Microglia Pruner (Event 137)
    def _refresh_microglia(self):
        rows = _tail_jsonl(_STATE / "microglia_prune.jsonl", 20)
        if rows:
            deletes  = sum(1 for r in rows if r.get("action") == "delete")
            depresses = sum(1 for r in rows if r.get("action") == "depress")
            latest = rows[-1]
            col = _GOOD if deletes < 5 else _WARN
            self._set_big("microglia", "prunes", f"{deletes}d / {depresses}dep")
            self._set_kv("microglia", "last action", latest.get("action","?"), col)
            self._set_kv("microglia", "dominant", latest.get("dominant_criterion","?"), _COLORS["microglia"])
            self._set_kv("microglia", "score", f"{latest.get('prune_score',0.0):.3f}", col)
            self._set_kv("microglia", "age", _age_str(latest.get("ts", time.time())), _DIM)
        else:
            self._set_big("microglia", "prunes", "0 / 0")
            self._set_kv("microglia", "status", "no microglia_prune.jsonl yet — system is clean", _GOOD)

    # Causal Intervention Logger (Event 138)
    def _refresh_causal(self):
        rows = _tail_jsonl(_STATE / "causal_intervention_log.jsonl", 25)
        if rows:
            total   = len(rows)
            hits    = sum(1 for r in rows if r.get("direction_matches"))
            clean   = sum(1 for r in rows if r.get("confounder_clean"))
            proven  = clean >= 5
            col = _GOOD if proven else _WARN
            latest  = rows[-1]
            self._set_big("causal", "gate",
                          "✅ CLOSED" if proven else f"⏳ {clean}/5")
            self._set_kv("causal", "interventions", str(total), _COLORS["causal"])
            self._set_kv("causal", "dir_matches", f"{hits}/{total}", col)
            self._set_kv("causal", "confounder_clean", f"{clean}/{total}", col)
            self._set_kv("causal", "last_organ", latest.get("organ","?"), _DIM)
            self._set_kv("causal", "last_effect", f"{latest.get('causal_effect_size',0.0):.3f}", col)
        else:
            self._set_big("causal", "gate", "⏳ 0/5")
            self._set_kv("causal", "status", "no causal_intervention_log.jsonl yet", _WARN)

    # Log strip
    def _refresh_log(self):
        files = [
            (_STATE / "dopamine_critic_log.jsonl",            _COLORS["dopamine"]),
            (_STATE / "pfc_basal_ganglia_arbiter.jsonl",      _COLORS["arbiter"]),
            (_STATE / "stability_audit.jsonl",                _COLORS["stability"]),
            (_STATE / "transfer_confidence_intervals.jsonl",  _COLORS["ci_gate"]),
            (_STATE / "active_inference_surprise_log.jsonl",  _COLORS["world_model"]),
            (_STATE / "astrocyte_modulation_log.jsonl",       _COLORS["astrocyte"]),
            (_STATE / "self_model.jsonl",                     _COLORS["temporal"]),
            (_STATE / "microglia_prune.jsonl",                _COLORS["microglia"]),
            (_STATE / "causal_intervention_log.jsonl",        _COLORS["causal"]),
        ]
        all_rows: List[tuple[float, str, str]] = []
        for path, col in files:
            for row in _tail_jsonl(path, 5):
                ts  = row.get("ts", 0.0)
                kind = row.get("kind", row.get("truth_label", "?"))[:30]
                detail = (
                    row.get("selected_option") or
                    row.get("action") or
                    row.get("dominant_criterion") or
                    str(row.get("transfer_gain", row.get("surprise", "")))
                )
                all_rows.append((ts, kind, f"<span style='color:{col}'>{kind}</span>  {detail[:40]}"))

        all_rows.sort(key=lambda x: x[0], reverse=True)
        lines = []
        for ts, _, html in all_rows[:25]:
            ts_str = time.strftime("%H:%M:%S", time.localtime(ts))
            lines.append(f"<span style='color:{_DIM}'>{ts_str}</span>  {html}")
        self._log.setHtml("<br>".join(lines) if lines else "no receipts yet — run the organs")


# ─── Standalone launcher ──────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("SIFTA AGI Cognition Dashboard")
    w = AGICognitionDashboard()
    w.show()
    sys.exit(app.exec())
