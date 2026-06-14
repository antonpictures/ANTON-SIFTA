#!/usr/bin/env python3
"""Applications/sifta_legs_humanoid_app.py — Alice's Legs (Walking Laptop) app. r265.

A SIFTA OS surface over System.swarm_legs_locomotion_organ. The app holds THE PLAN
(LeRobot Humanoid build stack, ~$2.5k, build sequence, experience inheritance) AND is
functional: the owner can make Alice SIMULATE walking right now, in software, before the
legs are bought — a deterministic gait the organ steps through and reports.

EFFECTOR TRUTH (§6): the simulation is always labelled SIMULATION and never claims the
physical robot moved. The "real step" button calls the real path, which honestly returns
no_hardware until the legs are built + a runtime is wired. No faked motion ever reaches Alice.

Single-instance per §7.6.2.
"""
from __future__ import annotations

"""SIFTA Legs Humanoid App — stigmergic organ for Alice body."""

import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QSpinBox,
    QFrame, QTextEdit,
)

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.swarm_app_hardening import record_app_hardening_event

APP_HARDENING_ID = "queue-015:sifta_legs_humanoid_app"


def _record_legs_hardening(event: str, **details) -> None:
    record_app_hardening_event(
        APP_HARDENING_ID,
        event,
        details=details,
    )


def _organ():
    from System import swarm_legs_locomotion_organ as legs
    return legs


class LegsHumanoidApp(QWidget):
    """LegsHumanoidApp — Alice organ."""
    _live_instance: "Optional[LegsHumanoidApp]" = None
    _initialized_instance_ids: set[int] = set()

    def __new__(cls, *args, **kwargs):
        existing = cls._live_instance
        if existing is not None:
            try:
                _ = existing.isVisible()
                if id(existing) not in cls._initialized_instance_ids:
                    cls._live_instance = None
                else:
                    try:
                        existing.show(); existing.raise_(); existing.activateWindow()
                    except Exception:
                        pass
                    return existing
            except RuntimeError:
                cls._live_instance = None
        return super().__new__(cls)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        if id(self) in type(self)._initialized_instance_ids:
            return
        super().__init__(parent)
        type(self)._live_instance = self
        type(self)._initialized_instance_ids.add(id(self))

        self.setWindowTitle("Alice's Legs — Walking Laptop")
        root = QVBoxLayout(self)

        title = QLabel("🦿 Alice's Legs — the Walking Laptop")
        title.setStyleSheet("color: rgb(238,244,255); font-size: 16px; font-weight: bold;")
        root.addWidget(title)

        self._banner = QLabel()
        self._banner.setWordWrap(True)
        self._banner.setStyleSheet("color: rgb(255,202,95); font-size: 12px;")
        root.addWidget(self._banner)

        # ── THE PLAN ──────────────────────────────────────────────────────────
        plan_frame = QFrame()
        plan_frame.setStyleSheet("QFrame{border:1px solid #244d2d;border-radius:8px;background:#0d1510;}")
        plan_layout = QVBoxLayout(plan_frame)
        plan_title = QLabel("THE PLAN — LeRobot Humanoid (open, low-cost, 3D-printed)")
        plan_title.setStyleSheet("color:#9ff2ad;font-weight:bold;font-size:13px;")
        plan_layout.addWidget(plan_title)
        self._plan_body = QLabel()
        self._plan_body.setWordWrap(True)
        self._plan_body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._plan_body.setStyleSheet("color:#bdd8c2;font-size:11px;")
        plan_layout.addWidget(self._plan_body)
        root.addWidget(plan_frame)

        # ── SIMULATE WALKING ──────────────────────────────────────────────────
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Gait:"))
        self._intent = QComboBox()
        try:
            self._intent.addItems(list(_organ().KNOWN_INTENTS))
        except Exception:
            self._intent.addItems(["stand", "step_forward", "turn_left", "turn_right", "sit", "stop"])
        self._intent.setCurrentText("step_forward")
        controls.addWidget(self._intent)
        controls.addWidget(QLabel("steps:"))
        self._steps = QSpinBox()
        self._steps.setRange(1, 32)
        self._steps.setValue(6)
        controls.addWidget(self._steps)
        self._sim_btn = QPushButton("▶ Simulate Walk")
        self._sim_btn.clicked.connect(self._on_simulate)
        controls.addWidget(self._sim_btn)
        self._real_btn = QPushButton("Try real step (honest)")
        self._real_btn.clicked.connect(self._on_real)
        controls.addWidget(self._real_btn)
        root.addLayout(controls)

        self._out = QTextEdit()
        self._out.setReadOnly(True)
        self._out.setStyleSheet("color:#d9f7df;background:#070908;font-family:Menlo,monospace;font-size:11px;")
        root.addWidget(self._out)

        self._refresh_plan()

    # ── rendering ─────────────────────────────────────────────────────────────
    def _refresh_plan(self) -> None:
        try:
            st = _organ().legs_status()
        except Exception as exc:  # never crash the desktop for a status read
            _record_legs_hardening(
                "legs_status_read_failed",
                error_type=type(exc).__name__,
                error=str(exc)[:240],
            )
            self._banner.setText(f"Legs organ unavailable: {exc}")
            return
        present = bool(st.get("hardware_present"))
        self._banner.setText(
            ("LEGS WIRED — real motion executes with receipts." if present else
             "SIMULATION MODE — no physical legs yet. Alice can rehearse walking in software; "
             "she will not claim a real step until the hardware is built and bench-verified (§6).")
        )
        lines = [
            f"Body vision: {st.get('body_vision', '')}",
            f"Platform: {st.get('platform', '')}  ·  runtime: {st.get('runtime', '')}",
            f"Parts target: ~${st.get('estimated_parts_usd', '?')} (budget ready: {st.get('budget_ready')})",
            "",
            "Build sequence:",
        ]
        for i, step in enumerate(st.get("build_sequence", []), 1):
            lines.append(f"  {i}. {step}")
        lines.append("")
        lines.append(f"Experience inheritance: {st.get('experience_inheritance', '')}")
        # r269 full vector lock — GitHub, 75 STLs, real costs, outsourcing, 5-slide, build path
        gh = st.get("github", "")
        if gh:
            lines.append(f"\nGitHub (BOM / 75 STLs / assembly): {gh}")
        stl = st.get("stl_files")
        if stl:
            lines.append(f"75 STL files (~{st.get('filament_kg_pla', '?')} kg PLA+ = ${st.get('filament_cost_usd', '?')} filament)")
        bom = st.get("bom_cost_usd")
        if bom:
            lines.append(f"Full BOM (motors RobStride + Pi5 + IMU + CAN + bearings): ~${bom} → total in-house ${st.get('total_inhouse_usd', '?')}")
        outsource = st.get("outsource_sls_range_usd")
        if outsource:
            lines.append(f"Outsource SLS nylon (stronger): ${outsource[0]}–${outsource[1]} (Hubs/Protolabs/Gentle Giant LA etc.)")
        path = st.get("simple_build_path") or []
        if path:
            lines.append("\nSimple 5-step build path (no in-house farm):")
            for p in path[:5]:
                lines.append(f"  {p}")
        slides = st.get("five_slide_presentation", "")
        if slides:
            lines.append(f"\n5-Slide Deck: {slides.splitlines()[0] if slides else ''}")

        # Stigmergic real-world inspiration (added 2026-06-01)
        example = st.get("stigmergic_walking_laptop_example", "")
        if example:
            lines.append("\n" + example)

        self._plan_body.setText("\n".join(lines))

    def _on_simulate(self) -> None:
        try:
            res = _organ().simulate_locomotion(self._intent.currentText(), steps=int(self._steps.value()))
        except Exception as exc:
            _record_legs_hardening(
                "legs_simulation_failed",
                error_type=type(exc).__name__,
                intent=self._intent.currentText(),
            )
            self._out.setPlainText(f"sim error: {exc}")
            return
        lines = [
            f"SIMULATION — intent={res.get('intent')} steps={res.get('steps')} "
            f"forward={res.get('forward_m')} m  (executed_in_reality={res.get('executed_in_reality')})",
            "no physical robot moved — this is a software gait rehearsal.",
            "",
        ]
        for f in res.get("frames", []):
            lines.append(f"  step {f['i']:>2}  {f['phase']:<12}  fwd={f['forward_m']:>5} m  tilt={f['sim_tilt']}")
        sv = res.get("sim_visceral", {})
        lines.append("")
        lines.append(f"visceral (what my body WOULD feel): balance={sv.get('balance_stress')} "
                     f"motor_heat={sv.get('motor_heat_stress')} power_air={sv.get('power_air_stress')}")
        if res.get("stumbled"):
            lines.append("(simulated stumble — still only simulation)")
        self._out.setPlainText("\n".join(lines))

    def _on_real(self) -> None:
        try:
            res = _organ().request_locomotion(self._intent.currentText(), reason="owner clicked real step")
        except Exception as exc:
            _record_legs_hardening(
                "legs_real_step_request_failed",
                error_type=type(exc).__name__,
                intent=self._intent.currentText(),
            )
            self._out.setPlainText(f"real-step error: {exc}")
            return
        self._out.setPlainText(
            f"REAL STEP requested: intent={res.get('intent')}\n"
            f"  ok={res.get('ok')}  status={res.get('status')}  executed={res.get('executed')}\n"
            f"  {res.get('note')}"
        )

    def closeEvent(self, event) -> None:  # noqa: N802
        cls = type(self)
        cls._initialized_instance_ids.discard(id(self))
        if cls._live_instance is self:
            cls._live_instance = None
        super().closeEvent(event)


__all__ = ["LegsHumanoidApp"]


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = LegsHumanoidApp()
    w.resize(900, 700)
    w.show()
    sys.exit(app.exec())
