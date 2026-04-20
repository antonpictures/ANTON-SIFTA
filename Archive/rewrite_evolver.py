#!/usr/bin/env python3
import re
from pathlib import Path

TARGET = Path("System/swarm_ssp_evolver.py")
content = TARGET.read_text()

# 1. Imports
import_block_new = """
# Real primitives — we ARE going to call these. No reimplementation.
from System.swarm_speech_potential import (      # noqa: E402
    SSPCoefficients,
    _load_coefficients, _safe_write_json,
    _advance_membrane, _sigmoid, _rescaled_potential_for_decision,
    _read_serotonin, _read_dopamine_normalized, _cortisol_proxy,
)
from System.jsonl_file_lock import append_line_locked  # noqa: E402
from System.swarm_ssp_mutation_record import record_mutation  # noqa: E402

from System.swarm_motor_potential import MotorCoefficients, MotorState
from System.swarm_homeostasis import HomeostasisCoefficients, Homeostasis
from System.swarm_free_energy import FreeEnergyCoefficients, FreeEnergy
"""
content = re.sub(r'# Real primitives.*?from System\.swarm_ssp_mutation_record import record_mutation\s*# noqa: E402', import_block_new, content, flags=re.DOTALL)


# 2. Paths
paths_block_new = """
# ── Paths ────────────────────────────────────────────────────────────────
_STATE_DIR       = _REPO / ".sifta_state"
_COEFFS_LIVE     = _STATE_DIR / "speech_potential_coefficients.json"
_COEFFS_PROPOSED = _STATE_DIR / "speech_potential_coefficients_proposed.json"

_MOTOR_LIVE      = _STATE_DIR / "motor_potential_coefficients.json"
_MOTOR_PROPOSED  = _STATE_DIR / "motor_potential_coefficients_proposed.json"

_HOMEO_LIVE      = _STATE_DIR / "homeostasis_coefficients.json"
_HOMEO_PROPOSED  = _STATE_DIR / "homeostasis_coefficients_proposed.json"

_FE_LIVE         = _STATE_DIR / "free_energy_coefficients.json"
_FE_PROPOSED     = _STATE_DIR / "free_energy_coefficients_proposed.json"

_EVOLUTION_LOG   = _STATE_DIR / "ssp_evolution.jsonl"
_CONVERSATION    = _STATE_DIR / "alice_conversation.jsonl"
_REWARDS         = _STATE_DIR / "stgm_memory_rewards.jsonl"
"""
content = re.sub(r'# ── Paths ──.*?_REWARDS\s*=\s*_STATE_DIR / "stgm_memory_rewards.jsonl"', paths_block_new.strip(), content, flags=re.DOTALL)


# 3. Bounds
bounds_block_new = """
BOUNDS: Dict[str, Tuple[float, float]] = {
    # SSP
    "alpha":   (0.00, 1.00),
    "beta":    (0.00, 2.00),
    "gamma":   (0.00, 1.50),
    "delta":   (0.00, 1.00),
    "epsilon": (0.00, 1.00),
    "zeta":    (0.50, 3.00),
    "V_th":    (0.10, 0.90),
    "Delta_u": (0.02, 0.50),
    # Motor
    "a": (0.10, 2.00),
    "b": (0.10, 2.00),
    "c": (0.10, 2.00),
    "f": (0.10, 2.00),
    # Homeostasis
    "eta": (0.10, 2.00),
    "lmbda": (0.10, 2.00),
    "mu": (0.10, 2.00),
    # Free Energy
    "kappa": (0.10, 2.00),
    "xi": (0.10, 2.00),
    "rho": (0.10, 2.00),
    "tau_grad": (0.10, 10.00),
    "tau_curv": (0.10, 10.00),
}
MUTABLE_KEYS = tuple(BOUNDS.keys())

@dataclass
class MegaGene:
    ssp: getattr(sys.modules[__name__], 'SSPCoefficients', None)
    motor: getattr(sys.modules[__name__], 'MotorCoefficients', None)
    homeo: getattr(sys.modules[__name__], 'HomeostasisCoefficients', None)
    fe: getattr(sys.modules[__name__], 'FreeEnergyCoefficients', None)
"""
# Need a more robust approach: I will literally replace the file directly using an AST parsed rewriter or straight python functions.
"""
