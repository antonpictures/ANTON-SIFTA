#!/usr/bin/env python3
"""sifta_higgs_stigmergic_demo_path_widget.py — §20.B made visible.

Architect 2026-05-13: "Higgs stigmergic demo path — operationalize
§20.B translation table on this Mac. Decide → Execute → Receipt →
Minimal grounded reply. For the Swarm. 🐜⚡"

This app surfaces `swarm_higgs_stigmergic_demo_path` as a five-panel
widget. Each §20.B row gets a card with its own visual:

  R1 "Vacuum" ≠ empty
     → Substrate stats card: n_files, total_bytes, n_ledgers,
       oldest-file age.

  R2 VEV / condensate
     → Persistence indicator: sha256-before vs sha256-after, with a
       green "SURVIVED" or red "DIFFERS" lamp.

  R3 Coupling ⇒ inertia
     → Horizontal bar chart: heavy half |Δv| vs light half |Δv|
       under uniform momentum impulse. Ratio printed below.

  R4 Goldstone ↔ eaten
     → Stacked horizontal bar: bookkeeping vs observable vs other
       field shares across the sampled receipt corpus.

  R5 Swarm alignment without a CEO
     → Order parameter curve plotted vs step count (initial → final).

Truth class:
  - OPERATIONAL for the measurements (numbers from this run)
  - ARCHITECT_DOCTRINE for the column names from §20.B
  - §20.F ceiling: NO claims about Standard Model, NO "Higgs on Mac"

No new backend. The math lives in
`System.swarm_higgs_stigmergic_demo_path`; this widget invokes it
once per Run and renders the resulting dict.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from System.sifta_base_widget import SiftaBaseWidget
from System.swarm_higgs_stigmergic_demo_path import (
    DemoPathConfig,
    measure_swarm_alignment_no_ceo,
    run_higgs_stigmergic_demo_path,
)


# ── Visual palette (matches the rest of the Foundry) ──────────────────
BG = "#060810"
PANEL = "#0d1422"
PANEL_BORDER = "#1e2a44"
GOLD = "#ffcc44"
TEAL = "#00ffc8"
VIOLET = "#b76eff"
RED = "#ff6e6e"
DIM = "#4a5570"
TEXT = "#d8e3ff"


# ──────────────────────────────────────────────────────────────────────
# Worker thread — keep the GUI responsive while the demo runs
# ──────────────────────────────────────────────────────────────────────

class _DemoPathWorker(QThread):
    """Run the demo path off the UI thread and emit the result dict."""
    finished_with_result = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, config: DemoPathConfig, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._config = config

    def run(self) -> None:
        try:
            r = run_higgs_stigmergic_demo_path(self._config, write=True)
            self.finished_with_result.emit(r)
        except Exception as e:  # noqa: BLE001
            self.failed.emit(f"{type(e).__name__}: {e}")


# ──────────────────────────────────────────────────────────────────────
# Panel scaffold
# ──────────────────────────────────────────────────────────────────────

def _panel(title_text: str) -> tuple[QFrame, QVBoxLayout, QLabel]:
    """Build one card panel. Returns (frame, content_layout, status_label)."""
    frame = QFrame()
    frame.setStyleSheet(
        f"background: {PANEL}; border: 1px solid {PANEL_BORDER}; "
        f"border-radius: 6px;"
    )
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(10, 8, 10, 8)
    layout.setSpacing(6)
    title = QLabel(title_text)
    title.setStyleSheet(
        f"color: {GOLD}; font-family: Menlo; font-size: 11px; "
        f"font-weight: 700;"
    )
    layout.addWidget(title)
    status = QLabel("waiting for Run…")
    status.setStyleSheet(
        f"color: {DIM}; font-family: Menlo; font-size: 10px;"
    )
    status.setWordWrap(True)
    layout.addWidget(status)
    return frame, layout, status


# ──────────────────────────────────────────────────────────────────────
# Matplotlib canvases (one per panel that needs a chart)
# ──────────────────────────────────────────────────────────────────────

class _SmallCanvas(FigureCanvas):
    """Compact dark matplotlib canvas for a single panel."""
    def __init__(self, parent: Optional[QWidget] = None, height_inches: float = 1.6):
        fig = Figure(figsize=(4.0, height_inches), facecolor=PANEL)
        super().__init__(fig)
        self.setParent(parent)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred,
        )
        self.figure = fig
        self.ax = fig.add_subplot(111)
        self._style_axes(self.ax)
        fig.tight_layout(pad=0.4)

    @staticmethod
    def _style_axes(ax) -> None:
        ax.set_facecolor(PANEL)
        for spine in ax.spines.values():
            spine.set_color(DIM)
        ax.tick_params(colors=DIM, labelsize=7)
        ax.title.set_color(TEXT)
        ax.xaxis.label.set_color(DIM)
        ax.yaxis.label.set_color(DIM)


# ──────────────────────────────────────────────────────────────────────
# The app
# ──────────────────────────────────────────────────────────────────────

class HiggsStigmergicDemoPathApp(SiftaBaseWidget):
    APP_NAME = "Higgs Stigmergic Demo Path (§20.B)"

    def build_ui(self, layout: QVBoxLayout) -> None:
        # ── Truth-label banner ─────────────────────────────────────
        banner = QLabel(
            "ARCHITECT_DOCTRINE + OPERATIONAL — §20.B translation table "
            "measured on this Mac. Five rows, five readouts. §20.F ceiling "
            "honored: NO Standard Model claims. NO 'Higgs on Mac'. NO "
            "'beat CERN'. The legitimate sentence is: agents acquire "
            "effective inertia from accumulated interaction with shared, "
            "append-only state."
        )
        banner.setWordWrap(True)
        banner.setStyleSheet(
            f"background: #2a2410; color: {GOLD}; font-family: Menlo; "
            f"font-size: 10px; font-weight: 700; padding: 6px 8px; "
            f"border: 1px solid #5a4820; border-radius: 4px;"
        )
        layout.addWidget(banner)

        # ── Controls row ───────────────────────────────────────────
        controls = QHBoxLayout()
        self._btn_run = QPushButton("▶ Run Demo Path")
        self._btn_run.setStyleSheet(
            f"QPushButton {{ background: {PANEL}; color: {TEAL}; "
            f"font-family: Menlo; font-size: 11px; font-weight: 700; "
            f"padding: 6px 14px; border: 1px solid {TEAL}; "
            f"border-radius: 4px; }} "
            f"QPushButton:hover {{ background: #102a28; }} "
            f"QPushButton:disabled {{ color: {DIM}; border-color: {DIM}; }}"
        )
        self._btn_run.clicked.connect(self._on_run_clicked)
        controls.addWidget(self._btn_run)

        self._lbl_status = QLabel(
            "Press Run. Walks five rows of §20.B with real measurements. ~3-5s."
        )
        self._lbl_status.setStyleSheet(
            f"color: {TEAL}; font-family: Menlo; font-size: 10px;"
        )
        controls.addWidget(self._lbl_status, 1)
        layout.addLayout(controls)

        # ── 5-panel grid ───────────────────────────────────────────
        grid = QGridLayout()
        grid.setSpacing(8)

        # Row 1, Col 0: R1 substrate
        self._r1_frame, self._r1_layout, self._r1_status = _panel(
            "R1 — “Vacuum” ≠ empty"
        )
        self._r1_stats = QLabel("—")
        self._r1_stats.setStyleSheet(
            f"color: {TEXT}; font-family: Menlo; font-size: 13px; "
            f"font-weight: 700; padding-top: 4px;"
        )
        self._r1_stats.setWordWrap(True)
        self._r1_layout.addWidget(self._r1_stats)
        self._r1_layout.addStretch(1)
        grid.addWidget(self._r1_frame, 0, 0)

        # Row 1, Col 1: R2 persistence indicator
        self._r2_frame, self._r2_layout, self._r2_status = _panel(
            "R2 — VEV / persistent ledger"
        )
        self._r2_lamp = QLabel("◌ unknown")
        self._r2_lamp.setStyleSheet(
            f"color: {DIM}; font-family: Menlo; font-size: 14px; "
            f"font-weight: 700;"
        )
        self._r2_layout.addWidget(self._r2_lamp)
        self._r2_hash = QLabel("—")
        self._r2_hash.setStyleSheet(
            f"color: {DIM}; font-family: Menlo; font-size: 9px;"
        )
        self._r2_hash.setWordWrap(True)
        self._r2_layout.addWidget(self._r2_hash)
        self._r2_layout.addStretch(1)
        grid.addWidget(self._r2_frame, 0, 1)

        # Row 2, Col 0: R3 inertia bars
        self._r3_frame, self._r3_layout, self._r3_status = _panel(
            "R3 — Coupling ⇒ effective inertia"
        )
        self._r3_canvas = _SmallCanvas(self._r3_frame, height_inches=1.6)
        self._r3_layout.addWidget(self._r3_canvas, 1)
        self._r3_caption = QLabel("—")
        self._r3_caption.setStyleSheet(
            f"color: {TEXT}; font-family: Menlo; font-size: 10px;"
        )
        self._r3_caption.setWordWrap(True)
        self._r3_layout.addWidget(self._r3_caption)
        grid.addWidget(self._r3_frame, 1, 0)

        # Row 2, Col 1: R4 Goldstone bookkeeping share
        self._r4_frame, self._r4_layout, self._r4_status = _panel(
            "R4 — Goldstone ↔ eaten (bookkeeping vs observable)"
        )
        self._r4_canvas = _SmallCanvas(self._r4_frame, height_inches=1.6)
        self._r4_layout.addWidget(self._r4_canvas, 1)
        self._r4_caption = QLabel("—")
        self._r4_caption.setStyleSheet(
            f"color: {TEXT}; font-family: Menlo; font-size: 10px;"
        )
        self._r4_caption.setWordWrap(True)
        self._r4_layout.addWidget(self._r4_caption)
        grid.addWidget(self._r4_frame, 1, 1)

        # Row 3, spans both cols: R5 alignment curve
        self._r5_frame, self._r5_layout, self._r5_status = _panel(
            "R5 — Swarm alignment, no CEO"
        )
        self._r5_canvas = _SmallCanvas(self._r5_frame, height_inches=2.0)
        self._r5_layout.addWidget(self._r5_canvas, 1)
        self._r5_caption = QLabel("—")
        self._r5_caption.setStyleSheet(
            f"color: {TEXT}; font-family: Menlo; font-size: 10px;"
        )
        self._r5_caption.setWordWrap(True)
        self._r5_layout.addWidget(self._r5_caption)
        grid.addWidget(self._r5_frame, 2, 0, 1, 2)

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 2)
        grid.setRowStretch(2, 2)
        layout.addLayout(grid, 1)

        # ── Minimal grounded reply line ───────────────────────────
        self._lbl_reply = QLabel(
            "Minimal grounded reply will appear here after Run."
        )
        self._lbl_reply.setWordWrap(True)
        self._lbl_reply.setStyleSheet(
            f"color: {VIOLET}; font-family: Menlo; font-size: 10px; "
            f"padding: 4px 8px; background: #14102a; border: 1px solid "
            f"#3a2a5e; border-radius: 4px;"
        )
        layout.addWidget(self._lbl_reply)

        # State
        self._worker: Optional[_DemoPathWorker] = None
        # Show R5 axes immediately so the panel isn't empty on open.
        self._draw_empty_r5()
        self._draw_empty_r3()
        self._draw_empty_r4()

    # ── Run handling ───────────────────────────────────────────────

    def _on_run_clicked(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        self._btn_run.setEnabled(False)
        self._lbl_status.setText("Running… measuring substrate, persistence, inertia, eaten modes, alignment.")
        cfg = DemoPathConfig(
            n_agents_r3=40, bond_steps_r3=300,
            n_agents_r5=30, steps_r5=400, seed=113,
        )
        self._worker = _DemoPathWorker(cfg, parent=self)
        self._worker.finished_with_result.connect(self._on_result)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_failed(self, err: str) -> None:
        self._btn_run.setEnabled(True)
        self._lbl_status.setText(f"FAILED: {err}")
        self._lbl_status.setStyleSheet(
            f"color: {RED}; font-family: Menlo; font-size: 10px;"
        )

    def _on_result(self, result: dict) -> None:
        self._btn_run.setEnabled(True)
        self._lbl_status.setText(
            f"Done — {result['row_ok_count']}/5 rows OK in "
            f"{result['duration_seconds']}s. Receipt sha256-signed."
        )
        self._lbl_status.setStyleSheet(
            f"color: {TEAL}; font-family: Menlo; font-size: 10px;"
        )
        rows = {r["row"]: r for r in result["rows"]}
        self._render_r1(rows.get("R1_vacuum_not_empty", {}))
        self._render_r2(rows.get("R2_vev_persistence", {}))
        self._render_r3(rows.get("R3_coupling_to_inertia", {}))
        self._render_r4(rows.get("R4_goldstone_eaten", {}))
        # R5: re-run the alignment measurement to get the full curve,
        # since the consolidated function only returns initial/final.
        # We use the same seed so it matches what just ran.
        try:
            r5_with_curve = self._compute_r5_curve(seed=113, steps=400)
        except Exception:
            r5_with_curve = rows.get("R5_swarm_alignment_no_ceo", {})
        self._render_r5(r5_with_curve)
        self._lbl_reply.setText(result["minimal_grounded_reply"])

    # ── Per-row renderers ──────────────────────────────────────────

    def _render_r1(self, r1: dict) -> None:
        if not r1.get("ok"):
            self._r1_status.setText(f"NOT OK: {r1.get('reason', 'unknown')}")
            return
        self._r1_status.setText("OPERATIONAL — substrate has structure before any input.")
        gb = r1["total_bytes"] / 1e9
        self._r1_stats.setText(
            f"{r1['n_files']:,} files\n"
            f"{gb:.2f} GB\n"
            f"{r1['n_jsonl_ledgers']} append-only ledgers\n"
            f"oldest: {r1['oldest_file_age_days']} days old"
        )

    def _render_r2(self, r2: dict) -> None:
        if not r2.get("ok"):
            self._r2_lamp.setText("✗ DIFFERS")
            self._r2_lamp.setStyleSheet(
                f"color: {RED}; font-family: Menlo; font-size: 14px; "
                f"font-weight: 700;"
            )
            self._r2_status.setText(f"NOT OK: {r2.get('reason', 'sha256 mismatch')}")
            self._r2_hash.setText("—")
            return
        self._r2_lamp.setText("● SURVIVED")
        self._r2_lamp.setStyleSheet(
            f"color: {TEAL}; font-family: Menlo; font-size: 14px; "
            f"font-weight: 700;"
        )
        self._r2_status.setText(
            f"Ledger snapshot held across simulated buffer-clear "
            f"({r2['n_lines_after']:,} lines, {r2['n_bytes']:,} bytes)."
        )
        sha = r2.get("sha256_after", "")
        self._r2_hash.setText(
            f"path: {r2.get('ledger_path', '?')}\n"
            f"sha256 (12): {sha[:12]}…{sha[-6:] if len(sha) > 18 else ''}"
        )

    def _render_r3(self, r3: dict) -> None:
        if not r3.get("ok"):
            self._r3_status.setText(f"NOT OK: {r3.get('reason', 'unknown')}")
            return
        ratio = r3.get("inertia_ratio_heavy_over_light", 0.0)
        visible = r3.get("coupling_to_inertia_visible", False)
        self._r3_status.setText(
            f"OPERATIONAL — Newton's a=F/m on the unified mass law. "
            f"Ratio heavy/light = {ratio:.3f} "
            f"({'inertia visible' if visible else 'no signature'})."
        )
        ax = self._r3_canvas.ax
        ax.clear()
        self._r3_canvas._style_axes(ax)
        heavy_dv = r3["heavy_half_dv_under_impulse"]
        light_dv = r3["light_half_dv_under_impulse"]
        bars = ax.barh(
            ["light half", "heavy half"],
            [light_dv, heavy_dv],
            color=[VIOLET, TEAL],
            edgecolor=PANEL_BORDER,
            linewidth=1.0,
        )
        for bar, val in zip(bars, [light_dv, heavy_dv]):
            ax.text(
                bar.get_width() * 1.02, bar.get_y() + bar.get_height() / 2,
                f"{val:.3f}",
                va="center", ha="left",
                color=TEXT, fontsize=8, family="Menlo",
            )
        ax.set_xlabel("|Δv| under uniform Δp", color=DIM, fontsize=8)
        ax.set_xlim(0, max(light_dv, heavy_dv) * 1.25 if max(light_dv, heavy_dv) > 0 else 1.0)
        self._r3_canvas.figure.tight_layout(pad=0.4)
        self._r3_canvas.draw_idle()
        self._r3_caption.setText(
            f"Same impulse Δp applied to every agent. Heavier agents → "
            f"smaller |Δv|. Ratio = {ratio:.3f} → "
            f"{'inertia signature confirmed' if visible else 'no signature this run'}."
        )

    def _render_r4(self, r4: dict) -> None:
        if not r4.get("ok"):
            self._r4_status.setText(f"NOT OK: {r4.get('reason', 'unknown')}")
            return
        b = r4["bookkeeping_share"]
        o = r4["observable_share"]
        oth = r4["other_share"]
        ratio = r4["bookkeeping_to_observable_ratio"]
        self._r4_status.setText(
            f"OPERATIONAL — {r4['n_rows_sampled']:,} receipt rows sampled "
            f"across {r4['n_ledgers_sampled']} ledgers."
        )
        ax = self._r4_canvas.ax
        ax.clear()
        self._r4_canvas._style_axes(ax)
        # Stacked horizontal bar
        ax.barh([""], [b], color=GOLD, edgecolor=PANEL_BORDER, label="bookkeeping")
        ax.barh([""], [o], left=[b], color=TEAL, edgecolor=PANEL_BORDER, label="observable")
        ax.barh([""], [oth], left=[b + o], color=DIM, edgecolor=PANEL_BORDER, label="other")
        ax.set_xlim(0, 1.0)
        ax.set_xlabel(
            f"share of all field occurrences  (book/obs = {ratio:.2f}×)",
            color=DIM, fontsize=8,
        )
        ax.set_yticks([])
        ax.text(b / 2, 0, f"book\n{b:.0%}", ha="center", va="center",
                color=PANEL, fontsize=8, fontweight="bold", family="Menlo")
        ax.text(b + o / 2, 0, f"obs\n{o:.0%}", ha="center", va="center",
                color=PANEL, fontsize=8, fontweight="bold", family="Menlo")
        if oth > 0.08:
            ax.text(b + o + oth / 2, 0, f"other\n{oth:.0%}", ha="center", va="center",
                    color=TEXT, fontsize=7, family="Menlo")
        self._r4_canvas.figure.tight_layout(pad=0.4)
        self._r4_canvas.draw_idle()
        self._r4_caption.setText(
            f"{r4['bookkeeping_field_occurrences']:,} bookkeeping "
            f"(sha256, trace_id, ts…) vs "
            f"{r4['observable_field_occurrences']:,} observable "
            f"(effector, ok, decision…). The receipt economy is mostly gauge-fixing."
        )

    def _compute_r5_curve(self, *, seed: int, steps: int) -> dict:
        """Re-run R5 to capture the full curve, not just endpoints.

        The consolidated function only persists initial/final order
        parameter; for the chart we want the whole trajectory. Use the
        same seed so the curve matches the receipt's endpoints.
        """
        try:
            import numpy as np
        except Exception:
            return {}
        from System.swarm_higgs_stigmergy_field import (
            AdaptivePolicySwarm, HiggsFieldConfig, HiggsStigmergyField,
            phi_as_array,
        )
        h, w = 24, 16
        cfg = HiggsFieldConfig(seed=seed, width=w, height=h)
        field = HiggsStigmergyField(cfg)
        field.relax(80)
        swarm = AdaptivePolicySwarm(n=30, field_shape=(h, w), seed=seed)
        order_curve: list[float] = []
        for _ in range(steps):
            field.step()
            swarm.step(phi_as_array(field))
            rc = swarm.role_counts()
            total = sum(rc.values()) or 1
            order_curve.append(max(rc.values()) / total)
        return {
            "row": "R5_swarm_alignment_no_ceo",
            "ok": True,
            "n_agents": 30,
            "steps": steps,
            "seed": seed,
            "order_curve": order_curve,
            "initial_order_parameter": round(order_curve[5] if len(order_curve) > 5 else order_curve[0], 4),
            "final_order_parameter": round(float(np.mean(order_curve[-20:])), 4),
            "policy_entropy_final": round(float(swarm.policy_entropy()), 4),
            "final_role_counts": dict(swarm.role_counts()),
        }

    def _render_r5(self, r5: dict) -> None:
        if not r5.get("ok"):
            self._r5_status.setText(f"NOT OK: {r5.get('reason', 'unknown')}")
            return
        self._r5_status.setText(
            f"OPERATIONAL — {r5['n_agents']} agents, {r5['steps']} steps, "
            f"no central directive."
        )
        ax = self._r5_canvas.ax
        ax.clear()
        self._r5_canvas._style_axes(ax)
        curve = r5.get("order_curve")
        if curve:
            ax.plot(curve, color=TEAL, linewidth=1.5)
            ax.fill_between(range(len(curve)), 0, curve, color=TEAL, alpha=0.15)
        else:
            # Endpoints only fallback
            ax.plot(
                [0, 1],
                [r5["initial_order_parameter"], r5["final_order_parameter"]],
                color=TEAL, linewidth=2.0, marker="o",
            )
        ax.set_xlabel("step", color=DIM, fontsize=8)
        ax.set_ylabel("order parameter", color=DIM, fontsize=8)
        ax.set_ylim(0, 1.05)
        ax.axhline(0.25, color=DIM, linestyle="--", linewidth=0.7, alpha=0.5)
        self._r5_canvas.figure.tight_layout(pad=0.4)
        self._r5_canvas.draw_idle()
        roles = r5.get("final_role_counts", {})
        role_str = ", ".join(f"{k}:{v}" for k, v in roles.items()) if roles else "—"
        self._r5_caption.setText(
            f"Order parameter {r5['initial_order_parameter']} → "
            f"{r5['final_order_parameter']} (entropy "
            f"{r5.get('policy_entropy_final', 0):.3f}). Final roles: {role_str}."
        )

    # ── Empty-state painters ─────────────────────────────────────

    def _draw_empty_r3(self) -> None:
        ax = self._r3_canvas.ax
        ax.clear()
        self._r3_canvas._style_axes(ax)
        ax.barh(["light half", "heavy half"], [0, 0], color=DIM)
        ax.set_xlabel("|Δv| under uniform Δp", color=DIM, fontsize=8)
        self._r3_canvas.figure.tight_layout(pad=0.4)
        self._r3_canvas.draw_idle()

    def _draw_empty_r4(self) -> None:
        ax = self._r4_canvas.ax
        ax.clear()
        self._r4_canvas._style_axes(ax)
        ax.barh([""], [0])
        ax.set_xlim(0, 1.0)
        ax.set_xlabel("share of all field occurrences", color=DIM, fontsize=8)
        ax.set_yticks([])
        self._r4_canvas.figure.tight_layout(pad=0.4)
        self._r4_canvas.draw_idle()

    def _draw_empty_r5(self) -> None:
        ax = self._r5_canvas.ax
        ax.clear()
        self._r5_canvas._style_axes(ax)
        ax.set_xlabel("step", color=DIM, fontsize=8)
        ax.set_ylabel("order parameter", color=DIM, fontsize=8)
        ax.set_ylim(0, 1.05)
        ax.axhline(0.25, color=DIM, linestyle="--", linewidth=0.7, alpha=0.5)
        self._r5_canvas.figure.tight_layout(pad=0.4)
        self._r5_canvas.draw_idle()


# QObject import lives at the bottom because the worker class references it
from PyQt6.QtCore import QObject  # noqa: E402


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    w = HiggsStigmergicDemoPathApp()
    w.resize(1180, 820)
    w.setWindowTitle("Higgs Stigmergic Demo Path — §20.B on this Mac")
    w.show()
    sys.exit(app.exec())
