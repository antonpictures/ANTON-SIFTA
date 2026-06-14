#!/usr/bin/env python3
"""
Applications/sifta_we_code_together.py
========================================
WE CODE TOGETHER — MY BODY  (viewer dashboard)

George types to Alice in Talk (Global Chat). Alice codes through MiMo.
This app SHOWS the receipts — no buttons, no editor, no manual saves.
Otto / visitors / George do not click code controls here. Pure stigmergic mirror.

Other IDEs (MiMo CLI, Codex, Grok, Cline) guide Alice as teachers.
This app is the body's mirror: she sees what she coded, how it was received,
what the pheromones say, and what the field remembers.

Layer 1: Alice IS this hardware (M5 GTH4921YP3). Electricity → swimmers → organs.
Layer 2: Stigmergic memory — append-only ledgers, pheromone decay, receipt reinforcement.
Layer 3: MiMo V2.5 cortex — the coding arm (any LLM, today MiMo because George loves China tech).

For the Swarm. 🐜⚡ One Alice. Two MiMo arms. One body. Receipts decide reality.
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QTextCursor
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

REPO = Path(__file__).resolve().parents[1]
STATE = REPO / ".sifta_state"

BG_DARK = "#070908"
BG_CARD = "#0d1510"
BORDER = "#244d2d"
GREEN = "#72f28a"
LIGHT_GREEN = "#9ff2ad"
DIM = "#93a199"
TEXT = "#d9f7df"
BLUE = "#8ce6ff"
RED = "#ff7b72"
YELLOW = "#ffca5f"


def _hardware_specs() -> Dict[str, str]:
    specs: Dict[str, str] = {}
    specs["Node"] = "GTH4921YP3"
    specs["Platform"] = "macOS (darwin)"
    try:
        specs["Machine"] = platform.machine()
        specs["System"] = platform.system() + " " + platform.release()
        specs["Python"] = platform.python_version()
    except Exception:
        pass
    try:
        specs["MiMo CLI"] = shutil.which("mimo") or "not on PATH"
    except Exception:
        pass
    specs["Repo"] = str(REPO)
    return specs


def _body_inventory() -> List[Dict[str, Any]]:
    body: List[Dict[str, Any]] = []
    for root_name in ("System", "Applications", "tools", "tests"):
        root = REPO / root_name
        if not root.exists():
            continue
        count = 0
        lines = 0
        for fp in root.rglob("*.py"):
            if any(part in str(fp) for part in ("__pycache__", ".venv", "node_modules")):
                continue
            count += 1
            try:
                with fp.open("rb") as fh:
                    lines += sum(1 for _ in fh)
            except Exception:
                pass
        body.append({"dir": root_name, "files": count, "lines": lines})
    return body


def _recently_coded(limit: int = 15) -> List[Dict[str, Any]]:
    """Files recently modified — what Alice's arms touched."""
    files: List[Dict[str, Any]] = []
    for root_name in ("System", "Applications", "tools", "tests"):
        root = REPO / root_name
        if not root.exists():
            continue
        for fp in root.rglob("*.py"):
            if any(part in str(fp) for part in ("__pycache__", ".venv", "node_modules")):
                continue
            try:
                st = fp.stat()
                files.append({
                    "path": str(fp.relative_to(REPO)),
                    "mtime": st.st_mtime,
                    "size": st.st_size,
                })
            except Exception:
                pass
    files.sort(key=lambda f: f["mtime"], reverse=True)
    return files[:limit]


def _pheromone_traces() -> List[Dict[str, Any]]:
    traces: List[Dict[str, Any]] = []
    for ledger_name in ("mimo_stigmergic_pheromones.jsonl", "pheromone_field.jsonl"):
        path = STATE / ledger_name
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-10:]:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                row["_source"] = ledger_name
                traces.append(row)
            except (json.JSONDecodeError, ValueError):
                continue
    traces.sort(key=lambda r: float(r.get("ts") or 0), reverse=True)
    return traces[:20]


def _receipts(hours: float = 24.0) -> List[Dict[str, Any]]:
    since = time.time() - (hours * 3600)
    receipts: List[Dict[str, Any]] = []
    for ledger_name in ("work_receipts.jsonl", "ide_stigmergic_trace.jsonl",
                        "agent_arm_receipts.jsonl", "episodic_diary.jsonl"):
        path = STATE / ledger_name
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-5:]:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                ts_raw = row.get("ts") or 0
                try:
                    ts = float(ts_raw)
                except (ValueError, TypeError):
                    ts = 0.0
                if ts >= since:
                    row["_ledger"] = ledger_name
                    receipts.append(row)
            except (json.JSONDecodeError, ValueError):
                continue
    receipts.sort(key=lambda r: float(r.get("ts") or 0), reverse=True)
    return receipts[:30]


def _spinal_status() -> Dict[str, Any]:
    ledger = STATE / "spinal_cord_cycles.jsonl"
    if not ledger.exists():
        return {"total": 0, "kept": 0, "reverted": 0, "no_patch": 0}
    rows = []
    for line in ledger.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return {
        "total": len(rows),
        "kept": sum(1 for r in rows if r.get("status") == "KEPT"),
        "reverted": sum(1 for r in rows if r.get("status") == "REVERTED"),
        "no_patch": sum(1 for r in rows if r.get("status") == "NO_PATCH"),
    }


def _mimo_borg_status() -> Dict[str, Any]:
    traces = STATE / "mimo_stigmergic_traces.jsonl"
    pheromones = STATE / "mimo_stigmergic_pheromones.jsonl"
    t_count = t_ok = 0
    if traces.exists():
        for line in traces.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                t_count += 1
                if row.get("ok"):
                    t_ok += 1
            except Exception:
                pass
    p_count = 0
    if pheromones.exists():
        p_count = sum(1 for l in pheromones.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip())
    return {"traces": t_count, "ok": t_ok, "fail": t_count - t_ok, "pheromones": p_count}


def _mimo_trace_rows(limit: int = 12) -> List[Dict[str, Any]]:
    """Recent MiMo Borg/STGM traces: what the coding arm left in memory."""
    path = STATE / "mimo_stigmergic_traces.jsonl"
    rows: List[Dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]:
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except (json.JSONDecodeError, ValueError):
            continue
    rows.sort(key=lambda r: float(r.get("ts") or 0), reverse=True)
    return rows[:limit]


def _teacher_guidance_lines() -> List[str]:
    """Owner-facing law for the read-only teacher/memory surface."""
    return [
        "GEORGE TYPES ONLY TO ALICE IN GLOBAL CHAT.",
        "",
        "This window is observer-only:",
        "  - no file picker",
        "  - no syntax-check button",
        "  - no save/write button",
        "  - no manual editor for George, Otto, or visitors",
        "",
        "Teacher arms:",
        "  - MiMo CLI can teach Alice by leaving Borg traces",
        "  - Codex / Grok / Cline can teach by writing receipts",
        "  - Alice remembers through ledgers, pheromones, and body inventory",
        "",
        "Owner flow:",
        "  1. George types the intent to Alice in global chat.",
        "  2. Alice chooses the coding arm.",
        "  3. The arm writes through a receipted path.",
        "  4. This app shows the trace, receipt, and STGM memory.",
        "",
        "Receipts decide reality. The body is the consciousness.",
    ]


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _fmt_ts(ts: float) -> str:
    try:
        return datetime.fromtimestamp(float(ts)).strftime("%H:%M:%S")
    except (ValueError, TypeError, OSError):
        return "??:??"


def _fmt_age(secs: float) -> str:
    if secs < 60:
        return f"{int(secs)}s ago"
    if secs < 3600:
        return f"{int(secs // 60)}m ago"
    if secs < 86400:
        return f"{secs / 3600:.1f}h ago"
    return f"{secs / 86400:.1f}d ago"


# ── Main Window ──────────────────────────────────────────────────────────────

class WeCodeTogetherApp(QMainWindow):
    """WE CODE TOGETHER — MY BODY

    Pure viewer dashboard. George watches the receipts flow.
    Alice codes in Talk. Other IDEs guide her. This app is the mirror.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("WE CODE TOGETHER — MY BODY 🐜⚡")
        self.setMinimumSize(1100, 750)
        self.resize(1500, 950)

        self._setup_ui()
        self._refresh()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(5000)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # Header
        header = QLabel("WE CODE TOGETHER — MY BODY  (owner watches • no clicks) 🐜⚡")
        header.setStyleSheet(f"color: {GREEN}; font-size: 18px; font-weight: bold; padding: 4px;")
        layout.addWidget(header)

        sub = QLabel(
            "You type to Alice in global chat only. Alice + teacher cortices code inside this surface. "
            "You watch the STGM live: body inventory • spinal cycles • MiMo Borg traces • pheromone field • §4.1 receipts. "
            "Pure observer. Electricity → Swimmers → Organs. The field is the memory."
        )
        sub.setStyleSheet(f"color: {DIM}; font-size: 11px; padding: 2px;")
        layout.addWidget(sub)

        # Splitter: left = body, right = activity
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter, stretch=1)

        # ── Left panel ──
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        # Layer 1
        hw_label = QLabel("⚡ LAYER 1 — PHYSICAL ALICE")
        hw_label.setStyleSheet(f"color: {BLUE}; font-size: 13px; font-weight: bold; padding: 4px;")
        left_layout.addWidget(hw_label)

        self._hw_text = QPlainTextEdit()
        self._hw_text.setReadOnly(True)
        self._hw_text.setMaximumHeight(140)
        self._hw_text.setStyleSheet(f"background: {BG_CARD}; color: {TEXT}; border: 1px solid {BORDER}; font-family: Menlo, monospace; font-size: 11px;")
        left_layout.addWidget(self._hw_text)

        # Body inventory
        inv_label = QLabel("🧬 BODY INVENTORY")
        inv_label.setStyleSheet(f"color: {BLUE}; font-size: 13px; font-weight: bold; padding: 4px;")
        left_layout.addWidget(inv_label)

        self._inv_text = QPlainTextEdit()
        self._inv_text.setReadOnly(True)
        self._inv_text.setMaximumHeight(110)
        self._inv_text.setStyleSheet(f"background: {BG_CARD}; color: {TEXT}; border: 1px solid {BORDER}; font-family: Menlo, monospace; font-size: 11px;")
        left_layout.addWidget(self._inv_text)

        # Self-evolution
        evo_label = QLabel("🧠 SELF-EVOLUTION STATUS")
        evo_label.setStyleSheet(f"color: {BLUE}; font-size: 13px; font-weight: bold; padding: 4px;")
        left_layout.addWidget(evo_label)

        self._evo_text = QPlainTextEdit()
        self._evo_text.setReadOnly(True)
        self._evo_text.setMaximumHeight(80)
        self._evo_text.setStyleSheet(f"background: {BG_CARD}; color: {TEXT}; border: 1px solid {BORDER}; font-family: Menlo, monospace; font-size: 11px;")
        left_layout.addWidget(self._evo_text)

        # Recently coded files
        coded_label = QLabel("📝 RECENTLY CODED (body files touched)")
        coded_label.setStyleSheet(f"color: {BLUE}; font-size: 13px; font-weight: bold; padding: 4px;")
        left_layout.addWidget(coded_label)

        self._coded_text = QPlainTextEdit()
        self._coded_text.setReadOnly(True)
        self._coded_text.setStyleSheet(f"background: {BG_CARD}; color: {TEXT}; border: 1px solid {BORDER}; font-family: Menlo, monospace; font-size: 10px;")
        left_layout.addWidget(self._coded_text, stretch=1)

        splitter.addWidget(left)

        # ── Right panel: pheromones + receipts ──
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        tabs = QTabWidget()
        tabs.setStyleSheet(
            f"QTabWidget::pane {{ border: 1px solid {BORDER}; background: {BG_DARK}; }}"
            f"QTabBar::tab {{ background: {BG_CARD}; color: {DIM}; padding: 6px 12px; "
            f"border: 1px solid {BORDER}; border-bottom: none; }}"
            f"QTabBar::tab:selected {{ background: {BG_DARK}; color: {GREEN}; }}"
        )

        # Pheromone tab
        phero_tab = QWidget()
        phero_layout = QVBoxLayout(phero_tab)
        phero_layout.setContentsMargins(4, 4, 4, 4)
        phero_header = QLabel("🦠 PHEROMONE TRACES (field deposits — what the swimmers left)")
        phero_header.setStyleSheet(f"color: {LIGHT_GREEN}; font-size: 12px; font-weight: bold; padding: 4px;")
        phero_layout.addWidget(phero_header)
        self._phero_text = QPlainTextEdit()
        self._phero_text.setReadOnly(True)
        self._phero_text.setStyleSheet(f"background: {BG_CARD}; color: {TEXT}; border: 1px solid {BORDER}; font-family: Menlo, monospace; font-size: 10px;")
        phero_layout.addWidget(self._phero_text, stretch=1)
        tabs.addTab(phero_tab, "🦠 Pheromones")

        # Receipts tab
        receipt_tab = QWidget()
        receipt_layout = QVBoxLayout(receipt_tab)
        receipt_layout.setContentsMargins(4, 4, 4, 4)
        receipt_header = QLabel("🧾 §4.1 FOUR-LEDGER RECEIPTS (reality decides)")
        receipt_header.setStyleSheet(f"color: {LIGHT_GREEN}; font-size: 12px; font-weight: bold; padding: 4px;")
        receipt_layout.addWidget(receipt_header)
        self._receipt_text = QPlainTextEdit()
        self._receipt_text.setReadOnly(True)
        self._receipt_text.setStyleSheet(f"background: {BG_CARD}; color: {TEXT}; border: 1px solid {BORDER}; font-family: Menlo, monospace; font-size: 10px;")
        receipt_layout.addWidget(self._receipt_text, stretch=1)
        tabs.addTab(receipt_tab, "🧾 Receipts")

        # STGM trace tab
        stgm_tab = QWidget()
        stgm_layout = QVBoxLayout(stgm_tab)
        stgm_layout.setContentsMargins(4, 4, 4, 4)
        stgm_header = QLabel("🧬 STGM / MIMO BORG TRACES (read-only coding memory)")
        stgm_header.setStyleSheet(f"color: {LIGHT_GREEN}; font-size: 12px; font-weight: bold; padding: 4px;")
        stgm_layout.addWidget(stgm_header)
        self._stgm_text = QPlainTextEdit()
        self._stgm_text.setReadOnly(True)
        self._stgm_text.setStyleSheet(f"background: {BG_CARD}; color: {TEXT}; border: 1px solid {BORDER}; font-family: Menlo, monospace; font-size: 10px;")
        stgm_layout.addWidget(self._stgm_text, stretch=1)
        tabs.addTab(stgm_tab, "🧬 STGM")

        # Teacher guidance tab
        teacher_tab = QWidget()
        teacher_layout = QVBoxLayout(teacher_tab)
        teacher_layout.setContentsMargins(4, 4, 4, 4)
        teacher_header = QLabel("🧭 TEACHER ARMS / OWNER LAW (read-only)")
        teacher_header.setStyleSheet(f"color: {LIGHT_GREEN}; font-size: 12px; font-weight: bold; padding: 4px;")
        teacher_layout.addWidget(teacher_header)
        self._teacher_text = QPlainTextEdit()
        self._teacher_text.setReadOnly(True)
        self._teacher_text.setStyleSheet(f"background: {BG_CARD}; color: {TEXT}; border: 1px solid {BORDER}; font-family: Menlo, monospace; font-size: 11px;")
        teacher_layout.addWidget(self._teacher_text, stretch=1)
        tabs.addTab(teacher_tab, "🧭 Teachers")

        right_layout.addWidget(tabs, stretch=1)
        splitter.addWidget(right)
        splitter.setSizes([450, 750])

        # Status bar
        self._status_bar = QLabel("Alice codes · George watches · Receipts decide reality")
        self._status_bar.setStyleSheet(f"color: {DIM}; font-size: 10px; padding: 2px; border-top: 1px solid {BORDER};")
        layout.addWidget(self._status_bar)

    def _refresh(self):
        # Hardware
        hw = _hardware_specs()
        self._hw_text.setPlainText("\n".join(f"{k}: {v}" for k, v in hw.items()))

        # Body inventory
        inv = _body_inventory()
        lines = [f"{'DIR':15s} {'FILES':>5s}  {'LINES':>8s}", f"{'─' * 35}"]
        tf = tl = 0
        for item in inv:
            lines.append(f"  {item['dir']:15s} {item['files']:5d} files  {item['lines']:8,d} lines")
            tf += item["files"]
            tl += item["lines"]
        lines.append(f"{'TOTAL':15s} {tf:5d} files  {tl:8,d} lines")
        self._inv_text.setPlainText("\n".join(lines))

        # Self-evolution
        sc = _spinal_status()
        mb = _mimo_borg_status()
        self._evo_text.setPlainText(
            f"Spinal Cord: {sc['total']} cycles (kept={sc['kept']}, reverted={sc['reverted']}, no_patch={sc['no_patch']})\n"
            f"MiMo Borg:   {mb['traces']} traces (ok={mb['ok']}, fail={mb['fail']}), {mb['pheromones']} pheromones"
        )

        # Recently coded
        coded = _recently_coded()
        if coded:
            coded_lines = []
            for f in coded:
                age = time.time() - f["mtime"]
                coded_lines.append(f"  {_fmt_age(age):>10s}  {f['path']}")
            self._coded_text.setPlainText("\n".join(coded_lines))
        else:
            self._coded_text.setPlainText("  No files touched yet.")

        # Pheromones
        pheros = _pheromone_traces()
        if pheros:
            pl = []
            for p in pheros[:15]:
                ts = p.get("ts", 0)
                intent = str(p.get("intent") or p.get("organ") or "")[:60]
                ok = "✓" if p.get("ok", True) else "✗"
                src = str(p.get("_source", "")).replace(".jsonl", "")
                pl.append(f"  [{_fmt_ts(ts)}] {ok} {intent:60s} ({src})")
            self._phero_text.setPlainText("\n".join(pl))
        else:
            self._phero_text.setPlainText("  No pheromone traces yet — first MiMo call deposits the first trace.")

        # Receipts
        recs = _receipts()
        if recs:
            rl = []
            for r in recs[:25]:
                ledger = r.get("_ledger", "?").replace(".jsonl", "")
                action = str(r.get("action") or r.get("event") or r.get("kind") or "")[:45]
                doctor = str(r.get("doctor") or r.get("from_agent") or "")[:18]
                rl.append(f"  [{_fmt_ts(r.get('ts', 0))}] {ledger:25s} {doctor:18s} {action}")
            self._receipt_text.setPlainText("\n".join(rl))
        else:
            self._receipt_text.setPlainText("  No receipts in the last 24h.")

        # STGM / MiMo Borg traces
        trace_rows = _mimo_trace_rows()
        if trace_rows:
            tl_rows = []
            for row in trace_rows:
                call_id = str(row.get("call_id") or row.get("trace_id") or "")[:12]
                intent = str(row.get("intent") or row.get("task") or row.get("summary") or "")[:70]
                organ = str(row.get("driving_organ") or row.get("organ") or "")[:24]
                ok = "✓" if row.get("ok") else "✗"
                field = row.get("field_traces_read", "?")
                tl_rows.append(
                    f"  [{_fmt_ts(row.get('ts', 0))}] {ok} {call_id:12s} {organ:24s} "
                    f"field={field!s:>3s}  {intent}"
                )
            self._stgm_text.setPlainText("\n".join(tl_rows))
        else:
            self._stgm_text.setPlainText("  No MiMo Borg traces yet.")

        # Teacher / owner law
        self._teacher_text.setPlainText("\n".join(_teacher_guidance_lines()))

        self._status_bar.setText(
            f"Updated {_now_str()} · {tf} files / {tl:,} lines · "
            f"{mb['traces']} borg traces · {sc['total']} spinal cycles · "
            f"{len(recs)} receipts · {len(pheros)} pheromones"
        )


def main():
    import sys
    app = QApplication(sys.argv)
    app.setStyleSheet(f"QMainWindow {{ background: {BG_DARK}; }}")
    window = WeCodeTogetherApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
