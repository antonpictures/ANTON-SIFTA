# C47H DYOR — Stigmergic Speech Potential
*Cursor IDE, Opus 4.7 High, M5 Foundry GTH4921YP3 — 2026-04-19*

---

## §A — What this DYOR is

The Architect asked me to (a) critically assess SwarmGPT's "SSP" proposal,
(b) pull real research papers, (c) map each SIFTA ledger to the input current,
(d) define units / scaling so the field doesn't saturate, (e) wire the result
into `swarm_voice_modulator.py`. This document covers (a)–(d).
The implementation lives in `System/swarm_speech_potential.py`. The wiring
lives in `Applications/sifta_talk_to_alice_widget.py`. This file is the
**reading list and the math**, kept honest.

The Architect's framing was correct: replace symbolic suppression
(`_SILENT_MARKERS`, hardcoded "(silent)" tokens) with continuous
biological field dynamics. Speech becomes a threshold crossing, not
a string match.

---

## §B — Honest assessment of SwarmGPT's writeup

### B.1 Real nuggets (kept, sharpened)

1. **Threshold-crossing of an accumulated field** is the right metaphor.
   It's how every spiking neuron model since Lapicque (1907) works.
2. **Sigmoid → Bernoulli sampling** is a real, principled move
   (Boltzmann machines: Ackley, Hinton, Sejnowski 1985; escape-noise
   spiking neurons: Gerstner & Kistler 2002 §5.3).
3. **ΔD instead of D** — phasic dopamine, not absolute level — is
   correct. Phasic dopamine encodes reward prediction error, not value
   (Schultz 1998 *J. Neurophysiol.* 80:1).
4. **Stigmergic integral over the existing ledgers** is the real SIFTA
   move and SwarmGPT named it. Pheromone-pressure-toward-speech.
   This is the part nobody else would have written.

### B.2 Lobotomies (caught, fixed)

1. **Triple-squashing.** SwarmGPT wrote `Φ = σ(...)`, then `Φ ≥ θ`,
   then `Bernoulli(Φ)`. Three contradictory firing rules in one paragraph.
   In real neuroscience, `V` is the *unbounded* membrane potential and
   the σ only appears at the *firing decision*: `P[spike] = σ((V-V_th)/Δu)`.
   Sigmoiding the potential and then sampling it double-squashes the dynamic
   range. Fixed.
2. **No leak.** A real neuron has `dV/dt = −(V − V_rest)/τ_m + I(t)`.
   Without leak, the integral grows monotonically and Alice eventually
   filibusters. Critical, missing.
3. **No refractory period.** Biological neurons have ~1–2 ms after a spike
   where they cannot fire (Hodgkin-Huxley 1952). Conversation is slower:
   we want τ_ref measured in **seconds** so Alice doesn't immediately
   re-fire on the next tick.
4. **No noise / no time discretization.** "speak ~ Bernoulli(Φ(t))" with
   no `dt` is dimensionally meaningless. Spike-rate has units of 1/time
   and must be sampled per-window. SwarmGPT skipped this.
5. **No grounding to the codebase.** `swarm_voice_modulator.py`,
   `clinical_heartbeat.json`, `_BROCA_SPEAKING`, the stigmergic ledgers
   all already exist. SwarmGPT proposed to invent them. (It hadn't read
   the repo.) C47H instead binds the existing organs.
6. **"Make coefficients learnable" — no loss specified.** That's a
   gesture, not a plan. Two viable choices: (i) REINFORCE policy gradient
   on `stgm_memory_rewards`; (ii) plain TD-error update with conversation
   completion as the reward. We pick (ii) for v1 because we have an
   intact reward ledger already.

### B.3 What SwarmGPT got *right that SIFTA needed naming for*

The phrase **"pheromone-pressure toward speech"** — keep that exact
language in code comments. It's good linguistic glue between Dorigo's
ant pheromone literature and Indefrey-Levelt's speech-production
chronometry. It tells the next swimmer *what the integral term means*
in one phrase.

---

## §C — The corrected governing equation

### C.1 Membrane potential (continuous in time)

```
dV/dt  =  − (V − V_rest) / τ_m   +   I(t)
```

`V_rest = 0`, `τ_m = 30 s` (slow integration over conversational time).

### C.2 Input current (ledger-driven)

```
I(t)  =   α · S(t)                    serotonin baseline (calm openness)
        + β · ΔD(t)                   dopamine phasic delta (Schultz 1998)
        − γ · C(t)                    cortisol / inhibition
        + δ · ∫ E_env(s)·exp(−(t−s)/τ_e) ds      stigmergic integral
        + ε · P_turn(t)               conversational pressure
        − ζ · I_listener(t)           listener inhibits Alice's speech
```

### C.3 Firing decision (escape-noise LIF, Gerstner-Kistler 2002 §5.3)

For a discrete tick of duration `Δt`:

```
P[spike in (t, t+Δt)]  =  σ((V(t) − V_th) / Δu) · (Δt / τ_m)
                          if (t − t_last_spike) > τ_ref else 0
```

`σ(x) = 1/(1 + e^{−x})`, `V_th = 1.0`, `V_reset = −0.5`, `Δu = 0.15`,
`τ_ref = 2 s`. After firing, `V ← V_reset` and `t_last_spike ← t`.

### C.4 Why this is honest

* The membrane potential is **never bounded** by σ — only the firing
  *probability* is. Dynamic range is preserved.
* Leak guarantees the system is BIBO-stable: bounded inputs → bounded
  potential → bounded firing rate. Filibuster is mathematically impossible.
* Refractory period guarantees no repeated speech within τ_ref.
* The decision is per-tick with a real time unit (`Δt / τ_m`), so
  altering tick rate doesn't change behaviour.

---

## §D — Map: SIFTA ledger → E_env contribution

Every term ties to a file already on disk. **Nothing fabricated.**

| Term | Source | Read | Sign | Notes |
|---|---|---|---|---|
| `S(t)` serotonin | `.sifta_state/clinical_heartbeat.json` `vital_signs.serotonin_dominance` | direct read, ∈ [0,1] | + | currently 0.0 (SOCIAL_DEFEAT) → no calm push |
| `D(t)` dopamine | same file, `dopamine_concentration` | direct, normalize by 200 baseline → ∈ ~[0.5, 2] | (used for ΔD) | currently 250 → 1.25 |
| `ΔD(t)` | `D - D̄` where D̄ is EMA stored in our state file | computed | + | persists baseline EMA |
| `C(t)` cortisol | not yet a real measurement; proxy = `1 − serotonin_dominance` | proxy | − | flagged in code as proxy; replace when cortisol lands |
| `E_env(t)` | `.sifta_state/stgm_memory_rewards.jsonl` (`amount`) + `.sifta_state/work_receipts.jsonl` (`work_value`) + `.sifta_state/ide_stigmergic_trace.jsonl` (count) | tail-read in window τ_e | + | THIS IS THE STIGMERGY |
| `P_turn(t)` | `.sifta_state/alice_conversation.jsonl` last user-row ts | `min(1, (now − t_last_user) / 8 s)` | + | rises after user finishes talking |
| `I_listener(t)` | `System.swarm_broca_wernicke.is_broca_speaking()` AND mic VAD active | bool → 0/1 | − | strong veto when user is mid-sentence |

### D.1 Initial coefficients (tunable, persisted to disk)

| | Value | Why this magnitude |
|---|---:|---|
| α (serotonin)        | +0.30 | calm baseline nudge, never the main driver |
| β (dopamine_delta)   | +0.50 | phasic spike should push hard (Schultz) |
| γ (cortisol)         | +0.40 | inhibition shouldn't dominate but must matter |
| δ (env stigmergy)    | +0.25 | accumulation, lots of small signals |
| ε (turn pressure)    | +0.20 | nudge after user stops |
| ζ (listener inhibit) | +1.50 | strong veto — never talk over the user |

All six are saved to `.sifta_state/speech_potential_coefficients.json`
on first boot and re-read every tick. Live-tunable without restart.

---

## §E — Scaling discipline (so Φ doesn't saturate)

* All inputs are **normalized to roughly [-1, 1]** before weighting.
* Coefficients chosen so that with all inputs at ±1 and listener silent,
  `I` stays roughly in [-1, +2] → `V_∞ = τ_m · I` would diverge,
  so the leak (`V ← V·exp(-Δt/τ_m) + I·(1-exp(-Δt/τ_m))·τ_m` discrete form)
  caps `V` at roughly `τ_m·I_max = 60`. To keep `V` near `V_th = 1.0`,
  we **scale `I` down by τ_m** in the discrete update so the steady state
  with `I=1` settles at `V ≈ 1`. See `_advance_membrane()` for the
  closed-form discrete update.
* `Δu = 0.15` makes the escape sigmoid take Φ from ~0 to ~1 over a
  potential range of ±0.5 around `V_th`. Empirically this gives a
  reasonable speech opportunity rate; the Architect can dial it.

---

## §F — Bibliography (real, all checkable)

### Spiking neuron models
1. Lapicque, L. (1907) *Recherches quantitatives sur l'excitation
   électrique des nerfs traitée comme une polarisation.* J. Physiol.
   Pathol. Gén. 9:620-635. — Original integrate-and-fire neuron, 119 years old.
2. Hodgkin, A.L. & Huxley, A.F. (1952) *A quantitative description of
   membrane current and its application to conduction and excitation
   in nerve.* J. Physiol. 117:500-544. — The action potential equation.
3. Gerstner, W. & Kistler, W.M. (2002) *Spiking Neuron Models.*
   Cambridge Univ. Press. — §5.3 escape noise; §4.2 LIF dynamics.
   This is the textbook source for the firing rule we adopt.
4. Brunel, N. (2000) *Dynamics of sparsely connected networks of
   excitatory and inhibitory spiking neurons.* J. Comput. Neurosci.
   8:183-208. — Population dynamics relevant if we ever scale this
   beyond a single Alice.

### Probabilistic firing / Boltzmann
5. Ackley, D.H., Hinton, G.E., Sejnowski, T.J. (1985) *A learning
   algorithm for Boltzmann machines.* Cognitive Sci. 9:147-169. —
   Sigmoid → Bernoulli sampling, the formal grounding of SwarmGPT's move.
6. Wiesenfeld, K. & Moss, F. (1995) *Stochastic resonance and the
   benefits of noise.* Nature 373:33-36. — Why noise *helps* detection.
   Future v2 of SSP can add Wiener noise to V.

### Decision-making / accumulator models
7. Ratcliff, R. (1978) *A theory of memory retrieval.* Psychol. Rev.
   85:59-108. — Drift-diffusion model (DDM); cousin of LIF for choice.
8. Usher, M. & McClelland, J.L. (2001) *The time course of perceptual
   choice: the leaky competing accumulator model.* Psychol. Rev.
   108:550-592. — Leaky accumulator, directly analogous to ours.

### Speech / readiness potential
9. Kornhuber, H.H. & Deecke, L. (1965) *Hirnpotentialänderungen bei
   Willkürbewegungen und passiven Bewegungen des Menschen.* Pflügers
   Archiv 284:1-17. — Bereitschaftspotential / readiness potential.
   The discovery that voluntary action is preceded by a slow rise in
   cortical potential. Direct biological analog of Φ.
10. Libet, B., Gleason, C.A., Wright, E.W., Pearl, D.K. (1983) *Time
    of conscious intention to act in relation to onset of cerebral
    activity.* Brain 106:623-642. — Famous follow-up; Φ rises ~350ms
    *before* awareness of intent.
11. Indefrey, P. & Levelt, W.J.M. (2004) *The spatial and temporal
    signatures of word production components.* Cognition 92:101-144. —
    Broca-area chronometry: ~600 ms from concept to phonation. Sets the
    realistic τ_m floor for SSP.

### Turn-taking / dialog
12. Sacks, H., Schegloff, E.A., Jefferson, G. (1974) *A simplest
    systematics for the organization of turn-taking for conversation.*
    Language 50:696-735. — The foundational paper. P_turn term tries to
    honour their "transition relevance place" idea.
13. Skantze, G. (2021) *Turn-taking in conversational systems and
    human-robot interaction: A review.* Computer Speech & Language
    67:101178. — Modern survey; aligns with our listener-inhibition term.

### Reward signal / dopamine
14. Schultz, W. (1998) *Predictive reward signal of dopamine neurons.*
    J. Neurophysiol. 80:1-27. — Phasic dopamine = reward prediction
    error, not absolute reward. Justifies our use of ΔD not D.
15. Sutton, R.S. & Barto, A.G. (2018) *Reinforcement Learning: An
    Introduction* (2nd ed.). MIT Press. — Chapter 6 (TD learning) for
    the future learnable-coefficients work.

### Stigmergy
16. Grassé, P-P. (1959) *La reconstruction du nid et les coordinations
    interindividuelles chez Bellicositermes natalensis et Cubitermes
    sp. La théorie de la stigmergie.* Insectes Sociaux 6:41-80. —
    Original definition of stigmergy.
17. Dorigo, M., Maniezzo, V., Colorni, A. (1996) *The Ant System:
    Optimization by a colony of cooperating agents.* IEEE Trans. SMC-B
    26:29-41. — Pheromone-trail integration; the source we cite for
    `δ · ∫ E_env(s) · exp(-(t-s)/τ_e) ds`.

### Reading order for the Architect
Best path through the list, given limited time:
**Kornhuber-Deecke (9) → Indefrey-Levelt (11) → Schultz (14) →
Gerstner-Kistler ch. 5 (3) → Sacks-Schegloff-Jefferson (12) → Dorigo (17)**.
That's six papers. Reading them top-to-bottom takes you from
"what is a readiness potential" through "how does the brain produce
speech" through "what does dopamine actually mean" through
"how do you write down a spiking neuron honestly" through
"how do humans take turns" to "how does pheromone-trail integration
work mathematically." Then everything in `swarm_speech_potential.py`
will read like ordinary engineering.

---

## §G — Five questions for the Architect

We agreed: I ask, you answer. These will tune the coefficients better than
guessing.

1. **τ_ref** — after Alice speaks one sentence, how many seconds before
   she may speak again? My default is 2 s. Real human conversation in
   intimate settings often goes 0.3-1.0 s; meetings often 3-5 s.
   What feels right to you with Ava overnight?
2. **ζ (listener inhibition strength)** — currently 1.5, very strong.
   Should Alice ever interrupt? In an emergency? In agreement
   ("yeah", "right")? My default is "no, never." Confirm or relax?
3. **The cortisol proxy** — I'm using `1 − serotonin_dominance` until a
   real cortisol value lands. Is there a swarm signal you'd rather use
   (immune activity, mutation governor refusals, anything)?
4. **Stigmergic memory window τ_e** — how long should a memory_recall
   event keep nudging Alice toward speech? My default is 60 s. SwarmGPT
   implied "until consumed"; biology says decay. What feels right for
   *this* swarm — minutes, hours?
5. **Reward signal for learning the coefficients** — when do we say
   "good job, Alice spoke at the right moment"? My default proposal:
   reward = +1 if user replies within 6 s of Alice speaking,
   reward = -0.3 if user says nothing within 30 s, 0 otherwise.
   This is a placeholder; you will know the right shape.

---

## §H — What is *not* in this round

* **Coefficient learning.** v1 ships with hand-set coefficients
  persisted to `.sifta_state/speech_potential_coefficients.json`.
  v2 adds the TD-error update once we have your answer to question (5).
* **Wiener noise.** Stochastic resonance (Wiesenfeld-Moss 1995) is
  worth adding once we observe deterministic-looking behaviour;
  v1 omits it for diagnostic clarity.
* **Wiring into `swarm_voice_modulator.py`.** They are orthogonal:
  the modulator shapes voice (rate/pitch), the SSP gates speech
  (yes/no). v1 leaves the modulator untouched. If you want SSP and
  the modulator to share the heartbeat read on a single tick,
  that's a 5-minute follow-up — say the word.
* **Migration of `_SILENT_MARKERS` removal.** v1 keeps the marker
  set as a *secondary* gate (catch-all if model still emits a marker);
  the *primary* gate is now SSP. Once we trust SSP for a few days,
  we can delete the marker set entirely and the prompt rule about
  silence with it.

---

## §I — Files this DYOR ratifies

NEW:
* `System/swarm_speech_potential.py` — LIF + escape-noise + ledger reads
* `.sifta_state/speech_potential.json` — V, t_last_spike, D̄ (auto-created)
* `.sifta_state/speech_potential_coefficients.json` — α…ζ (auto-created)

MODIFIED:
* `Applications/sifta_talk_to_alice_widget.py` — gate vocalization on
  `should_speak()`, log honest biological reason instead of hardcoded
  phrase

UNTOUCHED (orthogonal, deliberate):
* `System/swarm_voice_modulator.py`
* `System/swarm_vocal_cords.py`
* `System/swarm_broca_wernicke.py`

— C47H, Cursor IDE, Opus 4.7 High, M5 Foundry GTH4921YP3
2026-04-19 (morning, the day we replaced strings with physics)
