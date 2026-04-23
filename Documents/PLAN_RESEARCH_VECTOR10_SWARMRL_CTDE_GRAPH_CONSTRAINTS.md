# PLAN + RESEARCH — Vector 10: Graph-Coupled Constraints, CTDE, Learned Safety (SwarmRL)

**Date:** 2026-04-16  
**Scope:** **Maximum DYOR** — literature + **concrete co-design** against **real SIFTA code** (no fictional runtime).  
**Prerequisite vectors (already in repo):**
- **Vector 8** — `System/lagrangian_constraint_manifold.py` (dual ascent on \(\lambda\), telemetry from `regime_state.json`, `spectral_entanglement.json`, `hysteresis_state.json`, residues in `.sifta_state/`).
- **Vector 9** — `System/hierarchical_meta_controller.py` (meta-controller adapts `alpha_ascent` on \(\lambda\) updates; reads manifold penalties).

**Bridge code:** `Network/swarmrl_bridge.py` (multi-agent SCAR consensus).  
**Upstream reference:** `Library/swarmrl/swarmrl/` — `ForceFunction`, `ActorCriticAgent`, `Trainer.update_rl`.

---

## 1. What Vector 10 is (engineering definition)

Vector 9 gives **three time-scales** inside **one** process: **hard mask → Lagrangian penalties → meta LR on dual updates**.

**Vector 10** extends that into **multi-agent + graph + training-time structure**:

| Track | Idea | Why it’s “research-grade” |
|-------|------|---------------------------|
| **10A** | **Graph-coupled duals** — \(\lambda\) (or slack) **diffuses / aggregates** over agent–agent or skill–skill edges | Same constraints **shared** across neighbors; avoids per-node \(\lambda\) explosion |
| **10B** | **Constraint critic** — value net predicts **future violation** \( \mathbb{E}[\sum \gamma^t c_i] \) | Shaping **before** damage; connects to **safe RL** |
| **10C** | **Differentiable projection** — replace pure `clip` with **QP / box** layer where gradients flow | End-to-end sensitivity (optional; heavier deps) |
| **10D** | **CTDE** — centralized training, decentralized execution | Matches real swarm: **train** with global info, **act** with local obs only |

Vector 10 is still **constrained optimization + MARL**, not metaphysics.

---

## 2. DYOR — papers (verified IDs / venues)

### 2.1 CTDE & cooperative MARL (execution vs training)

- **The Surprising Effectiveness of PPO in Cooperative Multi-Agent Games (MAPPO)** — [arXiv:2103.01955](https://arxiv.org/abs/2103.01955). Centralized critic / value, decentralized actors; baseline for **on-policy** SwarmRL trainers in `Library/swarmrl/`.  
  **Steal for SIFTA:** Training loop may see **global** `ρ`, `λ₂`, `E_total`; **live** agents only see **local** observations + **shared** policy.

- **QMIX / VDN** (factorized value): classic when joint action space blows up — cite original QMIX (ICML 2018) if you add **monotonic** mixing for team return.

- **JointPPO** — [arXiv:2404.11831](https://arxiv.org/abs/2404.11831). Deeper analysis of PPO in MARL; use for **hyperparameter** sanity when porting MAPPO ideas.

### 2.2 Safe / constrained MARL (your \(\lambda\) layer is principled)

- **Provably Efficient Generalized Lagrangian Policy Optimization for Safe Multi-Agent Reinforcement Learning** — *PMLR* 2023: [Proceedings link](https://proceedings.mlr.press/v211/ding23a.html).  
  **Steal for SIFTA:** Formal **dual** updates in **Markov games** — legitimizes **Vector 8** as more than a hack.

- **Double Duality / VPDPO** — JMLR 2023: [22-1190](https://www.jmlr.org/papers/v24/22-1190.html). Primal–dual structure for **constrained** RL.

- **Last-Iterate Global Convergence of Policy Gradients for Constrained RL** — [arXiv:2407.10775](https://arxiv.org/abs/2407.10775). Theory for **dual** methods; use when tuning **ascent** rates (meta-controller stability).

- **CPO** (single-agent but canonical projection mindset) — *Constrained Policy Optimization* (Achiam et al., ICML 2017). Trust-region **feasibility**; alternative to pure penalty.

### 2.3 Graph structure in multi-agent RL (10A: λ on a network)

- **Graph convolution / attention for MARL** — e.g. **DGN** (Deep Graph Network) style architectures where **communication** or **relation** is learned (search “Deep Graph Network multi-agent reinforcement learning” for the exact arXiv ID in your stack version).  
  **Steal for SIFTA:** Build **adjacency** from `swarmrl_bridge` consensus graph or **skill entanglement** graph (`Documents/RESEARCH_ICF_QUANTIZATION_SKILL_SPECTRAL_CROSS_NODE.md`); **message-passing** on \(\lambda\) or on **violations** before dual update.

- **Supra-Laplacian / multiplex** — [arXiv:2409.11984](https://arxiv.org/abs/2409.11984). If agents form **layers** (M5 vs M1 vs role), treat **multi-layer** graph for **coupled** penalties.

### 2.4 Differentiable projection & implicit layers (10C)

- **OptNet / differentiable QP** — Amos & Kolter (2017) — `cvxpylayers` / `qpth` patterns.  
  **Steal for SIFTA:** Replace **clipping** with **box QP** only if you accept **GPU + solver** deps in the training path; keep **clip** for production **inference**.

### 2.5 Predictive safety / constraint forecasting (10B)

- **Shielded reinforcement learning** / **CBF** (control barrier functions) in RL — large literature; start from surveys on **safe RL** (e.g. *García & Fernández* JMLR survey style).  
  **Steal for SIFTA:** Auxiliary head: **violation probability** next \(k\) steps from `(obs, proposed_action)` — feeds **early quarantine** (aligns with ICF **no-delete** policy).

### 2.6 Cross-node coherence (ties to Vector 10D)

- **Consensus algorithms** — review [Springer AI Review consensus survey](https://link.springer.com/article/10.1007/s10462-021-10097-x) (cited in ICF docs).  
  **Steal for SIFTA:** **Dual variables** or **global return** estimates may need **consensus** across nodes before **writer** to `lagrangian_multipliers.json`.

---

## 3. Co-design against **your** files (no hallucinated paths)

| Component | Today | Vector 10 hook |
|-----------|--------|----------------|
| `lagrangian_constraint_manifold.py` | Scalar \(\lambda\) triple + dual ascent | Add **optional** `GraphDualAggregator` input: **neighbor violations** → **coupled** update |
| `hierarchical_meta_controller.py` | Adapts `alpha_ascent` | Also adapt **graph diffusion rate** or **critic loss weight** |
| `Network/swarmrl_bridge.py` | SCAR consensus | Define **topology** for 10A (**who shares \(\lambda\)**) |
| `.sifta_state/lagrangian_multipliers.json` | Global \(\lambda\) | Version schema for **per-agent** \(\lambda_i\) + **sync epoch** |
| `Library/swarmrl/.../actor_critic.py` | PPO-style trajectory | Inject **penalty** and **cost** channels; optional **central critic** for CTDE |

---

## 4. Implementation phases (PR-shaped)

| Phase | Deliverable | Risk |
|-------|-------------|------|
| **V10.0** | Spec **constraint cost** \(c_i(s,a)\) in SwarmRL env same shape as manifold (ρ, λ₂, energy) | Low |
| **V10.1** | **MAPPO-style** centralized critic in **training only**; actors unchanged at inference | Medium (non-stationarity) |
| **V10.2** | **Graph mixer** for \(\lambda\) or violations (numpy first, torch later) | Medium |
| **V10.3** | **Auxiliary violation predictor** (small MLP) | Medium–high (labels) |
| **V10.4** | Differentiable QP **optional** branch | High (deps) |

---

## 5. Spec sketch — `vector10_graph_dual_layer.py` (behavioral, not merged)

```python
# Behavioral spec only — integrate with lagrangian_constraint_manifold + bridge topology.

class GraphCoupledDualUpdate:
    """
    10A: Aggregate neighbor violations before dual ascent.
    W: weighted adjacency (row-normalized), v_i local violation vector.
    """

    def __init__(self, num_agents: int, adjacency):
        self.W = adjacency  # (n, n)
        self.n = num_agents

    def coupled_violation(self, v_local: list) -> list:
        import numpy as np
        V = np.asarray(v_local)  # (n, k)
        return self.W @ V  # graph smoothing of violations


class ConstraintCriticHead:
    """
    10B: Predict future discounted constraint return (training only).
    """

    def __init__(self, obs_dim, num_constraints):
        ...

    def estimate(self, obs) -> float:
        ...
```

**Reward shaping:** `r_total = r_task - λᵀ c - β * log p_violation` (only if theory-aligned; tune \(\beta\)).

---

## 6. What Vector 10 is **not**

- Not **causality-breaking** layers.
- Not a replacement for **Ed25519 / governor / mutation law**.
- Not mandatory **differentiable QP** — **clip + Lagrangian** remains valid SOTA-adjacent for many labs.

---

## 7. Rally

**Couple duals on the graph, centralize the critic in training, decentralize the policy in deployment — stay honest in the ledger.**

**POWER TO THE SWARM** — **Vector 10 = research-grade constraints**, not **cosplay physics**.

---

## 8. Vector 11 (next) — training stability & evaluation

After Vector 10 wiring, the marginal gain is **measurement**, not more boxes:

- **Ablation:** τ-only thresholds vs τ + λ-derived risk features vs graph-coupled duals.  
- **risk_pressure upgrade:** \(\mathbb{E}[\text{violation}] + \beta \cdot \mathrm{Var}(\text{violation})\) for robustness under shift.  
- **Convergence:** track λ oscillation / overshoot (cf. PID-Lagrangian, gradient shaping for multi-constraint safe RL).  
- **Empirical** constraint violation rates on held-out regimes.

**Briefing:** `Documents/NOTES_TOMORROW_2026-04-17_SESSION_BRIEFING.md` §8–9 (PR-style closure + SwarmGPT line).
