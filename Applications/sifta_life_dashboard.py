#!/usr/bin/env python3
"""
Applications/sifta_life_dashboard.py
═══════════════════════════════════════════════════════════════
SIFTA Stigmergic Life Dashboard — Contacts + Schedule + Health + Swarm

Four-tab PyQt6 app that reads live stigmergic data to keep the
Architect optimized in life, health, and computing.

Tab 1: CONTACTS — WhatsApp social graph + interaction recency
Tab 2: SCHEDULE — Circadian rhythm + task queue + reminders
Tab 3: HEALTH   — Owner vitals, thermal, energy, pheromone score
Tab 4: SWARM    — Event 104/106/107 ledgers + nightly audit + BioSIFTA (live refresh)
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
    QTextEdit, QGridLayout, QProgressBar, QComboBox, QMessageBox,
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

        # Swarm Regime strip (Phase Detector)
        regime_frame = QFrame()
        regime_frame.setStyleSheet(
            f"QFrame {{ background: {_CARD}; border: 1px solid {_ACCENT};"
            f" border-radius: 6px; padding: 6px 10px; }}"
        )
        rl = QHBoxLayout(regime_frame)
        rl.setContentsMargins(0, 0, 0, 0)
        self.regime_label = QLabel("🌌 Regime: loading...")
        self.regime_label.setFont(QFont("Menlo", 12, QFont.Weight.Bold))
        rl.addWidget(self.regime_label)
        rl.addStretch()
        self.cusum_label = QLabel("")
        self.cusum_label.setFont(QFont("Menlo", 10))
        self.cusum_label.setStyleSheet(f"color: {_DIM};")
        rl.addWidget(self.cusum_label)
        layout.addWidget(regime_frame)

        # Allostatic Load strip (Event 102)
        al_frame = QFrame()
        al_frame.setStyleSheet(
            f"QFrame {{ background: {_CARD}; border: 1px solid {_ACCENT};"
            f" border-radius: 6px; padding: 4px 10px; }}"
        )
        al_layout = QHBoxLayout(al_frame)
        al_layout.setContentsMargins(0, 0, 0, 0)
        al_layout.setSpacing(8)
        self.al_label = QLabel("🧠 Load: —")
        self.al_label.setFont(QFont("Menlo", 11, QFont.Weight.Bold))
        al_layout.addWidget(self.al_label)
        self.al_bar = QProgressBar()
        self.al_bar.setMaximum(100)
        self.al_bar.setValue(0)
        self.al_bar.setFixedHeight(10)
        self.al_bar.setTextVisible(False)
        al_layout.addWidget(self.al_bar, stretch=1)
        self.al_policy_label = QLabel("")
        self.al_policy_label.setFont(QFont("Menlo", 10))
        self.al_policy_label.setStyleSheet(f"color: {_DIM};")
        al_layout.addWidget(self.al_policy_label)
        layout.addWidget(al_frame)

        # ── Event 104/106 Auditor strip ───────────────────────────────────────
        obs_frame = QFrame()
        obs_frame.setStyleSheet(
            f"QFrame {{ background: {_CARD}; border: 1px solid #1a3a5c;"
            f" border-radius: 6px; padding: 4px 10px; }}"
        )
        obs_layout = QHBoxLayout(obs_frame)
        obs_layout.setContentsMargins(0, 0, 0, 0)
        obs_layout.setSpacing(8)
        self.obs_label = QLabel("🔍 Auditor: —")
        self.obs_label.setFont(QFont("Menlo", 11, QFont.Weight.Bold))
        obs_layout.addWidget(self.obs_label)
        self.obs_bar = QProgressBar()
        self.obs_bar.setMaximum(100)
        self.obs_bar.setValue(0)
        self.obs_bar.setFixedHeight(8)
        self.obs_bar.setTextVisible(False)
        obs_layout.addWidget(self.obs_bar, stretch=1)
        self.obs_detail = QLabel("")
        self.obs_detail.setFont(QFont("Menlo", 9))
        self.obs_detail.setStyleSheet(f"color: {_DIM};")
        obs_layout.addWidget(self.obs_detail)
        layout.addWidget(obs_frame)

        # ── BioSIFTA corpus strip ─────────────────────────────────────────────
        bio_frame = QFrame()
        bio_frame.setStyleSheet(
            f"QFrame {{ background: {_CARD}; border: 1px solid #1a3a5c;"
            f" border-radius: 6px; padding: 4px 10px; }}"
        )
        bio_layout = QHBoxLayout(bio_frame)
        bio_layout.setContentsMargins(0, 0, 0, 0)
        bio_layout.setSpacing(8)
        self.bio_label = QLabel("🧬 BioSIFTA: —")
        self.bio_label.setFont(QFont("Menlo", 11, QFont.Weight.Bold))
        bio_layout.addWidget(self.bio_label)
        self.bio_bar = QProgressBar()
        self.bio_bar.setMaximum(500)   # LoRA threshold
        self.bio_bar.setValue(0)
        self.bio_bar.setFixedHeight(8)
        self.bio_bar.setTextVisible(False)
        bio_layout.addWidget(self.bio_bar, stretch=1)
        self.bio_detail = QLabel("")
        self.bio_detail.setFont(QFont("Menlo", 9))
        self.bio_detail.setStyleSheet(f"color: {_DIM};")
        bio_layout.addWidget(self.bio_detail)
        layout.addWidget(bio_frame)

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

        # ── Swarm Regime (Phase Detector) ─────────────────────────────────
        try:
            import sys as _sys
            if str(_REPO) not in _sys.path:
                _sys.path.insert(0, str(_REPO))
            from System.phase_transition_control import get_ptc
            ptc = get_ptc()
            regime = ptc.evaluate_regime()
            _REGIME_COLORS = {
                "EXPLORATION":      _GREEN,
                "CONSOLIDATION":    _AMBER,
                "CRITICAL_COLLAPSE": _RED,
            }
            _REGIME_EMOJI = {
                "EXPLORATION":      "🌱",
                "CONSOLIDATION":    "🔄",
                "CRITICAL_COLLAPSE": "⚠️",
            }
            rc = _REGIME_COLORS.get(regime, _DIM)
            re = _REGIME_EMOJI.get(regime, "🌌")
            self.regime_label.setText(f"{re} Regime: {regime}")
            self.regime_label.setStyleSheet(f"color: {rc}; font-weight: bold;")
            s = ptc.state
            alarm_txt = " 🚨CUSUM" if s.cusum_alarm else ""
            self.cusum_label.setText(
                f"ρ={s.stigmergic_density:.2f}  EWS={s.EWS_score:.2f}  "
                f"TD={s.td_mean:.3f}  S={s.cusum_score:.2f}{alarm_txt}"
            )
            self.cusum_label.setStyleSheet(
                f"color: {_RED if s.cusum_alarm else _DIM}; font-family: Menlo; font-size: 10px;"
            )
        except Exception:
            self.regime_label.setText("🌌 Regime: —")
            self.cusum_label.setText("")

        # ── Allostatic Load (Event 102) ───────────────────────────────────
        try:
            import sys as _sys
            if str(_REPO) not in _sys.path:
                _sys.path.insert(0, str(_REPO))
            from System.swarm_allostatic_load import compute_allostatic_load
            al_row = compute_allostatic_load()
            load = al_row.get("allostatic_load", 0.0)
            policy = al_row.get("policy", "ALLOW_GROWTH")
            _AL_COLORS = {
                "ALLOW_GROWTH":        _GREEN,
                "SUPPRESS_EXPLORATION": _AMBER,
                "FORCE_REST_REPAIR":    _RED,
            }
            _AL_EMOJI = {
                "ALLOW_GROWTH":        "🟢",
                "SUPPRESS_EXPLORATION": "🟡",
                "FORCE_REST_REPAIR":    "🔴",
            }
            al_color = _AL_COLORS.get(policy, _DIM)
            al_emoji = _AL_EMOJI.get(policy, "⚪")
            self.al_label.setText(f"🧠 Load: {load:.2f}")
            self.al_label.setStyleSheet(f"color: {al_color}; font-weight: bold;")
            self.al_bar.setValue(int(load * 100))
            # Colour the bar chunk via stylesheet
            self.al_bar.setStyleSheet(
                f"QProgressBar::chunk {{ background: {al_color}; border-radius: 3px; }}"
            )
            window = al_row.get("window", 0)
            self.al_policy_label.setText(f"{al_emoji} {policy}  (n={window})")
            self.al_policy_label.setStyleSheet(
                f"color: {al_color if policy != 'ALLOW_GROWTH' else _DIM};"
                f" font-family: Menlo; font-size: 10px;"
            )
        except Exception:
            self.al_label.setText("🧠 Load: —")
            self.al_bar.setValue(0)
            self.al_policy_label.setText("")

        # ── Event 104/106 Auditor strip ───────────────────────────────────────
        try:
            summary_path = _STATE / "nightly_health_summary.json"
            if summary_path.exists():
                summary = json.loads(summary_path.read_text("utf-8"))
                score = float(summary.get("composite_score", 0.0))
                obs_sec = summary.get("sections", {}).get("observability", {})
                ledger_obs = summary.get("ledger_metrics", {}).get("observability", {})
                confidence = float(
                    ledger_obs.get("observability_score", obs_sec.get("attribution_confidence", 0.0))
                )
                parentage = float(
                    ledger_obs.get("parentage_score", obs_sec.get("trace_linkage", 0.0))
                )
                race = float(ledger_obs.get("race_pressure", obs_sec.get("race_pressure", 0.0)))
                n_rows = int(
                    ledger_obs.get(
                        "n_merged_audit_rows",
                        obs_sec.get("n_merged_audit_rows", obs_sec.get("n_obs_rows_24h", 0)),
                    )
                )
                cusum_reject = obs_sec.get("cusum_null_reject")
                cusum_icon = "🔴" if cusum_reject is False else ("🟢" if cusum_reject else "⚪")
                color = _GREEN if confidence > 0.6 else _AMBER if confidence > 0.3 else _RED
                self.obs_label.setText(f"🔍 Auditor: {confidence:.2f}")
                self.obs_label.setStyleSheet(f"color: {color}; font-weight: bold;")
                self.obs_bar.setValue(int(confidence * 100))
                self.obs_bar.setStyleSheet(
                    f"QProgressBar::chunk {{ background: {color}; border-radius: 3px; }}"
                )
                ts = summary.get("ts", 0)
                self.obs_detail.setText(
                    f"parent={parentage:.2f}  race={race:.2f}  rows={n_rows}  "
                    f"CUSUM={cusum_icon}  score={score:.3f}  [{_ago(ts)}]"
                )
            else:
                # Live fallback from obs log directly
                obs_rows = _tail_jsonl(_STATE / "stigmergic_observability.jsonl", 50)
                linked = sum(1 for r in obs_rows if r.get("causal_parent_ids"))
                linkage = linked / len(obs_rows) if obs_rows else 0.0
                color = _GREEN if linkage > 0.6 else _AMBER if linkage > 0.3 else _DIM
                self.obs_label.setText(f"🔍 Auditor: {linkage:.2f}")
                self.obs_label.setStyleSheet(f"color: {color}; font-weight: bold;")
                self.obs_bar.setValue(int(linkage * 100))
                self.obs_detail.setText(f"rows={len(obs_rows)}  link={linkage:.2f}  no audit run yet")
        except Exception:
            self.obs_label.setText("🔍 Auditor: —")
            self.obs_bar.setValue(0)
            self.obs_detail.setText("")

        # ── BioSIFTA corpus strip ─────────────────────────────────────────────
        try:
            def _count_jsonl(name: str) -> int:
                p = _STATE / name
                if not p.exists():
                    return 0
                return sum(1 for l in p.read_text("utf-8", errors="replace").splitlines() if l.strip())
            n_papers  = _count_jsonl("bio_papers.jsonl")
            n_claims  = _count_jsonl("bio_claims.jsonl")
            n_exp     = _count_jsonl("bio_experiments.jsonl")
            n_skills  = _count_jsonl("bio_skills.jsonl")
            lora_ready = n_claims >= 500
            color = _GREEN if lora_ready else _AMBER if n_claims > 50 else _CYAN
            self.bio_label.setText(f"🧬 BioSIFTA: {n_claims}c")
            self.bio_label.setStyleSheet(f"color: {color}; font-weight: bold;")
            self.bio_bar.setValue(min(n_claims, 500))
            self.bio_bar.setStyleSheet(
                f"QProgressBar::chunk {{ background: {color}; border-radius: 3px; }}"
            )
            lora_icon = "✅ LoRA ready" if lora_ready else f"📥 {500 - n_claims} to LoRA"
            self.bio_detail.setText(
                f"papers={n_papers}  claims={n_claims}  exp={n_exp}  skills={n_skills}  {lora_icon}"
            )
        except Exception:
            self.bio_label.setText("🧬 BioSIFTA: —")
            self.bio_bar.setValue(0)
            self.bio_detail.setText("")

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
            p = max(0, min(int(task.get("priority", 0)), 2))  # clamp [0-2] — never IndexError
            border_color = _DIM if is_done else [_GREEN, _AMBER, _RED][p]
            card.setStyleSheet(f"""
                QFrame {{ background: {_CARD}; border-left: 3px solid {border_color};
                          border-radius: 4px; padding: 8px; margin: 2px; }}
            """)
            cl = QHBoxLayout(card)
            priority_icons = ["🟢", "🟡", "🔴"]
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
# TAB 4: SWARM (Event 104/106 deep view)
# ═════════════════════════════════════════════════════════════════════
class SwarmTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        hdr = QLabel("🐜 SWARM HEALTH — Observability · Motor · BioSIFTA")
        hdr.setFont(QFont("Menlo", 14, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {_CYAN};")
        hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hdr)

        self.swarm_grid = QGridLayout()
        self.swarm_grid.setSpacing(10)
        layout.addLayout(self.swarm_grid)

        _TT = {
            "attribution": "Event 107 — ide trace rows with trace_id / total (ledger)",
            "linkage": "Event 107 — rows with causal_parent_ids / merged audit tail",
            "race": "Event 107 — duplicate id pressure in 60s windows (lower better)",
            "cusum": "Event 106 — permutation null on regime→TD (body_brain_memory)",
            "allostatic": "Event 102/107 — latest load + policy; score = 1−load",
            "regime": "Event 106 — regime_state.json + motor_policy tail",
            "crystal": "Event 103/107 — skill-weighted motor rows / recent tail",
            "papers": "Event 105 — bio_papers.jsonl line count",
            "claims": "Event 105 — bio_claims.jsonl (500 → LoRA-ready)",
            "experiments": "Event 105 — bio_experiments.jsonl",
            "skills": "Event 105 — bio_skills.jsonl shipped receipts",
            "composite": "Event 107 — composite_nightly_score from ledgers + tests",
            "last_audit": "nightly_health_summary.json ts field",
        }
        metrics = [
            ("🔍 Observability",  "attribution"),
            ("🔗 Parentage",      "linkage"),
            ("🏃 Race Pressure",  "race"),
            ("📡 CUSUM Signal",   "cusum"),
            ("🫁 Allostatic",     "allostatic"),
            ("⚙️  Motor Regime",  "regime"),
            ("🧠 Motor Score",    "crystal"),
            ("📄 Papers",         "papers"),
            ("💡 Claims",         "claims"),
            ("🔬 Experiments",    "experiments"),
            ("🎓 Skills Shipped", "skills"),
            ("🏆 Composite",      "composite"),
            ("⏱  Last Audit",    "last_audit"),
        ]
        self._swarm_labels: dict[str, QLabel] = {}
        for i, (label, key) in enumerate(metrics):
            frame = QFrame()
            frame.setStyleSheet(f"""
                QFrame {{ background: {_CARD}; border: 1px solid {_ACCENT};
                          border-radius: 8px; padding: 10px; }}
            """)
            tip = _TT.get(key, "")
            if tip:
                frame.setToolTip(tip)
            fl = QVBoxLayout(frame)
            fl.setSpacing(2)
            nl = QLabel(label)
            nl.setFont(QFont("Menlo", 10, QFont.Weight.Bold))
            nl.setStyleSheet(f"color: {_DIM};")
            if tip:
                nl.setToolTip(tip)
            fl.addWidget(nl)
            vl = QLabel("—")
            vl.setFont(QFont("Menlo", 18, QFont.Weight.Bold))
            vl.setStyleSheet(f"color: {_CYAN};")
            if tip:
                vl.setToolTip(tip)
            fl.addWidget(vl)
            self._swarm_labels[key] = vl
            self.swarm_grid.addWidget(frame, i // 3, i % 3)

        # Nightly audit log
        layout.addWidget(QLabel("📋 Nightly Audit History:"))
        self.audit_log = QTextEdit()
        self.audit_log.setReadOnly(True)
        self.audit_log.setFixedHeight(100)
        layout.addWidget(self.audit_log)

        # Manual audit button
        btn_row = QHBoxLayout()
        btn_audit = QPushButton("▶ Run Audit Now (no arXiv)")
        btn_audit.clicked.connect(self._run_audit)
        btn_row.addWidget(btn_audit)
        btn_sweep = QPushButton("🌐 arXiv Sweep")
        btn_sweep.clicked.connect(self._run_arxiv_sweep)
        btn_row.addWidget(btn_sweep)
        layout.addLayout(btn_row)

        self._audit_result_label = QLabel("")
        self._audit_result_label.setFont(QFont("Menlo", 9))
        self._audit_result_label.setStyleSheet(f"color: {_DIM};")
        self._audit_result_label.setWordWrap(True)
        layout.addWidget(self._audit_result_label)

    def _run_audit(self):
        self._audit_result_label.setText("⏳ Running audit…")
        QApplication.processEvents()
        try:
            from System.swarm_nightly_health_audit import run_nightly_audit
            result = run_nightly_audit(run_arxiv=False, fast_tests=True)
            score = result.get("composite_score", 0.0)
            dur   = result.get("duration_s", 0)
            tests = result.get("sections", {}).get("tests", {})
            self._audit_result_label.setText(
                f"✅ Audit done  composite={score:.4f}  "
                f"tests={tests.get('passed', 0)} passed  {dur:.1f}s"
            )
            self._audit_result_label.setStyleSheet(f"color: {_GREEN};")
            QMessageBox.information(
                self, "Nightly audit",
                f"Composite {score:.4f}\nTests passed: {tests.get('passed', 0)}\nDuration {dur:.1f}s",
            )
        except Exception as exc:
            self._audit_result_label.setText(f"❌ Audit error: {exc}")
            self._audit_result_label.setStyleSheet(f"color: {_RED};")
            QMessageBox.warning(self, "Nightly audit", str(exc))
        self.refresh()

    def _run_arxiv_sweep(self):
        self._audit_result_label.setText("⏳ Running arXiv sweep (4 queries, ~15s)…")
        self._audit_result_label.setStyleSheet(f"color: {_AMBER};")
        QApplication.processEvents()
        try:
            from System.swarm_bio_arxiv_ingester import run_sifta_bio_sweep
            receipts = run_sifta_bio_sweep(
                max_results_per_query=2, run_claim_extraction=False
            )
            total = sum(r.get("n_fetched", 0) for r in receipts)
            chunks = sum(r.get("ingested_chunks", 0) for r in receipts)
            self._audit_result_label.setText(
                f"✅ Sweep done  fetched={total}  chunks={chunks}"
            )
            self._audit_result_label.setStyleSheet(f"color: {_GREEN};")
            QMessageBox.information(
                self, "arXiv sweep",
                f"Papers fetched: {total}\nChunks ingested: {chunks}",
            )
        except Exception as exc:
            self._audit_result_label.setText(f"❌ Sweep error: {exc}")
            self._audit_result_label.setStyleSheet(f"color: {_RED};")
            QMessageBox.warning(self, "arXiv sweep", str(exc))
        self.refresh()

    def refresh(self):
        L = self._swarm_labels

        # ── Read nightly_health_summary.json ────────────────────────────────
        summary_path = _STATE / "nightly_health_summary.json"
        summary = _load_json(summary_path)
        sections = summary.get("sections", {})
        ledger_metrics = summary.get("ledger_metrics", {})
        if not ledger_metrics:
            # Tiles stay truthful even before the first nightly run writes ledger_metrics.
            try:
                from System.swarm_health_metrics import (
                    score_allostatic_ledger,
                    score_motor_policy_ledger,
                    score_observability_ledgers,
                )
                ledger_metrics = {
                    "observability": score_observability_ledgers(state_dir=_STATE),
                    "allostatic": score_allostatic_ledger(state_dir=_STATE),
                    "motor": score_motor_policy_ledger(state_dir=_STATE),
                }
            except Exception:
                ledger_metrics = {}
        ledger_obs = ledger_metrics.get("observability", {})
        ledger_allo = ledger_metrics.get("allostatic", {})
        ledger_motor = ledger_metrics.get("motor", {})

        obs = sections.get("observability", {})
        al  = sections.get("allostatic", {})
        mp  = sections.get("motor_policy", {})
        bc  = sections.get("bio_corpus", {})
        tg  = sections.get("tests", {})
        composite = float(summary.get("composite_score", 0.0))
        ts_audit  = float(summary.get("ts", 0.0))

        def _color_score(v: float) -> str:
            return _GREEN if v > 0.7 else _AMBER if v > 0.4 else _RED

        # Event 107 ledger-derived observability score, with Event 104 fallback.
        conf = float(ledger_obs.get("observability_score", obs.get("attribution_confidence", 0.0)))
        L["attribution"].setText(f"{conf:.3f}")
        L["attribution"].setStyleSheet(f"color: {_color_score(conf)};")

        # Parentage score: fraction of audit rows with causal parents.
        link = float(ledger_obs.get("parentage_score", obs.get("trace_linkage", 0.0)))
        L["linkage"].setText(f"{link:.3f}")
        L["linkage"].setStyleSheet(f"color: {_color_score(link)};")

        # Race pressure (lower is better), Event 107 first.
        race = float(ledger_obs.get("race_pressure", obs.get("race_pressure", 0.0)))
        race_color = _GREEN if race < 0.2 else _AMBER if race < 0.5 else _RED
        L["race"].setText(f"{race:.3f}")
        L["race"].setStyleSheet(f"color: {race_color};")

        # CUSUM null signal
        cusum_reject = obs.get("cusum_null_reject")
        if cusum_reject is True:
            L["cusum"].setText("✅ Signal")
            L["cusum"].setStyleSheet(f"color: {_GREEN};")
        elif cusum_reject is False:
            L["cusum"].setText("⚠️ Noise")
            L["cusum"].setStyleSheet(f"color: {_AMBER};")
        else:
            L["cusum"].setText("⚪ No data")
            L["cusum"].setStyleSheet(f"color: {_DIM};")

        # Allostatic (ledger load + policy)
        load = float(ledger_allo.get("allostatic_load", al.get("allostatic_load", 0.0)))
        pol = str(ledger_allo.get("policy", al.get("policy", "—")))[:14]
        L["allostatic"].setText(f"{load:.2f} {pol}")
        L["allostatic"].setStyleSheet(
            f"color: {_GREEN if load < 0.45 else _AMBER if load < 0.75 else _RED};"
        )

        # Motor regime
        regime = mp.get("last_regime", "—")
        _REGIME_COLORS = {
            "EXPLORATION": _GREEN, "CONSOLIDATION": _AMBER,
            "CRITICAL_COLLAPSE": _RED,
        }
        L["regime"].setText(regime[:12])
        L["regime"].setStyleSheet(f"color: {_REGIME_COLORS.get(regime, _DIM)};")

        # Motor score: fraction of recent motor rows bearing skill-weighted policy mass.
        motor_score = ledger_motor.get("motor_score")
        if motor_score is None:
            try:
                mp_rows = _tail_jsonl(_STATE / "motor_policy.jsonl", 50)
                biased = sum(
                    1
                    for r in mp_rows
                    if str(r.get("truth_label", "")).upper() == "SKILL_WEIGHTED_POLICY"
                )
                motor_score = (biased / len(mp_rows)) if mp_rows else 0.0
            except Exception:
                motor_score = 0.0
        motor_score = float(motor_score)
        L["crystal"].setText(f"{motor_score:.3f}")
        L["crystal"].setStyleSheet(f"color: {_color_score(motor_score)};")

        # BioSIFTA corpus metrics (live from files — faster than waiting for audit)
        def _count(name: str) -> int:
            p = _STATE / name
            if not p.exists():
                return 0
            return sum(1 for l in p.read_text("utf-8", errors="replace").splitlines() if l.strip())

        n_papers = _count("bio_papers.jsonl") or bc.get("n_paper_chunks", 0)
        n_claims = _count("bio_claims.jsonl") or bc.get("n_claims", 0)
        n_exp    = _count("bio_experiments.jsonl") or bc.get("n_experiments", 0)
        n_skills = _count("bio_skills.jsonl") or bc.get("n_skills", 0)

        L["papers"].setText(str(n_papers))
        L["claims"].setText(str(n_claims))
        L["claims"].setStyleSheet(
            f"color: {_GREEN if n_claims >= 500 else _AMBER if n_claims > 50 else _CYAN};"
        )
        L["experiments"].setText(str(n_exp))
        L["skills"].setText(str(n_skills))
        L["skills"].setStyleSheet(f"color: {_GREEN if n_skills > 0 else _DIM};")

        # Composite
        L["composite"].setText(f"{composite:.4f}")
        L["composite"].setStyleSheet(f"color: {_color_score(composite)};")

        # Last audit
        if ts_audit:
            L["last_audit"].setText(_ago(ts_audit))
            L["last_audit"].setStyleSheet(
                f"color: {_GREEN if time.time() - ts_audit < 86400 else _AMBER};"
            )
        else:
            L["last_audit"].setText("never")
            L["last_audit"].setStyleSheet(f"color: {_RED};")

        # Audit history log
        history = _tail_jsonl(_STATE / "nightly_health.jsonl", 5)
        lines = []
        for h in reversed(history):
            ts = h.get("ts", 0)
            sc = h.get("composite_score", 0.0)
            tp = h.get("sections", {}).get("tests", {}).get("passed", "?")
            lines.append(
                f"[{_ago(ts)}] composite={sc:.4f}  tests={tp}"
            )
        self.audit_log.setText(
            "\n".join(lines) if lines else "No audit history yet — click ▶ Run Audit Now."
        )


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

        subtitle = QLabel(
            "Contacts • Schedule • Health • Swarm — pheromone traces + nightly ledgers"
        )
        subtitle.setFont(QFont("Menlo", 10))
        subtitle.setStyleSheet(f"color: {_DIM};")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        # Tabs
        self.tabs = QTabWidget()
        self.contacts_tab = ContactsTab()
        self.schedule_tab = ScheduleTab()
        self.health_tab = HealthTab()
        self.swarm_tab = SwarmTab()

        self.tabs.addTab(self.contacts_tab, "🌐 Contacts")
        self.tabs.addTab(self.schedule_tab, "📅 Schedule")
        self.tabs.addTab(self.health_tab, "❤️ Health")
        self.tabs.addTab(self.swarm_tab, "🐜 Swarm")
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
        elif idx == 3:
            self.swarm_tab.refresh()


def main():
    app = QApplication(sys.argv)
    window = StigmergicLifeDashboard()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
