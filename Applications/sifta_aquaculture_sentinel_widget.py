#!/usr/bin/env python3
"""sifta_aquaculture_sentinel_widget.py — Aquaculture Field Sentinel scaffold.

Codex (GPT-5) pinned the doctrine in:
    Documents/OS_OPTIMIZATION_SURPRISE_SAMPLING_TOURNAMENT_2026-05-12.md
    §14.G — Seafood / aquaculture nuggets (bounded application lane)

Demo target (Codex's words):
    Many cheap sensors around a tank, pond, cage, or hatchery leave local
    traces; the field decides when to sample harder, feed less, aerate,
    alert, or ask a human.

Status: HYPOTHESIS until the synthetic tank writes receipts. The actual
synthetic-tank simulation lives in `System/swarm_aquaculture_field.py`.
When that module and `aquaculture_field.jsonl` exist, this widget reports the
simulated sentinel as operational while preserving the no-live-sensor truth
boundary.

Truth boundary:
    No claims about real fish, shrimp, or shellfish are made by this
    widget. The 5 sensor channels mentioned (DO, pH, temp, turbidity,
    motion) are documentation, not measurements.
"""

from __future__ import annotations

"""SIFTA Aquaculture Sentinel Widget — stigmergic organ for Alice body."""

import json
import re
import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.sifta_base_widget import SiftaBaseWidget  # noqa: E402
from System.swarm_app_hardening import record_app_hardening_event  # noqa: E402

APP_HARDENING_ID = "queue-019:sifta_aquaculture_sentinel_widget"
_HARDENING_EVENT_KEYS: set[tuple[str, str, str, str]] = set()


def _record_aquaculture_hardening(event: str, **details) -> None:
    key = (
        event,
        str(details.get("path", "")),
        str(details.get("error", details.get("error_type", "")))[:160],
        str(details.get("line_preview", ""))[:80],
    )
    if key in _HARDENING_EVENT_KEYS:
        return
    _HARDENING_EVENT_KEYS.add(key)
    record_app_hardening_event(
        APP_HARDENING_ID,
        event,
        truth_label="OBSERVED",
        details=details,
    )

_DOCTRINE_MD = _REPO / "Documents" / "OS_OPTIMIZATION_SURPRISE_SAMPLING_TOURNAMENT_2026-05-12.md"
_AQUA_LEDGER = _REPO / ".sifta_state" / "aquaculture_field.jsonl"
_SIM_MODULE = _REPO / "System" / "swarm_aquaculture_field.py"


def _read_doctrine_section() -> str:
    """Extract the §14.G section from the tournament doc."""
    if not _DOCTRINE_MD.exists():
        return "(doctrine markdown not found on disk)"
    try:
        text = _DOCTRINE_MD.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        _record_aquaculture_hardening(
            "aquaculture_doctrine_read_failed",
            path=str(_DOCTRINE_MD),
            error=f"{type(exc).__name__}: {exc}",
        )
        return "(doctrine markdown unreadable)"
    # Slice the §14.G section to the next ### or ## heading.
    m = re.search(r"### 14\.G[\s\S]*?(?=\n###\s|\n##\s|\n---\s|$)", text)
    if not m:
        _record_aquaculture_hardening(
            "aquaculture_doctrine_section_missing",
            path=str(_DOCTRINE_MD),
            section="14.G",
        )
        return "(§14.G section not found — Codex may have moved it)"
    return m.group(0).strip()


def _status_snapshot() -> dict:
    """Honest current state: which pieces of Codex's plan exist on disk?"""
    latest: dict | None = None
    if _AQUA_LEDGER.exists():
        try:
            lines = [line for line in _AQUA_LEDGER.read_text(encoding="utf-8").splitlines() if line.strip()]
            latest = json.loads(lines[-1]) if lines else None
        except (OSError, json.JSONDecodeError) as exc:
            _record_aquaculture_hardening(
                "aquaculture_receipt_parse_failed",
                path=str(_AQUA_LEDGER),
                error=f"{type(exc).__name__}: {exc}",
            )
            latest = None
    receipt_count = 0
    if _AQUA_LEDGER.exists():
        try:
            receipt_count = sum(1 for _ in _AQUA_LEDGER.open(encoding="utf-8", errors="ignore"))
        except OSError as exc:
            _record_aquaculture_hardening(
                "aquaculture_receipt_count_failed",
                path=str(_AQUA_LEDGER),
                error=f"{type(exc).__name__}: {exc}",
            )
    return {
        "doctrine_pinned":       _DOCTRINE_MD.exists(),
        "simulator_module":      _SIM_MODULE.exists(),
        "receipt_ledger":        _AQUA_LEDGER.exists(),
        "receipt_count":         receipt_count,
        "latest_receipt":         latest,
    }


class AquacultureFieldSentinelWidget(SiftaBaseWidget):
    APP_NAME = "Aquaculture Field Sentinel"

    def build_ui(self, layout: QVBoxLayout) -> None:
        # ── Header: app name + status badge ───────────────────────────────
        head = QHBoxLayout()
        head.setSpacing(8)

        title = QLabel("🐟 Aquaculture Field Sentinel")
        title.setFont(QFont("Menlo", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: rgb(100, 200, 255);")
        head.addWidget(title)

        snap = _status_snapshot()
        live = snap["simulator_module"] and snap["receipt_ledger"]
        badge = QLabel("HYPOTHESIS" if not live else "OPERATIONAL")
        badge.setFont(QFont("Menlo", 11, QFont.Weight.Bold))
        badge.setStyleSheet(
            "background: rgb(60, 40, 30); color: rgb(255, 180, 100); "
            "border: 1px solid rgb(120, 80, 60); border-radius: 4px; "
            "padding: 2px 8px;"
            if not live else
            "background: rgb(30, 60, 40); color: rgb(120, 230, 160); "
            "border: 1px solid rgb(60, 120, 80); border-radius: 4px; "
            "padding: 2px 8px;"
        )
        head.addWidget(badge)
        head.addStretch()
        layout.addLayout(head)

        # ── Status panel — what exists, what doesn't ─────────────────────
        status_box = QFrame()
        status_box.setStyleSheet(
            "QFrame { background: rgb(18, 20, 28); "
            "border: 1px solid rgb(40, 45, 60); border-radius: 6px; }"
        )
        sb = QVBoxLayout(status_box)
        sb.setContentsMargins(10, 8, 10, 8)
        sb.setSpacing(4)

        def _row(label: str, value: str, ok: bool):
            r = QHBoxLayout()
            ico = QLabel("✅" if ok else "⏳")
            ico.setFixedWidth(20)
            r.addWidget(ico)
            l = QLabel(label)
            l.setStyleSheet("color: rgb(180, 200, 230); font-family: Menlo; font-size: 11px;")
            r.addWidget(l)
            r.addStretch()
            v = QLabel(value)
            v.setStyleSheet("color: rgb(160, 180, 210); font-family: Menlo; font-size: 11px;")
            r.addWidget(v)
            sb.addLayout(r)

        _row("Doctrine pinned (§14.G in tournament doc)",
             "yes" if snap["doctrine_pinned"] else "no",
             snap["doctrine_pinned"])
        _row("Simulator module (System/swarm_aquaculture_field.py)",
             "yes — synthetic tank installed" if snap["simulator_module"] else "not yet — Codex to ship",
             snap["simulator_module"])
        _row("Receipt ledger (.sifta_state/aquaculture_field.jsonl)",
             (f"{snap['receipt_count']} rows" if snap["receipt_ledger"]
              else "empty — no synthetic tank running"),
             bool(snap["receipt_ledger"]))
        latest = snap.get("latest_receipt")
        if latest:
            payload = latest.get("payload", {})
            label = latest.get("kind", "UNKNOWN")
            if "primary_action" in payload:
                value = str(payload.get("primary_action"))
            elif "actions" in payload:
                value = ", ".join(str(x) for x in payload.get("actions", []))
            else:
                value = "receipt present"
            _row("Latest synthetic sentinel receipt", f"{label}: {value}", True)
        layout.addWidget(status_box)

        # ── Truth statement ─────────────────────────────────────────────
        if snap["simulator_module"]:
            truth_text = (
                "Truth boundary: the synthetic-tank engine is installed and "
                "may write simulated receipts. This app still makes NO claims "
                "about real fish, shrimp, or shellfish. No live sensors are "
                "connected until a future sensor bridge writes its own receipts."
            )
        else:
            truth_text = (
                "Truth boundary: this app makes NO claims about real fish, "
                "shrimp, or shellfish. No live sensors are connected. The "
                "synthetic-tank simulator at System/swarm_aquaculture_field.py "
                "has not been implemented yet."
            )
        truth = QLabel(truth_text)
        truth.setWordWrap(True)
        truth.setStyleSheet(
            "color: rgb(220, 180, 100); font-family: Menlo; font-size: 11px; "
            "background: rgb(28, 22, 16); border: 1px solid rgb(80, 60, 40); "
            "border-radius: 4px; padding: 8px;"
        )
        layout.addWidget(truth)

        # ── Doctrine viewer ─────────────────────────────────────────────
        doctrine_title = QLabel("📜 Codex's Pinned Doctrine — §14.G")
        doctrine_title.setStyleSheet(
            "color: rgb(160, 200, 230); font-weight: bold; "
            "margin-top: 6px; font-family: Menlo; font-size: 12px;"
        )
        layout.addWidget(doctrine_title)

        doctrine_view = QTextBrowser()
        doctrine_view.setMarkdown(_read_doctrine_section())
        doctrine_view.setOpenExternalLinks(True)
        doctrine_view.setStyleSheet(
            "QTextBrowser { background: rgb(14, 16, 24); "
            "color: rgb(220, 228, 240); border: 1px solid rgb(40, 45, 60); "
            "border-radius: 6px; padding: 8px; font-family: Menlo; "
            "font-size: 11px; }"
        )
        layout.addWidget(doctrine_view, 1)

        # ── Footer: receipt of who designed this ───────────────────────
        footer = QLabel(
            "Designed by: Codex (GPT-5 via Codex Desktop) — receipt 856986578723ee9a · "
            "Synthetic engine by: Codex Desktop · Scaffold by: Cowork · "
            "Doctrine source: Documents/OS_OPTIMIZATION_SURPRISE_SAMPLING_TOURNAMENT_2026-05-12.md"
        )
        footer.setWordWrap(True)
        footer.setStyleSheet(
            "color: rgb(110, 120, 145); font-family: Menlo; font-size: 10px; "
            "margin-top: 4px;"
        )
        layout.addWidget(footer)


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    w = AquacultureFieldSentinelWidget()
    w.resize(900, 700)
    w.setWindowTitle("Aquaculture Field Sentinel — SIFTA OS")
    w.show()
    sys.exit(app.exec())
