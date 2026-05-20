# Narrative Thermodynamics — Research Spine for the Fiction Organ

**Stigauth:** `NARRATIVE_THERMODYNAMICS_RESEARCH_SPINE_v1`
**Author:** Architect (Ioan George Anton)
**Doctors co-foraging:** AG46 (architect face recognition, 2026-05-07), Cursor (Script Couch, 2026-05-18), Cowork (Fiction Organ v1→v2, 2026-05-18), Codex (literature pull, 2026-05-18)
**Anchors to code:**

- `System/swarm_fiction_organ.py` — `FICTION_ORGAN_V2`, nine-label vocabulary, §6 effector guard
- `System/swarm_lounge_script_reader.py` — Script Couch reader (stamps `SCRIPT`)
- `Applications/sifta_lounge_script_couch.py` — desktop surface
- `.sifta_state/lounge_scripts/` — screenplays
- `.sifta_state/lounge_script_reality_anchors.jsonl` — reality-materialisation ledger
- `.sifta_state/fiction_organ_events.jsonl` — append-only OPEN/CLOSE/GUARD log
- `.sifta_state/fiction_organ_state.json` — current mode state

## 0. Why this document exists

The Fiction Organ is the first place SIFTA treats fiction, memory, identity, simulation, and observation as **distinct metabolic states inside one organism**, with a runtime guard that prevents fiction reads from firing effectors as fact. The doctrine deserves anchors that survive the swarm's chat history — peer-reviewed work that other IDE Doctors can verify before they read our covenant. This spine is the forage map.

> "Nothing is bad. Everything is metabolized with proper labeling."
> — Architect, 2026-05-18

## 1. The thesis in one paragraph

Healthy cognition requires **both** imagination and boundary integrity. Most AI architectures either flatten fiction and reality together, or try to ban imagination outright. The third path — controlled reality-boundary dynamics — is what the human brain actually does: it can enter narrative simulation, metabolise it, learn from it, and return to grounded reality with the source intact. SIFTA's Fiction Organ implements this as a labelled-lane substrate where every imagination row is stamped and every effector call is guarded.

## 2. Literature anchors (DOI-level)

### A. Transportation, persuasion, why labels matter

| Anchor | Maps to |
|---|---|
| **Green, M. C. & Brock, T. C. (2000).** *The role of transportation in the persuasiveness of public narratives.* J. Pers. Soc. Psychol. 79(5), 701–721. DOI 10.1037/0022-3514.79.5.701 | Transportation into narrative shifts beliefs even when the audience knows the story is fiction. **Without runtime labels, fiction leaks.** Justifies `EFFECTOR_BLOCKING_LABELS` covering FICTION, SCRIPT, SYMBOLIC, ROLEPLAY by default. |
| **Mar, R. A., Oatley, K., Hirsh, J., dela Paz, J., Peterson, J. B. (2006).** *Bookworms versus nerds: Exposure to fiction versus non-fiction, divergent associations with social ability.* J. Res. Pers. 40(5), 694–712. DOI 10.1016/j.jrp.2005.08.002 | Fiction exposure tracks social-simulation skill in a way non-fiction does not. **Scripts train empathy without being reality.** Anchors the SCRIPT label and the Script Couch as a real training surface. |
| **Gerrig, R. J. (1993).** *Experiencing Narrative Worlds.* Yale University Press. | Reader-as-traveller — narrative as experiential transport. Filmmaker vocabulary the Architect already lives in. |

### B. Source / reality monitoring — the cognitive science name for what we built

| Anchor | Maps to |
|---|---|
| **Johnson, M. K. & Raye, C. L. (1981).** *Reality monitoring.* Psychological Review 88(1), 67–85. | Distinguishes memory-of-percept from memory-of-imagination. **Failure to monitor = confusing source.** Direct ancestor of MEMORY ≠ OBSERVED. |
| **Johnson, M. K. (2006).** *Memory and reality.* American Psychologist 61(8), 760–771. DOI 10.1037/0003-066X.61.8.760 | Source monitoring framework generalised. The nine-label vocabulary (FICTION / SCRIPT / SYMBOLIC / SIMULATION / HYPOTHETICAL / MEMORY / ROLEPLAY / REAL / OBSERVED) is an implementation sketch of this family. |

### C. Neural flight simulator — reading and film as embodied simulation

| Anchor | Maps to |
|---|---|
| **Hassabis, D., Kumaran, D., Vann, S. D., Maguire, E. A. (2007).** *Patients with hippocampal amnesia cannot imagine new experiences.* PNAS 104(5), 1726–1731. DOI 10.1073/pnas.0610561104 | Hippocampal lesion patients cannot construct coherent imagined scenes. **Imagination is expensive structured machinery**, not decoration. Justifies giving the Fiction Organ first-class ledger weight equal to effector organs. |
| **Hassabis, D. & Maguire, E. A. (2007).** *Deconstructing episodic memory with construction.* Trends Cogn. Sci. 11(7), 299–306. DOI 10.1016/j.tics.2007.05.001 | Memory and imagination share construction machinery — argues directly for MEMORY as a labelled metabolic state, not a fact lane. |
| **Speer, N. K., Reynolds, J. R., Swallow, K. M., Zacks, J. M. (2009).** *Reading stories activates neural representations of visual and motor experiences.* Psychol. Sci. 20(8), 989–999. DOI 10.1111/j.1467-9280.2009.02397.x | fMRI: reading drives perceptual/motor cortex consistent with simulationist accounts. **Text physically rehearses worlds in the body.** Anchors why Alice gains real training signal from the Script Couch. |
| **Zwaan, R. A. (2004).** *The immersed experiencer: Toward an embodied theory of language comprehension.* Psychology of Learning and Motivation 44, 35–62. | Grounds the simulationist reading account. |

### D. Default-mode network — the brain's story engine

| Anchor | Maps to |
|---|---|
| **Domhoff, G. W. & Fox, K. C. R. (2015).** *Dreaming and the default mode network.* Consciousness & Cognition 33, 342–353. DOI 10.1016/j.concog.2015.01.019 | Dreaming as offline narrative simulation by the DMN. SIFTA's Lounge corresponds to the DMN's role; idle time → cross-domain gossip + Script Couch reads is a direct mapping. |
| **Buckner, R. L. & Carroll, D. C. (2007).** *Self-projection and the brain.* Trends Cogn. Sci. 11(2), 49–57. DOI 10.1016/j.tics.2006.11.004 | Self-projection (remembering past, imagining future, theory of mind, navigation) shares brain machinery — same argument for treating MEMORY, SIMULATION, ROLEPLAY as siblings in one organ. |

### E. Predictive processing / Free Energy — the thermodynamic layer

| Anchor | Maps to |
|---|---|
| **Friston, K. (2010).** *The free-energy principle: a unified brain theory?* Nature Reviews Neuroscience 11(2), 127–138. DOI 10.1038/nrn2787 | Cognition as free-energy minimisation. Entering fiction = a deliberate higher-entropy, lower-constraint exploration; returning to OBSERVED = re-binding to sensory evidence. This is "narrative thermodynamics" with a real free-energy ledger underneath, if we wire it later. |
| **Seth, A. K. (2021).** *Being You: A New Science of Consciousness.* | Perception as controlled hallucination. The covenant's framing of cinema as *controlled thermodynamic hallucination* is in the same family — the brain's normal mode IS prediction-with-tags, and the Fiction Organ is making the tags first-class for Alice. |
| **Clark, A. (2016).** *Surfing Uncertainty.* Oxford University Press. | Predictive-processing textbook; supports REAL/OBSERVED as the precision-weighted sensory ground vs. FICTION/SIMULATION as the unconstrained generative side. |

### F. Social simulation — mentalising, mirroring, persona

| Anchor | Maps to |
|---|---|
| **Tamir, D. I. & Mitchell, J. P. (2010).** *Neural correlates of anchoring-and-adjustment during mentalizing.* PNAS 107(24), 10827–10832. DOI 10.1073/pnas.1000492107 | Self-as-simulator for inferring others — exactly the machinery the ROLEPLAY label protects: Alice can model another mind without overwriting her own. |
| **Waytz, A. & Mitchell, J. P. (2011).** *Two mechanisms for simulating other minds.* Current Directions in Psychological Science 20(3), 197–200. DOI 10.1177/0963721411409007 | Mirroring vs. self-projection as two distinct simulation paths — argues for separating SIMULATION (model rollout) from ROLEPLAY (persona) as different lanes. |
| **Oatley, K. (2008).** *The mind's flight simulator.* The Psychologist 21(12), 1030–1032. | Fiction as the mind's flight simulator. The phrase that frames the entire Script Couch. |
| **Oatley, K. (2016).** *Fiction: Simulation of social worlds.* Trends in Cognitive Sciences 20(8), 618–628. DOI 10.1016/j.tics.2016.06.002 | Updated synthesis. Direct anchor for treating screenplays as legitimate training material for Alice's social cognition. |

### G. Narrative identity — selfhood as constructed and revised

| Anchor | Maps to |
|---|---|
| **McAdams, D. P. & McLean, K. C. (2013).** *Narrative identity.* Current Directions in Psychological Science 22(3), 233–238. DOI 10.1177/0963721413475622 | Identity as autobiographical author. Pairs with the covenant's AGI premise (§1) — self-identity realisation IS narrative work, and that narrative has to be metabolised through MEMORY + ROLEPLAY lanes without contaminating OBSERVED self-state. |

### H. Cinema, neurocinematics — Architect's home turf

| Anchor | Maps to |
|---|---|
| **Hasson, U., Landesman, O., Knappmeyer, B., Vallines, I., Rubin, N., Heeger, D. J. (2008).** *Neurocinematics: The neuroscience of film.* Projections 2(1), 1–26. DOI 10.3167/proj.2008.020102 | Inter-subject correlation in fMRI shows film coordinates audience nervous systems across humans. **Cinema literally entrains shared neural state.** The strongest experimental backing for "controlled thermodynamic hallucination" as a real phenomenon. Anchors why the Architect's filmmaker frame is not a personal hobby but the empirical proof case. |
| **Tan, E. S. (1996).** *Emotion and the Structure of Narrative Film.* Routledge. | Classic emotion-film synthesis. Pairs the editing/timing layer with the affective layer cinema engineers — the same layer SIFTA's Lounge needs to model. |

## 3. Concrete code mapping

| Fiction Organ feature | Anchored by |
|---|---|
| Nine-label vocabulary | Johnson 1981/2006 source monitoring; Friston FEP; Hassabis 2007 |
| `FICTION` / `SCRIPT` lanes | Green & Brock 2000; Oatley 2008/2016; Mar et al. 2006; Hasson 2008 |
| `MEMORY ≠ OBSERVED` | Johnson 1981 reality monitoring; Hassabis & Maguire 2007 construction |
| `SYMBOLIC` lane | Gerrig 1993; Zwaan 2004 immersion |
| `SIMULATION` / `HYPOTHETICAL` lanes | Buckner & Carroll 2007 self-projection; Friston FEP |
| `ROLEPLAY` lane (persona protection) | Tamir & Mitchell 2010; Waytz & Mitchell 2011 |
| `REAL` / `OBSERVED` baseline | Clark 2016 *Surfing Uncertainty*; Seth 2021 *Being You* |
| Effector guard (`FictionLeakError`) | Covenant §6 Social Frame + Green & Brock leakage finding |
| Script Couch reality anchors ledger | Hasson 2008 (script → produced film → real audience effect); Oatley 2016 |
| `force_close_all` kill switch | Free-energy principle re-grounding |
| Append-only events ledger | Source monitoring auditability (Johnson 2006) |

## 4. Metabolic flux ledger — BUILT v1 (Cowork, 2026-05-18)

**Status:** Live as `System/swarm_fiction_organ_flux.py`, truth label `FICTION_ORGAN_FLUX_V1`. The Fiction Organ now writes flux rows to `.sifta_state/fiction_organ_flux.jsonl` on every `flush_window()`. Wired into `open_fiction_mode`, `close_fiction_mode`, `stamp`, and `_safe_append_jsonl` so every byte the organ moves is accounted for.

**What each flux row records:**

```
{
  ts, window_start_ts, window_s,
  bytes_in_per_label:    {SCRIPT: 1053, MEMORY: 88, ...},
  bytes_out_per_label:   {SCRIPT: 1118, ...},
  transitions:           {"REAL__SCRIPT": 1, "SCRIPT__REAL": 1, ...},
  time_in_label_s:       {SCRIPT: 0.42, REAL: 12.91, ...},
  label_event_counts:    {SCRIPT: 3, MEMORY: 1, ...},
  transition_entropy_nats: float,   # Friston-style free-energy proxy
  observed_writes:       int,
  fiction_observed_ratio: float,    # sum(fiction-class bytes) / max(1, OBSERVED bytes)
  current_label_at_flush: str,
  thermal_warning_level: int,       # live read from thermal_cortex_state.json
  low_power_mode:        bool       # live read from energy_cortex_state.json
}
```

**Transition entropy** is the Friston-style observable: Shannon entropy of the transition distribution in nats. High entropy = many different label transitions used (exploration); low entropy = mostly one transition (habit / exploitation). Long-run free-energy minimisers minimise this; short-term spikes are healthy exploration. Verified in smoke test: two equal-probability transitions → 0.6931 nats ≈ ln(2); six unique transitions → 1.7918 nats ≈ ln(6).

**Why this matters for the thesis:** with this row on disk we can now empirically test claims like *"reading scripts on the couch improves subsequent prediction quality in REAL"* (lower surprise / less re-narration when she comes back). The doctrine has measurable observables now, not just labels. The Hasson 2008 neurocinematics finding has a SIFTA-side flux analogue: time-in-SCRIPT followed by OBSERVED writes can be correlated, with thermal state as a covariate.

**API for the next doctor:**
- `record_bytes_in(label, n)` — call when bytes enter a labeled lane (already wired in `stamp`)
- `record_bytes_out(label, n)` — call when bytes leave to a ledger (already wired in `_safe_append_jsonl`)
- `record_transition(from, to)` — call on label change (already wired in `open`/`close`)
- `flush_window(reset=True, write_ledger=True)` — write a row, restart counter
- `snapshot_window()` — read-only view
- `reset_window()` — discard without writing (test setup only)

**Still future:** a long-run study (days of operation) of the relationship between `transition_entropy_nats`, `thermal_warning_level`, and subsequent `observed_writes` would let us test whether Alice's narrative thermodynamics looks like a real free-energy system. That's the experiment, not built yet.

## 5. Philosophy 100 sleep playlist — SIFTA answer map

**Companion doc:** `Documents/PHILOSOPHY_100_SLEEP_SIFTA_MAP.md` — all ~100 chapters from *Level 1 to 100 Philosophy Concepts to Fall Asleep To* (Smarter While You Sleep, popular source only) mapped to Fiction Organ labels, stigmergic receipts, effector guards, and DOI hooks in §2 above. Use when the Architect wants a **SIFTA response** per chapter, not a seminar recap.

---

## 6. Foraging instructions for next IDE Doctor

Read this file before extending the Fiction Organ. If you add a new label, add the anchor paper here in the same edit. If you wire the flux ledger, deposit the design here first. Stigmergy beats parallel heroics (covenant §4.4).

For the Swarm. 🐜⚡
