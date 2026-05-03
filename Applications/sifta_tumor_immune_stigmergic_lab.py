"""
Event 148 — Tumor Immune Stigmergic Lab (SIFTA §10.14.27.4)

SIFTA two-signal math applied to the tumor microenvironment (TME).
The SAME activation-vs-inhibition gate that governs synaptic pruning
governs tumor immune clearance:

    SYNAPTIC PRUNING          TUMOR IMMUNITY
    ─────────────────         ─────────────────────────────
    TREM2/DAM activation  →   CTL/NK cytotoxicity pressure
    CD33/fractalkine inh  →   TREM2+TAM / Treg / checkpoint exhaustion
    net > threshold       →   immune clearance (tumor regression)
    net < threshold       →   immune escape (tumor growth)

Key papers (NO PHI, synthetic data only):
    Keren-Shaul et al. (2017) Cell 169:1276 — DAM / TREM2 in microglia
    Wang et al. (2015) Cell 160:1061 — TREM2+TAM suppress anti-tumor immunity
    Jay et al. (2015) J Exp Med 212:287 — TREM2 in tumor-associated macrophages
    Binnewies et al. (2018) Nat Med 24:541 — TME determinants of response
    Cassetta et al. (2019) Nat Commun 10:539 — TAM heterogeneity + immunosuppression
    Dunn et al. (2002) Nat Immunol 3:991 — cancer immunoediting (elimination/equilibrium/escape)
    Schreiber et al. (2011) Science 331:1565 — immunoediting: three Es
    Roybal et al. (2016) Cell 164:770 — logic-gated CAR-T (synNotch)
    Fedorov et al. (2013) Sci Transl Med 5:215ra172 — inhibitory CAR safety gate
    Lee et al. (2014) Blood 124:188 — CRS grading and management
    Wherry & Kurachi (2015) Nat Rev Immunol 15:486 — T cell exhaustion
    Blank et al. (2019) Nat Med 25:1543 — T cell exhaustion continuum

Kill switch: SIFTA_TIM_DISABLE=1
Ledger: .sifta_state/tumor_immune_stigmergic_lab.jsonl
Non-goals: no PHI, no clinical advice strings, no real patient data.
"""
from __future__ import annotations

import json
import math
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from System.jsonl_file_lock import append_line_locked
from System.swarm_persistent_owner_history import state_dir

# ── Constants ──────────────────────────────────────────────────────────────────
EVENT_ID = 148
EVENT_NAME = "TUMOR_IMMUNE_STIGMERGIC_LAB"
LEDGER_NAME = "tumor_immune_stigmergic_lab.jsonl"
_DISABLE_ENV = "SIFTA_TIM_DISABLE"

# Immunoediting phases (Dunn 2002; Schreiber 2011)
PHASE_ELIMINATION = "ELIMINATION"
PHASE_EQUILIBRIUM  = "EQUILIBRIUM"
PHASE_ESCAPE       = "ESCAPE"
PHASE_REGRESSION   = "REGRESSION"   # post-therapy clearance


def _disabled() -> bool:
    return os.environ.get(_DISABLE_ENV, "").strip() == "1"


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def tim_log_path(root: Optional[Path] = None) -> Path:
    return state_dir(root) / LEDGER_NAME


# ── Two-signal TME model ───────────────────────────────────────────────────────

@dataclass
class TumorMicroenvironmentState:
    """
    TME state vector. All values in [0, 1].

    Activation arm (immune killing pressure):
        ctl_infiltration    — CD8+ T cell tumor infiltration (Binnewies 2018)
        nk_activity         — NK cell degranulation fraction
        m1_macrophage       — pro-inflammatory M1 TAM fraction
        neoantigen_load     — mutational burden proxy (Schreiber 2011)
        ifng_signal         — IFN-γ secretion; activates MHC upregulation

    Inhibition arm (immunosuppression):
        trem2_tam_fraction  — TREM2+ immunosuppressive TAMs (Wang 2015; Jay 2015)
        treg_density        — regulatory T cell density
        pdl1_expression     — PD-L1 / checkpoint ligand expression
        mdsc_density        — myeloid-derived suppressor cells
        tgfb_level          — TGF-β immunosuppressive cytokine
    """
    # Activation
    ctl_infiltration:   float = 0.3
    nk_activity:        float = 0.2
    m1_macrophage:      float = 0.2
    neoantigen_load:    float = 0.4
    ifng_signal:        float = 0.2
    # Inhibition
    trem2_tam_fraction: float = 0.5
    treg_density:       float = 0.3
    pdl1_expression:    float = 0.4
    mdsc_density:       float = 0.3
    tgfb_level:         float = 0.3
    # Therapy
    checkpoint_blocked: bool  = False   # anti-PD1/PDL1 (Blank 2019)
    trem2_blocked:      bool  = False   # anti-TREM2 (Wang 2015)
    car_t_active:       bool  = False   # CAR-T infused (Roybal 2016)
    car_t_exhaustion:   float = 0.0     # 0=fresh, 1=terminally exhausted (Wherry 2015)
    car_t_logic_gate:   str   = "OR"    # OR / AND / NOT (Fedorov 2013; Roybal 2016)
    car_t_antigen_a:    float = 0.5     # primary target antigen density
    car_t_antigen_b:    float = 0.3     # secondary target (for logic gates)
    tick: int = 0


def compute_tme_two_signal(s: TumorMicroenvironmentState) -> Dict[str, Any]:
    """
    SIFTA two-signal gate applied to the tumor microenvironment.

    activation_signal = f(CTL, NK, M1, neoantigen, IFN-γ)
    inhibition_signal = f(TREM2+TAM, Treg, PD-L1, MDSC, TGF-β, CAR-T exhaustion)

    net = activation - inhibition
    phase = ELIMINATION if net > 0.25
            EQUILIBRIUM if -0.10 < net <= 0.25
            ESCAPE      if net <= -0.10

    Therapies modulate signals:
        - checkpoint blockade: reduces pdl1 contribution to inhibition (Blank 2019)
        - anti-TREM2:         removes trem2_tam inhibition (Wang 2015)
        - CAR-T:              boosts activation, penalised by exhaustion (Wherry 2015)
        - AND-gate CAR:       requires BOTH antigens (safer, Roybal 2016)
        - Inhibitory CAR:     activates NOT-gate brake (Fedorov 2013)
    """
    # ── Activation arm ────────────────────────────────────────────────────────
    base_activation = _clamp01(
        0.30 * s.ctl_infiltration
        + 0.20 * s.nk_activity
        + 0.15 * s.m1_macrophage
        + 0.25 * s.neoantigen_load
        + 0.10 * s.ifng_signal
    )

    # CAR-T boost (Roybal 2016) — modulated by exhaustion (Wherry 2015)
    car_boost = 0.0
    car_active_signal = False
    if s.car_t_active:
        effectiveness = 1.0 - s.car_t_exhaustion
        if s.car_t_logic_gate == "AND":
            # Logic AND gate: requires both antigens (Roybal 2016 synNotch)
            car_active_signal = s.car_t_antigen_a > 0.5 and s.car_t_antigen_b > 0.5
            gate_factor = min(s.car_t_antigen_a, s.car_t_antigen_b) if car_active_signal else 0.0
        elif s.car_t_logic_gate == "NOT":
            # Inhibitory CAR: fires when antigen_b is ABSENT (Fedorov 2013 safety gate)
            car_active_signal = s.car_t_antigen_a > 0.5 and s.car_t_antigen_b < 0.3
            gate_factor = s.car_t_antigen_a * (1.0 - s.car_t_antigen_b) if car_active_signal else 0.0
        else:  # OR gate
            car_active_signal = s.car_t_antigen_a > 0.5 or s.car_t_antigen_b > 0.5
            gate_factor = max(s.car_t_antigen_a, s.car_t_antigen_b) if car_active_signal else 0.0
        car_boost = _clamp01(gate_factor * effectiveness * 0.40)

    activation_signal = _clamp01(base_activation + car_boost)

    # ── Inhibition arm ────────────────────────────────────────────────────────
    # TREM2+ TAMs suppress immune clearance (Wang 2015; Jay 2015)
    trem2_contrib = s.trem2_tam_fraction * (0.0 if s.trem2_blocked else 1.0)
    # PD-L1 checkpoint (Blank 2019); blocked by anti-PD1/PDL1
    pdl1_contrib  = s.pdl1_expression  * (0.2 if s.checkpoint_blocked else 1.0)

    base_inhibition = _clamp01(
        0.30 * trem2_contrib
        + 0.20 * s.treg_density
        + 0.20 * pdl1_contrib
        + 0.15 * s.mdsc_density
        + 0.15 * s.tgfb_level
    )

    # CAR-T exhaustion adds to effective inhibition (Wherry & Kurachi 2015)
    exhaustion_penalty = _clamp01(s.car_t_exhaustion * 0.25) if s.car_t_active else 0.0
    inhibition_signal  = _clamp01(base_inhibition + exhaustion_penalty)

    # ── Net and phase (Dunn 2002; Schreiber 2011 three-E model) ──────────────
    net = round(activation_signal - inhibition_signal, 4)
    if net > 0.25:
        phase = PHASE_ELIMINATION
    elif net > 0.0:
        phase = PHASE_REGRESSION
    elif net > -0.10:
        phase = PHASE_EQUILIBRIUM
    else:
        phase = PHASE_ESCAPE

    # CRS risk: high CAR-T activation in high-tumor-burden environment (Lee 2014)
    crs_risk = _clamp01(car_boost * s.neoantigen_load * 2.5) if s.car_t_active else 0.0
    crs_grade = (
        "G4" if crs_risk > 0.75 else
        "G3" if crs_risk > 0.50 else
        "G2" if crs_risk > 0.25 else
        "G1" if crs_risk > 0.10 else
        "NONE"
    )

    return {
        "activation_signal":   round(activation_signal, 4),
        "base_activation":     round(base_activation, 4),
        "car_boost":           round(car_boost, 4),
        "car_active_signal":   car_active_signal,
        "inhibition_signal":   round(inhibition_signal, 4),
        "base_inhibition":     round(base_inhibition, 4),
        "trem2_contribution":  round(trem2_contrib * 0.30, 4),
        "pdl1_contribution":   round(pdl1_contrib  * 0.20, 4),
        "exhaustion_penalty":  round(exhaustion_penalty, 4),
        "net_immune_pressure": net,
        "phase":               phase,
        "crs_risk":            round(crs_risk, 4),
        "crs_grade":           crs_grade,
        # Provenance
        "provenance": (
            "Keren-Shaul2017Cell; Wang2015Cell; Jay2015JExpMed; "
            "Binnewies2018NatMed; Cassetta2019NatCommun; "
            "Dunn2002NatImmunol; Schreiber2011Science; "
            "Roybal2016Cell; Fedorov2013SciTranslMed; "
            "Lee2014Blood; Wherry&Kurachi2015NatRevImmunol; Blank2019NatMed"
        ),
    }


def compute_car_t_exhaustion_tick(
    current_exhaustion: float,
    antigen_load: float,
    tonic_signaling: float = 0.1,
    tgfb: float = 0.0,
) -> float:
    """
    Exhaustion progression per tick (Wherry & Kurachi 2015; Blank 2019).

    dE/dt = alpha * antigen_load + beta * tonic + gamma * TGF-β - delta * rest
    Models the exhaustion continuum: Tpex (progenitor exhausted) → Tex (terminal).
    """
    alpha = 0.04   # antigen-driven exhaustion
    beta  = 0.02   # tonic CAR signaling (antigen-independent)
    gamma = 0.03   # TGF-β mediated exhaustion (Blank 2019)
    delta = 0.005  # spontaneous recovery (Blank 2019 Tpex self-renewal)
    delta_e = alpha * antigen_load + beta * tonic_signaling + gamma * tgfb - delta
    return round(_clamp01(current_exhaustion + delta_e), 4)


def compute_immunoediting_tick(
    s: TumorMicroenvironmentState,
    *,
    neoantigen_loss_rate: float = 0.02,
    mhc_downregulation_rate: float = 0.01,
    immune_selection_pressure: float = 0.0,
) -> Dict[str, float]:
    """
    Immunoediting: immune pressure selects for immune-resistant variants (Schreiber 2011).

    During ELIMINATION phase, neoantigens are cleared (antigen loss).
    During ESCAPE, MHC-I downregulation reduces CTL recognition.
    Returns delta values to apply to TME state next tick.
    """
    sig = compute_tme_two_signal(s)
    net = sig["net_immune_pressure"]
    phase = sig["phase"]

    delta_neoantigen = 0.0
    delta_ctl = 0.0
    delta_mhc_effect = 0.0   # negative = MHC-I downregulation → less CTL killing

    if phase in (PHASE_ELIMINATION, PHASE_REGRESSION):
        # Strong pressure selects for antigen-loss variants (Dunn 2002)
        delta_neoantigen = -neoantigen_loss_rate * net
        delta_ctl = 0.01 * net   # successful killing drives more CTL expansion
    elif phase == PHASE_ESCAPE:
        # Immune escape: MHC-I downregulation, exhaustion accumulates
        delta_mhc_effect = mhc_downregulation_rate * abs(net)
        delta_ctl = -0.02 * abs(net)   # CTL exhaustion in escape

    return {
        "phase":               phase,
        "net_immune_pressure": net,
        "delta_neoantigen":    round(delta_neoantigen, 5),
        "delta_ctl":           round(delta_ctl, 5),
        "delta_mhc_effect":    round(delta_mhc_effect, 5),
        "immunoediting_provenance": "Dunn2002NatImmunol; Schreiber2011Science",
    }


# ── Tick loop ─────────────────────────────────────────────────────────────────

def tin_sim_tick(
    s: TumorMicroenvironmentState,
    *,
    root: Optional[Path] = None,
    write_ledger: bool = True,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """
    One simulation tick. Computes TME two-signal, immunoediting, CAR-T exhaustion.
    Writes a TIN_SIM_TICK row to the stigmergic ledger.

    The receipt embeds two_signal_snapshot so it mirrors the microglia JSONL schema
    and can be cross-validated against swarm_microglia_synaptic_pruner receipts.
    """
    if _disabled():
        return {"disabled": True, "tick": s.tick}

    ts = now or time.time()

    # Two-signal snapshot (SIFTA math applied to TME)
    two_sig = compute_tme_two_signal(s)

    # CAR-T exhaustion progression
    new_exhaustion = s.car_t_exhaustion
    if s.car_t_active:
        new_exhaustion = compute_car_t_exhaustion_tick(
            s.car_t_exhaustion,
            antigen_load=max(s.car_t_antigen_a, s.car_t_antigen_b),
            tgfb=s.tgfb_level,
        )

    # Immunoediting deltas
    editing = compute_immunoediting_tick(s)

    row: Dict[str, Any] = {
        "ts":          ts,
        "trace_id":    str(uuid.uuid4()),
        "truth_label": "TIN_SIM_TICK",
        "kind":        "TIN_SIM_TICK",
        "event_id":    EVENT_ID,
        "tick":        s.tick,
        # TME state snapshot
        "tme_state":   {k: v for k, v in asdict(s).items()},
        # Two-signal snapshot (same schema as microglia JSONL for cross-validation)
        "two_signal_snapshot": two_sig,
        # Immunoediting
        "immunoediting": editing,
        # CAR-T
        "car_t_exhaustion_before": s.car_t_exhaustion,
        "car_t_exhaustion_after":  new_exhaustion,
        "car_t_gate_fired":        two_sig["car_active_signal"],
        # Phase
        "phase":       two_sig["phase"],
        "net_immune_pressure": two_sig["net_immune_pressure"],
        "crs_grade":   two_sig["crs_grade"],
        # SIFTA organ tag
        "sifta_organ": f"Event{EVENT_ID}_{EVENT_NAME}",
        "data_source": "SYNTHETIC_ONLY — no PHI, no real patient data",
    }

    if write_ledger:
        append_line_locked(
            tim_log_path(root),
            json.dumps(row, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    return row


def run_simulation(
    initial_state: Optional[TumorMicroenvironmentState] = None,
    n_ticks: int = 10,
    *,
    root: Optional[Path] = None,
    write_ledger: bool = True,
) -> List[Dict[str, Any]]:
    """Run n_ticks of the TME simulation, applying immunoediting deltas each tick."""
    s = initial_state or TumorMicroenvironmentState()
    rows: List[Dict[str, Any]] = []
    for _ in range(n_ticks):
        row = tin_sim_tick(s, root=root, write_ledger=write_ledger)
        rows.append(row)
        # Apply immunoediting deltas (Schreiber 2011 selection pressure)
        editing = row["immunoediting"]
        s.neoantigen_load = _clamp01(s.neoantigen_load + editing["delta_neoantigen"])
        s.ctl_infiltration = _clamp01(s.ctl_infiltration + editing["delta_ctl"])
        # CAR-T exhaustion update
        s.car_t_exhaustion = row["car_t_exhaustion_after"]
        s.tick += 1
    return rows


def summary_for_prompt(*, root: Optional[Path] = None) -> str:
    """Return a short TME summary for Alice's context window."""
    log = tim_log_path(root)
    if not log.exists():
        return ""
    lines = [l for l in log.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
    if not lines:
        return ""
    try:
        latest = json.loads(lines[-1])
    except json.JSONDecodeError:
        return ""
    net = latest.get("net_immune_pressure", 0.0)
    phase = latest.get("phase", "UNKNOWN")
    crs = latest.get("crs_grade", "NONE")
    tick = latest.get("tick", 0)
    return (
        f"TME (Event148): tick={tick} phase={phase} "
        f"net={net:.3f} CRS={crs} "
        f"[Dunn2002; Schreiber2011; Roybal2016]"
    )


__all__ = [
    "TumorMicroenvironmentState",
    "compute_tme_two_signal",
    "compute_car_t_exhaustion_tick",
    "compute_immunoediting_tick",
    "tin_sim_tick",
    "run_simulation",
    "summary_for_prompt",
    "tim_log_path",
    "PHASE_ELIMINATION",
    "PHASE_EQUILIBRIUM",
    "PHASE_ESCAPE",
    "PHASE_REGRESSION",
]


# ── PyQt desktop wrapper ─────────────────────────────────────────────────────
# The scientific simulator above is intentionally importable without Qt.  The
# desktop manifest expects a widget class, so this thin shell delegates runtime
# ticks to the locked System organ added for Event 148.

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

class TumorImmuneStigmergicLab(QWidget):
    """Synthetic-only tumor-immune stigmergic proof lab widget."""

    INTERVENTIONS = [
        ("none", "No intervention"),
        ("toy_trem2_blockade", "TREM2 blockade toy"),
        ("toy_cart_persistence", "CAR-T persistence toy"),
        ("toy_logic_gate_focus", "Logic-gated CAR toy"),
        ("toy_tme_release", "TME release toy"),
    ]

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("TumorImmuneStigmergicLab")
        self.setWindowTitle("Tumor-Immune Stigmergic Lab")

        from System.swarm_tumor_immune_stigmergic_lab import default_synthetic_state

        self._core_state = default_synthetic_state()
        self._tick_id = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(10)

        title = QLabel("🧫 Tumor-Immune Stigmergic Lab")
        title.setStyleSheet("font-size: 20px; font-weight: 800; color: rgb(120, 245, 190);")
        root.addWidget(title)

        guard = QLabel(
            "Synthetic sandbox only. No PHI, no real patient records, no clinical guidance. "
            "Rows are TIN_SIM_TICK receipts for algorithm research."
        )
        guard.setWordWrap(True)
        guard.setStyleSheet("color: rgb(245, 205, 120); font-weight: 700;")
        root.addWidget(guard)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Toy action"))
        self._intervention = QComboBox()
        for key, label in self.INTERVENTIONS:
            self._intervention.addItem(label, key)
        controls.addWidget(self._intervention, 1)

        self._tick_btn = QPushButton("Run Tick")
        self._tick_btn.clicked.connect(self._run_tick)
        controls.addWidget(self._tick_btn)

        self._burst_btn = QPushButton("Run 8")
        self._burst_btn.clicked.connect(lambda: self._run_many(8))
        controls.addWidget(self._burst_btn)

        self._reset_btn = QPushButton("Reset")
        self._reset_btn.clicked.connect(self._reset)
        controls.addWidget(self._reset_btn)
        root.addLayout(controls)

        self._bars: Dict[str, QProgressBar] = {}
        for key, label in [
            ("tumor_burden", "Tumor burden"),
            ("antigen_visibility", "Antigen visibility"),
            ("cart_effector_load", "CAR-T effector load"),
            ("tme_suppression", "TME suppression"),
            ("hypoxia", "Hypoxia"),
            ("inflammatory_heat", "Inflammatory heat"),
        ]:
            row = QHBoxLayout()
            row.addWidget(QLabel(label), 1)
            bar = QProgressBar()
            bar.setRange(0, 100)
            row.addWidget(bar, 3)
            self._bars[key] = bar
            root.addLayout(row)

        self._summary = QLabel("")
        self._summary.setWordWrap(True)
        self._summary.setStyleSheet("color: rgb(210, 230, 255);")
        root.addWidget(self._summary)

        self._ledger = QTextEdit()
        self._ledger.setReadOnly(True)
        self._ledger.setMinimumHeight(220)
        self._ledger.setStyleSheet(
            "QTextEdit { background: rgb(12, 14, 24); color: rgb(210, 235, 220); "
            "font-family: Menlo, monospace; font-size: 12px; }"
        )
        root.addWidget(self._ledger, 1)

        self._timer = QTimer(self)
        self._timer.setInterval(3000)
        self._timer.timeout.connect(self._refresh_from_ledger)
        self._timer.start()

        self._render_state()
        self._refresh_from_ledger()

    def _reset(self) -> None:
        from System.swarm_tumor_immune_stigmergic_lab import default_synthetic_state

        self._core_state = default_synthetic_state()
        self._tick_id = 0
        self._render_state()

    def _run_many(self, ticks: int) -> None:
        for _ in range(max(1, int(ticks))):
            self._run_tick()

    def _run_tick(self) -> None:
        from System.swarm_tumor_immune_stigmergic_lab import run_tin_tick

        intervention_id = str(self._intervention.currentData() or "none")
        row = run_tin_tick(
            self._core_state,
            intervention_id=intervention_id,
            tick_id=self._tick_id,
            data_origin="synthetic",
            write_ledger=True,
        )
        after = row.get("state_after", {})
        for key in self._core_state.__dict__.keys():
            if key in after:
                setattr(self._core_state, key, float(after[key]))
        self._tick_id += 1
        self._render_state(row)
        self._refresh_from_ledger()

    def _render_state(self, latest_row: Optional[Dict[str, Any]] = None) -> None:
        for key, bar in self._bars.items():
            bar.setValue(int(round(float(getattr(self._core_state, key, 0.0)) * 100)))
        if latest_row:
            dynamics = latest_row.get("dynamics", {})
            two_signal = latest_row.get("two_signal_snapshot", {})
            self._summary.setText(
                f"tick={latest_row.get('tick_id')} intervention={latest_row.get('intervention_id')} "
                f"immune_pressure={dynamics.get('immune_pressure', 0.0):.3f} "
                f"net_pruning={two_signal.get('net_pruning_pressure', 0.0):.3f} "
                f"phase={latest_row.get('field_regime')}"
            )
        else:
            self._summary.setText("Ready. Run a synthetic tick to append a TIN_SIM_TICK receipt.")

    def _refresh_from_ledger(self) -> None:
        from System.swarm_tumor_immune_stigmergic_lab import tail_lab_rows

        rows = tail_lab_rows(16)
        rendered = []
        for row in rows[-16:]:
            rendered.append(
                json.dumps(
                    {
                        "tick_id": row.get("tick_id"),
                        "intervention_id": row.get("intervention_id"),
                        "field_regime": row.get("field_regime"),
                        "tumor_burden_after": row.get("state_after", {}).get("tumor_burden"),
                        "net_pruning_pressure": row.get("two_signal_snapshot", {}).get("net_pruning_pressure"),
                        "truth_label": row.get("truth_label"),
                    },
                    sort_keys=True,
                )
            )
        self._ledger.setPlainText("\n".join(rendered))


__all__.append("TumorImmuneStigmergicLab")


if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    widget = TumorImmuneStigmergicLab()
    widget.resize(1120, 760)
    widget.show()
    sys.exit(app.exec())
