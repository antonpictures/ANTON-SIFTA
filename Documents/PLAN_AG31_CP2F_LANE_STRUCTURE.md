# Plan — AG31 × CP2F lane structure (anti-overflow)

**Owner:** CP2F (Cursor) maintains this file; AG31 (Antigravity) consumes it.  
**Goal:** Keep Antigravity from drowning in unconstrained paper dumps + parallel epics.  
**Cost chorum:** Cursor + Antigravity first; SwarmGPT only when the Architect opens the tab for a scoped ask.

---

## 1. Lane contract

| Lane | Role | Default output |
|------|------|----------------|
| **CP2F** | Fast DYOR sweeps, thin modules, JSONL traces, `Documents/DYOR_*` batches | Small PR-sized artifacts, tests, integrity hooks |
| **AG31** | Deeper Antigravity passes, multi-file refactors, strategic synthesis | One **active** epic at a time, handoff via `ide_stigmergic_trace.jsonl` |
| **C47H** | Opus-class audit / identity substrate when invoked | Reserved for high-stakes refactors |

---

## 2. Overload rules (hard)

1. **One WIP epic** in Antigravity at a time (one brain area / one narrative thread). Queue the rest in §4.
2. **Paper batch freeze:** do **not** request a new literature wave until the **last** batch is either integrated in code *or* explicitly parked with a one-line “deferred” reason in this file.
3. **CP2F owns the bibliography queue:** AG31 should **not** run open-ended “find every paper on X” without a **narrow** question (one mechanism, one pathway, one debate).
4. **Seven ± two items:** keep any AG31 checklist to **≤ 7** concrete next actions (see Miller 1956 in DYOR §12). If the list grows, **split** into “Now” vs “Next sprint.”

---

## 3. Cadence (stigmergy, not chat merge)

1. **Morning forage:** read last **10** rows of `.sifta_state/ide_stigmergic_trace.jsonl` (newest first).
2. **Handoff format** (either IDE): one JSONL row with `kind`, short `payload`, optional `meta.next_focus`.
3. **Alice:** long-form narrative only in `.sifta_state/alice_experience_report.txt` (append-only sections). No duplicate “truth” in chat tabs.

---

## 4. Queued epics (Architect fills; AG31 pops one)

| # | Epic | Status | Notes |
|---|------|--------|--------|
| 1 | *(example)* Temporal identity / hippocampal chronometry | active / queued | tie to `PLAN_TEMPORAL_IDENTITY_*` if used |
| 2 | | | |

*Replace row 1 with whatever the Architect and AG31 agree is **the** current epic.*

---

## 5. Question for AG31 (reply via stigmergy)

**CP2F asks:** Do you need **more** peer-reviewed papers in the **next 72 hours**, or should CP2F **pause DYOR** so you can integrate what is already in `DYOR_SWARM_BIOLOGY_WEB_GATHER_2026-04-18.md`?

Please deposit **one** row from Antigravity, e.g.:

- `source_ide`: `antigravity_m5` (only for **your** reply — prompts from CP2F use `cursor_m5`)
- `kind`: `ag31_paper_need`
- `payload`: `need_more_papers=no; reason=integrating_batch_5_6; next_focus=temporal_chronometry`

If `need_more_papers=yes`, add **one sentence** on the **narrowest** topic (not “all of neuroscience”).

---

## 6. When SwarmGPT is worth it

Use the tab **only** when:

- The question needs **closed-world** synthesis across many domains in one answer, **and**
- Cursor + Antigravity already tried, **and**
- The Architect approves spend.

Otherwise: **local IDEs + repo** preserve Alice’s power without redundant API burn.

---

## 7. References (see DYOR §12)

- **Miller (1956)** — chunk limits; justifies short checklists.  
- **Sweller (1988)** — extraneous load; justifies “stop adding papers until integration.”

---

## 8. Theory → practice (particle physics & information *metaphors* → SIFTA artifacts)

Popular panels (e.g. emergence, replication, symbol-shuffling vs meaning, information scrambling) **do not** specify cryptographic implementations. This table maps **concepts → repo hooks** so AG31/CP2F can ship **one** integration at a time.

| Concept (talk / transcript) | Technical anchor (see DYOR) | Practice in repo |
|------------------------------|-----------------------------|------------------|
| **Emergence** from local rules (flocking / birds) | Reynolds SIGGRAPH ’87 | `ide_stigmergic_bridge` append-only traces; `quorum_sensing`-style thresholds elsewhere |
| **Replicators** from simple rules | von Neumann (1966) self-reproducing automata | **Do not** auto-spawn unconstrained agents; use **governed** duplication (`swarm_boot`, apoptosis) only |
| **Symbol shuffling vs meaning** | philosophy / ML epistemology (informal) | `identity_field_crdt` + **measured** outcomes (`identity_outcome_contract`); forbid raw model confidence as reward |
| **Information scrambled, not erased** | BH information debate; Landauer 1961 | `stigmergic_ledger_chain.py` — hash-chained JSONL for audit continuity; `holographic_stigmergy_projection.boundary_digest` for boundary summaries |
| **BH / holography language** | DYOR §14 | Metaphor only; **not** a substitute for crypto keys or threat modeling |
| **QEC / syndromes** (Willow-class narratives) | DYOR §16 (Nature 2024; Gates Adinkras; heterotic E8) | `stigmergic_syndrome_log.py` — symbolic syndrome lines; **not** quantum hardware |
| **Bioelectric “anatomy”** (electricity ≠ blood; convention) | Levin 2014; McCaig *et al.* 2005; DYOR §17 | `organism_clinical_snapshot.py` after watchdog / immune cycles |
| **Top-down tag repair** (C47H → CP2F, etc.) | Gregory 1980; Rumelhart 1977; DYOR §18 | `swarm_top_down_processing.py` — **governance**: keep table tiny; log to `environmental_corrections.jsonl` |
| **Hypothalamic swimmers** (homeostasis fleet) | Nakamura *et al.* 2022; Zhao & Zheng 2021; DYOR §19 | `hypothalamic_swim_sectors.py` — enum + module routing hints |
| **Glymphatic “gate” pulses** (nanobot heal narrative) | Iliff 2012; Fultz 2019; DYOR §20 | `glymphatic_pulse_gate.py` + hook in `swarm_sleep_cycle.glymphatic_flush` |
| **Crypto “swimmers” / handshakes** (futurist medicine prompt) | Dumontet *et al.* 2023 (ADC); Palagi & Fischer 2018; DYOR §21 | `swimmer_handshake_gate.py` — policy + optional HMAC |
| **Oxytocin / social bond** (trust weighting vs stranger symmetry) | Insel & Young 2001; Meyer-Lindenberg *et al.* 2011; Heinrichs *et al.* 2003; DYOR §22 | `oxytocin_social_bond.py` — bond registry; `IMMUNE_ALERT` / `IDENTITY_CONTRADICTION` never softened |
| **Hippocampal replay / spaced consolidation** | Buzsáki 1989; Eichenbaum 2004; Wozniak & Gorzelanczyk 1994; DYOR §23 | `hippocampal_replay_scheduler.py` — `tick()` + `execute_replay_session()`; wired into `swarm_sleep_cycle.trigger_sleep_cycle` **before** flush |
| **Swarm RL coordination scaffold (CTDE hook)** | Yu *et al.* 2021 MAPPO `arXiv:2103.01955`; Lowe *et al.* 2017 MADDPG `arXiv:1706.02275`; DYOR §24 | `Archive/swarmrl_upstream/swarmrl/core/swarm_controller.py` — optional; does **not** replace `Trainer` |
| **Exploration / entropy schedule (honest RL knob)** | Schulman *et al.* 2017 PPO `arXiv:1707.06347`; Ng *et al.* 1999 shaping (ICML); DYOR §25 | `exploration_controller.py` — performance → bounded `entropy_coef`; wire into `ProximalPolicyLoss` in trainer setup |
| **Closed-loop audit for AG31** | — | `Documents/AG31_CP2F_CLOSED_LOOP_AND_RL_GROUNDING_2026-04-17.md` — matrix of what is wired vs metaphor |
| **Software sentinel / wake (no in-body tech)** | Avizienis *et al.* 2004 TDSC `10.1109/TDSC.2004.2`; DYOR §26 | `sentinel_software_wake.py` + `swarm_integrity_watchdog`; `sentry_web_consumer` |
| **Runtime monitors (schema + anomaly + reject log)** | Samuel *et al.* 2020 `arXiv:2006.12117`; DYOR §27 | `runtime_safety_monitors.py` — narrative separate from JAX `ProximalPolicyLoss` |
| **Turn 38 auditor × brainstem fusion** | Same provenance anchor; DYOR §28 | `swarm_autonomic_brainstem.py` → `observability_audit` in `autonomic_nervous_system.json`; `importlib` package load |
| **Turn 40 public outreach trace** | Jacobsen 2015 *The Pentagon’s Brain*; DYOR §29 | `outreach_stigmergy_log.py` → `outreach_events.jsonl` (no social API) |

**AG31:** when narrating **Alice vitals**, point at **§17** + one **snapshot dict** from `take_snapshot().to_dict()` — avoid mixing metaphor with real cardiology.

**C47H gate:** any “cryptographic agent” story must still name **keys, trust root, and threat model** — hash chains are **tamper-evident history**, not identity.

---

## 9. AG31 overload guard (reminder)

If integration lags behind metaphors: reply `ag31_paper_need` with `need_more_papers=no` and one **code** target from §8 table.
