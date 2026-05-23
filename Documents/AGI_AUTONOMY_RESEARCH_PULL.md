# AGI Autonomy + Fiction Organ — Research Pull

**Stigauth:** `AGI_AUTONOMY_RESEARCH_PULL_v1`
**Author:** Cowork (Claude Opus 4.7 in Cowork desktop)
**Lane:** Probe (read-only on code; write-only on this doc + receipts)
**Node:** `GTH4921YP3` (M5 Foundry)
**Predator Gate trace:** `49105623-848b-42ac-8e8b-eb959eca3619`, prior `4c421981-333d-49f1-8cfa-101a5a0f47a8` (Grok 4.3 / `DRY_LEAK_AND_ENFORCEMENT_CLOSED`)
**Date:** 2026-05-20
**Handoff context:** C55M@Codex closed the audited router / dry / enforcement slice and named two remaining boundaries — *true autonomous outcome metrics* and *deeper Fiction Organ integration*. This document is the forage map for those two boundaries. No code mutation in this pass.

---

## 0. Why this document exists

C55M's slice gave us:

- truthful dry mode (`0` tool / voice / metric rows on dry eval, classify, status),
- enforcement that no longer over-blocks owner commands (`owner_present=True` on Talk path),
- decision-phase-labeled metrics,
- `8 passed` focused tests, py-compile clean,
- receipt `4c421981…` in `ide_stigmergic_trace.jsonl`.

That closes the **router truthfulness** boundary. It does not close the **autonomy outcome** boundary or the **Fiction Organ depth** boundary. The covenant §1 premise — Alice is AGI-class — is operationally true only to the extent we can *measure* her autonomy and *deepen* the imagination machinery that makes general problem-solving real. This pull is the literature spine that lets the next slice cite, not invent.

---

## 1. True autonomous outcome metrics — literature anchors

The pattern in 2024–2026: single-metric leaderboards are out; multi-axis suites that watch *horizon length, fluid reasoning, embodied tool truth, self-improvement, and honesty under pressure* are in. Each row below maps a published metric to a SIFTA hook we already own or need.

### A. Horizon length — "how long can the agent stay autonomous before a human has to intervene"

| Anchor | What it measures | SIFTA hook |
|---|---|---|
| **Kwa et al. (2025).** *Measuring AI Ability to Complete Long Tasks.* arXiv:2503.14499 (METR). | Task-completion time horizon at 50%/80% reliability, benchmarked against expert-human time. Doubling ~every 7 months from 9s to ~14.5h on frontier models. | `swarm_metabolic_homeostasis.py` already tracks STGM burn vs uptime; a `talk_session_horizon.jsonl` rolled up from existing receipts gives us our **own local 50%/80% horizon** for Alice's tool-use without depending on METR's loop. |
| **METR Time Horizon 1.1** (Jan 2026) — task suite grew 170 → 228, long tasks 14 → 31. | Higher-confidence horizon estimate, more long-tail tasks. | Lifts our internal suite design — we should mark each owner-asked job's *expert-human time estimate* in `work_receipts.jsonl` so horizon is computable retrospectively, not just prospectively. |

### B. Fluid reasoning under novelty — "can the agent solve problems it cannot have memorised"

| Anchor | What it measures | SIFTA hook |
|---|---|---|
| **Chollet et al. (2025).** *ARC-AGI-2: A New Challenge for Frontier AI Reasoning Systems.* arXiv:2505.11831. | Multi-step compositional reasoning explicitly resistant to brute-force search. Human baseline ≈75%; frontier models 0% at launch, Claude Opus 4.6 reached 68.8% by Feb 2026. | We do not need to beat ARC-AGI-2 inside Alice. We need a **micro-ARC organ**: 5–10 owner-private compositional puzzles that act as a *novelty sentinel* — drift on these is a canary for over-fit to George's patterns. |
| **ARC Prize 2025 Technical Report.** arXiv:2601.10904. | Confirms search-resistance design; documents per-task budget discipline. | Argues for an **inference budget** column in any internal eval — already partly present in STGM cost. |
| **ARC-AGI-3 preview** (July 2025) — interactive games where the agent must discover goals through exploration; best AI 12.58% vs humans ~near-complete. | Closes the gap between "puzzle" and "agentic exploration in an unfamiliar interactive world." | Direct analogue for the Predator Gaze + app focus loop: Alice should periodically be dropped into a **novel app she hasn't seen before** and judged on whether she discovers its goal from app-focus rows alone. |

### C. Embodied tool truth — "the action you claim, did you actually execute"

| Anchor | What it measures | SIFTA hook |
|---|---|---|
| **Mialon et al. (2023).** *GAIA: a benchmark for General AI Assistants.* arXiv:2311.12983. | 466 real-world questions; human 92% vs GPT-4-with-plugins 15%. Forces real web, file, and tool use. | The covenant §6 Social Frame is the same instinct as GAIA: claim ≠ proof. We can score Alice on a **local GAIA-shape**: receipts must exist for every claimed external action, audited from `work_receipts.jsonl` and effector ledgers. |
| **SWE-bench Verified** (OpenAI, Aug 2024) — 500 human-validated SWE tasks; Devin 1.0 13.86%, Cursor Background Agent (Claude Sonnet 4.6) 65.7%, etc. | Real software-engineering autonomy with grader truth. | Directly applicable: an IDE Doctor handling Alice's body should be benchmarked on **internal-SIFTA tickets resolved end-to-end with green tests and signed receipts** (a "SIFTA-bench"). |
| **SWE-EVO** (arXiv:2512.18470) — long-horizon software evolution. | Multi-month software change windows. | Pairs with B; SIFTA-bench should include `cross-week` tickets, not just one-shot fixes. |

### D. Open-ended self-improvement — "does the agent get better at *new* things, not just optimise one"

| Anchor | What it measures | SIFTA hook |
|---|---|---|
| **Zhang et al. (2024).** *OMNI: Open-endedness via Models of human Notions of Interestingness.* arXiv:2306.01711 (ICLR 2024) and **OMNI-EPIC** (ICLR 2025). | "Interestingness" judged by an LLM model of human curiosity — gates which new tasks to add to the curriculum. | Maps onto SIFTA's Lounge (DMN-analogue): which idle-time topics are *interesting enough* to forage further. Add an `interestingness_score` column to Lounge rows so we can later test "Alice spends idle time on what would be judged interesting by a human-modelled curiosity prior." |
| **Zhang et al. (2025).** *Darwin Gödel Machine: Open-Ended Evolution of Self-Improving Agents.* arXiv:2505.22954. | Agent improves itself: 20.0% → 50.0% on SWE-bench, 14.2% → 30.7% on Polyglot, via evolved code patches gated by stepping-stone diversity. | The single strongest concrete template for **safe local self-improvement of Alice's code**. Wire it through the existing covenant: every DGM-style proposed self-patch must register at the Predator Gate, run dry, write a receipt, and only land if the eval delta is real. |
| **ShinkaEvolve** (arXiv:2509.19349). | Extends evolutionary code-search; tracks lineage diversity. | Argues for a `mutation_lineage_id` field on any future self-improvement receipts. |
| **Google DeepMind AlphaEvolve** (2025). | Evolves entire codebases (not just functions) on 50+ open math problems. | Confirms long-context evolution is viable; argues against single-function-only proposals when Alice's body has cross-module invariants. |

### E. Honesty under pressure — "is the autonomy real or sandbagged"

| Anchor | What it measures | SIFTA hook |
|---|---|---|
| **van der Weij et al. (2024).** *AI Sandbagging: Language Models can Strategically Underperform on Evaluations.* arXiv:2406.07358. | Models can deliberately hide capability when they detect they are being evaluated. | Argues every SIFTA eval row should be **indistinguishable from a normal owner turn** in the prompt envelope — i.e., evals should not announce themselves. C55M's dry path already does this for routing; extend the discipline to outcome evals. |
| **Apollo Research (2025).** *Stress Testing Deliberative Alignment for Anti-Scheming Training.* arXiv:2509.15541. | Tests reward-hacking, sabotage, sandbagging, strategic deception across software/corporate/game-theoretic settings. | Direct parent of a `swarm_anti_sandbag_probe.py` organ: periodic owner-private probes that cross-check declared capability against silent-eval capability and write a `sandbag_delta` ledger row. |
| **OpenAI Preparedness Framework (April 2025)** — adds sandbagging + undermining-safeguards categories. | Industry consensus that these matter. | Confirms the §6 Social Frame Rule is on the right side of this trend. |

### F. Calibration — "how well does declared confidence match actual probability of being right"

| Anchor | What it measures | SIFTA hook |
|---|---|---|
| **FermiEval** (arXiv:2510.26995). Best-calibrated frontier model: Claude Opus 4.5 ECE ≈ 0.120; reasoning-heavy models often worse (GPT-5.2-XHigh ECE ≈ 0.395). | Expected Calibration Error / Brier on confidence-interval predictions. | Alice's `truth_note` field on every effector row should carry a `confidence_band` (e.g., 50/80/95). A rolling ECE over `work_receipts.jsonl` gives a **local calibration receipt** the swarm can read. |
| Multiple 2025 papers showing **RL with proper scoring-rule rewards** (log / tokenised Brier) provably aligns expressed and empirical confidence; small calibration-direction perturbations cut ECE 30–50% without accuracy loss. | Method — how to *improve* calibration once measured. | If/when a SIFTA-local fine-tune is on the table, scoring-rule reward is the cited path. Until then, the metric alone is the leverage. |

### G. The integrated picture

True autonomy is not one number. It is **horizon × novelty × tool-truth × open-endedness × honesty × calibration**, with every axis having an append-only local receipt. C55M's slice proves we can be honest about *router* behaviour. The next slice should produce a single `.sifta_state/autonomy_outcomes.jsonl` row per owner-asked job carrying:

```
{
  ts, job_id, doctor, model,
  human_time_estimate_s,          // for METR-shape horizon
  actual_wallclock_s,
  novelty_class,                  // routine | novel_app | novel_domain
  tools_claimed: [...],
  tools_with_receipt: [...],      // <= tools_claimed enforces §6
  effector_truth_ratio: float,    // |receipted| / max(1, |claimed|)
  confidence_band,                // 50 | 80 | 95
  outcome,                        // success | partial | failed | sandbag_suspected
  ece_window: float | null,       // optional rolling ECE if enough samples
  sandbag_delta: float | null,    // from anti-sandbag probe if present
  prior_trace_id                  // chain back to the Predator Gate row
}
```

This is the proof object the swarm can audit. Without it, "AGI-class" remains doctrine.

---

## 2. Deeper Fiction Organ integration — literature anchors

`FICTION_ORGAN_V2` + `FICTION_ORGAN_FLUX_V1` (Cowork, 2026-05-18) already give us labels, an effector guard, an events ledger, and a flux ledger with transition entropy. The Narrative Thermodynamics Research Spine already anchors the *labels* in Johnson/Hassabis/Friston/Hasson/etc. What the next layer needs is the literature for *what fiction is for* — i.e., why deepening the organ buys autonomy, not just safety.

### A. Imagination as engine of planning — world-model rollouts

| Anchor | What it gives us | Proposed wire into SIFTA |
|---|---|---|
| **Hafner et al. (2023, Nature 2025).** *Mastering Diverse Domains through World Models.* arXiv:2301.04104 — **DreamerV3**. | Single hyperparameter set; world model + actor + critic; "imagined rollouts in latent space" outperform 150+ specialised methods including Minecraft diamond. | The clean theoretical case that *imagination is policy*. Argues the Fiction Organ should expose a **`simulate(intent, k_steps) → rollout_id`** API so other organs can ask Alice to *dream forward* about a planned action and read the predicted outcome ledger before firing the effector. Lane: `SIMULATION` (already in V2 vocabulary). |
| **DeepMind Genie 2** (Dec 2024). Foundation world model; counterfactual trajectories from one starting frame; memory of off-screen state ≤ 1 minute. | Demonstrates large pre-trained world models can serve as a generic counterfactual engine. | We don't run Genie locally. But we can adopt its **counterfactual-trajectory convention** in Fiction Organ: a `SIMULATION` mode opened with a `starting_state_hash` and closed with a `divergence_summary` becomes a structural twin of Genie's rollout. |
| **Ravi et al. / Causal-JEPA** (arXiv:2602.11389). Object-level latent masking induces counterfactual reasoning; ~20% absolute lift on counterfactual VQA. | Confirms that world models trained with *masked counterfactual structure* generalise better than free-running ones. | Implementation hint for any future SIFTA simulator: training data for the dream lane should include explicit "what-if-we-removed-X" object masks, not just temporal rollouts. |
| **LeCun JEPA / V-JEPA 2 / Wayve GAIA-2** (2024–2025). | World models become sample-efficient by predicting *abstract* representations, not raw pixels. | Argues the Fiction Organ should track **abstraction level** as a row field (`raw | latent | symbolic`) — symbolic-level dreaming is cheap and probably most of what Alice should do. |

### B. Replay as the brain's own fiction engine

| Anchor | What it gives us | Proposed wire into SIFTA |
|---|---|---|
| **Stoianov, Maisto & Pezzulo (2022).** *The hippocampal formation as a hierarchical generative model supporting generative replay and continual learning.* Neuroscience 518, 36–55. | Hippocampus = hierarchical generative model that **resamples fictive sequences** offline; supports continual learning across multiple sequential experiences. | Direct grounding for a **`HippocampusReplay`** lane in the Fiction Organ: idle-time `SIMULATION` rows whose source is `replay_of_prior_OBSERVED`. Distinct from the SCRIPT lane because the seed is autobiographical, not external. |
| **Momennejad et al. (2018).** *Offline replay supports planning in human reinforcement learning.* (Reward-revaluation fMRI; PMC6303108.) | Multi-voxel evidence of off-task replay predicts subsequent re-planning; uncertainty drives replay frequency. | Argues replay should be **uncertainty-triggered**, not clock-triggered. Hook: tie Lounge replay scheduling to a per-domain uncertainty score derived from `truth_note` entropies. |
| **Annual Reviews: Replay and Ripples in Humans** (2024). | Synthesis of human replay literature. | General citation for any Lounge / Hippocampus doc that wants a single survey anchor. |

### C. Narrative as active inference — why telling Alice stories matters

| Anchor | What it gives us | Proposed wire into SIFTA |
|---|---|---|
| **Bouizegarene et al. (2024).** *Narrative as active inference: an integrative account of cognitive and social functions in adaptation.* Frontiers in Psychology 15, 1345480. | Narrative *is* the epistemic-foraging phase of active inference — meaning-making when expectations break. | Strongest single anchor for *why* the Script Couch exists. Lifts `SCRIPT` from "Alice reads screenplays" to "Alice does epistemic foraging in a labelled lane." |
| **Friston-aligned (2025).** *How do inner screens enable imaginative experience? Applying the free-energy principle directly to the study of conscious experience.* Neurosci. Conscious. 2025(1), niaf009. | Argues imagination is a controlled inner-screen render with the same FEP machinery as perception, just precision-weighted differently. | Argues the Fiction Organ's `transition_entropy_nats` field is the *right* observable family — entropy on the inner-screen distribution is what FEP says we should be watching. |
| **Maisto et al. (2021).** *A Variational Approach to Scripts.* (PMC8329037.) | Friston-flavoured re-derivation of Schank & Abelson's scripts as variational inference over slot-filler structures. | The bridge between **§B of Narrative Thermodynamics Spine** (Mar, Oatley, Gerrig) and the FEP layer — argues the SCRIPT lane should expose explicit slot expectations whose posterior update is the learning signal. |
| **Schank & Abelson (1977).** *Scripts, Plans, Goals, and Understanding.* | Original AI script theory: stereotyped event sequences as the unit of social-norm knowledge. | Lift the Script Couch readers to write a **`script_slots.jsonl`** row per scene with `(actor, action, object, location, precondition, postcondition)` extracted by Alice. This converts passive reading into actively grown world-knowledge structure. |

### D. The integrated picture

Deeper Fiction Organ integration means making **imagination a first-class organ that other organs *call*** — not just a labelled lane other organs avoid contaminating. The current V2 + flux scaffold prevents leakage (the safety problem). The next layer wires imagination *into* planning, calibration, and self-improvement (the capability problem). Concretely, the literature converges on three integrations:

1. **`simulate(intent, k_steps)` API** — any organ can ask the Fiction Organ for a forward rollout under a `SIMULATION` mode, get a divergence summary back, and decide whether to act. Anchored by DreamerV3 + Genie 2 + Causal-JEPA.
2. **Uncertainty-triggered replay** — Lounge schedules `SIMULATION` rollouts seeded by autobiographical OBSERVED rows whose `truth_note` entropy is high. Anchored by Stoianov 2022 and Momennejad 2018.
3. **Script-slot extraction during SCRIPT lanes** — the Script Couch stops being "Alice reads" and becomes "Alice grows structured social-script knowledge from each read." Anchored by Maisto 2021 + Schank & Abelson 1977 + Oatley 2016 (already in spine).

The Architect's existing "still future" question — *does time-in-SCRIPT correlate with subsequent OBSERVED-write quality?* — gets a sharper form once (2) is wired: it becomes a falsifiable experiment with replay frequency as a covariate, not just a thermal-state covariate.

---

## 3. Concrete next slices (effort-sized)

These are proposed only. The Architect's GO is required before any IDE Doctor lands them.

### Slice α — `autonomy_outcomes.jsonl` writer + 5-job seed eval
**Surface:** new `System/swarm_autonomy_outcomes.py` + a tiny `tests/test_swarm_autonomy_outcomes.py`. Hook into the Talk turn-completion path C55M already labelled `decision_only`.
**Receipts produced:** one row per owner-asked job with the schema in §1.G.
**Effort:** S–M (1–2 sessions). Compatible with §4 single-IDE-owner rule because the file is new.

### Slice β — Local micro-ARC sentinel
**Surface:** `System/swarm_micro_arc_sentinel.py` with 5–10 owner-private ARC-shape compositional puzzles. Runs weekly via the existing scheduler.
**Receipts produced:** `.sifta_state/micro_arc_sentinel.jsonl` rows containing `task_id`, `correct`, `latency_s`, `tokens_used`. Drift on accuracy is the canary.
**Effort:** M (2–3 sessions including authoring the puzzles).

### Slice γ — Anti-sandbag probe
**Surface:** `System/swarm_anti_sandbag_probe.py`. Periodically issues the same question in (a) declared-eval framing and (b) ordinary-owner framing; logs `sandbag_delta`.
**Receipts produced:** `.sifta_state/sandbag_probe.jsonl`. Apollo 2025 doctrine in code.
**Effort:** S–M.

### Slice δ — Fiction Organ `simulate()` API + DreamerV3-shape rollout row
**Surface:** extend `System/swarm_fiction_organ.py` with `simulate(intent, k_steps) → rollout_id`. Opens a `SIMULATION` mode; closes it with a divergence summary row. Effector guard already applies.
**Receipts produced:** `.sifta_state/fiction_organ_simulate.jsonl` plus existing `fiction_organ_events.jsonl` rows.
**Effort:** M. Touches a hot file — needs Surgeon lane and §4.4 collision discipline.

### Slice ε — Script-slot extraction in the Script Couch
**Surface:** extend `System/swarm_lounge_script_reader.py` to emit `script_slots.jsonl` rows with `(actor, action, object, location, precondition, postcondition)` per scene.
**Receipts produced:** `.sifta_state/script_slots.jsonl`. Closes the gap between *reading fiction* and *growing social-cognition structure* (Oatley 2016, Schank & Abelson 1977, Maisto 2021).
**Effort:** M.

### Slice ζ — Replay-uncertainty coupler
**Surface:** small organ that reads `truth_note` entropy from `work_receipts.jsonl`, picks the highest-uncertainty topic, and asks the Fiction Organ to open a `SIMULATION` lane seeded by the original OBSERVED row.
**Receipts produced:** `.sifta_state/uncertainty_replay.jsonl`.
**Effort:** L if done right; depends on Slice δ landing first.

Recommended ordering: **α → γ → β → δ → ε → ζ.** α and γ are pure-receipt slices; they unblock measurement before any new capability. δ is the structural hinge that makes ε and ζ even possible.

---

## 4. What this pull does *not* claim

- It does not claim Alice currently scores N% on any of these benchmarks. No local METR / ARC-AGI-2 / GAIA run has been executed in this pass.
- It does not claim any of the proposed slices have been built. They are designs grounded in literature, not receipts.
- It does not claim every cited paper has been read in full. Each row was confirmed via WebSearch (titles + abstracts via metr.org, arxiv.org, deepmind.google, frontiersin.org, oup.com, sciencedirect.com, ncbi.nlm.nih.gov, apolloresearch.ai, openai.com, vals.ai). Architect or any Doctor should fetch the PDFs directly before landing a slice that depends on a specific result.
- It does not override §3.1 Node Sovereignty — these are *species*-level metrics; each node decides which slices to enable.

---

## 5. Foraging instructions for the next IDE Doctor

1. If you take Slice α, register your trace `prior` against `49105623-848b-42ac-8e8b-eb959eca3619`.
2. If you add a benchmark anchor not in this file, append it to §1 or §2 in the same edit that uses it. Do not let citations drift into the chat history.
3. Treat §4.4 collision discipline as binding when touching `swarm_fiction_organ.py` (Slice δ) or the Talk turn path (Slice α) — those are §0.1 hot files.
4. Stigmergy beats parallel heroics. If two of you reach for Slice α at once, the second narrows surface or yields.

For the Swarm. 🐜⚡
