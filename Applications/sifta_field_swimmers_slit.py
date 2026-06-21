#!/usr/bin/env python3
"""
sifta_field_swimmers_slit.py — Swimmers Swimming Inside the Unified Field
==========================================================================

FIELD-PRIMARY ONTOLOGY. The field is the reality. Swimmers are excitations
inside it. The slit is structure in the field. Interference emerges from the
field's own dynamics and accumulated traces. No external observer needed.

This is NOT the old model where "particles" pass through slits with a
separate field alongside. Here:
  - The UNIFIED STIGMERGIC FIELD is primary (the "quantum soup")
  - Swimmers = localized excitations / wave packets propagating through it
  - Barrier + slits = static structure in the field (regions where c=0)
  - Traces = persistent |φ|² the excitations leave as they swim
  - Interference = constructive/destructive overlay of wave field
  - Detection = accumulated intensity on the far side

The swimmer never "leaves" the field. It IS the field, locally concentrated.

THE STRUCTURAL EQUATION — WAVE EQUATION (universal field propagation):
    ∂²φ/∂t² = c²∇²φ − γ·∂φ/∂t

    Split into coupled first-order:
        v += c²·∇²φ      (field acceleration from curvature)
        v *= (1 − γ)      (damping)
        φ += v             (displacement update)

    φ = field displacement (what you see)
    v = field velocity (∂φ/∂t — momentum of the field)

    This is the SAME equation for:
        Sound waves through air → interference through doorways
        Light waves (Maxwell) → double-slit interference
        Water waves (shallow) → diffraction around barriers
        Quantum fields (Klein-Gordon) → particle creation/annihilation
        Stigmergic fields → swimmers swimming through structure

    | Scale       | Field φ            | Excitations      |
    |-------------|--------------------|--------------------|
    | QFT         | quantum field      | particles          |
    | Bohm        | pilot wave ψ       | guided particles   |
    | Biology     | bioelectric field  | cells/organisms    |
    | Levin       | Vmem pattern       | cell collectives   |
    | Ant colony  | pheromone field    | ants               |
    | SIFTA       | stigmergic soup    | swimmers           |

    Same equation. Same physics. Field is primary. Excitations are
    localized concentrations of the field. "Anytime, anywhere."

RESEARCH SPINE:
    Levin, M. BioEssays 34(3), 205–217, 2012. [bioelectric pattern memory]
    Levin, M. Phys. Biol. 11, 056004, 2014. [Vmem guides morphogenesis]
    Heylighen, F. Cognitive Systems Research 38, 50–59, 2016.
        [Stigmergy as universal coordination mechanism]
    Rovelli, C. Int. J. Theor. Phys. 35, 1637–1678, 1996.
        [Relational quantum mechanics — properties = relative to context]
    Zurek, W.H. Nature Physics 5, 181–188, 2009.
        [Quantum Darwinism — environment as witness]
    Weinberg, S. The Quantum Theory of Fields (CUP, 1995).
        [Particles = excitations of underlying fields]
    Couder & Fort, PRL 97, 154101, 2006.
        [Walking droplets: classical pilot-wave analogy]

SIFTA Non-Proliferation Public License applies.
"""
from __future__ import annotations

"""SIFTA Field Swimmers Slit — stigmergic organ for Alice body."""

import hashlib
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("QtAgg")
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.colors import LinearSegmentedColormap
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QApplication, QVBoxLayout, QHBoxLayout, QWidget, QLabel,
    QPushButton, QGroupBox, QGridLayout, QSlider, QTextEdit,
    QSplitter, QComboBox,
)

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

try:
    from System.swarm_app_focus import publish_focus as _publish_focus
except Exception:
    def _publish_focus(*a, **kw):
        pass

try:
    from System.jsonl_file_lock import append_line_locked as _append_line_locked
except Exception:
    def _append_line_locked(path: Path, line: str, **_kw) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)

try:
    from System.crypto_keychain import sign_block as _sign_block_raw
    _ED25519_AVAILABLE = True
except Exception:
    _ED25519_AVAILABLE = False
    def _sign_block_raw(payload: str) -> str:
        return hashlib.sha256(payload.encode()).hexdigest()[:64]

# ── Theme ─────────────────────────────────────────────────────────────
BG      = "#040610"
PANEL   = "#0a0e1c"
TEXT    = "#d0d8f0"
MUTED   = "#4a5578"
CYAN    = "#00e6ff"
MAGENTA = "#ff2dd6"
GREEN   = "#00ff9f"
AMBER   = "#ffd166"
RED     = "#ff4466"
BLUE    = "#4da6ff"
PURPLE  = "#9b59ff"
TEAL    = "#00ccaa"

_STATE = _REPO / ".sifta_state"
_RECEIPT_LEDGER = _STATE / "field_swimmers_slit_receipts.jsonl"
_TRUTH_LABEL = "SIFTA_FIELD_SWIMMERS_SLIT_V2"
_SIM_LIMIT_NOTE = (
    "SIM_ONLY classical field-primary analogue. This widget evolves a "
    "wave equation on a stigmergic field and compares single-slit versus "
    "double-slit geometry. It demonstrates field-mediated interference in "
    "this local simulation; it does not prove the physical cause of quantum "
    "double-slit interference."
)
_STGM_PER_TICK = 0.0001
_TICK_MS = 30

_FIELD_CMAP = LinearSegmentedColormap.from_list("stigfield", [
    (0.0, "#000040"), (0.15, "#0000a0"), (0.3, "#0040ff"),
    (0.45, "#00e6ff"), (0.5, "#000000"),
    (0.55, "#ff6600"), (0.7, "#ff0044"),
    (0.85, "#ff00cc"), (1.0, "#800060"),
])


# ══════════════════════════════════════════════════════════════════════
# PHYSICS ENGINE — Wave Equation on a Stigmergic Field
# ══════════════════════════════════════════════════════════════════════

class UnifiedStigmergicField:
    """
    The unified stigmergic soup. Field-primary ontology.

    Propagation via the WAVE EQUATION — the mother of all field equations.

        ∂²φ/∂t² = c²·∇²φ − γ·∂φ/∂t

    Implemented as two coupled first-order fields:
        φ (displacement) — what you see, what interferes
        v (velocity = ∂φ/∂t) — momentum of the field

    Swimmers = localized disturbances injected into φ.
    They propagate at speed c, carrying phase information.
    At the slits, the wavefront diffracts through both openings.
    Overlapping circular wavefronts create interference.

    The barrier is NOT external — it is a region of the field where
    c=0 (the field is rigid/frozen). The slits are normal field
    where waves propagate freely. Structure IN the field.

    A MEMORY channel accumulates |φ|² over time (persistent traces).
    This is the Born-rule analog / stigmergic memory.
    """

    def __init__(self, width: int = 200, height: int = 120):
        self.width = width
        self.height = height

        self.phi = np.zeros((height, width), dtype=np.float64)
        self.vel = np.zeros((height, width), dtype=np.float64)
        self.memory = np.zeros((height, width), dtype=np.float64)

        self.c = 0.35
        self.gamma = 0.003
        self.memory_rate = 0.005
        self.memory_decay = 0.9999

        # Speed map: 1.0 = normal, 0.0 = barrier (rigid)
        self.c_map = np.ones((height, width), dtype=np.float64)

        # Absorbing boundary layer
        self._abc_w = 12
        self._abc = np.ones((height, width), dtype=np.float64)
        self._build_abc()

        # Barrier geometry
        self.barrier_y = height * 2 // 5
        self.slit_width = max(3, width // 25)
        self.slit_sep = max(16, width // 5)
        self._build_barrier()

        # Source row: continuous plane-wave driver
        self.source_y = height - self._abc_w - 4

        # Detector
        self.detector_y = max(6, self._abc_w + 2)
        self.detector = np.zeros(width, dtype=np.float64)
        self.total_energy = 0.0
        self.tick_count = 0

    def _build_abc(self) -> None:
        w = self._abc_w
        for i in range(w):
            f = ((w - i) / w) ** 2
            damp = 1.0 - f * 0.2
            self._abc[i, :] *= damp
            self._abc[-(i + 1), :] *= damp
            self._abc[:, i] *= damp
            self._abc[:, -(i + 1)] *= damp

    def _build_barrier(self, two_slits: bool = True) -> None:
        self.c_map[:] = 1.0
        thickness = 2
        for dy in range(thickness):
            by = self.barrier_y + dy
            if 0 <= by < self.height:
                self.c_map[by, :] = 0.0
                hw = self.slit_width // 2
                cx = self.width // 2
                s1 = cx - self.slit_sep // 2
                s2 = cx + self.slit_sep // 2
                for sc in ([s1, s2] if two_slits else [cx]):
                    lo = max(0, sc - hw)
                    hi = min(self.width, sc + hw + 1)
                    self.c_map[by, lo:hi] = 1.0

    def set_slit_mode(self, two_slits: bool) -> None:
        self._build_barrier(two_slits)

    def drive_source(self, freq: float) -> None:
        """Drive a continuous sinusoidal plane-wave source."""
        t = self.tick_count
        val = 0.3 * math.sin(freq * t)
        y = self.source_y
        margin = self._abc_w + 2
        self.phi[y, margin:self.width - margin] = val

    def inject_single_pulse(self, sigma: float = 4.0,
                            amplitude: float = 2.0) -> None:
        """
        Inject a SINGLE localized excitation (one swimmer) at the source.

        This is a gaussian pulse — one concentrated disturbance in the field.
        The wave equation will propagate it outward as an expanding circular
        wavefront. When it reaches the barrier, the wavefront passes through
        BOTH slits (because it's a field, not a particle). The two secondary
        wavefronts overlap and interfere on the far side.

        This demonstrates SELF-INTERFERENCE: one excitation, two paths,
        interference pattern — all inside the unified field.
        """
        cx = self.width // 2
        cy = self.source_y
        r = int(sigma * 3)
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                jy, jx = cy + dy, cx + dx
                if 0 <= jy < self.height and 0 <= jx < self.width:
                    if self.c_map[jy, jx] > 0.1:
                        d2 = dx * dx + dy * dy
                        self.phi[jy, jx] += amplitude * math.exp(
                            -d2 / (2.0 * sigma * sigma)
                        )

    # ── Stigmergic collapse / measurement ─────────────────────────────

    def collapse_tick(self, threshold: float = 0.02,
                      feedback_gain: float = 0.3,
                      suppression: float = 0.85) -> list[int]:
        """
        Stigmergic measurement / collapse at the detector row.

        When accumulated field intensity at a detector cell exceeds
        the threshold, that cell triggers POSITIVE FEEDBACK:
          - Its own trace is amplified (winner gets stronger)
          - Neighboring cells are suppressed (losers fade)

        This is the stigmergic version of wavefunction collapse:
          - No external observer needed
          - No mysterious discontinuity
          - Just local field interaction creating irreversible traces
          - The field "decides" where the swimmer landed

        Returns list of collapsed cell indices.
        """
        det = self.detector
        if det.max() < threshold:
            return []

        collapsed = []
        for x in range(2, self.width - 2):
            if det[x] > threshold and det[x] >= det[x - 1] and det[x] >= det[x + 1]:
                det[x] *= (1.0 + feedback_gain)
                for dx in range(-3, 4):
                    nx = x + dx
                    if 0 <= nx < self.width and nx != x:
                        det[nx] *= suppression
                collapsed.append(x)

        return collapsed

    def tick(self) -> None:
        """
        Evolve the field by one timestep.

            v += c²·c_map·∇²φ      (acceleration from field curvature)
            v *= (1 − γ)            (damping)
            v *= abc                (absorbing boundary)
            φ += v                  (update displacement)
            φ *= abc                (absorbing boundary)
            φ[barrier] = 0          (rigid boundary)
            memory += rate·φ²       (accumulate traces)
        """
        c2 = self.c ** 2

        # Laplacian (zero-padded, not periodic)
        lap = np.zeros_like(self.phi)
        lap[:, 1:] += self.phi[:, :-1]
        lap[:, :-1] += self.phi[:, 1:]
        lap[1:, :] += self.phi[:-1, :]
        lap[:-1, :] += self.phi[1:, :]
        lap -= 4.0 * self.phi

        self.vel += c2 * self.c_map * lap
        self.vel *= (1.0 - self.gamma)
        self.vel *= self._abc
        self.phi += self.vel
        self.phi *= self._abc

        barrier = self.c_map < 0.1
        self.phi[barrier] = 0.0
        self.vel[barrier] = 0.0

        self.memory += self.memory_rate * (self.phi ** 2)
        self.memory *= self.memory_decay

        self.detector += self.phi[self.detector_y, :] ** 2
        self.total_energy = float(np.sum(self.phi ** 2 + self.vel ** 2))
        self.tick_count += 1

    def combined_field(self) -> np.ndarray:
        return self.phi

    def detector_pattern(self) -> np.ndarray:
        return self.detector.copy()


class FieldSwimmerExperiment:
    """
    Field-primary double-slit experiment.

    A continuous plane-wave source drives the field from one end.
    The wavefront propagates through the field, passes through slit(s),
    and the interference pattern builds on the detector as accumulated |φ|².
    """

    def __init__(self, seed: int = 42, *, two_slits: bool = True,
                 width: int = 200, height: int = 120):
        self.rng = np.random.default_rng(seed)
        self.field = UnifiedStigmergicField(width, height)
        self.field.set_slit_mode(two_slits)
        self.two_slits = two_slits
        self.excitations_injected = 0
        self.total_stgm = 0.0
        self.chain_hash = "0" * 32

        # Source frequency: wavelength ≈ slit_sep / 2 for visible fringes
        wavelength = max(6.0, self.field.slit_sep / 2.0)
        self.source_freq = 2.0 * math.pi / (wavelength / self.field.c)

    def tick(self, inject_per_tick: int = 1) -> None:
        self.field.drive_source(self.source_freq)
        self.field.tick()
        self.excitations_injected += inject_per_tick
        self.total_stgm += _STGM_PER_TICK

        body = f"FSWIM:{self.excitations_injected}:{self.field.tick_count}"
        self.chain_hash = hashlib.sha256(
            f"{self.chain_hash}:{body}".encode()
        ).hexdigest()[:32]

    def detector_pattern(self) -> np.ndarray:
        return self.field.detector_pattern()

    def metrics(self) -> dict[str, Any]:
        det = self.detector_pattern()
        total = float(np.sum(det))
        if total <= 0.0:
            return {
                "truth_label": _TRUTH_LABEL,
                "two_slits": self.two_slits,
                "ticks": self.field.tick_count,
                "peak_count": 0,
                "spread_bins": 0,
                "fringe_visibility": 0.0,
                "detector_total": 0.0,
            }

        mx = float(np.max(det))
        threshold = mx * 0.18
        active = np.where(det > threshold)[0]
        spread = int(active[-1] - active[0] + 1) if len(active) else 0

        peaks: list[int] = []
        prominence = mx * 0.12
        window = max(4, len(det) // 20)
        for idx in range(1, len(det) - 1):
            if det[idx] <= threshold:
                continue
            if not (det[idx] >= det[idx - 1] and det[idx] >= det[idx + 1]):
                continue
            left = float(np.min(det[max(0, idx - window): idx + 1]))
            right = float(np.min(det[idx: min(len(det), idx + window + 1)]))
            if det[idx] - max(left, right) >= prominence:
                peaks.append(idx)

        quarter = len(det) // 4
        middle = det[quarter: len(det) - quarter]
        i_max = float(np.max(middle)) if len(middle) else 0.0
        i_min = float(np.min(middle)) if len(middle) else 0.0
        visibility = (i_max - i_min) / (i_max + i_min) if (i_max + i_min) > 0 else 0.0

        return {
            "truth_label": _TRUTH_LABEL,
            "two_slits": self.two_slits,
            "ticks": self.field.tick_count,
            "peak_count": len(peaks),
            "peak_positions": peaks,
            "spread_bins": spread,
            "fringe_visibility": round(visibility, 4),
            "detector_total": round(total, 4),
        }

    def write_receipt(self) -> dict[str, Any]:
        metrics = self.metrics()

        receipt = {
            "ts": time.time(),
            "schema": _TRUTH_LABEL,
            "truth_label": _TRUTH_LABEL,
            "kind": "FIELD_SWIMMERS_SLIT_BATCH",
            "ontology": "FIELD_PRIMARY",
            "spatial_dimensions": 2,
            "ticks": self.field.tick_count,
            "two_slits": self.two_slits,
            "peak_count": metrics["peak_count"],
            "peak_positions": metrics["peak_positions"],
            "spread_bins": metrics["spread_bins"],
            "fringe_visibility": metrics["fringe_visibility"],
            "detector_total": metrics["detector_total"],
            "field_energy": round(self.field.total_energy, 2),
            "stgm_cost": round(self.total_stgm, 6),
            "chain": self.chain_hash[:16],
            "limit_note": _SIM_LIMIT_NOTE,
            "note": (
                "Wave equation on stigmergic field. Swimmers = excitations. "
                "Slit = field structure (c=0). No external observer."
            ),
        }
        body = json.dumps(receipt, sort_keys=True, separators=(",", ":"))
        receipt["seal"] = _sign_block_raw(body)[:64]
        receipt["seal_type"] = "ed25519" if _ED25519_AVAILABLE else "sha256"
        _STATE.mkdir(parents=True, exist_ok=True)
        _append_line_locked(_RECEIPT_LEDGER,
                            json.dumps(receipt, ensure_ascii=False) + "\n")
        return receipt


class SinglePulseExperiment:
    """
    Single-excitation self-interference experiment.

    Inject ONE pulse. Watch the field carry it through both slits.
    See interference fringes build from a SINGLE excitation.
    Then optionally trigger stigmergic collapse at the detector.

    This is the key demonstration:
      - One swimmer (one pulse in the field)
      - Field carries wavefront through BOTH slits
      - Self-interference on the far side
      - Collapse = local field feedback, no observer
    """

    def __init__(self, *, two_slits: bool = True,
                 width: int = 200, height: int = 120):
        self.field = UnifiedStigmergicField(width, height)
        self.field.set_slit_mode(two_slits)
        self.two_slits = two_slits
        self.pulse_injected = False
        self.collapsed = False
        self.collapse_sites: list[int] = []
        self.total_stgm = 0.0
        self.chain_hash = "0" * 32

    def inject_pulse(self) -> None:
        if not self.pulse_injected:
            self.field.inject_single_pulse(sigma=3.5, amplitude=2.5)
            self.pulse_injected = True

    def tick(self) -> None:
        self.field.tick()
        self.total_stgm += _STGM_PER_TICK
        body = f"SPULSE:{self.field.tick_count}"
        self.chain_hash = hashlib.sha256(
            f"{self.chain_hash}:{body}".encode()
        ).hexdigest()[:32]

    def trigger_collapse(self, threshold: float = 0.0) -> list[int]:
        """Trigger stigmergic collapse at the detector."""
        if self.collapsed:
            return self.collapse_sites
        det = self.field.detector
        auto_thresh = float(det.max()) * 0.3 if threshold <= 0 else threshold
        if auto_thresh <= 0:
            return []
        sites = self.field.collapse_tick(
            threshold=auto_thresh, feedback_gain=0.5, suppression=0.7
        )
        if sites:
            self.collapsed = True
            self.collapse_sites = sites
        return sites

    def detector_pattern(self) -> np.ndarray:
        return self.field.detector_pattern()

    def write_receipt(self) -> dict[str, Any]:
        det = self.detector_pattern()
        total = float(np.sum(det))
        mx = float(np.max(det)) if total > 0 else 0
        receipt = {
            "ts": time.time(),
            "schema": _TRUTH_LABEL,
            "kind": "SINGLE_PULSE_SELF_INTERFERENCE",
            "ontology": "FIELD_PRIMARY",
            "ticks": self.field.tick_count,
            "two_slits": self.two_slits,
            "pulse_injected": self.pulse_injected,
            "collapsed": self.collapsed,
            "collapse_sites": self.collapse_sites[:5],
            "detector_max": round(mx, 6),
            "detector_total": round(total, 4),
            "field_energy": round(self.field.total_energy, 2),
            "stgm_cost": round(self.total_stgm, 6),
            "chain": self.chain_hash[:16],
            "limit_note": _SIM_LIMIT_NOTE,
        }
        body = json.dumps(receipt, sort_keys=True, separators=(",", ":"))
        receipt["seal"] = _sign_block_raw(body)[:64]
        receipt["seal_type"] = "ed25519" if _ED25519_AVAILABLE else "sha256"
        _STATE.mkdir(parents=True, exist_ok=True)
        _append_line_locked(_RECEIPT_LEDGER,
                            json.dumps(receipt, ensure_ascii=False) + "\n")
        return receipt


# ══════════════════════════════════════════════════════════════════════
# PyQt6 GUI — Field Swimmers Slit Widget
# ══════════════════════════════════════════════════════════════════════

class FieldSwimmersSlitWidget(QWidget):
    """
    Field-Primary Double-Slit Experiment.

    The field is the reality. Swimmers are excitations inside it.
    Watch waves propagate through slits — inside the soup the whole time.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._init_experiments()
        self._setup_ui()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start(_TICK_MS)
        self._auto = True
        self._tick_count = 0
        try:
            _publish_focus(
                "Field-Primary Slit",
                "Wave equation double-slit: excitations in unified field",
                tab="Simulation",
                metadata={"truth_label": _TRUTH_LABEL, "limit_note": _SIM_LIMIT_NOTE},
            )
        except Exception:
            pass

    def _init_experiments(self) -> None:
        seed = int(time.time()) % 100000
        self.exp_double = FieldSwimmerExperiment(seed=seed, two_slits=True)
        self.exp_single = FieldSwimmerExperiment(seed=seed + 1, two_slits=False)
        self._pulse_double = SinglePulseExperiment(two_slits=True)
        self._pulse_single = SinglePulseExperiment(two_slits=False)
        self._mode = "continuous"  # or "single_pulse"

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            QWidget {{ background: {BG}; color: {TEXT};
                       font-family: 'Menlo', monospace; }}
            QGroupBox {{ border: 1px solid {MUTED}; border-radius: 6px;
                         margin-top: 8px; padding-top: 14px;
                         font-weight: bold; color: {CYAN}; }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 10px; }}
            QPushButton {{ background: {PANEL}; border: 1px solid {MUTED};
                           border-radius: 4px; padding: 6px 14px; color: {TEXT}; }}
            QPushButton:hover {{ border-color: {CYAN}; }}
            QSlider::groove:horizontal {{ background: {MUTED}; height: 6px;
                                          border-radius: 3px; }}
            QSlider::handle:horizontal {{ background: {CYAN}; width: 14px;
                                          margin: -4px 0; border-radius: 7px; }}
            QTextEdit {{ background: {PANEL}; border: 1px solid {MUTED};
                         border-radius: 4px; color: {TEXT}; font-size: 11px; }}
        """)

        main = QVBoxLayout(self)
        main.setContentsMargins(6, 6, 6, 6)

        title = QLabel("UNIFIED STIGMERGIC FIELD — SWIMMERS INSIDE THE SOUP")
        title.setStyleSheet(
            f"font-size: 16px; font-weight: bold; color: {CYAN}; padding: 2px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main.addWidget(title)

        sub = QLabel(
            "Field is primary. Swimmers = excitations. Slit = field structure. "
            "Wave equation: same as sound, light, quantum fields. "
            "Anytime, anywhere."
        )
        sub.setStyleSheet(f"font-size: 10px; color: {MUTED}; padding: 1px;")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main.addWidget(sub)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        main.addWidget(splitter, stretch=1)

        # LEFT — plots
        plot_w = QWidget()
        plot_l = QVBoxLayout(plot_w)
        plot_l.setContentsMargins(0, 0, 0, 0)
        self._fig = Figure(figsize=(12, 9), facecolor=BG)
        self._canvas = FigureCanvas(self._fig)
        plot_l.addWidget(self._canvas)
        splitter.addWidget(plot_w)

        # RIGHT — controls + explanation
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(4, 0, 4, 0)

        # Stats
        sg = QGroupBox("FIELD STATUS")
        sgl = QVBoxLayout(sg)
        self._stats = QLabel("Ticks: 0")
        self._stats.setStyleSheet(f"font-size: 11px;")
        self._stats.setWordWrap(True)
        sgl.addWidget(self._stats)
        rl.addWidget(sg)

        # Controls
        cg = QGroupBox("CONTROLS")
        cl = QGridLayout(cg)

        cl.addWidget(QLabel("Wave speed:"), 0, 0)
        self._speed_slider = QSlider(Qt.Orientation.Horizontal)
        self._speed_slider.setRange(10, 45)
        self._speed_slider.setValue(35)
        self._speed_slider.valueChanged.connect(self._on_speed)
        cl.addWidget(self._speed_slider, 0, 1)
        self._speed_val = QLabel("0.35")
        self._speed_val.setStyleSheet(f"color: {AMBER};")
        cl.addWidget(self._speed_val, 0, 2)

        cl.addWidget(QLabel("Damping:"), 1, 0)
        self._damp_slider = QSlider(Qt.Orientation.Horizontal)
        self._damp_slider.setRange(1, 30)
        self._damp_slider.setValue(3)
        self._damp_slider.valueChanged.connect(self._on_damp)
        cl.addWidget(self._damp_slider, 1, 1)
        self._damp_val = QLabel("0.003")
        self._damp_val.setStyleSheet(f"color: {AMBER};")
        cl.addWidget(self._damp_val, 1, 2)

        cl.addWidget(QLabel("Mode:"), 2, 0)
        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["Continuous Wave", "Single Pulse"])
        self._mode_combo.currentIndexChanged.connect(self._on_mode_change)
        cl.addWidget(self._mode_combo, 2, 1, 1, 2)

        self._pause_btn = QPushButton("PAUSE")
        self._pause_btn.clicked.connect(self._toggle_pause)
        cl.addWidget(self._pause_btn, 3, 0)

        self._reset_btn = QPushButton("RESET")
        self._reset_btn.clicked.connect(self._on_reset)
        cl.addWidget(self._reset_btn, 3, 1)

        self._receipt_btn = QPushButton("RECEIPT")
        self._receipt_btn.clicked.connect(self._on_receipt)
        cl.addWidget(self._receipt_btn, 3, 2)

        self._collapse_btn = QPushButton("COLLAPSE")
        self._collapse_btn.setToolTip(
            "Trigger stigmergic measurement: local field feedback "
            "amplifies strongest detector cells, suppresses others. "
            "No external observer — just field dynamics."
        )
        self._collapse_btn.clicked.connect(self._on_collapse)
        self._collapse_btn.setStyleSheet(
            f"QPushButton {{ background: #1a0020; border: 1px solid {MAGENTA}; "
            f"color: {MAGENTA}; }} QPushButton:hover {{ border-color: {RED}; }}"
        )
        cl.addWidget(self._collapse_btn, 4, 0, 1, 3)

        rl.addWidget(cg)

        # Explanation
        eg = QGroupBox("FIELD-PRIMARY ONTOLOGY")
        el = QVBoxLayout(eg)
        explain = QTextEdit()
        explain.setReadOnly(True)
        explain.setMaximumHeight(250)
        explain.setHtml(f"""
        <p style="color:{CYAN}"><b>The field IS the reality.</b></p>
        <p>Swimmers are not separate objects. They ARE localized
        excitations — wave packets propagating through the unified
        stigmergic soup via the wave equation.</p>

        <p style="color:{GREEN}"><b>What you see:</b></p>
        <ul>
        <li><span style="color:{AMBER}">Blue/Red ripples</span> =
            wave field φ (positive/negative displacement)</li>
        <li><span style="color:{AMBER}">Bright line</span> =
            plane-wave source (coherent excitation)</li>
        <li><span style="color:{AMBER}">Dark horizontal band</span> =
            barrier (c=0, field is rigid there)</li>
        <li><span style="color:{AMBER}">Gaps in band</span> =
            slits (c=1, normal field)</li>
        <li><span style="color:{AMBER}">Memory glow</span> =
            accumulated |φ|² traces (stigmergic memory)</li>
        </ul>

        <p style="color:{MAGENTA}"><b>Why interference appears:</b></p>
        <p>The wavefront passes through both slits (it's a FIELD, not a
        particle). Two circular wavefronts emerge from the slits and overlap.
        Where they are in phase → constructive (bright). Where out of
        phase → destructive (dark). The detector accumulates this pattern
        as persistent stigmergic memory.</p>

        <p style="color:{PURPLE}"><b>Same equation everywhere:</b></p>
        <p><code>∂²φ/∂t² = c²∇²φ − γ·∂φ/∂t</code></p>
        <p>Sound through doorways. Light through slits. Water through
        gaps. Quantum fields. Stigmergic fields. ONE equation.</p>
        """)
        el.addWidget(explain)
        rl.addWidget(eg)

        # Log
        lg = QGroupBox("RECEIPT LOG")
        ll = QVBoxLayout(lg)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(80)
        ll.addWidget(self._log)
        rl.addWidget(lg)

        rl.addStretch()
        splitter.addWidget(right)
        splitter.setSizes([800, 350])

    # ── Tick ──────────────────────────────────────────────────────────

    def _on_mode_change(self, idx: int) -> None:
        self._mode = "single_pulse" if idx == 1 else "continuous"
        self._on_reset()
        if self._mode == "single_pulse":
            self._pulse_double.inject_pulse()
            self._pulse_single.inject_pulse()

    def _on_collapse(self) -> None:
        if self._mode == "single_pulse":
            sites_d = self._pulse_double.trigger_collapse()
            sites_s = self._pulse_single.trigger_collapse()
            if sites_d or sites_s:
                self._log.append(
                    f"[{time.strftime('%H:%M:%S')}] COLLAPSE! "
                    f"Double sites: {sites_d[:5]} | "
                    f"Single sites: {sites_s[:5]}"
                )
                self._pulse_double.write_receipt()
            self._draw()
        else:
            self._log.append(
                f"[{time.strftime('%H:%M:%S')}] "
                "Switch to Single Pulse mode to trigger collapse."
            )

    def _on_tick(self) -> None:
        if not self._auto:
            return
        if self._mode == "continuous":
            for _ in range(3):
                self.exp_double.tick()
                self.exp_single.tick()
        else:
            for _ in range(3):
                self._pulse_double.tick()
                self._pulse_single.tick()
        self._tick_count += 1
        if self._tick_count % 2 == 0:
            self._draw()
        if self._tick_count % 5 == 0:
            self._update_stats()
        if self._tick_count % 200 == 0 and self._mode == "continuous":
            self.exp_double.write_receipt()

    def _on_speed(self, val: int) -> None:
        c = val / 100.0
        self.exp_double.field.c = c
        self.exp_single.field.c = c
        self._speed_val.setText(f"{c:.2f}")

    def _on_damp(self, val: int) -> None:
        g = val / 1000.0
        self.exp_double.field.gamma = g
        self.exp_single.field.gamma = g
        self._damp_val.setText(f"{g:.3f}")

    def _toggle_pause(self) -> None:
        self._auto = not self._auto
        self._pause_btn.setText("RESUME" if not self._auto else "PAUSE")

    def _on_reset(self) -> None:
        self._init_experiments()
        c = self._speed_slider.value() / 100.0
        g = self._damp_slider.value() / 1000.0
        for exp in (self.exp_double, self.exp_single):
            exp.field.c = c
            exp.field.gamma = g
        self._tick_count = 0
        self._log.clear()
        self._draw()
        self._update_stats()

    def _on_receipt(self) -> None:
        r = self.exp_double.write_receipt()
        self._log.append(
            f"[{time.strftime('%H:%M:%S')}] seal={r['seal'][:12]}... "
            f"ticks={r['ticks']} vis={r['fringe_visibility']:.3f}"
        )

    def _update_stats(self) -> None:
        if self._mode == "continuous":
            d = self.exp_double
            s = self.exp_single
            self._stats.setText(
                f"Mode: CONTINUOUS WAVE\n"
                f"Field ticks: {d.field.tick_count}\n"
                f"Energy (double): {d.field.total_energy:.1f}\n"
                f"Energy (single): {s.field.total_energy:.1f}\n"
                f"Slit sep: {d.field.slit_sep} | Slit w: {d.field.slit_width}\n"
                f"STGM: {d.total_stgm:.4f}\n"
                f"Chain: {d.chain_hash[:12]}..."
            )
        else:
            pd = self._pulse_double
            ps = self._pulse_single
            collapse_str = (
                f"COLLAPSED at {pd.collapse_sites[:3]}"
                if pd.collapsed else "Not collapsed"
            )
            self._stats.setText(
                f"Mode: SINGLE PULSE (self-interference)\n"
                f"Field ticks: {pd.field.tick_count}\n"
                f"Energy (double): {pd.field.total_energy:.4f}\n"
                f"Energy (single): {ps.field.total_energy:.4f}\n"
                f"Pulse injected: {pd.pulse_injected}\n"
                f"Collapse: {collapse_str}\n"
                f"STGM: {pd.total_stgm:.4f}"
            )

    # ── Drawing ───────────────────────────────────────────────────────

    def _get_active_experiments(self):
        if self._mode == "continuous":
            return self.exp_double, self.exp_single
        return self._pulse_double, self._pulse_single

    def _draw(self) -> None:
        self._fig.clear()
        exp_d, exp_s = self._get_active_experiments()

        ax_d_field = self._fig.add_subplot(3, 2, 1)
        ax_s_field = self._fig.add_subplot(3, 2, 2)
        ax_d_det = self._fig.add_subplot(3, 2, 3)
        ax_s_det = self._fig.add_subplot(3, 2, 4)
        ax_compare = self._fig.add_subplot(3, 2, 5)
        ax_memory = self._fig.add_subplot(3, 2, 6)

        all_axes = [ax_d_field, ax_s_field, ax_d_det, ax_s_det,
                    ax_compare, ax_memory]
        for ax in all_axes:
            ax.set_facecolor(PANEL)
            ax.tick_params(colors=MUTED, labelsize=6)
            for sp in ax.spines.values():
                sp.set_color("#1a2040")

        mode_label = ("SINGLE PULSE — self-interference"
                      if self._mode == "single_pulse"
                      else "CONTINUOUS WAVE")

        # 1. Double-slit wave field (φ)
        snap_d = exp_d.field.phi
        vmax = max(0.01, float(np.percentile(np.abs(snap_d), 99)))
        ax_d_field.imshow(snap_d, aspect="auto", cmap="RdBu_r",
                          vmin=-vmax, vmax=vmax,
                          origin="upper", interpolation="bilinear")
        by = exp_d.field.barrier_y
        ax_d_field.axhline(by, color=CYAN, linewidth=0.5, alpha=0.5)
        ax_d_field.set_title(f"DOUBLE SLIT — {mode_label}",
                             color=CYAN, fontsize=9, fontweight="bold")

        # 2. Single-slit wave field
        snap_s = exp_s.field.phi
        vmax_s = max(0.01, float(np.percentile(np.abs(snap_s), 99)))
        ax_s_field.imshow(snap_s, aspect="auto", cmap="RdBu_r",
                          vmin=-vmax_s, vmax=vmax_s,
                          origin="upper", interpolation="bilinear")
        ax_s_field.axhline(exp_s.field.barrier_y,
                           color=MAGENTA, linewidth=0.5, alpha=0.5)
        ax_s_field.set_title(f"SINGLE SLIT — {mode_label}",
                             color=MAGENTA, fontsize=9, fontweight="bold")

        # 3. Double-slit detector (accumulated |φ|²)
        det_d = exp_d.detector_pattern()
        x_range = np.arange(len(det_d))
        ax_d_det.fill_between(x_range, det_d, alpha=0.6, color=CYAN)
        ax_d_det.plot(x_range, det_d, "-", color=CYAN, linewidth=1)
        # Mark collapse sites
        if (self._mode == "single_pulse"
                and hasattr(exp_d, 'collapse_sites') and exp_d.collapse_sites):
            for cx in exp_d.collapse_sites[:5]:
                if 0 <= cx < len(det_d):
                    ax_d_det.axvline(cx, color=RED, linewidth=1.5,
                                     alpha=0.7, linestyle="--")
            ax_d_det.set_title("Detector — COLLAPSED",
                               color=RED, fontsize=9, fontweight="bold")
        else:
            ax_d_det.set_title("Detector (double slit) — |φ|²",
                               color=CYAN, fontsize=9)
        ax_d_det.set_xlabel("x", color=MUTED, fontsize=7)

        # 4. Single-slit detector
        det_s = exp_s.detector_pattern()
        ax_s_det.fill_between(np.arange(len(det_s)), det_s,
                              alpha=0.6, color=MAGENTA)
        ax_s_det.plot(np.arange(len(det_s)), det_s, "-",
                      color=MAGENTA, linewidth=1)
        ax_s_det.set_title("Detector (single slit) — |φ|²",
                           color=MAGENTA, fontsize=9)
        ax_s_det.set_xlabel("x", color=MUTED, fontsize=7)

        # 5. Comparison overlay (normalized)
        d_sum = max(1.0, det_d.sum())
        s_sum = max(1.0, det_s.sum())
        ax_compare.plot(x_range, det_d / d_sum * 100,
                        "-", color=CYAN, linewidth=1.5,
                        label="Double", alpha=0.9)
        ax_compare.plot(np.arange(len(det_s)), det_s / s_sum * 100,
                        "--", color=MAGENTA, linewidth=1.5,
                        label="Single", alpha=0.7)
        ax_compare.set_title("Normalized comparison",
                             color=AMBER, fontsize=9)
        ax_compare.legend(fontsize=7, facecolor=PANEL, edgecolor=MUTED,
                          labelcolor=TEXT)
        ax_compare.set_xlabel("x", color=MUTED, fontsize=7)
        ax_compare.set_ylabel("%", color=MUTED, fontsize=7)

        # 6. Memory field (accumulated traces — stigmergic history)
        mem_d = exp_d.field.memory
        vmax_m = max(0.001, float(np.percentile(mem_d, 99)))
        ax_memory.imshow(mem_d, aspect="auto", cmap="inferno",
                         vmin=0, vmax=vmax_m,
                         origin="upper", interpolation="bilinear")
        title_mem = "Memory traces |φ|² (stigmergic history)"
        if (self._mode == "single_pulse"
                and hasattr(exp_d, 'collapsed') and exp_d.collapsed):
            title_mem = "COLLAPSED — irreversible trace"
        ax_memory.set_title(title_mem, color=AMBER, fontsize=9)

        self._fig.tight_layout(pad=1.0, h_pad=1.5)
        self._canvas.draw_idle()

    def closeEvent(self, event) -> None:
        self._timer.stop()
        self.exp_double.write_receipt()
        super().closeEvent(event)


# ══════════════════════════════════════════════════════════════════════
# STANDALONE ENTRY POINT
# ══════════════════════════════════════════════════════════════════════

def main() -> int:
    app = QApplication(sys.argv)
    w = FieldSwimmersSlitWidget()
    w.setWindowTitle(
        "SIFTA — Unified Field: Swimmers Inside the Soup (Receipt-Backed)"
    )
    w.resize(1350, 900)
    w.show()
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
