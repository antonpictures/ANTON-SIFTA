#!/usr/bin/env python3
import re
from pathlib import Path

TARGET = Path("System/swarm_ssp_evolver.py")
content = TARGET.read_text(encoding="utf-8")

# 1. IMPORTS
content = content.replace(
    "from System.swarm_ssp_mutation_record import record_mutation  # noqa: E402",
    "from System.swarm_ssp_mutation_record import record_mutation  # noqa: E402\n"
    "from System.swarm_motor_potential import MotorCoefficients, MotorState\n"
    "from System.swarm_homeostasis import HomeostasisCoefficients, Homeostasis\n"
    "from System.swarm_free_energy import FreeEnergyCoefficients, FreeEnergy"
)

# 2. PATHS
content = content.replace(
    "_COEFFS_PROPOSED = _STATE_DIR / \"speech_potential_coefficients_proposed.json\"",
    "_COEFFS_PROPOSED = _STATE_DIR / \"speech_potential_coefficients_proposed.json\"\n"
    "_MOTOR_LIVE      = _STATE_DIR / \"motor_potential_coefficients.json\"\n"
    "_MOTOR_PROPOSED  = _STATE_DIR / \"motor_potential_coefficients_proposed.json\"\n"
    "_HOMEO_LIVE      = _STATE_DIR / \"homeostasis_coefficients.json\"\n"
    "_HOMEO_PROPOSED  = _STATE_DIR / \"homeostasis_coefficients_proposed.json\"\n"
    "_FE_LIVE         = _STATE_DIR / \"free_energy_coefficients.json\"\n"
    "_FE_PROPOSED     = _STATE_DIR / \"free_energy_coefficients_proposed.json\"\n"
)

# 3. BOUNDS
bounds_original = """BOUNDS: Dict[str, Tuple[float, float]] = {
    "alpha":   (0.00, 1.00),   # serotonin baseline — nonnegative
    "beta":    (0.00, 2.00),   # dopamine phasic   — nonnegative
    "gamma":   (0.00, 1.50),   # cortisol inhibit  — nonnegative
    "delta":   (0.00, 1.00),   # stigmergic accum  — nonnegative
    "epsilon": (0.00, 1.00),   # turn pressure     — nonnegative
    "zeta":    (0.50, 3.00),   # listener veto     — FLOOR 0.5 so she
                               #                     cannot learn to interrupt
    "V_th":    (0.10, 0.90),   # firing threshold  — outside this range
                               #                     Alice becomes pathological
    "Delta_u": (0.02, 0.50),   # escape softness   — too high → noise wins
}"""

bounds_new = """BOUNDS: Dict[str, Tuple[float, float]] = {
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
}"""

content = content.replace(bounds_original, bounds_new)


# 4. DATACLASSES
megagene_def = """
@dataclass
class MegaGene:
    ssp: SSPCoefficients
    motor: MotorCoefficients
    homeo: HomeostasisCoefficients
    fe: FreeEnergyCoefficients

    def __getattr__(self, name):
        if hasattr(self.ssp, name): return getattr(self.ssp, name)
        if hasattr(self.motor, name): return getattr(self.motor, name)
        if hasattr(self.homeo, name): return getattr(self.homeo, name)
        if hasattr(self.fe, name): return getattr(self.fe, name)
        raise AttributeError(f"MegaGene has no {name}")

    def replace_key(self, key, value):
        from dataclasses import replace
        if hasattr(self.ssp, key): return MegaGene(replace(self.ssp, **{key: value}), self.motor, self.homeo, self.fe)
        if hasattr(self.motor, key): return MegaGene(self.ssp, replace(self.motor, **{key: value}), self.homeo, self.fe)
        if hasattr(self.homeo, key): return MegaGene(self.ssp, self.motor, replace(self.homeo, **{key: value}), self.fe)
        if hasattr(self.fe, key): return MegaGene(self.ssp, self.motor, self.homeo, replace(self.fe, **{key: value}))
        return self
"""
content = content.replace("@dataclass\nclass AnnealingConfig:", megagene_def + "\n\n@dataclass\nclass AnnealingConfig:")


# 5. Type Hint Replacements
content = content.replace("coeffs: SSPCoefficients,", "coeffs: MegaGene,")
content = content.replace("best: SSPCoefficients", "best: MegaGene")
content = content.replace("-> SSPCoefficients:", "-> MegaGene:")
content = content.replace("initial: SSPCoefficients", "initial: MegaGene")


# 6. Simulator Modifications
simulator_old = """        # Advance membrane
        V = _advance_membrane(V, I, dt, coeffs.tau_m_s)

        # Decision (deterministic, noise=0)
        V_natural = _rescaled_potential_for_decision(V, coeffs.tau_m_s)
        in_refractory = (t - t_last_spike) < coeffs.tau_ref_s and t_last_spike > 0.0

        # Escape-noise spike probability (for reporting, not decision)
        p_spike = _sigmoid((V_natural - coeffs.V_th) / max(1e-6, coeffs.Delta_u))
        fire = (V_natural >= coeffs.V_th) and not in_refractory"""

simulator_new = """        # ── COUPLED PHYSICS INTEGRATION ────────────────────────────
        # Advance membrane (Phi)
        V = _advance_membrane(V, I, dt, coeffs.ssp.tau_m_s)
        V_natural = _rescaled_potential_for_decision(V, coeffs.ssp.tau_m_s)
        in_refractory = (t - t_last_spike) < coeffs.ssp.tau_ref_s and t_last_spike > 0.0
        
        # Stochastic Bernoulli Escape-noise spike probability (C47H Rule 4)
        p_spike = _sigmoid((V_natural - coeffs.ssp.V_th) / max(1e-6, coeffs.ssp.Delta_u))
        fire = (random.random() < p_spike) and not in_refractory"""

content = content.replace(simulator_old, simulator_new)


# 7. Loading coefficients
mega_load = """def _load_mega_coefficients() -> MegaGene:
    import json
    def _read_coeff(path, cls):
        try:
            return cls(**json.loads(path.read_text()))
        except:
            return cls()
    return MegaGene(
        ssp=_read_coeff(_COEFFS_LIVE, SSPCoefficients),
        motor=_read_coeff(_MOTOR_LIVE, MotorCoefficients),
        homeo=_read_coeff(_HOMEO_LIVE, HomeostasisCoefficients),
        fe=_read_coeff(_FE_LIVE, FreeEnergyCoefficients)
    )"""

content = content.replace("initial = _load_coefficients()", "initial = _load_mega_coefficients()")
content = content.replace("initial = _load_coefficients()", "initial = _load_mega_coefficients()")
content = content.replace(megagene_def + "\n\n@dataclass", megagene_def + "\n\n" + mega_load + "\n\n@dataclass")


# 8. Mutator clip
mutate_replace = """    changes: Dict[str, float] = {}
    for k in MUTABLE_KEYS:
        lo, hi = BOUNDS[k]
        span = hi - lo
        step = rng.gauss(0.0, sigma_frac * span)
        current = getattr(coeffs, k)
        coeffs = coeffs.replace_key(k, _clip(current + step, k))
    return coeffs"""
content = re.sub(r'    changes: Dict\[str, float\] = \{\}.*?return replace\(coeffs, \*\*changes\)', mutate_replace, content, flags=re.DOTALL)


# 9. Apply Proposal
apply_prop_old = """    full = asdict(best)
    full["_provenance"] = {"""

apply_prop_new = """    _safe_write_json(_MOTOR_PROPOSED, asdict(best.motor))
    _safe_write_json(_HOMEO_PROPOSED, asdict(best.homeo))
    _safe_write_json(_FE_PROPOSED, asdict(best.fe))
    
    full = asdict(best.ssp)
    full["_provenance"] = {"""

content = content.replace(apply_prop_old, apply_prop_new)

apply_routine = """    result = record_mutation(
        ide="cursor_m5",
        method="annealing_apply",
        coefficients=prop_clean,
        fitness_delta=prov.get("delta_fitness"),
        target_rate=prov.get("target_rate"),
        observed_rate=prov.get("observed_rate"),
        iterations_run=prov.get("iterations_run"),
        note="swarm_ssp_evolver.apply_proposal",
        module_version=MODULE_VERSION,
        coeffs_path=_COEFFS_LIVE,
        repo_root=_REPO,
        extra={
            "proposed_by": prov.get("proposed_by"),
            "proposal_provenance_ts": prov.get("ts"),
        },
    )"""

apply_mega_routine = """    result = record_mutation(
        ide="cursor_m5",method="annealing_apply",coefficients=prop_clean,fitness_delta=prov.get("delta_fitness"),
        target_rate=prov.get("target_rate"),observed_rate=prov.get("observed_rate"),iterations_run=prov.get("iterations_run"),
        note="swarm_ssp_evolver.apply_proposal",module_version=MODULE_VERSION,coeffs_path=_COEFFS_LIVE,repo_root=_REPO,
        extra={"proposed_by": prov.get("proposed_by"),"proposal_provenance_ts": prov.get("ts")}
    )
    
    # Write the coupled outputs
    import shutil
    shutil.copy(_MOTOR_PROPOSED, _MOTOR_LIVE)
    shutil.copy(_HOMEO_PROPOSED, _HOMEO_LIVE)
    shutil.copy(_FE_PROPOSED, _FE_LIVE)"""
content = content.replace(apply_routine, apply_mega_routine)

# Overwrite
TARGET.write_text(content, encoding="utf-8")
print("Rewrite script executed successfully.")
