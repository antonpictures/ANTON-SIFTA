#!/usr/bin/env python3
"""
Applications/sifta_life_dashboard.py
═══════════════════════════════════════════════════════════════
SIFTA Stigmergic Life Dashboard — Contacts + Schedule + Health

Three-tab PyQt6 app that reads live stigmergic data to keep the
Architect optimized in life, health, and computing.

Tab 1: CONTACTS — WhatsApp social graph + interaction recency
Tab 2: SCHEDULE — Circadian rhythm + task queue + reminders
Tab 3: HEALTH   — Owner vitals, thermal, energy, pheromone score
═══════════════════════════════════════════════════════════════
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QTabWidget, QScrollArea, QLineEdit,
    QTextEdit, QGridLayout, QProgressBar, QComboBox,
)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont, QColor

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

# ── Palette ──────────────────────────────────────────────────────────
_BG = "#1a1a2e"
_CARD = "#16213e"
_ACCENT = "#0f3460"
_CYAN = "#00d2ff"
_GREEN = "#00e676"
_AMBER = "#ffab00"
_RED = "#ff5252"
_TEXT = "#e0e0e0"
_DIM = "#888"

_STYLE = f"""
QWidget {{ background: {_BG}; color: {_TEXT}; font-family: 'SF Mono', 'Menlo', monospace; }}
QTabWidget::pane {{ border: 1px solid {_ACCENT}; border-radius: 6px; }}
QTabBar::tab {{ background: {_CARD}; color: {_DIM}; padding: 8px 18px; margin: 2px;
               border-radius: 4px; font-size: 13px; }}
QTabBar::tab:selected {{ background: {_ACCENT}; color: {_CYAN}; font-weight: bold; }}
QLabel {{ background: transparent; }}
QPushButton {{ background: {_ACCENT}; color: {_CYAN}; border: 1px solid {_CYAN};
              border-radius: 4px; padding: 6px 14px; font-weight: bold; }}
QPushButton:hover {{ background: {_CYAN}; color: {_BG}; }}
QLineEdit {{ background: {_CARD}; color: {_TEXT}; border: 1px solid {_ACCENT};
            border-radius: 4px; padding: 6px; }}
QTextEdit {{ background: {_CARD}; color: {_TEXT}; border: 1px solid {_ACCENT};
            border-radius: 4px; padding: 6px; }}
QProgressBar {{ border: 1px solid {_ACCENT}; border-radius: 4px; text-align: center;
               background: {_CARD}; color: {_TEXT}; }}
QProgressBar::chunk {{ background: qlineargradient(x1:0, x2:1, stop:0 {_CYAN}, stop:1 {_GREEN});
                       border-radius: 3px; }}
QScrollArea {{ border: none; background: transparent; }}
QComboBox {{ background: {_CARD}; color: {_TEXT}; border: 1px solid {_ACCENT};
            border-radius: 4px; padding: 4px 8px; }}
"""


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text("utf-8")) if path.exists() else {}
    except Exception:
        return {}


def _tail_jsonl(path: Path, n: int = 20) -> list:
    try:
        lines = path.read_text("utf-8", errors="replace").strip().splitlines()
        out = []
        for line in lines[-n:]:
            try:
                out.append(json.loads(line))
            except Exception:
                pass
        return out
    except Exception:
        return []


def _ago(ts: float) -> str:
    d = time.time() - ts
    if d < 60:
        return "just now"
    if d < 3600:
        return f"{int(d/60)}m ago"
    if d < 86400:
        return f"{int(d/3600)}h ago"
    return f"{int(d/86400)}d ago"


# ═════════════════════════════════════════════════════════════════════
# TAB 1: CONTACTS
# ═════════════════════════════════════════════════════════════════════
class ContactsTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        hdr = QLabel("🌐 STIGMERGIC CONTACTS")
        hdr.setFont(QFont("Menlo", 16, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {_CYAN};")
        hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hdr)

        self.grid = QGridLayout()
        self.grid.setSpacing(8)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        inner.setLayout(self.grid)
        scroll.setWidget(inner)
        layout.addWidget(scroll)

        self._cards: list[QFrame] = []

    def refresh(self):
        # Clear old cards
        for c in self._cards:
            c.setParent(None)
            c.deleteLater()
        self._cards.clear()

        contacts = _load_json(_STATE / "whatsapp_contacts.json")
        # Get interaction history
        bridge_log = _tail_jsonl(_STATE / "whatsapp_alice_bridge.jsonl", 200)
        inbox = _tail_jsonl(_STATE / "whatsapp_inbox.jsonl", 200)

        # Count messages per contact
        msg_counts: dict[str, int] = {}
        last_seen: dict[str, float] = {}
        for row in inbox:
            name = row.get("name", "")
            if name:
                msg_counts[name] = msg_counts.get(name, 0) + 1
                ts = row.get("ts", 0)
                if ts > last_seen.get(name, 0):
                    last_seen[name] = ts

        col, row_idx = 0, 0
        for _key, info in sorted(contacts.items(), key=lambda x: x[1].get("display_name", "")):
            name = info.get("display_name", "Unknown")
            jid = info.get("jid", "")
            if not name or name == "Unknown":
                continue

            card = QFrame()
            card.setStyleSheet(f"""
                QFrame {{ background: {_CARD}; border: 1px solid {_ACCENT};
                          border-radius: 8px; padding: 10px; }}
            """)
            cl = QVBoxLayout(card)
            cl.setSpacing(4)

            # Name + emoji
            emoji = "👤"
            if "group" in jid.lower() or "@g.us" in jid:
                emoji = "👥"
            if info.get("name_locked"):
                emoji = "⭐"
            nl = QLabel(f"{emoji} {name}")
            nl.setFont(QFont("Menlo", 13, QFont.Weight.Bold))
            nl.setStyleSheet(f"color: {_CYAN};")
            cl.addWidget(nl)

            # Stats
            msgs = msg_counts.get(name, 0)
            ls = last_seen.get(name, 0)
            stat = f"📨 {msgs} msgs"
            if ls:
                stat += f"  •  🕐 {_ago(ls)}"
            sl = QLabel(stat)
            sl.setFont(QFont("Menlo", 10))
            sl.setStyleSheet(f"color: {_DIM};")
            cl.addWidget(sl)

            # Interaction bar
            bar = QProgressBar()
            bar.setMaximum(max(max(msg_counts.values(), default=1), 1))
            bar.setValue(msgs)
            bar.setFixedHeight(8)
            bar.setTextVisible(False)
            cl.addWidget(bar)

            self.grid.addWidget(card, row_idx, col)
            self._cards.append(card)
            col += 1
            if col >= 2:
                col = 0
                row_idx += 1


# ═════════════════════════════════════════════════════════════════════
# TAB 2: SCHEDULE
# ═════════════════════════════════════════════════════════════════════
class ScheduleTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        hdr = QLabel("📅 STIGMERGIC SCHEDULE")
        hdr.setFont(QFont("Menlo", 16, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {_GREEN};")
        hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hdr)

        # Circadian phase
        self.circadian_label = QLabel("☀️ Circadian Phase: loading...")
        self.circadian_label.setFont(QFont("Menlo", 13))
        layout.addWidget(self.circadian_label)

        self.energy_bar = QProgressBar()
        self.energy_bar.setMaximum(100)
        self.energy_bar.setFixedHeight(16)
        layout.addWidget(self.energy_bar)

        # Quick-add task
        add_row = QHBoxLayout()
        self.task_input = QLineEdit()
        self.task_input.setPlaceholderText("Add a task or reminder...")
        add_row.addWidget(self.task_input)
        self.priority_combo = QComboBox()
        self.priority_combo.addItems(["🟢 Low", "🟡 Med", "🔴 High"])
        add_row.addWidget(self.priority_combo)
        btn = QPushButton("+ Add")
        btn.clicked.connect(self._add_task)
        add_row.addWidget(btn)
        layout.addLayout(add_row)

        # Task list
        self.task_area = QVBoxLayout()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        inner.setLayout(self.task_area)
        scroll.setWidget(inner)
        layout.addWidget(scroll)

        self._task_widgets: list[QFrame] = []

    def _add_task(self):
        text = self.task_input.text().strip()
        if not text:
            return
        priority = self.priority_combo.currentIndex()  # 0=low, 1=med, 2=high
        task = {
            "text": text,
            "priority": priority,
            "created": time.time(),
            "done": False,
        }
        tasks_file = _STATE / "stigmergic_schedule.jsonl"
        tasks_file.parent.mkdir(parents=True, exist_ok=True)
        with tasks_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(task, ensure_ascii=False) + "\n")
        self.task_input.clear()
        self.refresh()

    def refresh(self):
        # Clear old
        for w in self._task_widgets:
            w.setParent(None)
            w.deleteLater()
        self._task_widgets.clear()

        # Circadian
        now = datetime.now()
        hour = now.hour
        if 5 <= hour < 9:
            phase, emoji, energy = "Dawn Rise", "🌅", 60
        elif 9 <= hour < 12:
            phase, emoji, energy = "Peak Focus", "☀️", 95
        elif 12 <= hour < 14:
            phase, emoji, energy = "Midday Reset", "🍽️", 70
        elif 14 <= hour < 17:
            phase, emoji, energy = "Afternoon Drive", "⚡", 85
        elif 17 <= hour < 20:
            phase, emoji, energy = "Wind Down", "🌇", 55
        elif 20 <= hour < 23:
            phase, emoji, energy = "Evening Rest", "🌙", 35
        else:
            phase, emoji, energy = "Deep Night", "🌑", 15

        self.circadian_label.setText(f"{emoji} Circadian: {phase} ({now.strftime('%H:%M')})")
        self.energy_bar.setValue(energy)

        # Load tasks
        tasks = _tail_jsonl(_STATE / "stigmergic_schedule.jsonl", 50)
        # Sort: undone first, then by priority (high first)
        undone = [t for t in tasks if not t.get("done")]
        done = [t for t in tasks if t.get("done")]
        undone.sort(key=lambda t: -t.get("priority", 0))

        for task in undone + done[-5:]:
            card = QFrame()
            is_done = task.get("done", False)
            border_color = _DIM if is_done else [_GREEN, _AMBER, _RED][task.get("priority", 0)]
            card.setStyleSheet(f"""
                QFrame {{ background: {_CARD}; border-left: 3px solid {border_color};
                          border-radius: 4px; padding: 8px; margin: 2px; }}
            """)
            cl = QHBoxLayout(card)
            priority_icons = ["🟢", "🟡", "🔴"]
            p = task.get("priority", 0)
            txt = task.get("text", "")
            created = task.get("created", 0)
            label_text = f"{priority_icons[p]} {txt}"
            if is_done:
                label_text = f"✅ ~~{txt}~~"
            tl = QLabel(label_text)
            tl.setFont(QFont("Menlo", 12))
            if is_done:
                tl.setStyleSheet(f"color: {_DIM};")
            cl.addWidget(tl, stretch=1)

            age = QLabel(_ago(created) if created else "")
            age.setFont(QFont("Menlo", 10))
            age.setStyleSheet(f"color: {_DIM};")
            cl.addWidget(age)

            if not is_done:
                done_btn = QPushButton("✓")
                done_btn.setFixedSize(30, 30)
                done_btn.clicked.connect(lambda _, t=txt: self._mark_done(t))
                cl.addWidget(done_btn)

            self.task_area.addWidget(card)
            self._task_widgets.append(card)

    def _mark_done(self, text: str):
        fp = _STATE / "stigmergic_schedule.jsonl"
        if not fp.exists():
            return
        lines = fp.read_text("utf-8").strip().splitlines()
        out = []
        marked = False
        for line in lines:
            try:
                row = json.loads(line)
                if row.get("text") == text and not row.get("done") and not marked:
                    row["done"] = True
                    row["done_ts"] = time.time()
                    marked = True
                out.append(json.dumps(row, ensure_ascii=False))
            except Exception:
                out.append(line)
        fp.write_text("\n".join(out) + "\n", encoding="utf-8")
        self.refresh()


# ═════════════════════════════════════════════════════════════════════
# TAB 3: HEALTH
# ═════════════════════════════════════════════════════════════════════
class HealthTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        hdr = QLabel("❤️ OWNER HEALTH & SYSTEM VITALS")
        hdr.setFont(QFont("Menlo", 16, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {_RED};")
        hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hdr)

        self.vitals_grid = QGridLayout()
        self.vitals_grid.setSpacing(10)
        layout.addLayout(self.vitals_grid)

        self._vital_labels: dict[str, QLabel] = {}
        vitals = [
            ("🌡️ Thermal", "thermal"), ("🔋 Battery", "battery"),
            ("💾 Memory", "memory"), ("💿 Disk", "disk"),
            ("🍄 Pheromone", "pheromone"), ("🦐 Reflex Arc", "reflex"),
            ("🐦‍⬛ Corvid", "corvid"), ("🧠 Alice Brain", "alice"),
        ]
        for i, (label, key) in enumerate(vitals):
            frame = QFrame()
            frame.setStyleSheet(f"""
                QFrame {{ background: {_CARD}; border: 1px solid {_ACCENT};
                          border-radius: 8px; padding: 12px; }}
            """)
            fl = QVBoxLayout(frame)
            nl = QLabel(label)
            nl.setFont(QFont("Menlo", 12, QFont.Weight.Bold))
            nl.setStyleSheet(f"color: {_CYAN};")
            fl.addWidget(nl)
            vl = QLabel("—")
            vl.setFont(QFont("Menlo", 20, QFont.Weight.Bold))
            fl.addWidget(vl)
            self._vital_labels[key] = vl
            self.vitals_grid.addWidget(frame, i // 2, i % 2)

        # Health log
        layout.addWidget(QLabel("📋 Recent Health Events:"))
        self.health_log = QTextEdit()
        self.health_log.setReadOnly(True)
        self.health_log.setFixedHeight(120)
        layout.addWidget(self.health_log)

    def refresh(self):
        # Thermal
        try:
            import subprocess
            r = subprocess.run(["pmset", "-g", "therm"], capture_output=True, text=True, timeout=3)
            if "Normal" in r.stdout:
                self._vital_labels["thermal"].setText("✅ Normal")
                self._vital_labels["thermal"].setStyleSheet(f"color: {_GREEN};")
            else:
                self._vital_labels["thermal"].setText("⚠️ Elevated")
                self._vital_labels["thermal"].setStyleSheet(f"color: {_AMBER};")
        except Exception:
            self._vital_labels["thermal"].setText("—")

        # Battery
        try:
            import subprocess
            r = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True, timeout=3)
            import re
            m = re.search(r"(\d+)%", r.stdout)
            if m:
                pct = int(m.group(1))
                color = _GREEN if pct > 50 else _AMBER if pct > 20 else _RED
                self._vital_labels["battery"].setText(f"{pct}%")
                self._vital_labels["battery"].setStyleSheet(f"color: {color};")
        except Exception:
            self._vital_labels["battery"].setText("—")

        # Memory
        try:
            import psutil
            mem = psutil.virtual_memory().percent
            color = _GREEN if mem < 70 else _AMBER if mem < 90 else _RED
            self._vital_labels["memory"].setText(f"{mem:.0f}%")
            self._vital_labels["memory"].setStyleSheet(f"color: {color};")
        except Exception:
            self._vital_labels["memory"].setText("—")

        # Disk
        try:
            import shutil
            usage = shutil.disk_usage("/")
            pct = (usage.used / usage.total) * 100
            color = _GREEN if pct < 80 else _AMBER if pct < 95 else _RED
            self._vital_labels["disk"].setText(f"{pct:.0f}%")
            self._vital_labels["disk"].setStyleSheet(f"color: {color};")
        except Exception:
            self._vital_labels["disk"].setText("—")

        # Pheromone
        try:
            sys.path.insert(0, str(_REPO))
            from System.swarm_adapter_pheromone_scorer import calculate_swarm_pheromone_strength
            s = calculate_swarm_pheromone_strength(max_age_s=600)
            self._vital_labels["pheromone"].setText(f"{s:.3f}")
            color = _GREEN if s > 0.1 else _AMBER if s > 0.01 else _DIM
            self._vital_labels["pheromone"].setStyleSheet(f"color: {color};")
        except Exception:
            self._vital_labels["pheromone"].setText("—")

        # Reflex Arc
        reflex_traces = _tail_jsonl(_STATE / "reflex_arc_trace.jsonl", 5)
        if reflex_traces:
            last = reflex_traces[-1]
            self._vital_labels["reflex"].setText(f"🟢 {_ago(last.get('ts', 0))}")
            self._vital_labels["reflex"].setStyleSheet(f"color: {_GREEN};")
        else:
            self._vital_labels["reflex"].setText("⚪ idle")

        # Corvid
        corvid_traces = _tail_jsonl(_STATE / "corvid_apprentice_trace.jsonl", 5)
        if corvid_traces:
            last = corvid_traces[-1]
            self._vital_labels["corvid"].setText(f"🟢 {_ago(last.get('ts', 0))}")
            self._vital_labels["corvid"].setStyleSheet(f"color: {_GREEN};")
        else:
            self._vital_labels["corvid"].setText("⚪ idle")

        # Alice
        convo = _tail_jsonl(_STATE / "conversation_log.jsonl", 3)
        if convo:
            last = convo[-1]
            self._vital_labels["alice"].setText(f"🟢 {_ago(last.get('ts', 0))}")
            self._vital_labels["alice"].setStyleSheet(f"color: {_GREEN};")
        else:
            self._vital_labels["alice"].setText("⚪ idle")

        # Health log
        health = _tail_jsonl(_STATE / "extended_phenotype_health.jsonl", 8)
        log_lines = []
        for h in reversed(health):
            ts = h.get("ts", 0)
            kind = h.get("event_kind", "?")
            log_lines.append(f"[{_ago(ts)}] {kind}")
        self.health_log.setText("\n".join(log_lines) if log_lines else "No recent health events.")


# ═════════════════════════════════════════════════════════════════════
# MAIN WINDOW
# ═════════════════════════════════════════════════════════════════════
class StigmergicLifeDashboard(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SIFTA — Stigmergic Life Dashboard")
        self.resize(680, 720)
        self.setStyleSheet(_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        # Title bar
        title = QLabel("🪸 STIGMERGIC LIFE DASHBOARD")
        title.setFont(QFont("Menlo", 18, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {_CYAN};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Contacts • Schedule • Health — powered by pheromone traces")
        subtitle.setFont(QFont("Menlo", 10))
        subtitle.setStyleSheet(f"color: {_DIM};")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        # Tabs
        self.tabs = QTabWidget()
        self.contacts_tab = ContactsTab()
        self.schedule_tab = ScheduleTab()
        self.health_tab = HealthTab()

        self.tabs.addTab(self.contacts_tab, "🌐 Contacts")
        self.tabs.addTab(self.schedule_tab, "📅 Schedule")
        self.tabs.addTab(self.health_tab, "❤️ Health")
        layout.addWidget(self.tabs)

        # Auto-refresh
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh_all)
        self.timer.start(10_000)
        self._refresh_all()

    def _refresh_all(self):
        idx = self.tabs.currentIndex()
        if idx == 0:
            self.contacts_tab.refresh()
        elif idx == 1:
            self.schedule_tab.refresh()
        elif idx == 2:
            self.health_tab.refresh()


def main():
    app = QApplication(sys.argv)
    window = StigmergicLifeDashboard()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
