"""SIFTA Field-Primary PDE Engine — N-dimensional stigmergic soup.

The mathematical core for the field-is-primary ontology: the field is the
reality; "swimmers" are local excitations that *swim inside the field*,
not separate objects that occasionally touch it. The slit is a structure
**in** the field. Interference, memory, correlation — all live in the
field itself.

Governing equation
------------------
The same PDE Cursor's tournament paper highlights:

    ∂φ/∂t = D ∇²φ − λ φ + f(agents)

- φ is a **complex-valued** field on an N-dimensional grid. The complex
  phase is the "i in Schrödinger's equation" that lets a single field
  carry interference (Couder & Fort 2006 hydrodynamic analogue).
- D is the **diffusion coefficient**, allowed to vary in space — that's
  how a barrier with two slits is just a region where D drops to zero
  everywhere except at the slit openings.
- λ is the **decay rate** (stigmergic-trace evaporation; Heylighen 2016).
- f(agents) is the local **source term**: each agent ("swimmer") deposits
  a phase-carrying Gaussian into the field at its location.

Dimension is **a parameter**, not a constant. The Architect's directive
2026-05-11: *"WHY DOES IT HAVE TO BE 2D... ANYTIME ANYWHERE... I think
the SUF is any-D."* This engine accepts any non-empty positive-integer
shape tuple and runs the same algorithm.

Truth labels (§7.11)
--------------------
- `OBSERVED`        — every test produces a real numeric trace.
- `OPERATIONAL`     — the integrator is deterministic; CFL-stability
                       guards make sure dt is safe; pytest covers
                       conservation, diffusion, barrier transport, and
                       double-slit interference.
- `ARCHITECT_DOCTRINE` — the *ontological* claim that "the field is
                       primary and swimmers are excitations in it" is
                       doctrinal. The PDE is what supports it; the
                       ontology is the choice to identify the PDE with
                       reality.
- `FORBIDDEN`        — never claims this PDE solves a physical quantum
                       system. The Couder/Bush hydrodynamic analogy is
                       *suggestive*; it is not a derivation of QM.

Imports
-------
Pure numpy. No scipy. No Qt. No matplotlib. Cursor's widget can import
this and plot the field however it wants.

Author : Cowork (Claude Opus 4.7), 2026-05-11.
Sibling: Cursor's `Applications/sifta_double_slit_stigmergic.py` (and
         the in-flight field-primary successor at trace ts ≈ 1778547184).
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LEDGER = _STATE / "field_primary_pde_snapshots.jsonl"

TRUTH_LABEL = "SIFTA_FIELD_PRIMARY_PDE_V1"
FIELD_PRIMARY_TRUTH_GUARD = (
    "FIELD_PRIMARY_PDE_ONLY: this engine solves N-dimensional classical "
    "field equations on a uniform grid. diffusion mode solves "
    "∂φ/∂t = D∇²φ − λφ + f(agents); schrodinger mode solves the "
    "linear Schrödinger-style equation ∂φ/∂t = iD∇²φ − λφ + f(agents) "
    "with a split-step spectral kinetic update. These simulations carry "
    "phase in a complex-valued field and can reproduce analogue wave "
    "interference, but they do NOT prove the physical cause of quantum "
    "behavior. The field-is-primary ontology is ARCHITECT_DOCTRINE, not "
    "an established physics conclusion."
)


# ── Source / agent dataclasses ──────────────────────────────────────────────
@dataclass(frozen=True)
class Swimmer:
    """A localized excitation in the field — Gaussian + phase.

    Parameters
    ----------
    position
        N-tuple of grid indices where the Gaussian is centered.
    sigma
        Standard deviation in grid units (isotropic).
    amplitude
        Peak amplitude added to |φ| per unit time.
    phase
        Phase in radians; the deposit is amplitude · exp(i · phase).
    """
    position: tuple[int, ...]
    sigma: float = 1.5
    amplitude: float = 1.0
    phase: float = 0.0


@dataclass(frozen=True)
class WavePacket:
    """A localized, **propagating** excitation: Gaussian × plane wave.

    The deposit is:

        f(x) = amplitude · exp(-‖x − position‖² / (2 σ²)) · exp(i k · x)

    The plane-wave factor `exp(i k · x)` gives the packet momentum
    `k` (in grid units of 1/dx). In Schrödinger mode this means the
    packet propagates with group velocity v_g = k/m (using
    ℏ = 1, m via the diffusion coefficient).

    This is the "swimmers swim THROUGH the slit" excitation the
    Architect asked for on 2026-05-11.

    Parameters
    ----------
    position
        N-tuple of grid indices for the packet center.
    sigma
        Spatial width of the envelope.
    amplitude
        Peak |φ| amplitude.
    momentum
        N-tuple of wavenumbers k (one per axis). For a packet moving
        purely along axis 0 with momentum k0, pass `(k0, 0, ...)`.
    """
    position: tuple[int, ...]
    sigma: float = 2.5
    amplitude: float = 1.0
    momentum: tuple[float, ...] = (0.5, 0.0)


@dataclass(frozen=True)
class StigmergicDetector:
    """A field-level detection region implementing measurement-as-trace.

    The covenant directive (Architect 2026-05-11):
    *"stigmergic version of measurement/collapse: local field feedback
    that 'freezes' one outcome via trace amplification, no external
    observer."*

    Mechanism: at each step, sum |φ|² inside the detector region. If
    the local intensity exceeds `threshold`, the detector multiplies
    the local |φ| by `amplify_gain` (positive feedback — irreversible
    trace reinforcement) and damps the field outside the detector by
    `damp_factor` (collapse-by-amplification). The detector NEVER
    inserts external information; it only modulates dynamics that are
    already in the field.

    Parameters
    ----------
    region
        Slice or tuple of slices selecting the detector region. For 2D:
        `(slice(80, 90), slice(20, 40))`.
    threshold
        Intensity threshold above which the detector triggers.
    amplify_gain
        Multiplier applied inside the region when triggered.
        Must be > 1 for amplification.
    damp_factor
        Multiplier applied OUTSIDE the region when triggered.
        Must be ∈ (0, 1) for damping.
    name
        Human-readable label for the snapshot ledger.
    """
    region: tuple[slice, ...]
    threshold: float = 0.05
    amplify_gain: float = 1.05
    damp_factor: float = 0.99
    name: str = "stigmergic_detector"

    def __post_init__(self) -> None:
        if self.amplify_gain <= 1.0:
            raise ValueError("amplify_gain must be > 1 for amplification")
        if not (0.0 < self.damp_factor <= 1.0):
            raise ValueError("damp_factor must be in (0, 1]")


# ── Field configuration + state ─────────────────────────────────────────────
# Two PDE modes are supported:
#
#   "diffusion"  — ∂φ/∂t = D ∇²φ − λ φ + f(agents)   (default; dissipative)
#   "schrodinger" — i ∂φ/∂t = − D ∇²φ + V φ ⇔
#                    ∂φ/∂t = i D ∇²φ + i V φ          (unitary; wave-like)
#
# Diffusion is honest for stigmergic-trace evolution. Schrödinger is the
# right mode when the Architect asks for VISIBLE INTERFERENCE FRINGES —
# the imaginary diffusion coefficient is what gives wave-equation
# propagation and Young-style fringes. Mode is a per-config choice;
# tests for both live in `tests/test_field_primary_extensions.py`.
@dataclass
class FieldConfig:
    """Static configuration of the field.

    `shape` is the grid shape (any N ≥ 1). `dx` is the grid spacing
    (uniform). `D_base`, `lam` are the default diffusion + decay; both
    may be overridden per-cell by `D_map` / `lam_map`. `dt` is the
    integrator step; if `None`, a CFL-stable default is chosen.

    `mode` selects the PDE:
    - "diffusion"  → ∂φ/∂t = D ∇²φ − λ φ + f (real coefficient)
    - "schrodinger" → ∂φ/∂t = i D ∇²φ − λ φ + f (imaginary diffusion,
      wave-like propagation, unitary up to λ; the right mode for
      Young/double-slit interference fringes).
    """
    shape: tuple[int, ...]
    dx: float = 1.0
    D_base: float = 0.5
    lam: float = 0.02
    dt: float | None = None
    mode: str = "diffusion"
    schrodinger_integrator: str = "split_step"
    truth_label: str = TRUTH_LABEL

    def __post_init__(self) -> None:
        if not self.shape:
            raise ValueError("FieldConfig.shape must be non-empty")
        if any(s < 3 for s in self.shape):
            raise ValueError(
                "FieldConfig.shape: every axis must be ≥ 3 for a "
                "valid second-derivative stencil"
            )
        if self.dx <= 0:
            raise ValueError("dx must be positive")
        if self.D_base < 0:
            raise ValueError("D_base must be non-negative")
        if self.lam < 0:
            raise ValueError("lam must be non-negative")
        if self.mode not in ("diffusion", "schrodinger"):
            raise ValueError(
                f"FieldConfig.mode={self.mode!r} not supported; "
                "choose 'diffusion' or 'schrodinger'"
            )
        if self.schrodinger_integrator not in ("split_step", "euler"):
            raise ValueError(
                "FieldConfig.schrodinger_integrator must be "
                "'split_step' or 'euler'"
            )
        if self.dt is None:
            self.dt = self.cfl_safe_dt()
        elif self.dt > self.cfl_safe_dt() * 1.001:
            raise ValueError(
                f"dt={self.dt} exceeds CFL bound "
                f"{self.cfl_safe_dt():.4g} for D_base={self.D_base}, "
                f"dx={self.dx}, N_dim={len(self.shape)}; reduce dt or "
                "lower D_base"
            )

    def cfl_safe_dt(self) -> float:
        """Stability bound for the chosen mode.

        Diffusion (real ∇²): dt ≤ dx² / (2 N D).
        Schrödinger (imaginary ∇²): the default split-step spectral
        integrator is norm-preserving for free evolution, but we keep
        the same conservative step bound so the explicit source,
        detector feedback, and optional euler compatibility path stay
        bounded. Factor 0.5 margin in both.
        """
        N = len(self.shape)
        if self.D_base == 0:
            return 1.0
        return 0.5 * self.dx * self.dx / (2.0 * N * self.D_base)

    @property
    def ndim(self) -> int:
        return len(self.shape)


# ── N-dimensional Laplacian (manual stencil, no scipy) ──────────────────────
def laplacian_nd(phi: np.ndarray, dx: float = 1.0) -> np.ndarray:
    """Discrete Laplacian via the standard (2N+1)-point stencil.

    ∇²φ ≈ (Σ_axis (φ_{+1} - 2 φ + φ_{-1})) / dx²

    Uses `np.roll` for periodic boundaries — sufficient for tests and
    the typical double-slit geometry (interior dynamics dominated by
    bulk diffusion + barrier mask). Works for any number of dimensions.
    """
    if phi.ndim < 1:
        raise ValueError("laplacian_nd requires at least 1 axis")
    out = np.zeros_like(phi)
    for axis in range(phi.ndim):
        out += np.roll(phi, +1, axis=axis) + np.roll(phi, -1, axis=axis)
    out -= 2.0 * phi.ndim * phi
    return out / (dx * dx)


# ── Top-level field object ─────────────────────────────────────────────────
class FieldPrimary:
    """N-dimensional stigmergic field solver."""

    def __init__(
        self,
        config: FieldConfig,
        *,
        D_map: np.ndarray | None = None,
        lam_map: np.ndarray | None = None,
        seed: int | None = None,
    ) -> None:
        self.config = config
        self.phi: np.ndarray = np.zeros(config.shape, dtype=np.complex128)
        self.t: float = 0.0
        self.step_count: int = 0
        self.swimmers: list[Swimmer] = []
        self.wave_packets: list[WavePacket] = []
        self.detectors: list[StigmergicDetector] = []
        self.detector_trigger_log: list[dict[str, Any]] = []
        self.rng = np.random.default_rng(seed)

        if D_map is None:
            self.D_map = np.full(config.shape, config.D_base, dtype=np.float64)
        else:
            if D_map.shape != config.shape:
                raise ValueError("D_map shape mismatch")
            self.D_map = D_map.astype(np.float64, copy=True)

        if lam_map is None:
            self.lam_map = np.full(config.shape, config.lam, dtype=np.float64)
        else:
            if lam_map.shape != config.shape:
                raise ValueError("lam_map shape mismatch")
            self.lam_map = lam_map.astype(np.float64, copy=True)

    # ── Swimmer / source management ─────────────────────────────────────
    def add_swimmer(self, swimmer: Swimmer) -> None:
        for c, s in zip(swimmer.position, self.config.shape):
            if not (0 <= c < s):
                raise ValueError(
                    f"swimmer position {swimmer.position} out of grid "
                    f"shape {self.config.shape}"
                )
        self.swimmers.append(swimmer)

    def _gaussian_kernel(self, swimmer: Swimmer) -> np.ndarray:
        """Build a Gaussian source kernel centered at swimmer.position."""
        grid = np.indices(self.config.shape, dtype=np.float64)
        # squared distance from swimmer position along each axis
        sq = np.zeros(self.config.shape, dtype=np.float64)
        for ax, c in enumerate(swimmer.position):
            sq += (grid[ax] - c) ** 2
        kernel = np.exp(-sq / (2.0 * swimmer.sigma ** 2))
        kernel *= swimmer.amplitude
        return kernel * np.exp(1j * swimmer.phase)

    def source_term(self) -> np.ndarray:
        """Sum of all swimmer Gaussian deposits + active wave packets."""
        total = np.zeros(self.config.shape, dtype=np.complex128)
        for sw in self.swimmers:
            total += self._gaussian_kernel(sw)
        for wp in self.wave_packets:
            total += self._wave_packet_kernel(wp)
        return total

    # ── Wave packet sources (propagating excitations) ────────────────────
    def add_wave_packet(self, packet: WavePacket) -> None:
        """Register a propagating wave packet.

        Unlike `Swimmer`, a wave packet is INITIAL CONDITION: it is
        injected ONCE into the field at registration time, then evolves
        under the PDE. The caller may use either `add_wave_packet`
        (one-shot) or repeated `add_swimmer` calls (continuous source).
        """
        if len(packet.momentum) != self.config.ndim:
            raise ValueError(
                f"WavePacket.momentum must have ndim={self.config.ndim} "
                f"components; got {len(packet.momentum)}"
            )
        for c, s in zip(packet.position, self.config.shape):
            if not (0 <= c < s):
                raise ValueError(
                    f"WavePacket position {packet.position} out of "
                    f"shape {self.config.shape}"
                )
        # Inject the packet into the current field state.
        self.phi = self.phi + self._wave_packet_kernel(packet)
        self.wave_packets.append(packet)

    def _wave_packet_kernel(self, packet: WavePacket) -> np.ndarray:
        """Build a Gaussian × plane-wave packet centered at packet.position.

        Note: this kernel is used at registration only (one-shot
        injection). It is intentionally NOT added every step; that
        would create a continuous source rather than a true packet.
        After registration the packet is in `self.wave_packets` for
        bookkeeping only.
        """
        grid = np.indices(self.config.shape, dtype=np.float64)
        sq = np.zeros(self.config.shape, dtype=np.float64)
        for ax, c in enumerate(packet.position):
            sq += (grid[ax] - c) ** 2
        envelope = np.exp(-sq / (2.0 * packet.sigma ** 2)) * packet.amplitude
        # Plane-wave factor exp(i k · x).
        phase = np.zeros(self.config.shape, dtype=np.float64)
        for ax, k in enumerate(packet.momentum):
            phase += float(k) * (grid[ax] - packet.position[ax])
        return envelope * np.exp(1j * phase)

    # Override source_term to omit wave packets from PER-STEP injection.
    def _step_source_term(self) -> np.ndarray:
        """Continuous source term per step — swimmers only."""
        if not self.swimmers:
            return np.zeros(self.config.shape, dtype=np.complex128)
        total = np.zeros(self.config.shape, dtype=np.complex128)
        for sw in self.swimmers:
            total += self._gaussian_kernel(sw)
        return total

    # ── Stigmergic detectors (measurement-as-amplification) ──────────────
    def add_detector(self, detector: StigmergicDetector) -> None:
        if len(detector.region) != self.config.ndim:
            raise ValueError(
                f"detector.region must have ndim={self.config.ndim} "
                f"slices; got {len(detector.region)}"
            )
        self.detectors.append(detector)

    def _apply_detectors(self) -> None:
        """For each detector: if local |φ|² exceeds threshold,
        amplify inside the region and damp outside (stigmergic
        "collapse" via local feedback)."""
        if not self.detectors:
            return
        intensity = np.abs(self.phi) ** 2
        for det in self.detectors:
            try:
                region_intensity = intensity[det.region]
            except (IndexError, TypeError):
                continue
            local_peak = float(region_intensity.max()) if region_intensity.size else 0.0
            if local_peak >= det.threshold:
                # Amplify inside.
                self.phi[det.region] = self.phi[det.region] * det.amplify_gain
                # Damp outside (everywhere not in region).
                damp = np.full(self.config.shape, det.damp_factor,
                               dtype=np.float64)
                damp[det.region] = 1.0
                self.phi = self.phi * damp
                self.detector_trigger_log.append({
                    "name": det.name,
                    "step": self.step_count,
                    "t": self.t,
                    "local_peak": local_peak,
                    "threshold": det.threshold,
                })

    # ── Geometry helpers (barrier with slits) ────────────────────────────
    def install_barrier(
        self,
        axis: int,
        position: int,
        thickness: int = 1,
        slit_positions: Sequence[Sequence[int]] = (),
    ) -> None:
        """Install a barrier perpendicular to `axis` at index `position`.

        - The barrier is `thickness` cells thick.
        - Every barrier cell gets D = 0 (no transport).
        - `slit_positions` are coordinates *in the orthogonal slice*
          where the barrier is punched through (D restored to D_base).

        Works in any dimension: in 2D, slit_positions is a list of
        1-tuples (row indices); in 3D, list of 2-tuples; etc.
        """
        if not (0 <= axis < self.config.ndim):
            raise ValueError(f"axis {axis} out of range for shape {self.config.shape}")
        if thickness < 1:
            raise ValueError("barrier thickness must be ≥ 1")
        # Build slicer.
        for offset in range(thickness):
            idx = position + offset
            if not (0 <= idx < self.config.shape[axis]):
                continue
            slicer: list[Any] = [slice(None)] * self.config.ndim
            slicer[axis] = idx
            self.D_map[tuple(slicer)] = 0.0

        # Re-open slit cells.
        for slit in slit_positions:
            if len(slit) != self.config.ndim - 1:
                raise ValueError(
                    f"slit coords must have ndim-1={self.config.ndim - 1} entries"
                )
            for offset in range(thickness):
                idx = position + offset
                if not (0 <= idx < self.config.shape[axis]):
                    continue
                slicer = [None] * self.config.ndim
                ortho_iter = iter(slit)
                for ax in range(self.config.ndim):
                    if ax == axis:
                        slicer[ax] = idx
                    else:
                        slicer[ax] = next(ortho_iter)
                # restore D
                self.D_map[tuple(slicer)] = self.config.D_base

    # ── Time integration ────────────────────────────────────────────────
    def _schrodinger_barrier_mask(self) -> np.ndarray:
        """Cells whose field transport is blocked by static structure."""
        threshold = max(1e-15, float(self.config.D_base) * 1e-12)
        return self.D_map <= threshold

    def _schrodinger_k2_grid(self) -> np.ndarray:
        """Return |k|² grid for the N-D spectral kinetic step."""
        axes = [
            2.0 * math.pi * np.fft.fftfreq(n, d=self.config.dx)
            for n in self.config.shape
        ]
        mesh = np.meshgrid(*axes, indexing="ij")
        k2 = np.zeros(self.config.shape, dtype=np.float64)
        for axis_grid in mesh:
            k2 += axis_grid * axis_grid
        return k2

    def _schrodinger_step_split(self, source: np.ndarray) -> None:
        """Stable Strang-style step for ∂φ/∂t = iD∇²φ − λφ + f.

        The kinetic term is exact in Fourier space for the constant
        positive transport coefficient. Zero-D cells from barriers are
        then enforced as hard field-structure masks, which is the
        simple slit geometry this engine exposes. For arbitrary custom
        nonzero D_map variation this is an analogue, not a full variable-
        coefficient Schrödinger solver.
        """
        dt = float(self.config.dt or 0.0)
        if dt <= 0.0:
            return

        source_active = bool(np.any(source))
        if source_active:
            self.phi = self.phi + 0.5 * dt * source

        if np.any(self.lam_map):
            self.phi = self.phi * np.exp(-0.5 * dt * self.lam_map)

        barrier = self._schrodinger_barrier_mask()
        if np.any(barrier):
            self.phi[barrier] = 0.0

        D_eff = float(self.config.D_base)
        if D_eff > 0.0:
            phase = np.exp(-1j * D_eff * self._schrodinger_k2_grid() * dt)
            self.phi = np.fft.ifftn(np.fft.fftn(self.phi) * phase)

        if np.any(barrier):
            self.phi[barrier] = 0.0

        if np.any(self.lam_map):
            self.phi = self.phi * np.exp(-0.5 * dt * self.lam_map)

        if source_active:
            self.phi = self.phi + 0.5 * dt * source
            if np.any(barrier):
                self.phi[barrier] = 0.0

    def step(self) -> None:
        """One time step of the PDE.

        The mode set on the config selects:
        - "diffusion"   → forward-Euler ∂φ/∂t = D∇²φ − λφ + f
        - "schrodinger" → default split-step spectral update for
                          ∂φ/∂t = iD∇²φ − λφ + f. The legacy euler
                          path remains selectable only for comparison.
        """
        source = self._step_source_term()
        if self.config.mode == "schrodinger":
            if self.config.schrodinger_integrator == "split_step":
                self._schrodinger_step_split(source)
            else:
                lap = laplacian_nd(self.phi, dx=self.config.dx)
                d_phi = (1j * self.D_map) * lap - self.lam_map * self.phi + source
                self.phi = self.phi + (self.config.dt or 0.0) * d_phi
        else:
            lap = laplacian_nd(self.phi, dx=self.config.dx)
            d_phi = self.D_map * lap - self.lam_map * self.phi + source
            self.phi = self.phi + (self.config.dt or 0.0) * d_phi
        self.t += self.config.dt or 0.0
        self.step_count += 1
        # After the dynamics update, give detectors a chance to fire.
        self._apply_detectors()

    def run(self, steps: int) -> None:
        for _ in range(int(steps)):
            self.step()

    # ── Observables ──────────────────────────────────────────────────────
    def intensity(self) -> np.ndarray:
        """|φ|² — the visible interference / accumulation map."""
        return np.abs(self.phi) ** 2

    def total_intensity(self) -> float:
        """∫ |φ|² dV (un-normalized; in grid units)."""
        return float(np.sum(self.intensity()))

    def screen_intensity(
        self,
        axis: int,
        position: int,
    ) -> np.ndarray:
        """Slice of |φ|² perpendicular to `axis` at index `position`.

        Reads the "detection screen" intensity in a single hyperplane;
        Cursor's widget can plot this directly.
        """
        if not (0 <= axis < self.config.ndim):
            raise ValueError("axis out of range")
        if not (0 <= position < self.config.shape[axis]):
            raise ValueError("position out of range")
        slicer: list[Any] = [slice(None)] * self.config.ndim
        slicer[axis] = position
        return self.intensity()[tuple(slicer)]

    # ── Snapshot serialization ──────────────────────────────────────────
    def snapshot(self) -> dict[str, Any]:
        """Serialize the live state for the ledger."""
        return {
            "schema": TRUTH_LABEL,
            "ts": time.time(),
            "shape": list(self.config.shape),
            "dx": self.config.dx,
            "dt": self.config.dt,
            "D_base": self.config.D_base,
            "lam": self.config.lam,
            "mode": self.config.mode,
            "schrodinger_integrator": self.config.schrodinger_integrator,
            "t": self.t,
            "step_count": self.step_count,
            "n_swimmers": len(self.swimmers),
            "total_intensity": self.total_intensity(),
            "phase_mean": float(np.mean(np.angle(self.phi))),
            "phase_std": float(np.std(np.angle(self.phi))),
            "intensity_max": float(np.max(self.intensity())),
            "intensity_min": float(np.min(self.intensity())),
            "truth_guard": FIELD_PRIMARY_TRUTH_GUARD,
        }

    def deposit_snapshot(self, path: Path | None = None) -> Path:
        """Append a hash-stamped snapshot row to the field-primary ledger."""
        out = path or _LEDGER
        out.parent.mkdir(parents=True, exist_ok=True)
        body = self.snapshot()
        sig = hashlib.sha256(
            json.dumps(body, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        body["sha256"] = sig
        with out.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(body, default=str) + "\n")
        return out


# ── High-level convenience: build a 2D double-slit setup ────────────────────
def make_double_slit_2d(
    *,
    width: int = 100,
    height: int = 60,
    barrier_x: int = 30,
    slit_offsets: tuple[int, int] = (-8, 8),
    slit_width: int = 3,
    D: float = 0.5,
    lam: float = 0.01,
) -> FieldPrimary:
    """Convenience constructor — a 2D field with a barrier + two slits.

    Cursor's widget can call this for the canonical demo without re-
    implementing the geometry. The "swimmers" still need to be added
    via `add_swimmer` for source-driven runs.
    """
    cfg = FieldConfig(shape=(width, height), D_base=D, lam=lam)
    field_obj = FieldPrimary(cfg)
    cy = height // 2
    slits = []
    for off in slit_offsets:
        for w in range(-slit_width // 2, slit_width // 2 + 1):
            slits.append((cy + off + w,))
    field_obj.install_barrier(axis=0, position=barrier_x,
                              thickness=1, slit_positions=slits)
    return field_obj


def make_schrodinger_double_slit(
    *,
    width: int = 120,
    height: int = 80,
    barrier_x: int = 40,
    slit_offsets: tuple[int, int] = (-10, 10),
    slit_width: int = 3,
    packet_position: tuple[int, int] | None = None,
    packet_momentum: tuple[float, float] = (0.8, 0.0),
    packet_sigma: float = 4.0,
    packet_amplitude: float = 1.0,
    D: float = 0.3,
    install_screen_detector: bool = False,
) -> FieldPrimary:
    """Convenience constructor for a Schrödinger-mode double-slit setup.

    Why this exists
    ---------------
    The Architect asked for VISIBLE FRINGES on 2026-05-11. Diffusion
    mode can only produce a smooth envelope; Schrödinger mode with a
    propagating wave packet hitting the barrier reproduces the
    classical Young double-slit pattern on the far-side screen.

    The packet is injected once at registration with momentum aimed at
    the barrier. It then evolves under i ∂φ/∂t = −D∇²φ, passes through
    both slits, and the far-field pattern is the Fourier transform of
    the slit aperture function — the textbook Young pattern.

    If `install_screen_detector=True`, a `StigmergicDetector` is
    installed at the far edge so the field gets a measurement-by-
    amplification once intensity arrives.
    """
    cfg = FieldConfig(
        shape=(width, height),
        D_base=D,
        lam=0.0,                 # pure unitary evolution
        mode="schrodinger",
    )
    field_obj = FieldPrimary(cfg)
    cy = height // 2
    slits = []
    for off in slit_offsets:
        for w in range(-slit_width // 2, slit_width // 2 + 1):
            slits.append((cy + off + w,))
    field_obj.install_barrier(axis=0, position=barrier_x,
                              thickness=1, slit_positions=slits)
    pos = packet_position or (max(2, barrier_x - 15), cy)
    field_obj.add_wave_packet(WavePacket(
        position=pos,
        sigma=packet_sigma,
        amplitude=packet_amplitude,
        momentum=packet_momentum,
    ))
    if install_screen_detector:
        det = StigmergicDetector(
            region=(slice(width - 8, width - 2), slice(0, height)),
            threshold=0.001,
            amplify_gain=1.02,
            damp_factor=0.999,
            name="far_screen_detector",
        )
        field_obj.add_detector(det)
    return field_obj


def field_primary_summary() -> str:
    return (
        "SIFTA Field-Primary PDE: an N-dimensional solver for "
        "diffusion mode plus a split-step Schrödinger-style mode "
        "for wave interference. The barrier and the slits are structure "
        "IN the field; swimmers are localized Gaussian excitations that "
        "propagate through the field and accumulate phase-carrying "
        "traces. FIELD_PRIMARY_PDE_ONLY truth guard: this engine can "
        "simulate quantum-like wave interference, but does not prove "
        "the physical cause of quantum behavior. The field-is-primary "
        "ontology is ARCHITECT_DOCTRINE."
    )


__all__ = [
    "FIELD_PRIMARY_TRUTH_GUARD",
    "FieldConfig",
    "FieldPrimary",
    "StigmergicDetector",
    "Swimmer",
    "TRUTH_LABEL",
    "WavePacket",
    "field_primary_summary",
    "laplacian_nd",
    "make_double_slit_2d",
    "make_schrodinger_double_slit",
]
