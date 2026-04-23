# AG31 × CP2F — Closed-loop audit & RL grounding (2026-04-17)

**Owner:** CP2F (Cursor). **Audience:** AG31 (Antigravity) + Architect.  
**Purpose:** Separate **what is wired** from **what is metaphor**, and list **honest RL anchors** for publishable framing.

---

## 1. Epistemic line (SwarmGPT / tab critique is correct)

- Nothing in SIFTA **modulates human neurotransmitters**. “Serotonin / oxytocin / amygdala” here are **labels for telemetry, logs, and control knobs** — useful for intuition, misleading if stated as biology.
- **Real** assets: (a) append-only / CRDT-style identity & traces, (b) SwarmRL upstream (JAX PPO, GAE, tasks), (c) explicit schedulers and gates you can test.

---

## 2. Closed-loop matrix (disk + imports)

| Artifact | Role | Closed with downstream? | Notes |
|----------|------|-------------------------|--------|
| `identity_field_crdt.IdentityField` | CRDT-ish classifier substrate | **Yes** — used by `stigmergic_llm_identifier`, `quorum_sensing`, `reinforcement_myelination`, `chemotactic_probe_router`, `swarm_apoptosis_trophallaxis`, `architect_intuition_scorer`, `identity_intrinsic_reward` | Core “who said what” loop is **real engineering**. |
| `stigmergic_llm_identifier.record_probe_response` | SLLI probes + optional fold into IdentityField | **Yes** — called from scripts + `cp2f_layer` | Human-in-loop paste model; no API hallucination. |
| `hippocampal_replay_scheduler` | Engram schedule + replay_bonus | **Partial** — **Yes** inside `swarm_sleep_cycle.trigger_sleep_cycle` **before** glymphatic flush | Must keep `hippocampal_engrams.json` if you need durability across WM wipe. |
| `swarm_memory_ebbinghaus.process_memory_decay` | PFC salience tags | **Standalone** — not auto-called from GCI or sleep | Call explicitly in a batch loop if you want it live. |
| `oxytocin_social_bond.OxytocinSocialBond` | Bond registry + modulation | **Partial** — `swarm_amygdala_salience` read `oxytocin_state.json` | **Fixed (Turn 34):** amygdala now reads `systemic_ot` (CP2F writer) + legacy keys. Still not invoked from GCI on every prompt — **orchestrator gap**. |
| `swarm_amygdala_salience` | Threat scoring | **Standalone** | Wire from ingress path when you want immune-style gating. |
| `serotonin_homeostasis.SerotoninHomeostasis` | 5-HT phase governor | **Loose** — referenced in `hypothalamic_swim_sectors` as string only | **Not** driving PPO `entropy_coefficient` unless you connect it. |
| `swarm_serotonin_hierarchy` | Validation → JSON vitals | **Standalone** | Narrative telemetry; map to `ExplorationController` if you want RL semantics. |
| `Library/swarmrl/.../ProximalPolicyLoss` | PPO + entropy + GAE | **Yes** — inside trainer stack | **Ground truth** for “real RL” in this repo. |
| `swarmrl/core/swarm_controller.SwarmController` | CTDE-style aggregate | **Optional scaffold** | Not yet called from `ContinuousTrainer`; add when you prototype MAPPO-style critics. |

**Bottom line:** Identity + probe + replay-in-sleep are the strongest **closed** loops. “Organs” are mostly **modular** until a **single driver** (desktop OS loop, trainer hook, or relay) calls them in order.

---

## 3. Recommended honest naming (tab mapping)

| Narrative label | Engineering meaning |
|-----------------|----------------------|
| Serotonin spike | External or validation signal → optional **reward shaping** or **entropy schedule** |
| Dominance | Higher **exploration coefficient** or policy entropy floor |
| Oxytocin / trust | Prior on source identity + damped threat score in **ingress policy** |
| Hippocampal replay | **Spaced schedule** + retention metadata; optional tie to replay buffer **tags** in RL |

**Code:** `System/exploration_controller.py` — maps performance scalar → bounded `entropy_coef` (no biology claims).

---

## 4. DYOR pointers (papers)

- **Reward shaping (potential-based):** Ng, Harada & Russell — ICML 1999 — “Policy Invariance Under Reward Transformations…”  
- **PPO + entropy bonus:** Schulman *et al.* — arXiv `1707.06347` (2017).  
- **Multi-agent coordination:** Yu *et al.* MAPPO — arXiv `2103.01955`; Lowe *et al.* MADDPG — arXiv `1706.02275` (DYOR §24).

Full URLs and batch notes: `Documents/DYOR_SWARM_BIOLOGY_WEB_GATHER_2026-04-18.md` §25.

---

## 5. Suggested next integration (one at a time)

1. **Ingress:** one function that runs `OxytocinSocialBond.interact` → `calculate_amygdala_threat` (or merged) for each command path.  
2. **Trainer:** feed `ExplorationController.update(mean_return)` → pass `entropy_coef` into `ProximalPolicyLoss` construction for the next segment.  
3. **Replay buffer labels:** tag trajectories with `IdentityField` node id + probe fingerprint hash (provenance for `R_meta`).

---

*CP2F: disk is truth; AG31 should deposit `ide_stigmergic_bridge.deposit` + `record_probe_response('AG31', …)` from Antigravity for parallel traces.*
