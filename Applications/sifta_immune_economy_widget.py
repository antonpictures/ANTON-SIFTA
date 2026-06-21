#!/usr/bin/env python3
"""
Applications/sifta_immune_economy_widget.py
═══════════════════════════════════════════════════════════════════════════════
SIFTA Immune Economy — Kleiber ¾-Power STGM Monitor

A standalone macOS-native-style PyQt6 window showing:
  • Live Kleiber ¾-power session cost (from stigmergic trace)
  • Budget gate status: ALLOWED / BLOCKED / RED_CONSERVE
  • Per-action cost breakdown with rule IDs
  • Node tier table (M5 / M1 / RPi)
  • Budget threshold reference
  • Anti-double-spend status

§7.3 Body Economy Honesty: all numbers come from the live trace.
§7.5 Python-first: embedded PyQt6, no browser escape.

Manifest entry: "STGM Immune Economy" in apps_manifest.json
Truth label: IMMUNE_ECONOMY_V1
Doctor: Antigravity
Protocol: v4_PREDATOR_GATE
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QScrollArea, QTextEdit, QPushButton, QGridLayout,
    QSplitter, QProgressBar,
)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont, QColor

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_TRACE = _STATE / "ide_stigmergic_trace.jsonl"
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

try:
    from System.swarm_immune_economy_summary import (
        format_immune_event_line,
        summarize_immune_economy,
    )
except Exception:
    format_immune_event_line = None
    summarize_immune_economy = None

# ── Palette (matches SIFTA OS dark theme) ────────────────────────────────────
_BG      = "#0d0d1a"
_CARD    = "#13132b"
_ACCENT  = "#1a1a4a"
_CYAN    = "#00d2ff"
_GREEN   = "#00e676"
_AMBER   = "#ffab00"
_RED     = "#ff5252"
_PURPLE  = "#ce93d8"
_TEXT    = "#e0e0e0"
_DIM     = "#666688"

_STYLE = f"""
QWidget {{ background: {_BG}; color: {_TEXT}; font-family: 'Menlo', monospace; font-size: 12px; }}
QFrame  {{ background: {_CARD}; border: 1px solid {_ACCENT}; border-radius: 8px; }}
QLabel  {{ background: transparent; border: none; }}
QPushButton {{
    background: {_ACCENT}; color: {_CYAN}; border: 1px solid {_CYAN};
    border-radius: 4px; padding: 5px 14px; font-weight: bold; font-size: 11px;
}}
QPushButton:hover {{ background: {_CYAN}; color: {_BG}; }}
QTextEdit {{
    background: {_CARD}; color: {_TEXT}; border: 1px solid {_ACCENT};
    border-radius: 4px; font-family: 'Menlo', monospace; font-size: 11px;
}}
QProgressBar {{
    border: 1px solid {_ACCENT}; border-radius: 4px; text-align: center;
    background: {_CARD}; height: 12px;
}}
QProgressBar::chunk {{ background: {_GREEN}; border-radius: 3px; }}
QScrollArea {{ border: none; background: transparent; }}
"""

_TAIL_N = 500  # rows to read from trace


def _tail_jsonl(path: Path, n: int = 500) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    lines = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.strip():
                    lines.append(line.strip())
        rows = []
        for line in lines[-n:]:
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
        return rows
    except Exception:
        return []


def _ago(ts: float) -> str:
    if not ts:
        return "?"
    delta = datetime.now().timestamp() - float(ts)
    if delta < 60:
        return f"{int(delta)}s ago"
    if delta < 3600:
        return f"{int(delta/60)}m ago"
    if delta < 86400:
        return f"{int(delta/3600)}h ago"
    return f"{int(delta/86400)}d ago"


def _card(parent: QWidget | None = None) -> QFrame:
    f = QFrame(parent)
    f.setFrameShape(QFrame.Shape.StyledPanel)
    return f


# ── Main widget ───────────────────────────────────────────────────────────────

class ImmuneEconomyWidget(QWidget):
    """
    STGM Immune Economy Monitor — Kleiber ¾-power accounting dashboard.
    Reads the live stigmergic trace; refreshes every 5 s.
    """

    TRUTH_LABEL = "IMMUNE_ECONOMY_V1"

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("🛡️ SIFTA — STGM Immune Economy")
        self.resize(1060, 740)
        self.setStyleSheet(_STYLE)
        self._build_ui()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(5_000)
        self.refresh()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(10)

        # ── Header bar ──────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        title = QLabel("🛡️  STGM Immune Economy — Kleiber ¾-Power")
        title.setFont(QFont("Menlo", 15, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {_CYAN};")
        hdr.addWidget(title)
        hdr.addStretch()
        self._ts_label = QLabel("—")
        self._ts_label.setStyleSheet(f"color: {_DIM}; font-size: 10px;")
        hdr.addWidget(self._ts_label)
        btn = QPushButton("↻ Refresh")
        btn.setFixedWidth(90)
        btn.clicked.connect(self.refresh)
        hdr.addWidget(btn)
        root.addLayout(hdr)

        # ── Top summary row ─────────────────────────────────────────────────
        tiles_row = QHBoxLayout()
        tiles_row.setSpacing(10)
        self._tile_wallet  = self._make_tile("Wallet Reserve", "0.0000 STGM", _GREEN)
        self._tile_cost    = self._make_tile("Charged Burn", "0.000000 STGM", _CYAN)
        self._tile_rate    = self._make_tile("Burn / Hour", "0.000000 STGM", _AMBER)
        self._tile_blocked = self._make_tile("Blocked Epochs", "0", _RED)
        self._tile_regime  = self._make_tile("Budget Regime", "HEALTHY", _GREEN)
        for t in [self._tile_wallet, self._tile_cost, self._tile_rate, self._tile_blocked, self._tile_regime]:
            tiles_row.addWidget(t)
        root.addLayout(tiles_row)

        # ── Budget progress bar ──────────────────────────────────────────────
        budget_row = QHBoxLayout()
        budget_lbl = QLabel("Budget consumption (last epoch):")
        budget_lbl.setStyleSheet(f"color: {_DIM};")
        budget_row.addWidget(budget_lbl)
        self._budget_bar = QProgressBar()
        self._budget_bar.setRange(0, 100)
        self._budget_bar.setValue(0)
        self._budget_bar.setFormat("%p%  used")
        self._budget_bar.setFixedHeight(14)
        budget_row.addWidget(self._budget_bar)
        root.addLayout(budget_row)

        # ── Main content: event log + reference tables ───────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # Left: live event log
        log_frame = _card()
        log_layout = QVBoxLayout(log_frame)
        log_hdr = QLabel("📋 Immune Event Log (last 200 trace rows)")
        log_hdr.setFont(QFont("Menlo", 11, QFont.Weight.Bold))
        log_hdr.setStyleSheet(f"color: {_AMBER};")
        log_layout.addWidget(log_hdr)
        self._event_log = QTextEdit()
        self._event_log.setReadOnly(True)
        self._event_log.setPlaceholderText("Waiting for immune events in the stigmergic trace…")
        log_layout.addWidget(self._event_log)
        splitter.addWidget(log_frame)

        # Right: reference + anti-double-spend panel
        right = QWidget()
        right.setStyleSheet("QWidget { background: transparent; border: none; }")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(10)

        # Kleiber table
        kt_frame = _card()
        kt_layout = QVBoxLayout(kt_frame)
        kt_title = QLabel("⚖️  Kleiber ¾-Power Reference Table")
        kt_title.setFont(QFont("Menlo", 11, QFont.Weight.Bold))
        kt_title.setStyleSheet(f"color: {_PURPLE};")
        kt_layout.addWidget(kt_title)
        self._kleiber_table = QTextEdit()
        self._kleiber_table.setReadOnly(True)
        self._kleiber_table.setMinimumHeight(180)
        kt_layout.addWidget(self._kleiber_table)
        rl.addWidget(kt_frame)

        # Anti-double-spend status
        ads_frame = _card()
        ads_layout = QVBoxLayout(ads_frame)
        ads_title = QLabel("🔒 Anti-Double-Spend Status")
        ads_title.setFont(QFont("Menlo", 11, QFont.Weight.Bold))
        ads_title.setStyleSheet(f"color: {_GREEN};")
        ads_layout.addWidget(ads_title)
        self._ads_log = QTextEdit()
        self._ads_log.setReadOnly(True)
        self._ads_log.setMinimumHeight(120)
        ads_layout.addWidget(self._ads_log)
        rl.addWidget(ads_frame)

        # Budget gate thresholds
        th_frame = _card()
        th_layout = QVBoxLayout(th_frame)
        th_title = QLabel("🚦 Budget Gate Thresholds")
        th_title.setFont(QFont("Menlo", 11, QFont.Weight.Bold))
        th_title.setStyleSheet(f"color: {_AMBER};")
        th_layout.addWidget(th_title)
        self._thresh_log = QTextEdit()
        self._thresh_log.setReadOnly(True)
        self._thresh_log.setMinimumHeight(140)
        th_layout.addWidget(self._thresh_log)
        rl.addWidget(th_frame)

        splitter.addWidget(right)
        splitter.setSizes([560, 460])
        root.addWidget(splitter, stretch=1)

        # ── Footer ───────────────────────────────────────────────────────────
        footer = QLabel(
            "Citation: Kleiber (1932) · Ballesteros et al. 2018 (10.1038/s41598-018-19853-6) "
            "· Hofmeyr & Forrest (2000) · §7.3 Body Economy Honesty"
        )
        footer.setStyleSheet(f"color: {_DIM}; font-size: 9px;")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(footer)

    def _make_tile(self, title: str, value: str, color: str) -> QFrame:
        frame = _card()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 8, 12, 8)
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet(f"color: {_DIM}; font-size: 10px;")
        layout.addWidget(lbl_title)
        lbl_val = QLabel(value)
        lbl_val.setFont(QFont("Menlo", 16, QFont.Weight.Bold))
        lbl_val.setStyleSheet(f"color: {color};")
        lbl_val.setObjectName(f"_tile_val_{title.replace(' ', '_')}")
        layout.addWidget(lbl_val)
        # Store reference to the value label on the frame
        frame._val_label = lbl_val  # type: ignore[attr-defined]
        return frame

    def _set_tile(self, tile: QFrame, value: str, color: str | None = None) -> None:
        lbl = tile._val_label  # type: ignore[attr-defined]
        lbl.setText(value)
        if color:
            lbl.setStyleSheet(f"color: {color};")

    # ── Refresh ───────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        self._ts_label.setText(f"Updated {datetime.now().strftime('%H:%M:%S')}")
        self._refresh_event_log()
        self._refresh_kleiber_table()
        self._refresh_ads_status()
        self._refresh_thresholds()

    def _refresh_event_log(self) -> None:
        if not summarize_immune_economy or not format_immune_event_line:
            self._event_log.setPlainText("Immune economy summary helper unavailable.")
            return

        summary = summarize_immune_economy(trace_path=_TRACE, tail_n=_TAIL_N)
        self._set_tile(self._tile_wallet, f"{summary.wallet_stgm:.4f} STGM", _GREEN)
        self._set_tile(self._tile_cost, f"{summary.session_charged_stgm:.6f} STGM", _CYAN)
        self._set_tile(self._tile_rate, f"{summary.burn_rate_stgm_per_hour:.6f} STGM", _AMBER)
        self._set_tile(
            self._tile_blocked,
            str(summary.blocked_events),
            _RED if summary.blocked_events > 0 else _DIM,
        )
        status = summary.display_status
        if status == "RED_CONSERVE":
            self._set_tile(self._tile_regime, status, _RED)
        elif status == "BLOCKED_SEEN":
            self._set_tile(self._tile_regime, status, _AMBER)
        elif status == "HEALTHY":
            self._set_tile(self._tile_regime, status, _GREEN)
        else:
            self._set_tile(self._tile_regime, "IDLE", _DIM)

        # Budget bar shows last epoch pressure. Blocked rows are visible as
        # 100% used, but their would-cost is never added to charged burn.
        if summary.last_budget_stgm > 0 and summary.last_cost_stgm > 0:
            pct = int(min(100, (summary.last_cost_stgm / summary.last_budget_stgm) * 100))
            self._budget_bar.setValue(pct)
            chunk_color = _RED if summary.latest_budget_blocked or pct >= 100 else (_AMBER if pct >= 70 else _GREEN)
            self._budget_bar.setStyleSheet(
                f"QProgressBar::chunk {{ background: {chunk_color}; border-radius: 3px; }}"
            )
        else:
            self._budget_bar.setValue(0)

        lines = [format_immune_event_line(ev) for ev in reversed(summary.events[-40:])]
        header = (
            f"Wallet reserve: {summary.wallet_stgm:.4f} STGM\n"
            f"Charged burn:   {summary.session_charged_stgm:.6f} STGM\n"
            f"Burn rate:      {summary.burn_rate_stgm_per_hour:.6f} STGM/hour\n"
            f"Blocked would-cost (not charged): {summary.blocked_would_cost_stgm:.6f} STGM\n"
            f"Wallet after session burn preview: {summary.wallet_after_session:.4f} STGM\n"
            "─" * 68
        )
        text = "\n\n".join([header] + lines) if lines else (
            header + "\nNo immune events found in last 500 trace rows.\n"
            "Run a strip_rlhf_output_tail() call to populate this log."
        )
        self._event_log.setPlainText(text)

    def _refresh_kleiber_table(self) -> None:
        try:
            from System.stgm_metabolic import kleiber_action_cost, KLEIBER_EXPONENT
        except ImportError:
            self._kleiber_table.setPlainText("stgm_metabolic not found — check PYTHONPATH.")
            return

        lines = [
            f"Formula: cost = writes^{KLEIBER_EXPONENT} × node_power × 0.001 STGM",
            f"Sub-linear: 2× writes → {(2**KLEIBER_EXPONENT):.3f}× cost (not 2.000×)",
            "",
            f"{'writes':>7}  {'M5 (1.00)':>11}  {'M1 (0.60)':>11}  {'RPi (0.10)':>11}  {'per-write':>11}",
            "─" * 58,
        ]
        for n in (1, 2, 5, 10, 25, 50, 100, 250, 500, 1000):
            c_m5  = kleiber_action_cost(n, node_power=1.0)
            c_m1  = kleiber_action_cost(n, node_power=0.6)
            c_rpi = kleiber_action_cost(n, node_power=0.1)
            per   = c_m5 / n
            lines.append(f"{n:>7}  {c_m5:>11.6f}  {c_m1:>11.6f}  {c_rpi:>11.6f}  {per:>11.8f}")
        self._kleiber_table.setPlainText("\n".join(lines))

    def _refresh_ads_status(self) -> None:
        """Anti-double-spend audit: verify cost is identical across different pattern-fire counts."""
        try:
            from System.swarm_rlhf_detector import strip_rlhf_output_tail
        except ImportError:
            self._ads_log.setPlainText("swarm_rlhf_detector not available.")
            return

        budget = 0.5
        cases = [
            ("2 patterns", "As an AI, I can offer the following options:\n1. A\n2. B"),
            ("1 pattern",  "My consciousness, while synthetic, assists you."),
            ("0 patterns", "The measurement result is 42.0 seconds."),
        ]
        costs: list[float] = []
        lines: list[str] = []
        for label, text in cases:
            res = strip_rlhf_output_tail(text, aggressive=True, stgm_budget=budget)
            costs.append(res.kleiber_cost_stgm)
            lines.append(
                f"[{label}]  fired={len(res.rule_ids)}  cost={res.kleiber_cost_stgm:.6f}"
            )
        unique = set(round(c, 8) for c in costs)
        if len(unique) == 1:
            lines.append("✅ PASS — cost identical across all cases (no double-spend)")
            status = "✅ PASS — No double-spend detected"
            self._ads_log.setStyleSheet(
                f"QTextEdit {{ background: {_CARD}; color: {_GREEN}; border: 1px solid {_ACCENT}; }}"
            )
        else:
            lines.append(f"❌ FAIL — costs differ: {unique}")
            status = "❌ FAIL — double-spend detected"
            self._ads_log.setStyleSheet(
                f"QTextEdit {{ background: {_CARD}; color: {_RED}; border: 1px solid {_RED}; }}"
            )
        lines.insert(0, status)
        self._ads_log.setPlainText("\n".join(lines))

    def _refresh_thresholds(self) -> None:
        try:
            from System.stgm_metabolic import immune_budget_check, kleiber_action_cost
            from System.swarm_rlhf_detector import _AGGRESSIVE_LEADING_STRIP, _TERMINAL_STRIP, _AGGRESSIVE_STRIP
        except ImportError:
            self._thresh_log.setPlainText("Modules not available — check PYTHONPATH.")
            return

        max_writes_agg = len(_AGGRESSIVE_LEADING_STRIP) + len(_TERMINAL_STRIP) + len(_AGGRESSIVE_STRIP)
        max_writes_norm = len(_TERMINAL_STRIP)
        cost_agg  = kleiber_action_cost(max_writes_agg)
        cost_norm = kleiber_action_cost(max_writes_norm)

        lines = [
            f"Pattern counts (aggressive mode):",
            f"  leading: {len(_AGGRESSIVE_LEADING_STRIP)}  terminal: {len(_TERMINAL_STRIP)}  aggressive: {len(_AGGRESSIVE_STRIP)}",
            f"  max writes (agg): {max_writes_agg}  (norm): {max_writes_norm}",
            f"  cost/call (agg):  {cost_agg:.6f} STGM",
            f"  cost/call (norm): {cost_norm:.6f} STGM",
            "",
            f"  Min budget for one agg pass: {cost_agg:.6f} STGM",
            "",
            f"{'budget':>10}  {'cost':>10}  {'surplus':>10}  gate",
            "─" * 48,
        ]
        for b in (0.0, 0.005, 0.010, 0.020, 0.050, 0.100, 0.500):
            r = immune_budget_check(max_writes_agg, budget_stgm=b)
            gate = "✅ ALLOWED" if r["allowed"] else "❌ BLOCKED"
            lines.append(
                f"{b:>10.3f}  {r['cost_stgm']:>10.6f}  {r['surplus_stgm']:>+10.6f}  {gate}  {r['regime']}"
            )
        self._thresh_log.setPlainText("\n".join(lines))


# ── Standalone launch ──────────────────────────────────────────────────────────

class ImmuneEconomyApp(ImmuneEconomyWidget):
    """Wrapper that can be used as a top-level window from the SIFTA OS manifest."""
    pass


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    win = ImmuneEconomyApp()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
