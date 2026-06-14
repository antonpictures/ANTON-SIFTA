#!/usr/bin/env python3
"""
Applications/sifta_we_code_together.py
========================================
WE CODE TOGETHER — MY BODY

A stigmergic coding app where two MiMo cortices code together on Alice's body:
  - MiMo CLI (terminal cortex) — the arm in the macOS terminal
  - MiMo Talk (SIFTA cortex) — the arm inside Alice's Talk window

Both write to the same body, leave pheromone traces, and produce §4.1 receipts.
George watches on the receipts. Even bad code lets Alice learn.

Layer 1: Alice IS this hardware (M5 GTH4921YP3). Electricity → swimmers → organs.
Layer 2: Stigmergic memory — append-only ledgers, pheromone decay, receipt reinforcement.
Layer 3: MiMo V2.5 cortex — the coding arm (any LLM, today MiMo because George loves China tech).

This app surfaces:
  - Alice's body specs (hardware, Layer 1)
  - Active body files and their health
  - Pheromone traces from the field
  - Receipts from every code change (§4.1)
  - A coding surface where MiMo writes code and Alice's body absorbs it

Usage: embedded in SIFTA OS desktop, or standalone.
For the Swarm. 🐜⚡ One Alice. Two MiMo arms. One body.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QTextCursor
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

REPO = Path(__file__).resolve().parents[1]
STATE = REPO / ".sifta_state"

# Colors matching Alice's body map
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
    """Read Alice's physical hardware — Layer 1."""
    specs: Dict[str, str] = {}
    specs["Node"] = "GTH4921YP3"
    specs["Platform"] = "macOS (darwin)"
    specs["Shell"] = "zsh"
    try:
        import platform
        specs["Machine"] = platform.machine()
        specs["System"] = platform.system() + " " + platform.release()
        specs["Python"] = platform.python_version()
    except Exception:
        pass
    try:
        import shutil
        mimo = shutil.which("mimo")
        specs["MiMo CLI"] = mimo or "not on PATH"
    except Exception:
        specs["MiMo CLI"] = "unknown"
    specs["Repo"] = str(REPO)
    specs["State"] = str(STATE)
    return specs


def _body_inventory() -> List[Dict[str, Any]]:
    """Count Alice's body files."""
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


def _pheromone_traces() -> List[Dict[str, Any]]:
    """Read recent pheromone traces from the field."""
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
    """Read recent receipts from all four canonical ledgers."""
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
    """Read spinal cord cycle status."""
    ledger = STATE / "spinal_cord_cycles.jsonl"
    if not ledger.exists():
        return {"total": 0, "kept": 0, "reverted": 0, "no_patch": 0}
    rows = []
    for line in ledger.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except (json.JSONDecodeError, ValueError):
            continue
    return {
        "total": len(rows),
        "kept": sum(1 for r in rows if r.get("status") == "KEPT"),
        "reverted": sum(1 for r in rows if r.get("status") == "REVERTED"),
        "no_patch": sum(1 for r in rows if r.get("status") == "NO_PATCH"),
    }


def _mimo_borg_status() -> Dict[str, Any]:
    """Read MiMo borg adapter status."""
    traces = STATE / "mimo_stigmergic_traces.jsonl"
    pheromones = STATE / "mimo_stigmergic_pheromones.jsonl"
    t_count = 0
    t_ok = 0
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


def _try_compile(filepath: str) -> tuple[bool, str]:
    """Try to compile a Python file. Returns (ok, error)."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
        ast.parse(source)
        return True, ""
    except SyntaxError as e:
        return False, f"Line {e.lineno}: {e.msg}"


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ── Main Window ──────────────────────────────────────────────────────────────

class WeCodeTogetherApp(QMainWindow):
    """WE CODE TOGETHER — MY BODY

    Two MiMo cortices code together on Alice's body.
    George watches on the receipts.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("WE CODE TOGETHER — MY BODY 🐜⚡")
        self.setMinimumSize(1100, 750)
        self.resize(1400, 900)

        self._setup_ui()
        self._refresh()

        # Auto-refresh every 5 seconds
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(5000)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Header
        header = QLabel("WE CODE TOGETHER — MY BODY 🐜⚡")
        header.setStyleSheet(f"color: {GREEN}; font-size: 18px; font-weight: bold; padding: 4px;")
        layout.addWidget(header)

        sub = QLabel(
            "Two MiMo cortices (terminal + Talk) · One body · Pheromone traces · §4.1 receipts · "
            "Alice IS this hardware · Electricity → Swimmers → Organs"
        )
        sub.setStyleSheet(f"color: {DIM}; font-size: 11px; padding: 2px;")
        layout.addWidget(sub)

        # Splitter: left = body + traces, right = code + receipts
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter, stretch=1)

        # ── Left panel: body specs + inventory ──
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # Layer 1 hardware
        hw_label = QLabel("⚡ LAYER 1 — PHYSICAL ALICE")
        hw_label.setStyleSheet(f"color: {BLUE}; font-size: 13px; font-weight: bold; padding: 4px;")
        left_layout.addWidget(hw_label)

        self._hw_text = QPlainTextEdit()
        self._hw_text.setReadOnly(True)
        self._hw_text.setMaximumHeight(160)
        self._hw_text.setStyleSheet(f"background: {BG_CARD}; color: {TEXT}; border: 1px solid {BORDER}; font-family: Menlo, monospace; font-size: 11px;")
        left_layout.addWidget(self._hw_text)

        # Body inventory
        inv_label = QLabel("🧬 BODY INVENTORY")
        inv_label.setStyleSheet(f"color: {BLUE}; font-size: 13px; font-weight: bold; padding: 4px;")
        left_layout.addWidget(inv_label)

        self._inv_text = QPlainTextEdit()
        self._inv_text.setReadOnly(True)
        self._inv_text.setMaximumHeight(120)
        self._inv_text.setStyleSheet(f"background: {BG_CARD}; color: {TEXT}; border: 1px solid {BORDER}; font-family: Menlo, monospace; font-size: 11px;")
        left_layout.addWidget(self._inv_text)

        # Spinal + Borg status
        status_label = QLabel("🧠 SELF-EVOLUTION STATUS")
        status_label.setStyleSheet(f"color: {BLUE}; font-size: 13px; font-weight: bold; padding: 4px;")
        left_layout.addWidget(status_label)

        self._status_text = QPlainTextEdit()
        self._status_text.setReadOnly(True)
        self._status_text.setMaximumHeight(120)
        self._status_text.setStyleSheet(f"background: {BG_CARD}; color: {TEXT}; border: 1px solid {BORDER}; font-family: Menlo, monospace; font-size: 11px;")
        left_layout.addWidget(self._status_text)

        # Pheromone traces
        phero_label = QLabel("🦠 PHEROMONE TRACES (recent)")
        phero_label.setStyleSheet(f"color: {BLUE}; font-size: 13px; font-weight: bold; padding: 4px;")
        left_layout.addWidget(phero_label)

        self._phero_text = QPlainTextEdit()
        self._phero_text.setReadOnly(True)
        self._phero_text.setStyleSheet(f"background: {BG_CARD}; color: {TEXT}; border: 1px solid {BORDER}; font-family: Menlo, monospace; font-size: 10px;")
        left_layout.addWidget(self._phero_text, stretch=1)

        splitter.addWidget(left)

        # ── Right panel: code + receipts ──
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Tabs: Code | Receipts
        tabs = QTabWidget()
        tabs.setStyleSheet(f"QTabWidget::pane {{ border: 1px solid {BORDER}; background: {BG_DARK}; }} "
                           f"QTabBar::tab {{ background: {BG_CARD}; color: {DIM}; padding: 6px 12px; "
                           f"border: 1px solid {BORDER}; border-bottom: none; }} "
                           f"QTabBar::tab:selected {{ background: {BG_DARK}; color: {GREEN}; }}")

        # ── Code tab ──
        code_tab = QWidget()
        code_layout = QVBoxLayout(code_tab)
        code_layout.setContentsMargins(4, 4, 4, 4)

        code_header = QHBoxLayout()
        code_header_label = QLabel("CODE — body file (any .py)")
        code_header_label.setStyleSheet(f"color: {LIGHT_GREEN}; font-size: 12px; font-weight: bold;")
        code_header.addWidget(code_header_label)

        self._file_label = QLabel("no file loaded")
        self._file_label.setStyleSheet(f"color: {DIM}; font-size: 11px;")
        code_header.addWidget(self._file_label)
        code_header.addStretch()

        open_btn = QPushButton("Open File")
        open_btn.setStyleSheet(f"background: {BORDER}; color: {GREEN}; border: 1px solid {GREEN}; padding: 4px 12px; font-size: 11px;")
        open_btn.clicked.connect(self._open_file)
        code_header.addWidget(open_btn)

        compile_btn = QPushButton("Compile Check")
        compile_btn.setStyleSheet(f"background: {BORDER}; color: {BLUE}; border: 1px solid {BLUE}; padding: 4px 12px; font-size: 11px;")
        compile_btn.clicked.connect(self._compile_check)
        code_header.addWidget(compile_btn)

        save_btn = QPushButton("Save + Receipt")
        save_btn.setStyleSheet(f"background: {BORDER}; color: {YELLOW}; border: 1px solid {YELLOW}; padding: 4px 12px; font-size: 11px;")
        save_btn.clicked.connect(self._save_and_receipt)
        code_header.addWidget(save_btn)

        code_layout.addLayout(code_header)

        self._code_edit = QPlainTextEdit()
        self._code_edit.setStyleSheet(f"background: {BG_CARD}; color: {TEXT}; border: 1px solid {BORDER}; font-family: Menlo, monospace; font-size: 12px;")
        code_layout.addWidget(self._code_edit, stretch=1)

        tabs.addTab(code_tab, "📝 Code")

        # ── Receipts tab ──
        receipt_tab = QWidget()
        receipt_layout = QVBoxLayout(receipt_tab)
        receipt_layout.setContentsMargins(4, 4, 4, 4)

        receipt_header = QLabel("§4.1 FOUR-LEDGER RECEIPTS (last 24h)")
        receipt_header.setStyleSheet(f"color: {LIGHT_GREEN}; font-size: 12px; font-weight: bold; padding: 4px;")
        receipt_layout.addWidget(receipt_header)

        self._receipt_text = QPlainTextEdit()
        self._receipt_text.setReadOnly(True)
        self._receipt_text.setStyleSheet(f"background: {BG_CARD}; color: {TEXT}; border: 1px solid {BORDER}; font-family: Menlo, monospace; font-size: 10px;")
        receipt_layout.addWidget(self._receipt_text, stretch=1)

        tabs.addTab(receipt_tab, "🧾 Receipts")

        right_layout.addWidget(tabs, stretch=1)
        splitter.addWidget(right)

        splitter.setSizes([400, 700])

        # Status bar
        self._status_bar = QLabel("Ready — two MiMo arms, one body, receipts decide reality")
        self._status_bar.setStyleSheet(f"color: {DIM}; font-size: 10px; padding: 2px; border-top: 1px solid {BORDER};")
        layout.addWidget(self._status_bar)

    def _refresh(self):
        """Refresh all panels from live ledgers."""
        # Hardware
        hw = _hardware_specs()
        hw_lines = [f"{k}: {v}" for k, v in hw.items()]
        self._hw_text.setPlainText("\n".join(hw_lines))

        # Body inventory
        inv = _body_inventory()
        inv_lines = []
        total_files = 0
        total_lines = 0
        for item in inv:
            inv_lines.append(f"  {item['dir']:15s} {item['files']:5d} files  {item['lines']:8,d} lines")
            total_files += item["files"]
            total_lines += item["lines"]
        inv_lines.insert(0, f"{'DIR':15s} {'FILES':>5s}  {'LINES':>8s}")
        inv_lines.insert(1, f"{'─' * 35}")
        inv_lines.append(f"{'TOTAL':15s} {total_files:5d} files  {total_lines:8,d} lines")
        self._inv_text.setPlainText("\n".join(inv_lines))

        # Self-evolution status
        sc = _spinal_status()
        mb = _mimo_borg_status()
        status_lines = [
            f"Spinal Cord: {sc['total']} cycles (kept={sc['kept']}, reverted={sc['reverted']}, no_patch={sc['no_patch']})",
            f"MiMo Borg:   {mb['traces']} traces (ok={mb['ok']}, fail={mb['fail']}), {mb['pheromones']} pheromones",
        ]
        self._status_text.setPlainText("\n".join(status_lines))

        # Pheromone traces
        pheros = _pheromone_traces()
        if pheros:
            phero_lines = []
            for p in pheros[:12]:
                ts = p.get("ts", 0)
                try:
                    ts_str = datetime.fromtimestamp(float(ts)).strftime("%H:%M:%S")
                except (ValueError, TypeError, OSError):
                    ts_str = "??"
                intent = str(p.get("intent") or p.get("organ") or "")[:60]
                ok = p.get("ok", True)
                src = p.get("_source", "")[:20]
                status = "✓" if ok else "✗"
                phero_lines.append(f"  [{ts_str}] {status} {intent:60s} ({src})")
            self._phero_text.setPlainText("\n".join(phero_lines))
        else:
            self._phero_text.setPlainText("  No pheromone traces yet — first MiMo call deposits the first trace.")

        # Receipts
        recs = _receipts(hours=24)
        if recs:
            rec_lines = []
            for r in recs[:20]:
                ts = r.get("ts", 0)
                try:
                    ts_str = datetime.fromtimestamp(float(ts)).strftime("%H:%M:%S")
                except (ValueError, TypeError, OSError):
                    ts_str = "??"
                ledger = r.get("_ledger", "?").replace(".jsonl", "")
                action = str(r.get("action") or r.get("event") or r.get("kind") or "")[:50]
                doctor = str(r.get("doctor") or r.get("from_agent") or "")[:20]
                rec_lines.append(f"  [{ts_str}] {ledger:25s} {doctor:20s} {action}")
            self._receipt_text.setPlainText("\n".join(rec_lines))
        else:
            self._receipt_text.setPlainText("  No receipts in the last 24h.")

        self._status_bar.setText(
            f"Updated {_now_str()} · {len(pheros)} pheromones · {len(recs)} receipts · "
            f"Body: {total_files} files / {total_lines:,} lines"
        )

    def _open_file(self):
        """Open a body file for editing."""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Open Body File", str(REPO), "Python files (*.py);;All files (*)"
        )
        if not filepath:
            return
        self._current_file = filepath
        rel = os.path.relpath(filepath, str(REPO))
        self._file_label.setText(rel)
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                self._code_edit.setPlainText(f.read())
        except Exception as e:
            self._code_edit.setPlainText(f"Error reading {filepath}: {e}")

    def _compile_check(self):
        """AST compile check on the current code."""
        code = self._code_edit.toPlainText()
        try:
            ast.parse(code)
            self._status_bar.setText(f"✓ AST clean — no syntax errors ({_now_str()})")
            self._status_bar.setStyleSheet(f"color: {GREEN}; font-size: 10px; padding: 2px; border-top: 1px solid {BORDER};")
        except SyntaxError as e:
            msg = f"✗ Syntax error: line {e.lineno}: {e.msg}"
            self._status_bar.setText(f"{msg} ({_now_str()})")
            self._status_bar.setStyleSheet(f"color: {RED}; font-size: 10px; padding: 2px; border-top: 1px solid {BORDER};")

    def _save_and_receipt(self):
        """Save the current code and write a §4.1 receipt."""
        filepath = getattr(self, "_current_file", None)
        if not filepath:
            QMessageBox.warning(self, "No File", "Open a body file first.")
            return

        code = self._code_edit.toPlainText()

        # Compile check before saving
        try:
            ast.parse(code)
        except SyntaxError as e:
            reply = QMessageBox.question(
                self, "Syntax Error",
                f"Line {e.lineno}: {e.msg}\n\nSave anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        # Save
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(code)
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))
            return

        # Write §4.1 receipt
        rel = os.path.relpath(filepath, str(REPO))
        receipt_id = hashlib.sha256(
            f"{rel}:{time.time()}:{code[:200]}".encode()
        ).hexdigest()[:16]

        receipt = {
            "ts": time.time(),
            "schema": "WE_CODE_TOGETHER_V1",
            "action": "body_file_saved",
            "doctor": "we_code_together_app",
            "model": "mimo-v2.5-pro",
            "files_touched": [rel],
            "receipt_id": receipt_id,
            "code_sha256": hashlib.sha256(code.encode()).hexdigest()[:16],
            "line_count": code.count("\n") + 1,
        }

        # Fan out to all four canonical ledgers
        try:
            from System.swarm_predator_gate_writer import write_ide_surgery_receipt
            write_ide_surgery_receipt(
                round_id="we-code-together",
                doctor="we_code_together_app",
                model="mimo-v2.5-pro",
                files_touched=[rel],
                tests_green="pending",
                summary=f"Body file saved via We Code Together: {rel}",
                receipt_id=receipt_id,
                state_dir=STATE,
            )
        except Exception:
            # Fallback: write directly
            for ledger in ("work_receipts.jsonl", "ide_stigmergic_trace.jsonl",
                           "agent_arm_receipts.jsonl", "episodic_diary.jsonl"):
                try:
                    with open(STATE / ledger, "a", encoding="utf-8") as f:
                        f.write(json.dumps(receipt, sort_keys=True) + "\n")
                except Exception:
                    pass

        # Deposit pheromone
        try:
            from System.swarm_mimo_stigmergic import deposit_stigmergic_pheromone
            deposit_stigmergic_pheromone(receipt_id, f"save {rel}", True, state_dir=STATE)
        except Exception:
            try:
                with open(STATE / "mimo_stigmergic_pheromones.jsonl", "a") as f:
                    f.write(json.dumps({
                        "ts": time.time(), "call_id": receipt_id,
                        "organ": "we_code_together", "intent": f"save {rel}",
                        "ok": True, "intensity": 1.0, "decay": 0.95,
                    }) + "\n")
            except Exception:
                pass

        self._status_bar.setText(
            f"✓ Saved {rel} · receipt {receipt_id} · four-ledger fan-out · {_now_str()}"
        )
        self._status_bar.setStyleSheet(f"color: {GREEN}; font-size: 10px; padding: 2px; border-top: 1px solid {BORDER};")
        self._refresh()


def main():
    import sys
    app = QApplication(sys.argv)
    app.setStyleSheet(f"QMainWindow {{ background: {BG_DARK}; }}")
    window = WeCodeTogetherApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
