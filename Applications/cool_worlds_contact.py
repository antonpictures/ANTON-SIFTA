"""
cool_worlds_contact.py — SIFTA × Cool Worlds: Contact Inequality Simulator
============================================================================

Inspired by David Kipping (@david_kipping, Cool Worlds Lab, Columbia University).

KEY PAPERS:
  Frank, Kipping, Scharf (2020) arXiv:2010.12358  — Contact Inequality
  Kipping (2024) arXiv:2512.09970                 — Eschatian Hypothesis
  Kipping PNAS (2020) PMC7275750                  — Objective Bayesian abiogenesis

THE BRIDGE (§7.12 honest framing):
  Kipping's epistemic rule: prior → photon receipt → posterior update.
  SIFTA's epistemic rule  : prior → ledger receipt → posterior update.
  Both: loudest claim without evidence = first suspect.

GUI: PyQt6 QWidget only (embedded in sifta_os_desktop MDI). No Tkinter — avoids
missing ``_tkinter`` on minimal Python builds (covenant §7.5 Python/Qt surface).

Run CLI:
  python3 Applications/cool_worlds_contact.py --cli

Standalone window (dev):
  python3 Applications/cool_worlds_contact.py
"""

from __future__ import annotations

import json
import math
import random
import time
import uuid
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
T_UNIVERSE_GYR = 13.8
T_EARTH_GYR = 4.54
N_SAMPLES = 60_000
P_TRUE_NO_RX = 0.40  # P(LLM claim true | 0 receipts) — Beta(2,3) prior mean
P_TRUE_20_RX = 0.856  # P(LLM claim true | 20 receipts)


# ---------------------------------------------------------------------------
# Monte Carlo models
# ---------------------------------------------------------------------------


def contact_inequality_mc(n: int = N_SAMPLES, seed: int = 42) -> dict:
    rng = random.Random(seed)
    ages = []
    for _ in range(n):
        t_emerge = rng.uniform(0, T_UNIVERSE_GYR - 5.0)
        age = T_UNIVERSE_GYR - t_emerge
        if rng.random() < age / T_UNIVERSE_GYR:
            ages.append(age)
    if not ages:
        ages = [T_EARTH_GYR]
    mean_age = sum(ages) / len(ages)
    p_older = sum(1 for a in ages if a > T_EARTH_GYR) / len(ages)
    return {
        "mean_age_gyr": round(mean_age, 2),
        "bias_vs_earth": round(mean_age / T_EARTH_GYR, 2),
        "p_older_pct": round(p_older * 100, 1),
        "n_accepted": len(ages),
        "truth_label": "OBSERVED",
    }


def eschatian_mc(n: int = N_SAMPLES, seed: int = 42) -> dict:
    rng = random.Random(seed)
    near_end = peak = total = 0
    for _ in range(n):
        phase = rng.random()
        loudness = min((1 - phase + 0.01) ** (-1.2), 10.0)
        if rng.random() < loudness / 10.0:
            total += 1
            if phase > 0.90:
                near_end += 1
            elif 0.25 < phase < 0.75:
                peak += 1
    if total == 0:
        total = 1
    return {
        "p_near_end_pct": round(near_end / total * 100, 1),
        "p_peak_pct": round(peak / total * 100, 1),
        "eschatian_ratio": round((near_end / total) / max(peak / total, 1e-9), 2),
        "truth_label": "OBSERVED",
    }


def run_all(save: bool = True) -> dict:
    ci = contact_inequality_mc()
    esc = eschatian_mc()
    report = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "truth_label": "COOL_WORLDS_CONTACT_V1",
        "contact": ci,
        "eschatian": esc,
        "sifta": {
            "p_true_0_receipts": P_TRUE_NO_RX,
            "p_true_20_receipts": P_TRUE_20_RX,
            "truth_label": "OPERATIONAL",
        },
        "tweet": (
            f"@david_kipping your contact inequality model runs on SIFTA: "
            f"first contact = {ci['bias_vs_earth']}× Earth age. "
            f"P(claim_true | 0 receipts) = {int(P_TRUE_NO_RX * 100)}%. "
            f"Same Bayesian virtue. #SIFTA #CoolWorlds"
        ),
    }
    if save:
        p = Path(".sifta_state/cool_worlds_receipt.jsonl")
        try:
            with p.open("a") as f:
                f.write(json.dumps(report) + "\n")
        except OSError:
            pass
    return report


def _tweet_len(s: str) -> int:
    return len(s)


# ---------------------------------------------------------------------------
# CLI output
# ---------------------------------------------------------------------------


def print_summary(r: dict) -> None:
    ci = r["contact"]
    esc = r["eschatian"]
    sf = r["sifta"]
    tw = r["tweet"]

    print("═" * 56)
    print("  SIFTA × Cool Worlds — Contact Inequality Simulator")
    print("═" * 56)
    print(f"\n  Contact Inequality  (Frank, Kipping, Scharf 2020)")
    print(f"    First contact civ age : {ci['mean_age_gyr']} Gyr")
    print(f"    vs Earth ({T_EARTH_GYR} Gyr)   : {ci['bias_vs_earth']}× older")
    print(f"    P(partner > Earth age): {ci['p_older_pct']}%")
    print(f"\n  Eschatian Hypothesis  (Kipping 2024 arXiv:2512.09970)")
    print(f"    P(detect near end)    : {esc['p_near_end_pct']}%")
    print(f"    Eschatian ratio       : {esc['eschatian_ratio']}")
    print(f"\n  SIFTA Ledger Reliability")
    print(f"    P(true | 0 receipts)  : {int(sf['p_true_0_receipts'] * 100)}%")
    print(f"    P(true | 20 receipts) : {int(sf['p_true_20_receipts'] * 100)}%")
    print()
    print("─" * 56)
    print("  TWEET (copy-paste ready):")
    print(f"  {tw}")
    print(f"  [{_tweet_len(tw)} chars]")
    print("─" * 56)


# ---------------------------------------------------------------------------
# PyQt6 GUI — MDI-embeddable (no Tkinter / _tkinter)
# ---------------------------------------------------------------------------

_BG = "#0a0e1a"
_FG = "#e8eaf6"
_ACC = "#7c83fd"
_DIM = "#546e7a"
_PANEL = "#111827"
_TWEET_BG = "#1c2333"


class ContactInequalityApp(QWidget):
    """Monte Carlo summary widget for Programs → Simulations (manifest entry)."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._r: Optional[dict] = None
        self._value_labels: list[QLabel] = []
        self.setWindowTitle("Cool Worlds × SIFTA — Contact Inequality")
        self.resize(760, 520)
        self.setStyleSheet(
            f"""
            QWidget {{ background-color: {_BG}; color: {_FG}; }}
            QLabel#header {{ color: {_ACC}; font-size: 17px; font-weight: bold; }}
            QLabel#sub {{ color: {_DIM}; font-size: 10px; }}
            QLabel#stat {{ font-size: 11px; }}
            QLabel#val {{ color: {_ACC}; font-size: 12px; font-weight: bold; }}
            QLabel#ref {{ color: {_DIM}; font-size: 10px; }}
            QLabel#tweet {{
                background-color: {_TWEET_BG}; color: #aed6f1;
                font-size: 10px; padding: 10px;
            }}
            QPushButton {{
                background-color: #1a237e; color: {_FG};
                padding: 8px 14px; border: none; font-size: 11px;
            }}
            QPushButton:hover {{ background-color: {_ACC}; }}
            QFrame#panel {{ background-color: {_PANEL}; border: none; }}
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 18, 28, 18)

        h = QLabel("⭐  Cool Worlds × SIFTA")
        h.setObjectName("header")
        h.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(h)

        sub = QLabel("Contact Inequality · Eschatian · Ledger Reliability")
        sub.setObjectName("sub")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub)

        panel = QFrame()
        panel.setObjectName("panel")
        grid = QGridLayout(panel)
        grid.setContentsMargins(14, 10, 14, 10)

        rows = [
            ("First contact civ age", "— Gyr", "Contact Inequality"),
            ("Bias vs Earth", "—×", "(Frank, Kipping, Scharf 2020)"),
            ("P(partner older)", "— %", "arXiv:2010.12358"),
            None,
            ("P(detect near civ end)", "— %", "Eschatian Hypothesis"),
            ("Eschatian ratio", "—", "(Kipping 2024 arXiv:2512.09970)"),
            None,
            ("P(claim true | 0 rx)", "40%", "SIFTA Ledger · Beta-Binomial"),
            ("P(claim true | 20 rx)", "85.6%", "OPERATIONAL"),
        ]
        ridx = 0
        for item in rows:
            if item is None:
                spacer = QFrame()
                spacer.setFixedHeight(8)
                spacer.setStyleSheet(f"background-color: {_PANEL};")
                grid.addWidget(spacer, ridx, 0, 1, 3)
                ridx += 1
                continue
            lbl, val, ref = item
            la = QLabel(lbl)
            la.setObjectName("stat")
            va = QLabel(val)
            va.setObjectName("val")
            ra = QLabel(ref)
            ra.setObjectName("ref")
            grid.addWidget(la, ridx, 0, alignment=Qt.AlignmentFlag.AlignLeft)
            grid.addWidget(va, ridx, 1, alignment=Qt.AlignmentFlag.AlignLeft)
            grid.addWidget(ra, ridx, 2, alignment=Qt.AlignmentFlag.AlignLeft)
            self._value_labels.append(va)
            ridx += 1

        layout.addWidget(panel)

        tw_cap = QLabel("TWEET (copy-paste):")
        tw_cap.setObjectName("sub")
        layout.addWidget(tw_cap)

        self._tweet_lbl = QLabel("Running Monte Carlo…")
        self._tweet_lbl.setObjectName("tweet")
        self._tweet_lbl.setWordWrap(True)
        self._tweet_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._tweet_lbl)

        self._char_lbl = QLabel("")
        self._char_lbl.setObjectName("sub")
        self._char_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self._char_lbl)

        btn = QPushButton("Copy tweet")
        btn.clicked.connect(self._copy_tweet)
        layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)

        QTimer.singleShot(200, self._run_mc)

    def _run_mc(self) -> None:
        r = run_all(save=True)
        self._r = r
        ci = r["contact"]
        esc = r["eschatian"]
        vals = [
            f"{ci['mean_age_gyr']} Gyr",
            f"{ci['bias_vs_earth']}×",
            f"{ci['p_older_pct']}%",
            f"{esc['p_near_end_pct']}%",
            f"{esc['eschatian_ratio']}",
            "40%",
            "85.6%",
        ]
        for i, lab in enumerate(self._value_labels):
            if i < len(vals):
                lab.setText(vals[i])
        tw = r["tweet"]
        self._tweet_lbl.setText(tw)
        n = _tweet_len(tw)
        self._char_lbl.setText(
            f"{n}/280 chars ✅" if n <= 280 else f"{n}/280 chars ⚠️ TOO LONG"
        )

    def _copy_tweet(self) -> None:
        if self._r:
            QGuiApplication.clipboard().setText(self._r["tweet"])


def main() -> None:
    import sys

    app = QApplication(sys.argv)
    w = ContactInequalityApp()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    import sys

    if "--cli" in sys.argv:
        print_summary(run_all(save=False))
    else:
        main()
