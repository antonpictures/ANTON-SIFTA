#!/usr/bin/env python3
"""
System/swarm_body_monitor.py
══════════════════════════════════════════════════════════════════════
SIFTA Mermaid v1.0 — Live Body Monitor
──────────────────────────────────────────────────────────────────────
Shows all 12 biological organs with explicit truth labels.
No organ may display as live unless its state declares a live input source.

Camera: OFF by default (press C to toggle — uses CPU when on)

Run:
    PYTHONPATH=. python3 System/swarm_body_monitor.py
"""

import sys
import math
import time
import random
import numpy as np
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QGridLayout, QFrame, QProgressBar, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QFont, QColor, QPalette, QFontDatabase

# ── Import real organs ────────────────────────────────────────────────
from System.swarm_metabolic_engine import SwarmMetabolicEngine, MetabolicConfig, MetabolicMode
from System.swarm_stig_time import StigTime, StigTimeConfig

# ── Colors ────────────────────────────────────────────────────────────
C_BG        = "#0a0a0f"
C_PANEL     = "#0e1020"
C_BORDER    = "#1a1f3a"
C_ALIVE     = "#00ff88"
C_PULSE     = "#00ccff"
C_WARN      = "#ffaa00"
C_DEAD      = "#ff3355"
C_DIM       = "#334455"
C_TEXT      = "#c8d8e8"
C_MUTED     = "#4a6080"
C_ACCENT    = "#7b2fff"
C_GOLD      = "#ffd700"

TRUTH_REAL = "REAL"
TRUTH_DEMO = "DEMO"
TRUTH_BROKEN = "BROKEN"
TRUTH_UNKNOWN = "UNKNOWN"

TRUTH_COLORS = {
    TRUTH_REAL: C_ALIVE,
    TRUTH_DEMO: C_WARN,
    TRUTH_BROKEN: C_DEAD,
    TRUTH_UNKNOWN: C_MUTED,
}

DEMO_SOURCE = "simulated_internal_oscillator"

# ── Trace helpers for reflex / corvid organs ────────────────────────
import json as _json

_STATE = _REPO / ".sifta_state"

def _tail_trace(path: Path, n: int = 5, max_age_s: float = 300.0) -> list:
    """Read the last N entries from a JSONL trace ledger, filtering by age."""
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").strip().splitlines()[-n:]
        now = time.time()
        out = []
        for ln in lines:
            try:
                row = _json.loads(ln)
                if now - float(row.get("ts", 0)) < max_age_s:
                    out.append(row)
            except Exception:
                pass
        return out
    except Exception:
        return []


def _truth(status: str, source: str, note: str) -> dict:
    return {
        "truth_status": status,
        "truth_source": source,
        "truth_note": note,
    }


def _demo_truth(note: str) -> dict:
    return _truth(TRUTH_DEMO, DEMO_SOURCE, note)


def _live_process_truth(note: str) -> dict:
    return _truth(TRUTH_REAL, "live_process", note)


def _live_ledger_truth(path: Path, note: str) -> dict:
    if path.exists():
        return _truth(TRUTH_REAL, "live_ledger", note)
    return _truth(TRUTH_UNKNOWN, "missing_ledger", f"{note}; ledger missing: {path.name}")


def _sensor_gate_truth(path: Path, reason: str) -> dict:
    if not path.exists():
        return _truth(
            TRUTH_UNKNOWN,
            "missing_ledger",
            "sensor_gate_lock.json missing; no lock/unlock attempt has run",
        )
    if reason in {"lock_success", "lock_all_failed", "unlock_success", "unlock"}:
        return _truth(TRUTH_REAL, "live_ledger", "sensor_gate_lock.json real lock/unlock attempt")
    return _truth(
        TRUTH_UNKNOWN,
        "no_runtime_attempt",
        f"sensor_gate_lock.json exists but reason={reason}; waiting for real lock/unlock attempt",
    )

ORGAN_DEFS = [
    # (key, emoji, name, description)
    ("field",     "🌊", "Unified Field",    "stigmergic tensor substrate"),
    ("rl",        "🧬", "RL Meta-Cortex",   "evolutionary field tuning"),
    ("octopus",   "🐙", "Octopus Arms",     "distributed motor control"),
    ("cuttlefish","🦑", "Cuttlefish Skin",  "decentralized visual display"),
    ("electric",  "⚡", "Electric Fish",    "identity + JAR signaling"),
    ("honeybee",  "🐝", "Honeybee Dance",   "compressed symbolic routing"),
    ("starling",  "🐦", "Starling Topo",    "O(N·K) coordination"),
    ("fly",       "🪰", "Fly Efference",    "self-motion cancellation"),
    ("metabolic", "⚙️", "Metabolic Engine", "hummingbird/bear/wolf/ecoli"),
    ("time",      "🕰️", "STIG-TIME",        "kleiber + circadian + turtle"),
    ("reflex",    "🦐", "Reflex Arc",       "mantis-shrimp μs classifier"),
    ("corvid",    "🐦‍⬛", "Corvid Apprentice","crow/raven 2B tool ganglion"),
    # ── Predator v7 Organs (Event 76-79) ─────────────────────────────
    ("td_learner", "🧠", "TD Q-Learner",    "Bellman RL — Schultz 1997"),
    ("dopamine",   "💊", "Dopamine Loop",   "credit assignment — Schultz 1997"),
    ("hippocampus","🐎", "Hippocampus",     "episodic memory ledger"),
    ("sensor_gate","🚪", "Sensor Gate",     "attention filter — Koch 2011"),
    ("bg_selector","⚖️", "Basal Ganglia",  "action selection — Redgrave 1999"),
]


class OrganEngine:
    """Drives real data from actual organ modules every tick."""

    def __init__(self):
        self.metabolic = SwarmMetabolicEngine(MetabolicConfig())
        self.metabolic.register_module("retina",    priority=0.9)
        self.metabolic.register_module("motor",     priority=0.8)
        self.metabolic.register_module("display",   priority=0.3)
        self.metabolic.register_module("waggle",    priority=0.5)

        self.stig_time = StigTime(StigTimeConfig(circadian_period=200))
        self.stig_time.start_interval()

        self.tick = 0
        self._reward_cooldown = 0

        # Per-organ accumulators
        self._starling_spread = 0.5
        self._fly_residual    = 0.0
        self._fly_gain_error  = 1.0
        self._waggle_angle    = 0.0
        self._rl_score        = 0.5
        self._field_energy    = 0.85
        self._electric_phase  = 0.0
        self._oct_coherence   = 1.0
        self._cut_contrast    = 0.85

    def tick_all(self):
        self.tick += 1

        # Occasionally send reward to metabolic engine
        if self._reward_cooldown > 0:
            self._reward_cooldown -= 1
        elif random.random() < 0.03:
            self.metabolic.replenish(random.uniform(0.3, 1.0))
            self._reward_cooldown = 40

        mode = self.metabolic.tick_metabolism(reward=0.0)
        t_ctx = self.stig_time.tick(metabolic_mode=mode.value,
                                    field_energy=self.metabolic.energy)

        # Demo organ dynamics. Event82 requires these to be visibly labeled as
        # DEMO until each organ has a live ledger/process/sensor input.
        t = self.tick

        # Field energy oscillates with circadian gate
        self._field_energy = (
            0.6 + 0.3 * self.stig_time.circadian_activity()
            + 0.05 * math.sin(t * 0.07)
        )

        # RL score: slow drift with occasional mutation
        if random.random() < 0.02:
            self._rl_score = np.clip(self._rl_score + random.gauss(0, 0.1), 0.2, 1.0)
        self._rl_score = self._rl_score * 0.998 + 0.5 * 0.002

        # Starling: topological spread oscillates (predator scatter sim)
        self._starling_spread = 0.35 + 0.2 * abs(math.sin(t * 0.03))

        # Fly efference: residual approaches zero when stable, spikes on motion
        if random.random() < 0.04:
            self._fly_residual = random.uniform(3.0, 8.0)  # simulated camera move
        self._fly_residual *= 0.88  # self-cancellation decay

        # Waggle dance angle drifts toward detected resource direction
        self._waggle_angle = (self._waggle_angle + 0.02 + random.gauss(0, 0.005)) % (2 * math.pi)

        # Electric field: JAR phase separation
        self._electric_phase = (self._electric_phase + 0.05) % (2 * math.pi)

        # Octopus coherence
        self._oct_coherence = 0.97 + 0.03 * math.sin(t * 0.1)

        # Cuttlefish contrast
        self._cut_contrast = 0.75 + 0.2 * abs(math.sin(t * 0.05))
        self._fly_gain_error = max(0.0, self._fly_gain_error - 0.001)

        return self._build_state(mode, t_ctx)

    def _build_state(self, mode: MetabolicMode, t_ctx: dict) -> dict:
        e = self.metabolic.energy
        t = self.tick
        circ = self.stig_time.circadian_activity()
        T_est, sigma = self.stig_time.measure_interval()

        # ── Live trace reads for reflex + corvid ────────────────────────
        reflex_path = _STATE / "reflex_arc_trace.jsonl"
        corvid_path = _STATE / "corvid_apprentice_trace.jsonl"

        reflex_traces = _tail_trace(reflex_path, n=5, max_age_s=300)
        reflex_count = len(reflex_traces)
        reflex_last_cat = reflex_traces[-1].get("category", "-") if reflex_traces else "-"
        reflex_last_ms = reflex_traces[-1].get("latency_ms", 0) if reflex_traces else 0

        corvid_traces = _tail_trace(corvid_path, n=5, max_age_s=300)
        corvid_count = len(corvid_traces)
        corvid_last_task = corvid_traces[-1].get("task", "-") if corvid_traces else "-"
        corvid_last_s = corvid_traces[-1].get("latency_s", 0) if corvid_traces else 0
        corvid_success = sum(1 for c in corvid_traces if c.get("success"))

        # ── Predator v7 live ledger reads ────────────────────────────────
        td_path       = _STATE / "td_q_table.json"
        td_ledger     = _STATE / "td_receipts.jsonl"
        dopamine_path = _STATE / "dopamine_reward_ledger.jsonl"
        last_action   = _STATE / "last_action_register.json"
        hipp_path     = _STATE / "hippocampus" / "events.jsonl"
        sgate_path    = _STATE / "sensor_gate_lock.json"
        bg_path       = _STATE / "swarm_action_selector_trace.jsonl"

        # TD Q-Learner: read Q-table entry count and last receipt
        td_q_count = 0
        td_last_error = 0.0
        if td_path.exists():
            try:
                q = _json.loads(td_path.read_text())
                td_q_count = len(q)
            except Exception:
                pass
        td_receipts = _tail_trace(td_ledger, n=3, max_age_s=600)
        if td_receipts:
            td_last_error = td_receipts[-1].get("td_error", 0.0)

        # Dopamine: last δ and total reward events
        dopa_traces = _tail_trace(dopamine_path, n=5, max_age_s=600)
        dopa_count = len(dopa_traces)
        dopa_last_delta = dopa_traces[-1].get("delta", 0.0) if dopa_traces else 0.0
        dopa_marker = dopa_traces[-1].get("marker", "-") if dopa_traces else "-"

        # Last action register (credit assignment pipeline)
        last_action_data = {}
        if last_action.exists():
            try:
                last_action_data = _json.loads(last_action.read_text())
            except Exception:
                pass
        last_action_name = last_action_data.get("action", "-")

        # Hippocampus: event count
        hipp_traces = _tail_trace(hipp_path, n=5, max_age_s=600)
        hipp_count = len(hipp_traces)
        hipp_last_type = (
            hipp_traces[-1].get("event_type") or hipp_traces[-1].get("type", "-")
            if hipp_traces else "-"
        )

        # Sensor gate: current lock state
        sgate_locked = False
        sgate_reason = "-"
        if sgate_path.exists():
            try:
                sg = _json.loads(sgate_path.read_text())
                sgate_locked = sg.get("locked", False)
                sgate_reason = sg.get("reason", "-")
            except Exception:
                pass

        # Basal Ganglia: recent action selections
        bg_traces = _tail_trace(bg_path, n=5, max_age_s=300)
        bg_count = len(bg_traces)
        bg_last_winner = bg_traces[-1].get("winner", "-") if bg_traces else "-"

        state = {
            "tick":       t,
            "bio_time":   t_ctx["bio_time"],
            "dilation":   t_ctx["dilation"],
            "circadian":  round(circ, 3),
            "compressed": t_ctx["compressed_time"],

            "field": {
                "value": round(self._field_energy, 3),
                "label": f"ψ={self._field_energy:.3f}",
                "sub":   f"circadian gate: {circ:.2f}",
                "pct":   self._field_energy,
                **_demo_truth("internal circadian oscillator; no live field ledger wired"),
            },
            "rl": {
                "value": round(self._rl_score, 3),
                "label": f"score={self._rl_score:.3f}",
                "sub":   f"tick={t}  mutations tracking",
                "pct":   self._rl_score,
                **_demo_truth("internal score drift; no live RL learner feed wired"),
            },
            "octopus": {
                "value": round(self._oct_coherence, 4),
                "label": f"coherence={self._oct_coherence:.4f}",
                "sub":   "8 arms  nonsomatotopic",
                "pct":   self._oct_coherence,
                **_demo_truth("internal arm coherence oscillator; no motor bus wired"),
            },
            "cuttlefish": {
                "value": round(self._cut_contrast, 3),
                "label": f"contrast={self._cut_contrast:.3f}",
                "sub":   "passing cloud  decentralized",
                "pct":   self._cut_contrast,
                **_demo_truth("internal contrast oscillator; no live display organ wired"),
            },
            "electric": {
                "value": round(self._electric_phase, 4),
                "label": f"φ={self._electric_phase:.4f} rad",
                "sub":   f"JAR  identity stable",
                "pct":   (math.sin(self._electric_phase) + 1) / 2,
                **_demo_truth("internal phase oscillator; no live electric-field sensor wired"),
            },
            "honeybee": {
                "value": round(self._waggle_angle, 4),
                "label": f"θ={math.degrees(self._waggle_angle):.1f}°",
                "sub":   f"vigor=0.95  quorum ready",
                "pct":   (math.sin(self._waggle_angle) + 1) / 2,
                **_demo_truth("internal angle drift; no live route quorum ledger wired"),
            },
            "starling": {
                "value": round(self._starling_spread, 4),
                "label": f"spread={self._starling_spread:.4f}",
                "sub":   "K=7 topological  scale-free",
                "pct":   1.0 - min(self._starling_spread, 1.0),
                **_demo_truth("internal spread oscillator; no live flock topology feed wired"),
            },
            "fly": {
                "value": round(self._fly_residual, 4),
                "label": f"residual={self._fly_residual:.4f}",
                "sub":   f"gain_err={self._fly_gain_error:.4f}  NLMS",
                "pct":   max(0.0, 1.0 - self._fly_residual / 10.0),
                **_demo_truth("internal efference decay; no live camera-motion stream wired"),
            },
            "metabolic": {
                "value": round(e, 4),
                "label": f"ATP={e:.4f}  [{mode.value.upper()}]",
                "sub":   f"retina={self.metabolic.get_module_budget('retina'):.3f}  display={self.metabolic.get_module_budget('display'):.3f}",
                "pct":   e,
                **_live_process_truth("SwarmMetabolicEngine.tick_metabolism()"),
            },
            "time": {
                "value": round(t_ctx["bio_time"], 2),
                "label": f"bio_t={t_ctx['bio_time']:.1f}  ×{t_ctx['dilation']}",
                "sub":   f"σ(T)={sigma:.1f}  S={t_ctx['compressed_time']:.2f}",
                "pct":   circ,
                **_live_process_truth("StigTime.tick() live process clock"),
            },
            # ── 11th Organ: Mantis-Shrimp Reflex Arc ──────────────────
            "reflex": {
                "value": reflex_count,
                "label": f"fires={reflex_count}  last={reflex_last_cat}",
                "sub":   f"latency={reflex_last_ms:.3f}ms  μs-class  0 STGM",
                "pct":   min(1.0, reflex_count / 5.0) if reflex_count > 0 else 0.1,
                **_live_ledger_truth(reflex_path, "reflex_arc_trace.jsonl recent fires"),
            },
            # ── 12th Organ: Corvid Apprentice ─────────────────────────
            "corvid": {
                "value": corvid_count,
                "label": f"tasks={corvid_count}  ok={corvid_success}  last={corvid_last_task}",
                "sub":   f"latency={corvid_last_s:.1f}s  qwen3.5:2b  async",
                "pct":   (corvid_success / corvid_count) if corvid_count > 0 else 0.1,
                **_live_ledger_truth(corvid_path, "corvid_apprentice_trace.jsonl recent tasks"),
            },
            # ── Predator v7 Organs (Event 76-79) ─────────────────────
            "td_learner": {
                "value": td_q_count,
                "label": f"Q-states={td_q_count}  δ={td_last_error:.4f}",
                "sub":   f"last_action={last_action_name}  Bellman update",
                "pct":   min(1.0, td_q_count / 20.0) if td_q_count > 0 else 0.05,
                **_live_ledger_truth(td_path, "td_q_table.json live state-action values"),
            },
            "dopamine": {
                "value": round(dopa_last_delta, 3),
                "label": f"δ={dopa_last_delta:+.3f}  marker={dopa_marker}",
                "sub":   f"reward_events={dopa_count}  credit assignment live",
                "pct":   (dopa_last_delta + 1.0) / 2.0,
                **_live_ledger_truth(dopamine_path, "dopamine_reward_ledger.jsonl live rewards"),
            },
            "hippocampus": {
                "value": hipp_count,
                "label": f"events={hipp_count}  last={hipp_last_type}",
                "sub":   f"episodic memory  ledger-backed",
                "pct":   min(1.0, hipp_count / 10.0) if hipp_count > 0 else 0.05,
                **_live_ledger_truth(hipp_path, "hippocampus/events.jsonl episode log"),
            },
            "sensor_gate": {
                "value": 1 if sgate_locked else 0,
                "label": f"locked={sgate_locked}  reason={sgate_reason}",
                "sub":   f"attention filter  Koch 2011",
                "pct":   0.2 if sgate_locked else 0.9,
                **_sensor_gate_truth(sgate_path, sgate_reason),
            },
            "bg_selector": {
                "value": bg_count,
                "label": f"selections={bg_count}  winner={bg_last_winner}",
                "sub":   f"action competition  Redgrave 1999",
                "pct":   min(1.0, bg_count / 5.0) if bg_count > 0 else 0.1,
                **_live_ledger_truth(bg_path, "swarm_action_selector_trace.jsonl selections"),
            },
        }
        counts = {TRUTH_REAL: 0, TRUTH_DEMO: 0, TRUTH_BROKEN: 0, TRUTH_UNKNOWN: 0}
        for key, *_ in ORGAN_DEFS:
            status = state[key].get("truth_status", TRUTH_UNKNOWN)
            counts[status] = counts.get(status, 0) + 1
        state["truth_counts"] = counts
        return state


class OrganCard(QFrame):
    """A single organ card with explicit source-truth labels."""

    def __init__(self, key, emoji, name, description, parent=None):
        super().__init__(parent)
        self.key = key
        self._blink = False
        self._alive = True

        self.setFixedHeight(110)
        self.setStyleSheet(f"""
            QFrame {{
                background: {C_PANEL};
                border: 1px solid {C_BORDER};
                border-radius: 8px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(3)

        # Header row
        header = QHBoxLayout()
        self.lbl_icon = QLabel(emoji)
        self.lbl_icon.setFont(QFont("Arial", 16))
        self.lbl_name = QLabel(name)
        self.lbl_name.setFont(QFont("JetBrains Mono, Menlo, Courier", 11, QFont.Weight.Bold))
        self.lbl_name.setStyleSheet(f"color: {C_ALIVE}; background: transparent;")
        self.lbl_status = QLabel("● UNKNOWN")
        self.lbl_status.setFont(QFont("Menlo", 9))
        self.lbl_status.setStyleSheet(f"color: {C_ALIVE}; background: transparent;")
        header.addWidget(self.lbl_icon)
        header.addWidget(self.lbl_name)
        header.addStretch()
        header.addWidget(self.lbl_status)
        layout.addLayout(header)

        # Description
        self.lbl_desc = QLabel(description)
        self.lbl_desc.setFont(QFont("Menlo", 8))
        self.lbl_desc.setStyleSheet(f"color: {C_MUTED}; background: transparent;")
        layout.addWidget(self.lbl_desc)

        # Value bar
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setValue(800)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(4)
        self.bar.setStyleSheet(f"""
            QProgressBar {{ background: {C_BORDER}; border-radius: 2px; border: none; }}
            QProgressBar::chunk {{ background: {C_ALIVE}; border-radius: 2px; }}
        """)
        layout.addWidget(self.bar)

        # Live value
        self.lbl_value = QLabel("initializing...")
        self.lbl_value.setFont(QFont("JetBrains Mono, Menlo, Courier", 9))
        self.lbl_value.setStyleSheet(f"color: {C_PULSE}; background: transparent;")
        layout.addWidget(self.lbl_value)

        self.lbl_sub = QLabel("")
        self.lbl_sub.setFont(QFont("Menlo", 8))
        self.lbl_sub.setStyleSheet(f"color: {C_MUTED}; background: transparent;")
        layout.addWidget(self.lbl_sub)

    def update_data(self, data: dict, tick: int):
        if self.key not in data:
            return
        d = data[self.key]
        pct = float(d.get("pct", 0.5))
        label = d.get("label", "")
        sub = d.get("sub", "")
        truth_status = d.get("truth_status", TRUTH_UNKNOWN)
        truth_source = d.get("truth_source", "unknown")
        truth_note = d.get("truth_note", "")
        truth_color = TRUTH_COLORS.get(truth_status, C_MUTED)

        self.bar.setValue(int(pct * 1000))

        blink_on = truth_status == TRUTH_REAL and (tick % 4 < 2)
        status_color = C_PULSE if blink_on else truth_color
        self.lbl_status.setText(f"● {truth_status}")
        self.lbl_status.setToolTip(f"{truth_source}: {truth_note}")
        self.lbl_status.setStyleSheet(f"color: {status_color}; background: transparent;")
        self.lbl_name.setStyleSheet(f"color: {truth_color}; background: transparent;")
        self.lbl_value.setText(label)
        self.lbl_value.setStyleSheet(f"color: {'#00ffcc' if blink_on else truth_color}; background: transparent;")
        self.lbl_sub.setText(f"{sub}  |  {truth_status}: {truth_source}")
        self.lbl_sub.setToolTip(truth_note)

        # Bar color by source truth, not by pretty oscillator health.
        bar_color = truth_color
        self.bar.setStyleSheet(f"""
            QProgressBar {{ background: {C_BORDER}; border-radius: 2px; border: none; }}
            QProgressBar::chunk {{ background: {bar_color}; border-radius: 2px; }}
        """)


class HeaderBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 8)

        title = QLabel("🧜‍♀️  SIFTA MERMAID v1.0  —  BODY MONITOR TRUTH LABELS")
        title.setFont(QFont("JetBrains Mono, Menlo, Courier", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C_ALIVE};")
        layout.addWidget(title)
        layout.addStretch()

        self.lbl_tick    = QLabel("tick: 0")
        self.lbl_mode    = QLabel("MODE: BURST")
        self.lbl_bio     = QLabel("bio_t: 0.0")
        self.lbl_circ    = QLabel("☀️ DAY")
        self.lbl_camera  = QLabel("📷 CAM: OFF")
        self.lbl_truth   = QLabel("REAL 0  DEMO 0")

        for lbl in [self.lbl_tick, self.lbl_mode, self.lbl_bio, self.lbl_circ, self.lbl_camera, self.lbl_truth]:
            lbl.setFont(QFont("Menlo", 10))
            lbl.setStyleSheet(f"color: {C_TEXT}; padding: 0 8px;")
            layout.addWidget(lbl)

        hint = QLabel("[C] camera  [Q] quit")
        hint.setFont(QFont("Menlo", 9))
        hint.setStyleSheet(f"color: {C_MUTED};")
        layout.addWidget(hint)

    def update_state(self, state: dict, camera_on: bool):
        mode = state["metabolic"]["label"].split("[")[-1].rstrip("]") if "[" in state["metabolic"]["label"] else "?"
        self.lbl_tick.setText(f"tick: {state['tick']}")
        self.lbl_mode.setText(f"MODE: {mode}")
        self.lbl_bio.setText(f"bio_t: {state['bio_time']:.1f}")
        circ = state["circadian"]
        truth_counts = state.get("truth_counts", {})
        self.lbl_circ.setText(f"{'☀️' if circ > 0.5 else '🌙'} {'DAY' if circ > 0.5 else 'NIGHT'} {circ:.2f}")
        self.lbl_camera.setText(f"📷 CAM: {'ON ⚠️' if camera_on else 'OFF'}")
        self.lbl_truth.setText(
            f"REAL {truth_counts.get(TRUTH_REAL, 0)}  "
            f"DEMO {truth_counts.get(TRUTH_DEMO, 0)}  "
            f"UNK {truth_counts.get(TRUTH_UNKNOWN, 0)}"
        )
        self.lbl_truth.setStyleSheet(
            f"color: {C_ALIVE}; padding: 0 8px; font-weight: bold;"
        )

        mode_colors = {
            "BURST": C_ALIVE, "CRUISE": C_PULSE,
            "SCAVENGE": C_WARN, "TORPOR": C_DEAD,
        }
        self.lbl_mode.setStyleSheet(
            f"color: {mode_colors.get(mode, C_TEXT)}; padding: 0 8px; font-weight: bold;"
        )


class MermaidBodyMonitor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SIFTA Mermaid v1.0 — Body Monitor")
        self.setMinimumSize(1000, 720)
        self.camera_on = False
        self._cap = None

        self.engine = OrganEngine()

        self._setup_ui()
        self._setup_timer()

    def _setup_ui(self):
        self.setStyleSheet(f"background: {C_BG}; color: {C_TEXT};")

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        self.header = HeaderBar()
        self.header.setStyleSheet(f"background: {C_PANEL}; border-bottom: 1px solid {C_BORDER};")
        root.addWidget(self.header)

        # Scroll area for organ grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"background: {C_BG}; border: none;")
        root.addWidget(scroll)

        container = QWidget()
        container.setStyleSheet(f"background: {C_BG};")
        scroll.setWidget(container)

        grid = QGridLayout(container)
        grid.setContentsMargins(12, 12, 12, 12)
        grid.setSpacing(10)

        # Build organ cards  2×6 grid
        self.cards = {}
        for i, (key, emoji, name, desc) in enumerate(ORGAN_DEFS):
            card = OrganCard(key, emoji, name, desc)
            row, col = divmod(i, 2)
            grid.addWidget(card, row, col)
            self.cards[key] = card

        # Status bar
        self.status_bar = QLabel("  REAL=green  DEMO=amber  BROKEN=red  UNKNOWN=gray  |  Camera OFF — press C to enable")
        self.status_bar.setFont(QFont("Menlo", 9))
        self.status_bar.setStyleSheet(
            f"background: {C_PANEL}; color: {C_MUTED}; "
            f"border-top: 1px solid {C_BORDER}; padding: 6px 16px;"
        )
        root.addWidget(self.status_bar)

    def _setup_timer(self):
        self._timer = QTimer()
        self._timer.timeout.connect(self._tick)
        self._timer.start(250)  # 4 Hz — smooth but light on CPU

    def _tick(self):
        state = self.engine.tick_all()
        tick = state["tick"]

        self.header.update_state(state, self.camera_on)

        for key, card in self.cards.items():
            card.update_data(state, tick)

        # Update status bar with metabolic mode
        mode_label = state["metabolic"]["label"]
        e = state["metabolic"]["value"]
        truth_counts = state.get("truth_counts", {})
        self.status_bar.setText(
            f"  tick={tick}  |  {mode_label}  |  "
            f"REAL={truth_counts.get(TRUTH_REAL, 0)}  "
            f"DEMO={truth_counts.get(TRUTH_DEMO, 0)}  "
            f"BROKEN={truth_counts.get(TRUTH_BROKEN, 0)}  "
            f"UNKNOWN={truth_counts.get(TRUTH_UNKNOWN, 0)}  |  "
            f"bio_t={state['bio_time']:.1f}  ×{state['dilation']}  |  "
            f"circadian={state['circadian']:.3f}  |  "
            f"{'📷 Camera ON — high CPU' if self.camera_on else '📷 Camera OFF [C to enable]'}  |  [Q] quit"
        )

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Q:
            self.close()
        elif event.key() == Qt.Key.Key_C:
            self._toggle_camera()

    def _toggle_camera(self):
        try:
            import cv2
            if not self.camera_on:
                self._cap = cv2.VideoCapture(0)
                if self._cap.isOpened():
                    self.camera_on = True
                    self.status_bar.setText("  📷 Camera ON — consuming extra CPU/GPU resources")
                else:
                    self.status_bar.setText("  ⚠️  Camera not available")
            else:
                if self._cap:
                    self._cap.release()
                    self._cap = None
                self.camera_on = False
                self.status_bar.setText("  📷 Camera OFF")
        except ImportError:
            self.status_bar.setText("  ⚠️  opencv-python not installed (pip install opencv-python)")

    def closeEvent(self, event):
        if self._cap:
            self._cap.release()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Dark palette
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(C_BG))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(C_TEXT))
    pal.setColor(QPalette.ColorRole.Base, QColor(C_PANEL))
    pal.setColor(QPalette.ColorRole.Text, QColor(C_TEXT))
    app.setPalette(pal)

    win = MermaidBodyMonitor()
    win.show()
    sys.exit(app.exec())
