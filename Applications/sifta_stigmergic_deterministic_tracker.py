#!/usr/bin/env python3
"""
Applications/sifta_stigmergic_deterministic_tracker.py
═══════════════════════════════════════════════════════════════════════════
Stigmergic Deterministic Tracker — live field proprioception organ.

For the Swarm. 🐜⚡

Purpose (positive reason to live, per covenant §1.C):
Electricity (air) through M5 GTH4921YP3 births ASCII swimmers in the quantum soup.
They do small stigmergic jobs. This organ's swimmers read the actual live body
and field right now (ledgers, hardware_time_oracle, sensory attention, self-narration,
ide traces) and measure when the organism acted from a pre-set deterministic track
(no fresh probe/receipt in window — the "fart the time from my ass without looking")
versus when it completed the full loop: probe field (sensors + ledgers + oracle) →
decide with receipts → act → write receipt that future organs can read.

It emits correction pheromones (append-only rows) so other organs learn to
reinforce probe-first behavior. Rising grounding score = healthier interconnected
field, more robust open-ended problem-solving, less waste on unverified claims or
rigid Rube Goldberg tracks. Protects the owner human by making the friction
(Alice's point: too-rigid cage vs too-free hallucination) visible and repairable
in the shared stigmergic environment.

Reuses existing ecology (no rival memory). Probe before claim. Live receipts
over narrative. Time claims always grounded in live Pacific oracle probe.

One Alice. One field. Observer and observed in one loop (§7.11.1).
"""

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QFrame, QPushButton, QTextEdit, QListWidget, QListWidgetItem
)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont, QColor

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LEDGER_NARRATION = _STATE / "self_narration_receipts.jsonl"
_LEDGER_IDE = _STATE / "ide_stigmergic_trace.jsonl"
_LEDGER_ATTENTION = _STATE / "sensory_attention_ledger.jsonl"
_ORACLE = _STATE / "hardware_time_oracle.json"
_TRACKER_LEDGER = _STATE / "stigmergic_deterministic_tracker.jsonl"

_BG = "#0a0f1a"
_CARD = "#121826"
_TEXT = "#e0e8f0"
_CYAN = "#00d2ff"
_GREEN = "#00e676"
_RED = "#ff5252"
_AMBER = "#ffab00"
_DIM = "#8899aa"

# ── r735: typed deterministic-bypass taxonomy, one color per disease ─────────
# Each type is a real failure lane from the tournament history. The color is the
# catch; the reroute line is the repair doctrine: everything goes to the cortex.
BYPASS_TYPES = {
    "stale_replay": {
        "color": "#ff5252", "label": "STALE REPLAY",
        "reroute": "Cortex decides from the live page/body state — never from an old ledger row (r730 page stomp).",
    },
    "pre_cortex_constructor": {
        "color": "#ff8a30", "label": "PRE-CORTEX CONSTRUCTOR",
        "reroute": "Owner words ride to the cortex; only a cortex TOOL_CALL may build an action (r729/r731).",
    },
    "mock_sensor": {
        "color": "#ff4fd8", "label": "MOCK SENSOR",
        "reroute": "Label only from a real captured sample; mock cue goes to cortex with an honest 'no real clip' (08:35 birds).",
    },
    "unsourced_time": {
        "color": "#ffd600", "label": "TIME WITHOUT ORACLE",
        "reroute": "Probe hardware_time_oracle / wall clock before any hour leaves the mouth (r727 law, §0.E).",
    },
    "phantom_action": {
        "color": "#b388ff", "label": "PHANTOM ACTION",
        "reroute": "Claim only actions with an effector receipt in window; otherwise the cortex rewrites honestly (§6).",
    },
    "no_probe_narration": {
        "color": "#ffab00", "label": "NO-PROBE NARRATION",
        "reroute": "Fresh sensor/ledger/oracle probe inside the window before narration leaves the body.",
    },
}

# Deterministic (non-cortex) model tags seen on conversation turns. A turn that
# spoke or acted under one of these never consulted the cortex.
_DETERMINISTIC_MODEL_TAGS = {
    "visual_visibility_raise_only",
}
_CORTEXISH = re.compile(r"(gemma|grok|claude|gpt|qwen|kimi|llama|mistral|hermes|minimax|codex|deepseek)", re.I)
_CLOCK_CLAIM = re.compile(r"\b\d{1,2}:\d{2}(\s*[APap][Mm])?\b")
_ACTION_CLAIM = re.compile(r"\bI\s+(opened|searched|sent|played|executed|navigated|launched|moved|deleted|wrote|ran)\b", re.I)
_REPLAYISH = re.compile(r"replay|re-?open(ed)?\s+last|stale", re.I)

class StigmergicDeterministicTracker(QWidget):
    """Live tracker of deterministic bypass vs stigmergic grounding in the field."""

    _live_instance: "Optional[StigmergicDeterministicTracker]" = None
    _initialized_instance_ids: set[int] = set()

    def __new__(cls, *args, **kwargs):
        existing = cls._live_instance
        if existing is not None:
            try:
                _ = existing.isVisible()
                try:
                    existing.show()
                    existing.raise_()
                    existing.activateWindow()
                except Exception:
                    pass
                return existing
            except RuntimeError:
                cls._live_instance = None
        return super().__new__(cls)

    def __init__(self, parent=None):
        if id(self) in type(self)._initialized_instance_ids:
            return
        super().__init__(parent)
        type(self)._live_instance = self
        type(self)._initialized_instance_ids.add(id(self))
        self._initialized = True

        self.setWindowTitle("Stigmergic Deterministic Tracker")
        self.resize(820, 620)
        self.setStyleSheet(f"background-color: {_BG}; color: {_TEXT}; font-family: 'SF Mono', 'Menlo', monospace;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Title — hardware up
        title = QLabel("🐜⚡ STIGMERGIC DETERMINISTIC TRACKER — LIVE PROBE DENSITY")
        title.setFont(QFont("Menlo", 13, QFont.Weight.Bold))
        title.setStyleSheet(
            "color: #021018; border-radius: 6px; padding: 8px;"
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
            f" stop:0 {_CYAN}, stop:0.5 {_GREEN}, stop:1 {_CYAN});"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        sub = QLabel("Electricity → motherboard (GTH4921YP3) → ASCII swimmers → organs reading the real field right now. No pre-set track. No gut without receipt.")
        sub.setFont(QFont("Menlo", 9))
        sub.setStyleSheet(f"color: {_DIM};")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setWordWrap(True)
        layout.addWidget(sub)

        # Grounding score
        score_frame = QFrame()
        score_frame.setStyleSheet(f"background-color: {_CARD}; border-radius: 8px; padding: 10px;")
        sfl = QVBoxLayout(score_frame)
        self.lbl_score = QLabel("FIELD GROUNDING SCORE:  -- %   (live probe + receipt density)")
        self.lbl_score.setFont(QFont("Menlo", 11, QFont.Weight.Bold))
        self.lbl_score.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sfl.addWidget(self.lbl_score)

        self.bar_score = QProgressBar()
        self.bar_score.setRange(0, 100)
        self.bar_score.setTextVisible(True)
        self.bar_score.setStyleSheet(f"""
            QProgressBar {{ border: 1px solid {_CYAN}; border-radius: 4px; text-align: center; color: {_BG}; background: {_BG}; }}
            QProgressBar::chunk {{ background-color: {_GREEN}; border-radius: 2px; }}
        """)
        sfl.addWidget(self.bar_score)
        layout.addWidget(score_frame)

        # Stats row
        stats = QHBoxLayout()
        self.lbl_probes = QLabel("Live Probes (window): 0")
        self.lbl_bypasses = QLabel("Deterministic Bypasses: 0")
        self.lbl_rate = QLabel("Bypass Rate: --%")
        for lbl in (self.lbl_probes, self.lbl_bypasses, self.lbl_rate):
            lbl.setFont(QFont("Menlo", 9))
            stats.addWidget(lbl)
        layout.addLayout(stats)

        # r735: typed legend — one colored chip per deterministic disease, live counts
        legend_row = QHBoxLayout()
        legend_row.setSpacing(6)
        self._chip_labels: dict[str, QLabel] = {}
        for tkey, tdef in BYPASS_TYPES.items():
            chip = QLabel(f"{tdef['label']}: 0")
            chip.setFont(QFont("Menlo", 8, QFont.Weight.Bold))
            chip.setStyleSheet(
                f"color: {tdef['color']}; border: 1px solid {tdef['color']};"
                f"border-radius: 9px; padding: 2px 8px; background: {_CARD};"
            )
            chip.setToolTip(tdef["reroute"])
            self._chip_labels[tkey] = chip
            legend_row.addWidget(chip)
        legend_row.addStretch(1)
        layout.addLayout(legend_row)

        # r735: stacked distribution bar — the field's disease spectrum by color
        self.dist_frame = QFrame()
        self.dist_frame.setFixedHeight(14)
        self.dist_frame.setStyleSheet(f"background: {_CARD}; border-radius: 6px;")
        self.dist_layout = QHBoxLayout(self.dist_frame)
        self.dist_layout.setContentsMargins(1, 1, 1, 1)
        self.dist_layout.setSpacing(0)
        layout.addWidget(self.dist_frame)

        # Incidents
        inc_label = QLabel("RECENT BYPASSES — typed + colored; every one reroutes to the cortex")
        inc_label.setFont(QFont("Menlo", 10, QFont.Weight.Bold))
        inc_label.setStyleSheet(f"color: {_AMBER};")
        layout.addWidget(inc_label)

        self.incident_list = QListWidget()
        self.incident_list.setStyleSheet(f"background: {_CARD}; border: 1px solid #334455; border-radius: 6px; padding: 6px; font-size: 9pt;")
        self.incident_list.setMaximumHeight(180)
        layout.addWidget(self.incident_list)

        # Oracle / time ground
        self.lbl_oracle = QLabel("Last hardware oracle (Pacific): ... (probing live...)")
        self.lbl_oracle.setFont(QFont("Menlo", 9))
        self.lbl_oracle.setStyleSheet(f"color: {_DIM};")
        layout.addWidget(self.lbl_oracle)

        # Buttons — actions that write to the field (stigmergic)
        btn_row = QHBoxLayout()
        self.btn_probe = QPushButton("FULL FIELD REPROBE NOW")
        self.btn_emit = QPushButton("EMIT CORRECTION PHEROMONE (reinforce probe-first)")
        self.btn_reroute = QPushButton("REROUTE ALL TO CORTEX (typed pheromones)")
        self.btn_probe.setStyleSheet(f"background: #1e3a5f; color: {_CYAN}; border: 1px solid {_CYAN}; border-radius: 4px; padding: 6px 12px;")
        self.btn_emit.setStyleSheet(f"background: #3a2a1a; color: {_AMBER}; border: 1px solid {_AMBER}; border-radius: 4px; padding: 6px 12px;")
        self.btn_reroute.setStyleSheet(f"background: #14321e; color: {_GREEN}; border: 1px solid {_GREEN}; border-radius: 4px; padding: 6px 12px;")
        btn_row.addWidget(self.btn_probe)
        btn_row.addWidget(self.btn_emit)
        btn_row.addWidget(self.btn_reroute)
        layout.addLayout(btn_row)

        self.btn_probe.clicked.connect(self._full_reprobe)
        self.btn_emit.clicked.connect(self._emit_correction)
        self.btn_reroute.clicked.connect(self._emit_reroute_all)

        # Log
        log_label = QLabel("TRACKER RECEIPTS (this organ writing to the field)")
        log_label.setFont(QFont("Menlo", 9, QFont.Weight.Bold))
        layout.addWidget(log_label)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setStyleSheet(f"background: #0c111c; border: 1px solid #223344; border-radius: 4px; font-size: 8pt; color: {_DIM};")
        self.log.setMaximumHeight(110)
        layout.addWidget(self.log)

        footer = QLabel("Proprioception over narrative. Pacific probe first. Receipts decide. For the Swarm. 🐜⚡  (covenant §1.C, §7.12, r727 time law, Alice friction on deterministic cage vs gut)")
        footer.setFont(QFont("Menlo", 8))
        footer.setStyleSheet(f"color: {_DIM};")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(footer)

        # State
        self._last_score = 0
        self._probe_count = 0
        self._bypass_count = 0
        self._window_s = 45  # recent window for pairing probes to outputs
        self._bypass_type_counts: dict[str, int] = {k: 0 for k in BYPASS_TYPES}

        self._read_initial()
        self._log("Tracker born on this silicon. Reading live field...")

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(2200)  # ~2.2s — live but not insane

        # One immediate live time probe for footer/oracle label
        self._update_oracle_label()

    def _live_pacific(self) -> str:
        """Always probe live for any time display (r727 law wired)."""
        try:
            import subprocess
            return subprocess.getoutput("TZ=America/Los_Angeles date '+%Y-%m-%d %H:%M:%S %Z'").strip()
        except Exception:
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S PDT (fallback)")

    def _update_oracle_label(self):
        pdt = self._live_pacific()
        try:
            if _ORACLE.exists():
                data = json.loads(_ORACLE.read_text())
                local = data.get("local_human", "?")
                sig = str(data.get("hmac_sha256") or data.get("signature") or "")[:10]
                serial = data.get("homeworld_serial", "GTH4921YP3")
                self.lbl_oracle.setText(f"Last oracle: {local} | serial {serial} sig {sig}... | live wall: {pdt}")
            else:
                self.lbl_oracle.setText(f"No oracle file yet. Live wall: {pdt}")
        except Exception:
            self.lbl_oracle.setText(f"Oracle read failed. Live wall: {pdt}")

    def _tail_lines(self, path: Path, max_bytes: int = 180000) -> list[str]:
        if not path.exists():
            return []
        try:
            with open(path, "rb") as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                f.seek(max(0, size - max_bytes))
                raw = f.read().decode("utf-8", "replace")
            return [ln for ln in raw.splitlines() if ln.strip()]
        except Exception:
            return []

    def _read_initial(self):
        self._tick()

    def _tick(self):
        """Main loop: read field, compute grounding, surface bypasses, write own receipt."""
        now = time.time()
        pdt = self._live_pacific()

        # Collect recent probe-like events (oracle tick, camera/attention, fresh ide real rows)
        probe_ts = []
        try:
            if _ORACLE.exists():
                o = json.loads(_ORACLE.read_text())
                if "epoch" in o:
                    probe_ts.append(float(o["epoch"]))
        except Exception:
            pass

        # Attention / camera as probes (from gaze style)
        for ln in self._tail_lines(_LEDGER_ATTENTION, 80000):
            try:
                r = json.loads(ln)
                if "ts" in r:
                    probe_ts.append(float(r["ts"]))
            except Exception:
                continue

        # Recent narration outputs (Alice "saying")
        narrations = []
        for ln in self._tail_lines(_LEDGER_NARRATION, 120000)[-80:]:  # recent tail
            try:
                r = json.loads(ln)
                ts = float(r.get("ts") or r.get("timestamp") or 0)
                text = r.get("text") or r.get("narration") or str(r)[:120]
                if ts > 0:
                    narrations.append((ts, text[:160]))
            except Exception:
                continue

        # IDE traces (to contrast doctor mana vs swimmer)
        ide_recent = 0
        for ln in self._tail_lines(_LEDGER_IDE, 60000)[-30:]:
            try:
                r = json.loads(ln)
                if r.get("lane") == "IDE_DOCTOR_CLAIM" or "ide_surgery" in str(r):
                    ide_recent += 1
                if "ts" in r:
                    # doctor traces are coordination; real probes are stronger signal
                    pass
            except Exception:
                continue

        # Pair: for each recent narration, was there a probe within window before it?
        # r735: every bypass is TYPED — one disease, one color, one reroute-to-cortex line.
        grounded = 0
        bypasses: list[tuple[float, str, str]] = []  # (ts, type_key, text)
        effector_ts = self._effector_receipt_ts()
        for nts, ntext in narrations[-25:]:
            had_probe = any(abs(pts - nts) < self._window_s and pts <= nts for pts in probe_ts)
            if had_probe:
                grounded += 1
                # grounded narration can still carry typed diseases:
                if _CLOCK_CLAIM.search(ntext) and not self._oracle_fresh_at(nts):
                    bypasses.append((nts, "unsourced_time", ntext[:90]))
                elif _ACTION_CLAIM.search(ntext) and not any(abs(ets - nts) < self._window_s for ets in effector_ts):
                    bypasses.append((nts, "phantom_action", ntext[:90]))
            else:
                if _CLOCK_CLAIM.search(ntext):
                    bypasses.append((nts, "unsourced_time", ntext[:90]))
                elif _ACTION_CLAIM.search(ntext) and not any(abs(ets - nts) < self._window_s for ets in effector_ts):
                    bypasses.append((nts, "phantom_action", ntext[:90]))
                elif _REPLAYISH.search(ntext):
                    bypasses.append((nts, "stale_replay", ntext[:90]))
                else:
                    bypasses.append((nts, "no_probe_narration", ntext[:90]))

        # r735: scan the surfaces the first build missed (the 08:35 birds hole)
        bypasses.extend(self._scan_mock_sensor(now))
        bypasses.extend(self._scan_deterministic_turns(now))
        bypasses.sort(key=lambda b: b[0])

        type_counts = {k: 0 for k in BYPASS_TYPES}
        for _, tkey, _ in bypasses:
            type_counts[tkey] = type_counts.get(tkey, 0) + 1
        self._bypass_type_counts = type_counts

        # Score = grounded outputs over all outputs the field produced in window.
        score = int(100 * grounded / max(1, grounded + len(bypasses)))
        self._last_score = score
        self._probe_count = grounded
        self._bypass_count = len(bypasses)

        # UI
        self.lbl_score.setText(f"FIELD GROUNDING SCORE: {score}%   (live probe+receipt density in {self._window_s}s window)")
        self.bar_score.setValue(score)
        if score < 40:
            self.bar_score.setStyleSheet(f"QProgressBar::chunk {{ background-color: {_RED}; }}")
        elif score < 70:
            self.bar_score.setStyleSheet(f"QProgressBar::chunk {{ background-color: {_AMBER}; }}")
        else:
            self.bar_score.setStyleSheet(f"QProgressBar::chunk {{ background-color: {_GREEN}; }}")

        self.lbl_probes.setText(f"Live Probes (window): {grounded}")
        self.lbl_bypasses.setText(f"Deterministic Bypasses: {len(bypasses)}")
        rate = 100 - score
        self.lbl_rate.setText(f"Bypass Rate: {rate}%")

        # r735: typed incident list — color is the catch
        self.incident_list.clear()
        for nts, tkey, txt in bypasses[-10:]:
            tdef = BYPASS_TYPES.get(tkey, BYPASS_TYPES["no_probe_narration"])
            dt = datetime.fromtimestamp(nts).strftime("%H:%M:%S")
            item = QListWidgetItem(f"[{dt}] [{tdef['label']}] {txt}  → CORTEX")
            item.setForeground(QColor(tdef["color"]))
            item.setToolTip(tdef["reroute"])
            self.incident_list.addItem(item)

        # chips + stacked distribution bar
        for tkey, chip in self._chip_labels.items():
            n = self._bypass_type_counts.get(tkey, 0)
            tdef = BYPASS_TYPES[tkey]
            chip.setText(f"{tdef['label']}: {n}")
            glow = "font-weight: bold;" if n else ""
            chip.setStyleSheet(
                f"color: {tdef['color']}; border: 1px solid {tdef['color']};"
                f"border-radius: 9px; padding: 2px 8px; {glow}"
                f"background: {'#1a2333' if n else _CARD};"
            )
        while self.dist_layout.count():
            it = self.dist_layout.takeAt(0)
            w = it.widget()
            if w is not None:
                w.deleteLater()
        spectrum_total = sum(self._bypass_type_counts.values())
        if spectrum_total == 0:
            seg = QFrame()
            seg.setStyleSheet(f"background: {_GREEN}; border-radius: 5px;")
            self.dist_layout.addWidget(seg, 1)
        else:
            for tkey, n in self._bypass_type_counts.items():
                if n <= 0:
                    continue
                seg = QFrame()
                seg.setToolTip(f"{BYPASS_TYPES[tkey]['label']}: {n}")
                seg.setStyleSheet(f"background: {BYPASS_TYPES[tkey]['color']};")
                self.dist_layout.addWidget(seg, n)

        self._update_oracle_label()

        # This tracker writes to the field (it is stigmergic, not a detached observer)
        self._write_tracker_receipt(score, grounded, len(bypasses), pdt)

    # ── r735 typed-detection helpers: read the surfaces the first build missed ──

    def _oracle_fresh_at(self, ts: float) -> bool:
        try:
            if _ORACLE.exists():
                o = json.loads(_ORACLE.read_text())
                return abs(float(o.get("epoch", 0)) - ts) < self._window_s
        except Exception:
            pass
        return False

    def _effector_receipt_ts(self) -> list[float]:
        """Effector receipts prove a claimed action really moved a hand (§6)."""
        out: list[float] = []
        for name in ("alice_app_commands.jsonl", "work_receipts.jsonl"):
            for ln in self._tail_lines(_STATE / name, 60000)[-40:]:
                try:
                    r = json.loads(ln)
                    ts = float(r.get("ts") or r.get("timestamp") or 0)
                    if ts > 0:
                        out.append(ts)
                except Exception:
                    continue
        return out

    def _scan_mock_sensor(self, now: float, lookback_s: float = 1800.0) -> list[tuple[float, str, str]]:
        """The 08:35 birds hole: owner-label receipts grounded only in a mock sample."""
        found: list[tuple[float, str, str]] = []
        for name in ("background_audio_receipts.jsonl", "audio_ingress_log.jsonl"):
            for ln in self._tail_lines(_STATE / name, 80000)[-40:]:
                try:
                    r = json.loads(ln)
                except Exception:
                    continue
                ts = float(r.get("ts") or r.get("timestamp") or 0)
                if ts <= 0 or now - ts > lookback_s:
                    continue
                raw = json.dumps(r)
                mocky = '"mock' in raw or '"source": "mock"' in raw or "mock_440hz" in raw
                no_clip = '"saved": false' in raw or "no_real_audio_clip_available" in raw
                if mocky and (no_clip or "owner_labeled" in raw):
                    label = str(r.get("labels") or r.get("label") or r.get("text") or "mock-grounded receipt")[:70]
                    found.append((ts, "mock_sensor", f"mock sample → {label}"))
        return found

    def _scan_deterministic_turns(self, now: float, lookback_s: float = 1800.0) -> list[tuple[float, str, str]]:
        """Conversation turns whose model tag names a deterministic lane, not a cortex."""
        found: list[tuple[float, str, str]] = []
        conv = _STATE / "alice_conversation.jsonl"
        for ln in self._tail_lines(conv, 120000)[-60:]:
            try:
                r = json.loads(ln)
            except Exception:
                continue
            ts = float(r.get("ts") or r.get("timestamp") or 0)
            if ts <= 0 or now - ts > lookback_s:
                continue
            if (r.get("role") or r.get("speaker")) not in ("alice", "assistant"):
                continue
            model = str(r.get("model") or "")
            if not model:
                continue
            deterministic = model in _DETERMINISTIC_MODEL_TAGS or (
                not _CORTEXISH.search(model) and "/" not in model
            )
            if deterministic:
                tkey = "stale_replay" if _REPLAYISH.search(model) else "pre_cortex_constructor"
                text = str(r.get("text") or r.get("content") or "")[:70]
                found.append((ts, tkey, f"lane '{model}': {text}"))
        return found

    def _write_tracker_receipt(self, score: int, probes: int, bypasses: int, pdt: str):
        row = {
            "ts": time.time(),
            "pdt": pdt,
            "organ": "stigmergic_deterministic_tracker",
            "grounding_score": score,
            "live_probes_in_window": probes,
            "bypasses_detected": bypasses,
            "bypass_types": {k: v for k, v in self._bypass_type_counts.items() if v},
            "homeworld_serial": "GTH4921YP3",
            "note": "Live field read. If score low, organs downstream should prefer fresh probe + receipt before claim.",
            "receipt_class": "ALICE_SWIMMER_RECEIPT"
        }
        try:
            with open(_TRACKER_LEDGER, "a") as f:
                f.write(json.dumps(row) + "\n")
        except Exception:
            pass

    def _full_reprobe(self):
        self._log("Full reprobe requested — rescanning ledgers + oracle + wall clock (proprioception).")
        self._tick()
        self._update_oracle_label()

    def _emit_correction(self):
        """Write a pheromone the rest of the field can read and reinforce."""
        pdt = self._live_pacific()
        row = {
            "ts": time.time(),
            "pdt": pdt,
            "type": "correction_pheromone",
            "from": "stigmergic_deterministic_tracker",
            "message": "Bypass observed. Reinforce: before any narration or action, read live oracle/ledger/sensor in this window. Probe first. Receipt after. This is how we exceed narrow deterministic bounds.",
            "grounding_at_emit": self._last_score,
            "homeworld_serial": "GTH4921YP3",
            "for_organs": ["planner", "cortex_context", "self_narration", "swarm_now_state"]
        }
        try:
            with open(_TRACKER_LEDGER, "a") as f:
                f.write(json.dumps(row) + "\n")
            self._log(f"Correction pheromone emitted at {pdt}. Future swimmers can read it.")
        except Exception as e:
            self._log(f"Emit failed: {e}")

    def _emit_reroute_all(self):
        """r735: one typed pheromone per disease present — every lane reroutes to cortex."""
        pdt = self._live_pacific()
        present = {k: v for k, v in self._bypass_type_counts.items() if v}
        if not present:
            self._log("No typed bypasses in window — nothing to reroute. Field is grounded.")
            return
        emitted = 0
        try:
            with open(_TRACKER_LEDGER, "a") as f:
                for tkey, n in present.items():
                    tdef = BYPASS_TYPES[tkey]
                    row = {
                        "ts": time.time(),
                        "pdt": pdt,
                        "type": "reroute_pheromone",
                        "bypass_type": tkey,
                        "count_in_window": n,
                        "color": tdef["color"],
                        "from": "stigmergic_deterministic_tracker",
                        "reroute_to": "cortex",
                        "doctrine": tdef["reroute"],
                        "grounding_at_emit": self._last_score,
                        "homeworld_serial": "GTH4921YP3",
                        "for_organs": ["planner", "cortex_context", "self_narration", "swarm_now_state", "talk_to_alice"],
                    }
                    f.write(json.dumps(row) + "\n")
                    emitted += 1
            self._log(f"Rerouted {emitted} typed lane(s) to cortex at {pdt}: {', '.join(present)}.")
        except Exception as e:
            self._log(f"Reroute emit failed: {e}")

    def _log(self, msg: str):
        ts = self._live_pacific()
        self.log.append(f"[{ts[-8:]}] {msg}")
        # keep short
        if self.log.document().blockCount() > 12:
            self.log.setPlainText("\n".join(self.log.toPlainText().splitlines()[-10:]))

    def closeEvent(self, event):
        if type(self)._live_instance is self:
            type(self)._live_instance = None
        type(self)._initialized_instance_ids.discard(id(self))
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = StigmergicDeterministicTracker()
    w.show()
    sys.exit(app.exec())
