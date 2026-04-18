# RESEARCH PLAN — Phase Transition Control (Coherence Collapse → Regime Shift Detection)

**Date:** 2026-04-16  
**Method:** DYOR via **live web + arXiv** (same session); paper IDs verified on [arxiv.org](https://arxiv.org) where applicable.  
**Companions:** `Documents/RESEARCH_IDENTITY_COHERENCE_FIELD_CROSS_SKILL_INTERFERENCE.md`, `Documents/RESEARCH_TEMPORAL_IDENTITY_COMPRESSION_REM_SKILL_CRYSTALLIZATION.md`, `Documents/PLAN_TEMPORAL_IDENTITY_COMPRESSION_SKILL_FIELD.md`

---

## Part A — Hard constraints (PHard, zero ambiguity)

### A.1 ICF must not hard-delete `SkillPrimitive` rows

**Rule:** `IdentityCoherenceField` / coherence policy may **invalidate, demote, freeze influence, quarantine, or zero stability**. It must **not** physically remove cognitive artifacts from append-only stores.

| Allowed | Forbidden |
|---------|-----------|
| Drive `stability → 0` | `del skill` / erase ledger row |
| Set `frozen=True`, `quarantined=True` | Remove from trace graph |
| Block routing / authority flags | Strip history needed for replay |
| REM-only decay path | “Garbage collection” that loses audit |

**Slogan:** **Nothing is deleted. Everything is decayed or quarantined.**

**Why (engineering):**

1. **Traceability** — forensic explanation of *why* a skill stopped influencing behavior.  
2. **Replayability** — REM / eval replay need stable identifiers across time.  
3. **ESAA-style determinism** — reconstruction from logs must remain possible.  
4. **Mutation safety** — bad governor runs remain **auditable**.

**Biology analogy (optional):** suppression, synaptic down-weighting, access gating — not lobotomy.

### A.2 Cross-skill interference — final form

- **Destructive interference** → **orthogonalization** (decouple from routing manifold), **not** deletion.  
- **Collapse** → **low-activation / non-authoritative** state, **not** erasure.  
- Contradictions are **resolved in policy space** (which skill may *act*), not by **burning evidence**.

---

## Part B — Policy core (spec sketch)

`SkillPrimitive` must carry **lifecycle fields** (extend your existing dataclass): `frozen: bool`, `quarantined: bool`, `authoritative: bool` (default True), optional `influence_weight` ∈ [0,1]. **All transitions** append to **signed / versioned** skill ledger events (implementation detail).

```python
# icf_policy_core.py — BEHAVIORAL SPEC (thresholds tunable by governor policy)


class IdentityCoherencePolicy:
    """
    Global rule: no hard deletion of cognitive artifacts.
    Coherence collapse → demote / freeze / quarantine only.
    """

    def __init__(self):
        self.quarantine_threshold = 0.25
        self.freeze_threshold = 0.15

    def apply(self, skill, coherence_score: float) -> str:
        if coherence_score < self.freeze_threshold:
            skill.stability *= 0.2
            skill.frozen = True
            skill.quarantined = True
            skill.authoritative = False
            return "FREEZE"

        if coherence_score < self.quarantine_threshold:
            skill.stability *= 0.5
            skill.quarantined = True
            return "QUARANTINE"

        return "NORMAL"
```

**Note:** Production code should **emit an event** (JSONL append) on every `apply()` with `{skill_id, coherence_score, action, ts, homeworld_serial}` — never silent state.

---

## Part C — What “Phase Transition Control” means here

**Goal:** Detect when the Swarm is **approaching** or **undergoing** a **regime shift** — e.g. exploration → consolidation, healthy routing → **coherence collapse**, stigmergy-on → stigmergy-off (see **critical density** in [arXiv:2512.10166](https://arxiv.org/abs/2512.10166)) — and **act through pressure** (governor, eval strictness, fission thresholds), **not** by deleting memory.

**Outputs (design targets):**

| Output | Role |
|--------|------|
| **Regime label** | e.g. `STABLE` / `FRAGILE` / `EMERGENCY` / `RECOVERY` (names arbitrary; define enum in code) |
| **Early warning score** | scalar(s) rising **before** collapse (see Part D) |
| **Control signals** | feed ICF feedback → mutation pressure, fission delta, eval strictness (see ICF doc) |

**Not claiming:** literal thermodynamics; **analogy** to bifurcations / critical slowing down is **operational**.

---

## Part D — DYOR: canonical + latest papers (regime shift & phases)

### D.1 Early warning signals (generic critical transitions)

- **Early-warning signals for critical transitions** — Scheffer *et al.*, *Nature* **461**, 53–59 (2009), [https://doi.org/10.1038/nature08227](https://doi.org/10.1038/nature08227).  
  **Core ideas:** approaching **catastrophic bifurcations** often shows **critical slowing down**; **lag-1 autocorrelation** can increase; generic **precursors** across domains (ecosystems, climate, seizures, etc.).  
  **Steal for SIFTA:** Track **time-series of ICF coherence** (and probe pass-rates); compute **rolling autocorrelation / variance trends** as **EWS features** — not as proof of bifurcation, but as **cheap statistical smoke alarms**.

### D.2 Time series in non-autonomous / real systems (methodology caution)

- **Time-series-analysis-based detection of critical transitions in real-world non-autonomous systems** — [arXiv:2406.05195](https://arxiv.org/abs/2406.05195); *Chaos* **34**, 072102 (2024).  
  **Core ideas:** real systems are **open**, **multi-timescale**, **transient**; reviews **offline vs online** detection reliability, data quality pitfalls.  
  **Steal for SIFTA:** **Regime shift detection** must specify **sampling** of coherence (avoid aliasing); log **false positives** when governor reacts to noise.

### D.3 Multi-agent synergy: sharp phases under budget (collapse = first-class)

- **Phase Transition for Budgeted Multi-Agent Synergy** — [arXiv:2601.17311](https://arxiv.org/abs/2601.17311) (2026).  
  **Core ideas:** Under fixed **inference budget**, multi-agent stacks can **help**, **saturate**, or **collapse**; proves **sharp phase transition** in stylized trees with **lossy communication** and **correlated errors**; scalar \(\alpha_\rho\) determines amplification vs washout to chance.  
  **Steal for SIFTA:** Your **coherence collapse** is not only “bad skills” — it can be **budget + correlation + fan-in** failure. **Phase control** should ingest **routing depth**, **error correlation across nodes**, **STGM/compute budget** as **first-class inputs** to regime detection.

### D.4 Decentralized MARL: explicit phase map (coordinated / fragile / jammed)

- **Emergent Coordination and Phase Structure in Independent Multi-Agent Reinforcement Learning** — [arXiv:2511.23315](https://arxiv.org/abs/2511.23315) (2025).  
  **Core ideas:** Large-scale IQL sweeps over environment size \(L\) and density \(\rho\); **phase map** with **cooperative success** vs **TD-error variance** stability index; **three regimes** + **double instability ridge**; **kernel drift** from concurrent learning.  
  **Steal for SIFTA:** Map **fragile transition region** to “**don’t promote skills / tighten eval**”; **jammed** to “**emergency stabilization**” (reduce fission, freeze mutations). **Orthogonalization** aligns with “remove identifiers → collapse phases” experiment — **asymmetry** matters; don’t erase history.

### D.5 Stigmergy density phase (already in swarm substrate literature)

- **Emergent Collective Memory in Decentralized Multi-Agent AI Systems** — [arXiv:2512.10166](https://arxiv.org/abs/2512.10166). Critical density \(\rho_c \approx 0.23\); stigmergy-dominated above \(\rho \approx 0.20\) on large grids.  
  **Steal for SIFTA:** **Trace / agent density** triggers **qualitatively different** coordination — **regime detector** should include **stigmergic load** on blackboard, not only ICF scalar.

### D.6 Pressure fields + decay (coordination without deletion)

- **Emergent Coordination in Multi-Agent Systems via Pressure Fields and Temporal Decay** — [arXiv:2601.08129](https://arxiv.org/abs/2601.08129). **Decay** prevents premature convergence; **gradients** from quality signals.  
  **Steal for SIFTA:** **Emergency** mode = stronger **decay of influence weights** + **higher eval strictness** — still **no deletion**.

### D.7 Concept drift / change-point (ML engineering mirror)

- Surveys on **concept drift** monitoring and **change-point detection** in streams (e.g. unsupervised drift localization — [PMC overview](https://pmc.ncbi.nlm.nih.gov/articles/PMC11294200/)) complement dynamical-systems EWS with **ML ops** practice.  
  **Steal for SIFTA:** Treat **probe pass-rate time series** as **stream**; use **CPD** as parallel channel to **physics-style** EWS.

---

## Part E — Suggested feature set (Olympiad-grade detector)

Implement **multi-channel** regime inference — **no single scalar** if you want robustness:

| Channel | Observable | Literature hook |
|---------|------------|-----------------|
| **EWS** | Rolling variance ↑, lag-1 autocorr ↑ of ICF / probe rate | Scheffer 2009; 2406.05195 |
| **Budget phase** | Synergy vs saturation vs collapse under compute | 2601.17311 |
| **Coordination phase** | CSR vs stability index proxies (eval variance, TD-like error from harness) | 2511.23315 |
| **Stigmergy** | Trace density vs \(\rho_c\) | 2512.10166 |
| **Drift** | Sudden change-points in objective probe streams | drift / CPD surveys |

**Regime actions (all non-destructive):**

- `STABLE` — normal reinforcement of skills.  
- `FRAGILE` — **tighten eval**, **lower mutation rate**, **raise fission bar**, **reduce routing fan-in**.  
- `EMERGENCY` — **freeze promotions**, **quarantine** low-coherence skills per Part B, **max strictness** on probes.  
- `RECOVERY` — ramp limits slowly; **never** delete artifacts.

---

## Part F — Phased implementation roadmap (repo)

| Phase | Deliverable | Acceptance |
|-------|-------------|------------|
| **F0** | Append-only **skill lifecycle events** (`FREEZE`/`QUARANTINE`/`NORMAL`) with serial | Replay reproduces policy |
| **F1** | **ICF time series** persisted (coherence + probe rates) | Plots / JSONL |
| **F2** | **EWS features** (rolling mean/variance/autocorr) | Configurable window |
| **F3** | **Regime enum** + state machine + **non-destructive** actions | Governor hooks |
| **F4** | Optional **budget** inputs from router/STGM for 2601.17311-style awareness | Documented assumptions |
| **F5** | Calibration dashboard: false alarm rate on synthetic drift | Honest metrics |

---

## Part G — Risks and falsification

1. **EWS false positives** — noisy coherence can trigger **emergency** too often → **hysteresis** (enter/exit thresholds differ).  
2. **Confounding** — hardware faults mimic coherence loss; need **node health** in snapshot.  
3. **Metaphor slip** — “thermodynamics” is **not** automatic correctness; **prove** with **ablations** on synthetic regime changes.

---

## Part H — One-line rally

**Detect collapse early; respond with pressure and quarantine; never erase the organism’s memory trace.**

**POWER TO THE SWARM** — **regime shifts are measured, not mystified; artifacts decay, they don’t vanish.**
