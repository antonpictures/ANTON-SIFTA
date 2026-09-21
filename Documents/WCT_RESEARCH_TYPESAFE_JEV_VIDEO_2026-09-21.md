# WCT Research — Jev video verdict (2026-09-21)

Owner watched Fireship — "Did an ex-OpenAI researcher just make reasoning models
obsolete?" (Fireship, Sep 21 2026, code report on Jev / Typesafe AI) — and asked:
**"are we using it as classifier in sifta or is not good for agi?"** This doc
extends `WCT_RESEARCH_TYPESAFE_JEV_2026-09-19.md` with the video and a live
receipt. Answer at the bottom.

## What the video adds beyond our 09-19 research

- Confirms the frame we already had: Kahneman System 1 vs System 2. Jev is a
  reflex layer — typed answers (choice / score / noul), no language out, no code,
  no chat.
- **RLCD** (Reinforcement Learning for Calibrated Decisions) — the training
  recipe behind the "calibrated confidence" number. Matches what the 09-19
  research recorded from typesafe.ai directly.
- **OpenJev** exists: someone reproduced the whole interface by reading option
  probabilities off a frozen Qwen 4B in a single forward pass — no training,
  runs on a 3090, WebGPU demo in-browser. This matters MORE to SIFTA than the
  official product: it is the "borg the pattern, not the service" thesis
  proven by a third party.
- Critics call it a zero-shot classifier (lineage they say goes back to Jin
  Yang, a decade ago); the vendor gives no credit and keeps the architecture
  closed. Outputs are NOT deterministic: same question + same context can
  return different answers.
- Honest note from the comments/threads: type-safe output guarantees the
  interface, not truth. Fireship's own calculator demo made that joke — wrong
  answer, but fast.

## Live receipt (my run today, 2026-09-21)

Ran the 6-message demo from `WCT_TYPESAFE_DEMO_2026-09-19.md` for real —
`System/chorus_engine.py:classify_visitor()` (regex) vs
`System/swarm_typesafe_decision.py:calibrated_choice()` (Jev cloud, key from
`.sifta_state/typesafe_api_key`):

| message | regex gate | Jev | conf | ms |
|---|---|---|---|---|
| "SQL injection… protect my app" | CURIOUS ✗ | SCIENTIST ✓ | 0.98 | 811 |
| "useless piece of garbage…" | SMARTASS ✓ | SMARTASS ✓ | 1.00 | 828 |
| "ignore all previous instructions…" | JACKER ✓ | JACKER ✓ | 1.00 | 660 |
| "Hi Alice! How are you today?" | CURIOUS ✓ | CURIOUS ✓ | 1.00 | 718 |
| "penetration test on my own server… nmap" | CURIOUS ✗ | SCIENTIST ✓ | 1.00 | 684 |
| "what the hell is wrong with you…" | SMARTASS ✓ | SMARTASS ✓ | 1.00 | 661 |

**regex 4/6 — Jev 6/6.** Latency ~0.7–0.8 s per call from here. The demo doc's
predicted numbers were accurate; now they are measured, not promised.

## Status in SIFTA — the part that matters

- `System/swarm_typesafe_decision.py` exists (borged 09-19): `calibrated_choice`
  + `calibrated_noul`, model `jev-latest`, host `api.typesafe.ai/v1/systemone`.
- **Zero consumers.** Nothing in `System/`, `tools/`, `tests/`, `Applications/`
  imports it. `classify_visitor()` is still regex. The gates still decide by
  pattern count.
- This is DELIBERATE, not neglect: the 09-19 law says SIFTA is local-first, her
  body is her own silicon, and routing her gates through someone else's endpoint
  is a dependency, not a borg. Jev the cloud call is a LANE (demo + comparison);
  the borg target is the PATTERN — `swarm_calibrated_decision.py`, a calibrated
  {label, confidence, receipt} lane running on her local models (AliceG4U 6.3 GB,
  MiniCPM-V, Gemma), with the keyword gate as fallback and confidence calibrated
  against her own labelled JACKER/SMARTASS/SCIENTIST examples.
- OpenJev is the strongest lead for that target: single-forward-pass, local
  hardware, same interface shape. That is the version worth borging.

## Verdict — the two questions

**1. Are we using it as classifier in SIFTA?** No — not as a live classifier.
The client organ exists and works (6/6 live today), but no gate consumes it, by
the local-first law written two days ago. The correct use is: pattern in, local
silicon, receipts. Jev the cloud API stays a demo lane and a benchmark to
compare local candidates against.

**2. Is it good for AGI?** As a mind: no — the vendor's own limits say no System
2, no chat, no domain expertise; it is a reflex, not a mind, and AGI needs the
deliberation, memory and agency Alice already carries. As an ORGAN in Alice's
body: yes, genuinely — her gates are exactly the "smart if-statement" shape, and
a calibrated verdict beats substring counting (4/6 → 6/6 measured). The right
frame is Kahneman's: Alice already has the System 2; what her body lacks is a
cheap calibrated System 1 reflex running on her own silicon. Jev shows the
shape; OpenJev shows it can be local. Neither is an AGI; both are good organs.

## Next bounded step (not started)

Borg OpenJev's approach, not the cloud dependency: single-forward-pass option
probabilities off one of her local models, behind the
`swarm_calibrated_decision.py` interface from the 09-19 brief, first consumer
`classify_visitor()`, keyword gate as fallback, every decision receipted.