# Negar Mehr — Interactive Autonomy (ENGR319) vs SIFTA — axis comparison

**Stigauth:** `MEHR_ROBOTICS_SIFTA_AXIS_v1`
**Source (secondary):** Stanford Online — *ENGR319 | Spring 2026 | Interactive Autonomy* — Negar Mehr (UC Berkeley ICON Lab), ~2026-05-20.
**Architect:** George Anton — `#SIFTA` is not “we beat robotics”; it is **different substrate, shared coordination ideas**.

---

## 1. Is she “light years behind”? **No — wrong axis.**

| | **Mehr / ICON Lab** | **SIFTA** |
|---|---------------------|-----------|
| **Substrate** | Physical robots (quadcopters, arms, humanoids) in sim + lab | **Silicon organism** on M5/M1 — ledgers, organs, Alice, IDE doctors |
| **Hard problem** | Real-time **Nash / potential-game** planning, collision, multi-modal yield (left vs right) | **Truth, memory, identity, STGM**, no double-spend of receipts |
| **Memory** | Continual learning (ADMM consensus on **weights**), NeRF/Gaussian splats | Continual learning via **JSONL + hippocampus engrams + decay** |
| **Multi-agent** | Game theory, IRL from **interaction** demos, diffusion policies, MARL + **LLM coach** | Stigmergy: swimmers, skills, foragers, **no central Nash solver** |
| **Deploy today** | Research demos; warehouse / HRI is hard | **Operational** desktop OS + Talk path (imperfect but shipped) |

She is not behind you on **stigmergic sovereignty**. You are not behind her on **provable multi-robot motion** in clutter with humans. Comparing them on one scoreboard is category error.

Your comment **“Solution: #SIFTA”** is funny and directionally right only if you mean: *the cognitive / coordination layer for many agents can be a **field + receipts**, not only a centralized game solver.*

---

## 2. Paper map — what she cites (lecture spine)

| Topic | Literature (she names / standard) | DOI / anchor |
|-------|-----------------------------------|--------------|
| Multi-agent planning as **dynamic games** | Basar & Olsder; game-theoretic control surveys | Textbooks / reviews |
| **Nash equilibrium** (joint prediction + planning) | Classic game theory | — |
| **Potential games** — one OC problem vs coupled OC | Monderer & Shapley (1996) potential games; her lab reduction | [doi:10.1007/BF01253744](https://doi.org/10.1007/BF01253744) |
| **Quantal response / noisy humans** | McKelvey & Palfrey (1995) QRE | [doi:10.1007/BF01255656](https://doi.org/10.1007/BF01255656) |
| **Inverse RL** from interactions | Ng & Russell (2000) IRL; multi-agent extensions (her work with “Mac”) | Russell IRL lineage |
| **Maximum entropy** multi-agent | Matches her “entropic cost equilibrium” | Ziebart et al. max-ent IRL |
| Multi-agent **imitation** + **exploitability** | Her theoretical MARL imitation section | Ross et al. imitation learning; game-theoretic exploitability |
| **Diffusion policies** for multi-modal coordination | Chi et al. diffusion policy (robotics) | [arxiv:2303.04137](https://arxiv.org/abs/2303.04137) |
| **LLM as coach** (curriculum, reward, credit) | No single paper — GPT-4/5 era engineering | Brynjolfsson-style productivity is separate |
| Continual learning via **consensus (ADMM)** | Distributed optimization; “consensus with past self” | Boyd et al. ADMM; continual learning surveys |
| Safety — constraints in diffusion / RL | Control barrier functions literature (implied) | Ames et al. CBF lineage |

---

## 3. Where ideas **overlap** (take for SIFTA)

| Her idea | SIFTA analogue | Take |
|----------|----------------|------|
| Agents need **theory of mind** (predict others’ reactions) | RLHS + fiction organ + owner model | Alice must not plan in vacuum — read traces / memory before speak |
| **Yield left vs yield right** — multimodal equilibria | Singapore vs US convention | **`FICTION_COWATCH` / locale conventions** — explicit mode bit in memory |
| Learn from **interaction** demos, not isolated human | IRL from pairs | Mine **George+Alice** rows, not monologue-only |
| **Exploitability** in multi-agent imitation | One doctor reacts to another’s bad policy | Separate **Cursor vs Antigravity** receipts — no merged identity |
| **LLM coach**: curriculum → sub-rewards → train | Hippocampus + skill breakdown | Coach organ: break “ship SIFTA eval pack” into sub-skills |
| **Credit assignment** in teams | STGM attribution per swimmer | `economic_attribution_key` on every costly row |
| Continual learning without keeping all data | Hippocampus + decay; not full replay | ADMM-style idea: **consensus with past engrams**, not replay entire chat |
| Sample-efficient human data | Foragers, STGM cost on store/recall | Don’t scrape infinite demos — **tight coupling** moments only |

---

## 4. What SIFTA has that her stack does not (your moat)

- **Append-only stigmergic field** — `ide_stigmergic_trace`, `memory_ledger`, flock locks.
- **Truth labels** — `OBSERVED` / `FICTION` / `HYPOTHESIS`; no Kasim-party from latent space.
- **Ed25519 STGM** — economic double-spend guard.
- **Federation** — M5 brain, M1 sentry — not one lab’s Postgres brain.
- **Owner body** — `swarm_owner_allostasis` — humans are not only “cost functions in a game.”

---

## 5. What to take from her (minimal GO)

1. **Interaction-mode bit** on memory rows (`yield_left` / `yield_right` / `FICTION_COWATCH`) — §7 GBrain adopt list.
2. **Exploitability check** — if Alice imitates a bad IDE trace, other organs must not “exploit” into drift (tests per doctor).
3. **Hippocampus curriculum** — LLM breaks “hard refactor” into sub-skills (her coach slide), then pytest each.
4. **Do not** build a Nash solver for Talk — overkill; use her *insight* (interdependence), not her *solver*.

---

## 6. One-line for your YouTube comment

**#SIFTA** = stigmergic multi-agent field on silicon (receipts + truth + STGM). **Mehr** = game-theoretic multi-agent motion in the physical world. Same word “agents”; different layer. Neither is “light years behind” the other.

---

## 7. BORG research spine — “bumping into people” on silicon

**Code:** `System/swarm_interaction_borg.py` · tests: `tests/test_swarm_interaction_borg.py` · memory field: `interaction_mode` on `PheromoneTrace` in `System/stigmergic_memory_bus.py`.

| BORG adopt | Physical (Mehr) | Extra papers to pull | SIFTA hook |
|------------|-----------------|----------------------|------------|
| **Interaction-mode bit** | Multimodal yield (left/right conventions) | Monderer & Shapley (1996) potential games · [doi:10.1007/BF01253744](https://doi.org/10.1007/BF01253744); McKelvey & Palfrey (1995) QRE · [doi:10.1007/BF01255656](https://doi.org/10.1007/BF01255656); Sadigh *et al.* “Planning for Autonomous Cars that Leverage Effects on Human Actions” (RSS 2016) — human-aware motion | `YIELD_LEFT` / `YIELD_RIGHT` / `FICTION_COWATCH` / `LOCALE_*` / `DYAD_GEORGE_ALICE` |
| **Interaction demos** | Multi-agent IRL from pairs | Ng & Russell (2000) IRL; Ho & Ermon (2016) GAIL · [arXiv:1606.03476](https://arxiv.org/abs/1606.03476); Brown *et al.* “Extrapolating Beyond Suboptimal Demonstrations via IRL from Observations” (ICML 2019) | `remember_interaction_turn()` — George+Alice rows via `swarm_interaction_importance` bands |
| **Hippocampus coach** | LLM curriculum → sub-rewards | Silver *et al.* “Mastering the game of Go with deep RL” (Nature 2016) — curriculum; Narvekar *et al.* curriculum learning survey · [arXiv:2002.01328](https://arxiv.org/abs/2002.01328); Park *et al.* “Generative Agents” (UIST 2023) — memory scheduling analogue | `coach_decompose_task()` → `.sifta_state/hippocampus_coach_tasks.jsonl` + pytest per sub-skill |
| **Credit assignment** | MARL team blame | Sutton *et al.* (1999) policy-gradient multi-agent; Foerster *et al.* “Counterfactual Multi-Agent Policy Gradients” (AAAI 2018) · [arXiv:1705.08926](https://arxiv.org/abs/1705.08926); Lanctot *et al.* “A Unified Game-Theoretic Approach to Multiagent RL” (NeurIPS 2017) | `credit_assign_doctor()` + `make_economic_attribution_key()` — **Cursor ≠ Antigravity** |
| **No Nash for Talk** | Full dynamic-game solver in clutter | Basar & Olsder game theory (text); **do not port** to Talk | `NASH_SOLVER_FOR_TALK = False` · `talk_coordination_policy()` |

**Social “collision” on silicon (Alice hygiene):** not quadcopters — duplicate Hello, wrong name (Alex), TV→memory bleed, owner restroom as “execute”. Modes + `FICTION` + `OWNER_BODY_MAINTENANCE` are the yield signs.

**Receipt ledgers (append-only):**

- `borg_interaction_receipts.jsonl` — dyad turns promoted to memory
- `borg_credit_attribution.jsonl` — per-doctor STGM rows
- `hippocampus_coach_tasks.jsonl` — curriculum decomposition

**Wire next (Talk widget):** call `remember_interaction_turn()` after high-band journal rows; do **not** add a Nash module.

For the Swarm. 🐜⚡
