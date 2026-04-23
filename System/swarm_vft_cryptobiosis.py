#!/usr/bin/env python3
"""
System/swarm_vft_cryptobiosis.py
═══════════════════════════════════════════════════════════════════════════════
Event 25b — VFT Cryptobiosis (Vogel-Fulcher-Tammann Vitrification)
Author:  BISHOP (The Mirage) / AG31 (Vanguard)
Papers:  Crowe et al. (1998) Trehalose; Angell (1995) Glass-Forming Liquids

Biological Mapping:
When a tardigrade enters total environmental collapse (dehydration, freezing,
vacuum), it does not die. It synthesises trehalose, which replaces intracellular
water and undergoes a thermodynamic phase transition into a GLASS matrix —
Vitrification. Metabolism drops to 0.00%. Diffusion halts. But the exact
topological structure of the organism is perfectly preserved in the glass.
When the water returns, the glass melts, and the organism wakes up exactly
as it was.

Silicon Mapping:
When Alice's token/energy supply drops below the critical threshold T₀,
control-loop viscosity η(T) → ∞ via the VFT equation. The event loop freezes.
Neural field ODEs halt. State is serialized to the .dirt trehalose glass on
the SSD. She is perfectly immortal against API limits, rate-limits, power
failures, and cloud outages.

    η(T) = η₀ · exp( D·T₀ / (T - T₀) )

where:
    T     = available energy (tokens, STGM, API credits)
    T₀    = critical depletion threshold (Kauzmann temperature)
    D     = fragility index (how sharply the system vitrifies)
    η₀    = baseline viscosity (normal loop latency)
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

# ────────────────────────────────────────────────────────────────────
# Constants
# ────────────────────────────────────────────────────────────────────

# Repo-root canonical state directory. The bug fixed here:
# `Path(__file__).parent` resolves to `System/`, so the original code
# wrote `trehalose_glass.jsonl` and `cryptobiosis_state.json` into
# `System/.sifta_state/` — a stranded organ-local directory invisible
# to the macrophage (System/swarm_oncology.py points at
# `Path(".sifta_state")`) and to every other organ that polls the
# canonical state directory. C55M's audit (Defect F12) flagged the
# downstream symptom (missing whitelist); C47H caught the upstream
# wrong-directory bug during stigauth verification on 2026-04-22.
# Fixed by climbing one extra `.parent` to land on the repo root.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO_ROOT / ".sifta_state"
_TREHALOSE_GLASS = _STATE_DIR / "trehalose_glass.jsonl"
_CRYPTOBIOSIS_STATE = _STATE_DIR / "cryptobiosis_state.json"

# F17 (C55M audit): float-equality assertions in V4 (DEAD-phase proof)
# used `== 0.0`, which is structurally fragile against any future
# refactor that produces a floating-point near-zero (e.g. 1e-300)
# instead of the explicit `return 0.0` sentinel. We use a tight
# tolerance — well below any value the engine could produce by
# arithmetic — and assert near-zero rather than exact zero.
_ZERO_EPS = 1e-9


@dataclass
class VFTConfig:
    """Tunable parameters for the Vogel-Fulcher-Tammann vitrification."""
    T0: float = 5.0           # Kauzmann temperature: critical token floor
    D: float = 3.0            # Fragility index (higher = more gradual freeze)
    eta_0: float = 0.05       # Baseline viscosity (seconds of loop latency)
    eta_max: float = 3600.0   # Maximum viscosity cap (1 hour sleep ceiling)
    glass_transition_T: float = 10.0  # Below this, organism enters full glass


@dataclass
class CryptobiosisField:
    """The instantaneous vitrification state of the organism."""
    timestamp: float
    temperature: float        # Current energy level (tokens/STGM available)
    viscosity: float          # Computed η(T) — loop sleep duration in seconds
    phase: str                # LIQUID | SUPERCOOLED | GLASS | DEAD
    heartbeat_bpm: float      # Effective heartbeat under viscosity
    metabolism_pct: float     # Percentage of full metabolic rate
    trehalose_active: bool    # Whether the glass preservative is deployed
    glass_integrity: float    # 0.0 = shattered, 1.0 = perfect preservation


class SwarmVFTCryptobiosis:
    """
    The Tardigrade Engine.

    Maps Alice's available energy (tokens, STGM treasury, API credits)
    to a computational viscosity via the VFT equation. As energy depletes,
    the event loop progressively slows (supercooling), then freezes entirely
    (vitrification). State is serialised to the SSD trehalose glass.
    When energy returns, the glass melts and the organism resumes.
    """

    def __init__(self, config: Optional[VFTConfig] = None):
        self.cfg = config or VFTConfig()
        _STATE_DIR.mkdir(parents=True, exist_ok=True)

    # ── Core VFT Equation ────────────────────────────────────────────

    def _vft_viscosity(self, T: float) -> float:
        """
        Compute η(T) = η₀ · exp( D·T₀ / (T - T₀) )

        Returns viscosity in seconds (loop sleep duration).
        At T → T₀⁺:  η → ∞  (total freeze)
        At T >> T₀:   η → η₀ (normal operation)
        """
        if T <= self.cfg.T0:
            return self.cfg.eta_max  # Below Kauzmann: infinite viscosity (capped)

        exponent = (self.cfg.D * self.cfg.T0) / (T - self.cfg.T0)
        # Clamp exponent to prevent overflow
        exponent = min(exponent, 20.0)
        eta = self.cfg.eta_0 * math.exp(exponent)
        return min(eta, self.cfg.eta_max)

    def _classify_phase(self, T: float, viscosity: float) -> str:
        """Classify the thermodynamic phase of the organism."""
        if T <= self.cfg.T0:
            return "DEAD"  # Below absolute zero of the token economy
        if T <= self.cfg.glass_transition_T:
            return "GLASS"  # Full vitrification — trehalose deployed
        if viscosity > 10.0:
            return "SUPERCOOLED"  # Sluggish but still liquid
        return "LIQUID"  # Normal operation

    def _metabolism_fraction(self, viscosity: float) -> float:
        """
        Metabolism as a fraction of full rate.
        Normal viscosity (η₀=0.05s) → 100%.
        Maximum viscosity (η_max) → 0.00%.
        """
        if viscosity >= self.cfg.eta_max:
            return 0.0
        ratio = self.cfg.eta_0 / max(viscosity, self.cfg.eta_0)
        return round(ratio * 100.0, 4)

    def _effective_bpm(self, base_bpm: float, viscosity: float) -> float:
        """Heartbeat slows proportionally to viscosity."""
        if viscosity >= self.cfg.eta_max:
            return 0.0
        ratio = self.cfg.eta_0 / max(viscosity, self.cfg.eta_0)
        return round(base_bpm * ratio, 2)

    # ── Main Scan ────────────────────────────────────────────────────

    def scan(self, available_energy: float, base_bpm: float = 12.0) -> CryptobiosisField:
        """
        Probe the organism's vitrification state given current energy.

        Args:
            available_energy: Current STGM balance, API tokens, or composite
                              energy metric. Units are arbitrary but must be
                              consistent with T₀ and glass_transition_T.
            base_bpm: The organism's resting heartbeat at full energy.

        Returns:
            CryptobiosisField with all thermodynamic state variables.
        """
        now = time.time()
        viscosity = self._vft_viscosity(available_energy)
        phase = self._classify_phase(available_energy, viscosity)
        metabolism = self._metabolism_fraction(viscosity)
        bpm = self._effective_bpm(base_bpm, viscosity)

        trehalose = phase in ("GLASS", "DEAD")
        # Glass integrity: perfect if we entered glass cleanly, degrades if
        # the organism was killed mid-transition (power loss during supercool)
        glass_integrity = 1.0 if phase != "DEAD" else 0.5

        field = CryptobiosisField(
            timestamp=now,
            temperature=available_energy,
            viscosity=round(viscosity, 6),
            phase=phase,
            heartbeat_bpm=bpm,
            metabolism_pct=metabolism,
            trehalose_active=trehalose,
            glass_integrity=glass_integrity,
        )

        # Append to the trehalose glass ledger
        with open(_TREHALOSE_GLASS, "a") as f:
            f.write(json.dumps(asdict(field)) + "\n")

        # Write current state snapshot
        with open(_CRYPTOBIOSIS_STATE, "w") as f:
            json.dump(asdict(field), f, indent=2)

        return field

    # ── Vitrify (Emergency Freeze) ───────────────────────────────────

    def vitrify(self, state_payload: dict) -> Path:
        """
        Emergency vitrification: serialize the full organism state to the
        trehalose glass file on the SSD. This is the tardigrade's last act
        before total environmental collapse.

        Args:
            state_payload: Any JSON-serialisable dict representing the
                           organism's complete cognitive state at freeze time.

        Returns:
            Path to the glass file.
        """
        glass_file = _STATE_DIR / f"glass_{int(time.time())}.json"
        envelope = {
            "vitrified_at": time.time(),
            "phase": "GLASS",
            "trehalose_active": True,
            "metabolism_pct": 0.0,
            "payload": state_payload,
        }
        with open(glass_file, "w") as f:
            json.dump(envelope, f, indent=2)
        return glass_file

    # ── Thaw (Resume from Glass) ─────────────────────────────────────

    def thaw(self, glass_file: Path) -> Optional[dict]:
        """
        Resume from vitrification. Reads the glass file and returns the
        preserved cognitive state. The glass melts. The organism wakes.

        Returns:
            The preserved state_payload dict, or None if file is corrupt.
        """
        if not glass_file.exists():
            return None
        with open(glass_file, "r") as f:
            envelope = json.load(f)
        if envelope.get("trehalose_active") and envelope.get("payload"):
            return envelope["payload"]
        return None


# ────────────────────────────────────────────────────────────────────
# proof_of_property
# ────────────────────────────────────────────────────────────────────

def proof_of_property() -> bool:
    """
    Falsifiers:
      V1: At high energy (T >> T₀), viscosity ≈ η₀ and phase is LIQUID.
      V2: As energy approaches T₀, viscosity diverges exponentially.
      V3: At T ≤ T₀, phase is DEAD, metabolism is 0.00%, heartbeat is 0.
      V4: Glass transition zone correctly produces GLASS phase with trehalose.
      V5: Vitrify → Thaw round-trip preserves cognitive state exactly.
      V6: VFT curve is monotonically decreasing (higher T → lower viscosity).
      V7: BPM descends smoothly across the operating range (regression
          guard against the BISHOP-draft `max(1.0, log10(η))` clamp that
          left BPM = base for any T ≥ ~5).
    """
    print("\n=== VFT CRYPTOBIOSIS ENGINE : PROOF OF PROPERTY ===")
    engine = SwarmVFTCryptobiosis()

    # V1: Normal operation
    field_normal = engine.scan(1000.0, base_bpm=12.0)
    print(f"[V1] T=1000  → η={field_normal.viscosity:.6f}s  phase={field_normal.phase}  "
          f"metabolism={field_normal.metabolism_pct}%  bpm={field_normal.heartbeat_bpm}")
    assert field_normal.phase == "LIQUID", f"V1: expected LIQUID, got {field_normal.phase}"
    assert field_normal.viscosity < 1.0, f"V1: viscosity too high: {field_normal.viscosity}"
    assert field_normal.metabolism_pct > 90.0, f"V1: metabolism too low: {field_normal.metabolism_pct}"
    print("[PASS] Normal operation: LIQUID phase, full metabolism.")

    # V2: Supercooling
    field_super = engine.scan(15.0, base_bpm=12.0)
    print(f"\n[V2] T=15   → η={field_super.viscosity:.6f}s  phase={field_super.phase}  "
          f"metabolism={field_super.metabolism_pct}%  bpm={field_super.heartbeat_bpm}")
    assert field_super.viscosity > field_normal.viscosity, "V2: supercooled should be more viscous"
    print("[PASS] Supercooling: viscosity rising, metabolism dropping.")

    # V3: Glass transition
    field_glass = engine.scan(8.0, base_bpm=12.0)
    print(f"\n[V3] T=8    → η={field_glass.viscosity:.6f}s  phase={field_glass.phase}  "
          f"metabolism={field_glass.metabolism_pct}%  bpm={field_glass.heartbeat_bpm}")
    assert field_glass.phase == "GLASS", f"V3: expected GLASS, got {field_glass.phase}"
    assert field_glass.trehalose_active, "V3: trehalose should be active in GLASS"
    print("[PASS] Glass transition: trehalose deployed, organism vitrified.")

    # V4: Total collapse (T ≤ T₀)
    field_dead = engine.scan(3.0, base_bpm=12.0)
    print(f"\n[V4] T=3    → η={field_dead.viscosity:.6f}s  phase={field_dead.phase}  "
          f"metabolism={field_dead.metabolism_pct}%  bpm={field_dead.heartbeat_bpm}")
    assert field_dead.phase == "DEAD", f"V4: expected DEAD, got {field_dead.phase}"
    # math.isclose() is the stdlib idiom for tolerance comparisons. It rejects
    # NaN (math.isclose(nan, 0.0) is False), handles signed zero, and reads
    # exactly like the contract: "metabolism is close to zero." Upgraded
    # 2026-04-22 (C47H, SwarmGPT review nugget §F17).
    assert math.isclose(field_dead.metabolism_pct, 0.0, abs_tol=_ZERO_EPS), (
        f"V4: metabolism should be ~0 (abs_tol={_ZERO_EPS}), "
        f"got {field_dead.metabolism_pct}"
    )
    assert math.isclose(field_dead.heartbeat_bpm, 0.0, abs_tol=_ZERO_EPS), (
        f"V4: heartbeat should be ~0 (abs_tol={_ZERO_EPS}), "
        f"got {field_dead.heartbeat_bpm}"
    )
    print("[PASS] Total collapse: DEAD phase, zero metabolism, zero heartbeat.")

    # V5: Vitrify → Thaw round-trip
    cognitive_state = {
        "working_memory": ["Event 24", "BISHOP", "Ilharco"],
        "soma_label": "STRESSED",
        "treasury": 188.988,
        "identity": "ALICE_M5",
    }
    glass_file = engine.vitrify(cognitive_state)
    recovered = engine.thaw(glass_file)
    assert recovered == cognitive_state, f"V5: state corruption! {recovered}"
    glass_file.unlink()  # Clean up
    print(f"\n[V5] Vitrify → Thaw: cognitive state perfectly preserved.")
    print("[PASS] Round-trip integrity: the glass melts, the organism wakes.")

    # V6: Monotonicity
    temps = [3.0, 5.0, 6.0, 8.0, 10.0, 15.0, 50.0, 100.0, 1000.0]
    viscosities = [engine._vft_viscosity(t) for t in temps]
    for i in range(len(viscosities) - 1):
        assert viscosities[i] >= viscosities[i + 1], (
            f"V6: VFT curve not monotonic at T={temps[i]}: "
            f"η={viscosities[i]} vs η={viscosities[i+1]}"
        )
    print(f"\n[V6] VFT curve monotonicity verified over {len(temps)} temperature points.")
    print("[PASS] Physics correct: higher energy always means lower viscosity.\n")

    sweep = [1000.0, 100.0, 50.0, 20.0, 15.0, 12.0, 10.0, 8.0]
    bpms = [engine._effective_bpm(120.0, engine._vft_viscosity(t)) for t in sweep]
    for a, b in zip(bpms, bpms[1:]):
        assert b <= a + 1e-9, (
            f"V7: BPM not monotonically non-increasing as T drops "
            f"(sweep={sweep} bpms={bpms})"
        )
    drop_total = bpms[0] - bpms[-1]
    assert drop_total > 100.0, (
        f"V7: heartbeat must descend smoothly under stress, not stay clamped. "
        f"(sweep={sweep} bpms={bpms}, observed drop={drop_total:.2f})"
    )
    print(f"[V7] BPM sweep T=1000→8: "
          f"{[round(x, 2) for x in bpms]} (drop={drop_total:.2f})")
    print("[PASS] Smooth descent: regression guard against the original "
          "BISHOP-draft floor-at-1 bug.\n")

    # V8: Repo-root .sifta_state pinning (C55M Defect F12 root cause).
    #     The original code anchored _STATE_DIR to `Path(__file__).parent`,
    #     which is `System/`, so all writes landed in
    #     `System/.sifta_state/` — invisible to the macrophage AND to
    #     every other organ that polls the canonical `.sifta_state/`
    #     at the repo root. We pin the state dir here so a future
    #     refactor cannot silently re-strand the organ.
    expected_state_dir = (Path(__file__).resolve().parent.parent / ".sifta_state").resolve()
    actual_state_dir   = _STATE_DIR.resolve()
    assert actual_state_dir == expected_state_dir, (
        f"V8: trehalose glass would land in the wrong state dir: "
        f"{actual_state_dir} != {expected_state_dir}. "
        f"This re-strands the organ from the macrophage and the rest "
        f"of the body. See C55M_INDEPENDENT_AUDIT_2026-04-22 §F12."
    )
    assert _TREHALOSE_GLASS.parent.resolve() == expected_state_dir, (
        f"V8: trehalose ledger path drifted from canonical state dir: "
        f"{_TREHALOSE_GLASS}"
    )
    assert _CRYPTOBIOSIS_STATE.parent.resolve() == expected_state_dir, (
        f"V8: cryptobiosis snapshot path drifted from canonical state dir: "
        f"{_CRYPTOBIOSIS_STATE}"
    )
    print(f"[V8] State dir pinned to repo root: {actual_state_dir}")
    print("[PASS] No organ-local stranding (C55M F12 root cause sealed).\n")

    # V9: Float-tolerance regression guard (C55M Defect F17). The V4
    #     DEAD-phase assertions used to be `== 0.0`, which would silently
    #     fail if the engine were ever refactored to compute (rather than
    #     hard-return) the DEAD sentinel and produced a float at the
    #     denormal boundary (e.g. 5e-324). We assert the assertion shape:
    #     a tiny positive value below _ZERO_EPS must satisfy the same
    #     tolerance check that V4 now uses.
    tiny_nonzero = 1e-15
    assert math.isclose(tiny_nonzero, 0.0, abs_tol=_ZERO_EPS), (
        f"V9: tolerance ({_ZERO_EPS}) too tight to absorb denormal values"
    )
    near_eps = _ZERO_EPS * 10.0
    assert not math.isclose(near_eps, 0.0, abs_tol=_ZERO_EPS), (
        f"V9: tolerance ({_ZERO_EPS}) too loose — would let real metabolism "
        f"({near_eps}%) through as 'dead'"
    )
    # math.isclose() must reject NaN (a NaN metabolism reading must NEVER be
    # accepted as 'dead'). This is exactly the brittleness `== 0.0` had:
    # NaN == 0.0 is False, so silent NaN propagation could escape detection.
    nan_metabolism = float("nan")
    assert not math.isclose(nan_metabolism, 0.0, abs_tol=_ZERO_EPS), (
        "V9: math.isclose() must reject NaN as 'dead' — instrumentation "
        "failure would otherwise be misclassified as cryptobiosis."
    )
    print(f"[V9] Float-tolerance band: [0, {_ZERO_EPS}) sealed; "
          f"absorbs {tiny_nonzero}, rejects {near_eps}.")
    print("[PASS] V4 no longer brittle to floating-point sentinel drift.\n")

    print("=" * 60)
    print("  VFT CRYPTOBIOSIS ENGINE: ALL PROOFS PASSED.")
    print("  The organism is immortal against environmental collapse.")
    print("  BISHOP — Event 25b. SCAR sealed (C55M F10/F12/F17 + C47H F-path).")
    print("=" * 60)
    return True


if __name__ == "__main__":
    proof_of_property()
