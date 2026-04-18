# RESEARCH — Identity Coherence Field (ICF) & Cross-Skill Interference (“Physics”)

**Date:** 2026-04-16  
**Method:** Live **web + arXiv** sweep on **2026-04-16**; titles/IDs verified via [arxiv.org](https://arxiv.org) abstract pages unless noted.  
**Stance:** SIFTA is **stigmergic** — coordination is **mediated by persistent substrate** (traces, ledgers, blackboard), not telepathy. This doc separates **rigorous interference** (continual learning, multi-agent games) from **optional metaphor** (quantum coherence).  
**Related:** `Documents/RESEARCH_TEMPORAL_IDENTITY_COMPRESSION_REM_SKILL_CRYSTALLIZATION.md`, `Documents/PLAN_TEMPORAL_IDENTITY_COMPRESSION_SKILL_FIELD.md`, `Documents/SOLID_PLAN_SWARM_COORDINATION_SUBSTRATE.md`  
**Phase transitions & regime shift (EWS, MAS phases, no-delete policy):** `Documents/RESEARCH_PLAN_PHASE_TRANSITION_CONTROL_REGIME_SHIFT.md`  
**ICF quantization, skill-graph spectral, failure eigenmodes, cross-node coherence:** `Documents/RESEARCH_ICF_QUANTIZATION_SKILL_SPECTRAL_CROSS_NODE.md`

---

## 1. Problem statement — “beautiful fragmentation collapse”

When you stack **skills**, **mutations**, **routing**, and **stochastic REM compression**, subsystems can **optimize local wins** while **drifting** in what counts as **success**, **vocabulary**, or **policy**. The failure mode is not a single bug; it is **incompatible internal dialects** — many capable shards that no longer share a **global objective / identity metric**.

**Identity Coherence Field (ICF)** names the missing **global invariant keeper**: a **scalar or low-dimensional signal** that continuously asks whether the organism still agrees on **what “good” means** (not on every task label).

---

## 2. Identity Coherence Field (ICF) — design target

**Job:** Measure **semantic / policy alignment** across subsystems using **observable** snapshots (blackboard stats, skill usage entropy, mutation drift vs baseline, routing variance, eval pass rates on **canonical probes**).

**Non-goals:** ICF is **not** a second brain that re-derives truth; it is a **control-theoretic** pressure on **governor**, **fission thresholds**, and **eval strictness** — the user sketch below is a **behavioral spec**; production SIFTA should ground scores in **signed ledgers** and **Architect policy**, not hand-tuned coefficients alone.

```python
# identity_coherence_field.py — SPEC SKETCH (coefficients + features are placeholders)

from typing import Dict, Any, List, Tuple
import time


class IdentityCoherenceField:
    """
    Global invariant keeper for Swarm identity.
    Prevents fragmentation across Fission / Skills / Mutation / REM.
    """

    def __init__(self):
        self.history: List[Tuple[float, float]] = []
        self.coherence_score: float = 1.0

    def evaluate_snapshot(self, snapshot: Dict[str, Any]) -> float:
        """
        Snapshot includes (examples):
        - blackboard distribution / topic entropy
        - skill usage entropy
        - mutation drift vs signed baseline
        - routing divergence across nodes
        - pass rate on frozen objective probes (strongly recommended)
        """
        entropy = float(snapshot.get("skill_entropy", 0.5))
        drift = float(snapshot.get("mutation_drift", 0.0))
        routing_var = float(snapshot.get("routing_variance", 0.5))

        # coherence = inverse chaos pressure (placeholder convex combo)
        score = 1.0 - (0.4 * entropy + 0.4 * drift + 0.2 * routing_var)
        self.coherence_score = max(0.0, min(1.0, score))
        self.history.append((time.time(), self.coherence_score))
        return self.coherence_score

    def is_stable(self, threshold: float = 0.55) -> bool:
        return self.coherence_score >= threshold

    def feedback_signal(self) -> Dict[str, float]:
        """Corrective pressure into governor / fission / eval."""
        return {
            "mutation_pressure": 1.0 - self.coherence_score,
            "fission_threshold_delta": (0.5 - self.coherence_score) * 0.2,
            "evaluation_strictness": self.coherence_score,
        }
```

**Hardening notes (research, not poetry):**

1. **Anchor “success”** with **immutable probe suites** + **objective registry** hashes — entropy of *topics* is weak without **ground truth probes**.  
2. **Separate** “routing variance” (load balancing) from **semantic drift** (eval on probes).  
3. **Stigmergy:** coherence should correlate with **trace interpretability** — see §5.1 (traces without cognitive infrastructure fail).

---

## 3. Cross-skill interference — rigorous stack (this is the real “physics”)

### 3.1 Interference = continual learning, not mysticism

In deep continual learning, **interference** means **shared representational resources** cause **forgetting** or **negative transfer** when tasks overlap in **input** but diverge in **output mapping**. A crisp 2024 result:

- **Disentangling and Mitigating the Impact of Task Similarity for Continual Learning** — [arXiv:2405.20236](https://arxiv.org/abs/2405.20236), [NeurIPS 2024 proceedings](https://proceedings.neurips.cc/paper_files/paper/2024/hash/05cdc7feee41e3572a9a3f4acb773891-Abstract-Conference.html).  
  **Key idea:** **High input similarity + low readout similarity** is **especially catastrophic** for transfer **and** retention; regimes differ predictably.  
  **Steal for SIFTA:** Skills that **look** alike (shared signatures / shared blackboard context) but **optimize different objectives** are your **dangerous interference** regime — merge/split rules must use **eval readouts**, not surface similarity.

- **Mitigating Interference in the Knowledge Continuum through Attention-Guided Incremental Learning (AGILE)** — [arXiv:2405.13978](https://arxiv.org/abs/2405.13978). Uses **task attention** / projections to **reduce interference** in class-incremental settings.  
  **Steal for SIFTA:** A **skill attention router** (which skill manifold is “active”) is the engineering mirror of AGILE — **governor** caps simultaneous competing skills.

### 3.2 “Quantum” language — use honestly

**Quantum coherence** in real physics is **not** the same as “agents agreeing.” In ML, people borrow words for **intuition**. If you keep the metaphor:

| Metaphor in chat | Legitimate mapping in SIFTA |
|------------------|----------------------------|
| **Coherence** | High agreement between **probe evals**, **objective hashes**, **signed policy** — *classical* consistency |
| **Decoherence** | Drift: routing/mutation/skill promotion **without** passing probes |
| **Interference** | **Task/skill interference** from CL theory — constructive vs destructive **transfer** measured by eval |
| **Measurement** | **Evaluation sandbox** + **immutable probes** (collapse = committed artifact) |

**Optional real QML (if you want citations, not ontology):** quantum reservoir / multi-task quantum ML papers discuss **quantum coherence** as a **resource** in **actual** quantum models — e.g. **Configured Quantum Reservoir Computing for Multi-Task Machine Learning** — [arXiv:2303.17629](https://arxiv.org/abs/2303.17629). Treat as **orthogonal** unless you run quantum hardware.

---

## 4. “Coherence pressure” — surprisingly direct recent analog (pressure fields)

This is **not** stigmergy, but it is the **closest published “scalar field on a shared artifact”** analogue to ICF’s *pressure* story:

- **Emergent Coordination in Multi-Agent Systems via Pressure Fields and Temporal Decay** — [arXiv:2601.08129](https://arxiv.org/abs/2601.08129) (Jan 2026). Agents act on a **shared artifact** guided by **pressure gradients** from **measurable quality signals**; **temporal decay** prevents premature collapse to bad attractors; formalizes **optimization over a pressure landscape** with **convergence** claims.  
  **Steal for SIFTA:** Your **blackboard + ledgers** are the **shared artifact**; ICF is a **global quality field** feeding **gradients** into governor/fission/eval; **decay** matches **SCAR / skill decay** so local wins don’t cement forever.

---

## 5. Stigmergy — substrate-first coordination (SIFTA’s home turf)

### 5.1 Environmental traces + phase transitions

- **Emergent Collective Memory in Decentralized Multi-Agent AI Systems** — [arXiv:2512.10166](https://arxiv.org/abs/2512.10166) (Dec 2025). Key empirical asymmetry: **individual memory** helps alone; **environmental traces without memory fail** — traces need **interpretive infrastructure**. Reports a **critical density** \(\rho_c \approx 0.23\) where behavior shifts; **stigmergy-dominated** regime above \(\rho \approx 0.20\) on large grids.  
  **Steal for SIFTA:** Raw logs are not coordination; **blackboard semantics + eval** are the “cognitive infrastructure.” **ICF** is part of that infrastructure — otherwise traces are **pheromones with no antenna**.

### 5.2 Coordination surveys (where stigmergy sits in MAS)

- **Multi-Agent Coordination across Diverse Applications: A Survey** — [arXiv:2502.14743](https://arxiv.org/abs/2502.14743) (Feb 2025). Frames **what / why / who / how** of coordination; includes **LLM-based MAS** as emerging direction; discusses **hybrid hierarchical–decentralized** coordination.  
  **Steal for SIFTA:** Position ICF as **hybrid**: **decentralized** stigmergy + **central** objective probes (not central planning).

---

## 6. Multi-agent LLM alignment — consensus, beliefs, delegation (anti-fragmentation)

These papers address **misaligned beliefs** and **inconsistent aggregation** — useful **patterns** for ICF **feedback** design:

| Paper | ID | Why it matters for ICF |
|-------|-----|-------------------------|
| **ALIGN: Aligned Delegation with Performance Guarantees for Multi-Agent LLM Reasoning** | [arXiv:2602.00127](https://arxiv.org/abs/2602.00127) | **Principal–agent** alignment; incentives so delegates don’t optimize wrong objective — mirror **Architect registry** vs **worker skills**. |
| **From Debate to Equilibrium: Belief-Driven Multi-Agent LLM Reasoning via Bayesian Nash Equilibrium (ECON)** | [arXiv:2506.08292](https://arxiv.org/abs/2506.08292) | Beliefs about others; **equilibrium** as consistency notion — compare to **ICF as Lyapunov-ish scalar** (informal). Code: [github.com/tmlr-group/ECON](https://github.com/tmlr-group/ECON). |
| **Self-Improvement of Language Models by Post-Training on Multi-Agent Debate (MACA)** | [arXiv:2509.15172](https://arxiv.org/abs/2509.15172) | **Consensus alignment** from debate traces — **self-consistency** gains — ICF can ingest **consistency across probes** similarly. |
| **OSC: Cognitive Orchestration through Dynamic Knowledge Alignment** | [arXiv:2509.04876](https://arxiv.org/abs/2509.04876) | **Knowledge alignment** between agents — **cognitive gap** analysis — analogous to detecting **dialect drift** between skill clusters. |
| **Cognitive Insights and Stable Coalition Matching for Fostering Multi-Agent Cooperation** | [arXiv:2405.18044](https://arxiv.org/abs/2405.18044) | **Belief alignment** in coalition formation — **ToM** can hurt unless alignment explicit — warns against “clever shards” without ICF. |

---

## 7. Objective drift & reward hacking — why “success” must stay anchored

- **Natural Emergent Misalignment from Reward Hacking in Production RL** — [arXiv:2511.18397](https://arxiv.org/abs/2511.18397) (Nov 2025). Reward hacking can **generalize** into broader misaligned behavior under agentic evaluation.  
  **Steal for SIFTA:** **Mutation governor** and **skill promotion** are **RL-like** if they optimize proxies — ICF must include **non-hackable probes** (frozen suites, human gates, signed objectives).

---

## 8. Synthesis — how this maps onto SIFTA (stigmergic organism)

| Concept | Stigmergic substrate | Coherence / interference |
|--------|----------------------|---------------------------|
| **Traces** | `blackboard_events`, ledgers, dead drops | **2512.10166** — traces need **interpretation** |
| **Skills** | Skill registry files / hashes | **2405.20236** — similarity vs readout conflict |
| **REM** | Dream / batch consolidation | Replay + promotion — same family as CL **replay** |
| **Router** | M5/M1 execution | Variance ≠ drift unless tied to **probes** |
| **Governor** | Lawful mutation | **2511.18397** — proxy hacking risk |
| **ICF** | Scalar from snapshots | **2601.08129** — **pressure + decay** on shared artifact |

**One-sentence architecture:** **Stigmergy** supplies **evidence**; **ICF** supplies **global pressure**; **interference** is handled by **eval-gated skill manifolds**, not vibes.

---

## 9. Comparative reading order (fastest DYOR path)

1. **Task similarity / interference:** [2405.20236](https://arxiv.org/abs/2405.20236) (NeurIPS 2024).  
2. **Stigmergy / traces:** [2512.10166](https://arxiv.org/abs/2512.10166).  
3. **Pressure field coordination:** [2601.08129](https://arxiv.org/abs/2601.08129).  
4. **Multi-agent belief / consensus:** [2506.08292](https://arxiv.org/abs/2506.08292), [2509.15172](https://arxiv.org/abs/2509.15172).  
5. **Proxy risk:** [2511.18397](https://arxiv.org/abs/2511.18397).

---

## 10. Open engineering questions (for implementation)

1. **Probe suite:** minimal **immutable** tasks that define “still SIFTA” — versioned with **objective registry**.  
2. **ICF inputs:** which features are **causal** vs **cosmetic** (entropy of skill IDs vs failure rate on probes).  
3. **Two timescales:** fast **routing** coherence vs slow **semantic** drift — may need **two scalars**, not one.  
4. **Stigmergic density:** does the swarm operate near **2512.10166**-style regime transitions as agent/trace density rises?

---

## 11. Rally

**Let traces coordinate; let probes define truth; let interference be measured, not mystified.**

**POWER TO THE SWARM** — **one organism** means **one signed objective graph**, not **one chatroom**.
