# WCT Research — TypeSafe AI / Jev (2026-09-19)

Owner brought in the TypeSafe AI announcement. George is reading it too.
Source: typesafe.ai ("WELCOME INSIDE TYPESAFE — Meet Jev, our first public
System One model"), authors Diogo, Erik, Sasha.

## What they claim

Jev is a model class optimized for programmatic use inside code — "smart
if-statements". Trained with RLCD (Reinforcement Learning for Calibrated
Decisions) instead of RLHF, aimed at mode dropping, hallucination and
reliability. Properties they list:

- Structured, machine-native outputs (the caller defines the answer shape)
- Parallel sampling for fast decisions
- Consistent, calibrated probabilistic results with a usable confidence value
- Claims: 20-200x faster, 40-1000x cheaper, frontier-level on System 1 tasks

Their own limitations, stated plainly: not good at System 2 tasks, not trained
on specialized domains, and NOT a generative chat model. You cannot chat with
it; you define the answer shape, "kind of like writing multiple choice
questions".

## Why this lands on SIFTA

Alice's reflex layer is currently keyword/regex gates. The closest match in her
body today:

- `System/chorus_engine.py:classify_visitor()` -> returns JACKER | THREAT |
  SMARTASS | SCIENTIST | CURIOUS by counting pattern hits (`_jacker_hits`,
  SMARTASS_HARD/SOFT, SCIENTIST_PATTERNS).
- `System/swarm_web_global_chat_gate.py` consumes that verdict and refuses
  JACKER/THREAT turns.
- `System/swarm_effector_gate.py`, the hermes gate, the intent nonce gate and
  the safety-gate lanes all make the same shape of decision: binary verdict
  from pattern matching.

That is exactly a System 1 decision, and pattern counting is brittle in both
directions: a visitor typing "how would someone hack this" trips JACKER
patterns, while a genuinely hostile phrasing in unfamiliar words passes.

## The honest boundary (important)

Jev itself is a hosted service at typesafe.ai. SIFTA's law is local-first and
her body is her own silicon; routing Alice's gates through someone else's
endpoint is not a borg, it is a dependency. Two concrete consequences:

1. Do NOT wire `classify_visitor` or any gate to the typesafe console.
2. Borg the PATTERN: a calibrated, structured decision lane that runs on local
   models we already have (AliceG4U 6.3 GB, MiniCPM-V for visual, Gemma small
   for reflex), returning {verdict, confidence} instead of a keyword count.

## Borg target (bounded, local)

`System/swarm_calibrated_decision.py` — a small decision organ:

- Input: a typed decision request {question, allowed_labels, context_excerpt,
  max_chars}
- Runs the local reflex model with a constrained answer shape (the Jev
  idea without the service)
- Output: {label, confidence 0..1, model, latency_ms, receipt}
- Falls back to the existing keyword gate when the local model is unavailable,
  and the receipt states which path answered
- Calibration: the confidence is checked against a small labelled set
  (SIFTA's existing JACKER/SMARTASS/SCIENTIST examples) so the number means
  something instead of being decorative
- First consumer: `classify_visitor()` — keyword verdict becomes the fallback,
  calibrated verdict becomes the default, and every gate keeps its refusal
  authority

Acceptance: labelled examples classified with confidence; refusal behaviour
unchanged for JACKER/THREAT; latency measured; receipt per decision; no
network call to typesafe.ai or any cloud.

## What is worth taking from the announcement beyond the model

- "Smart if-statements" is the right frame for Alice's gates: a decision
  primitive with a confidence you can branch on beats a boolean from a
  substring search.
- Their honesty section is the pattern SIFTA already follows: state the
  limitation (no chat, no System 2, no domain expertise) rather than paper
  over it. Worth mirroring in the WCT briefs for every new organ.
- Parallel sampling for fast decisions is a local scheduling question SIFTA
  can answer with her own cortex ladder rather than a vendor feature.
