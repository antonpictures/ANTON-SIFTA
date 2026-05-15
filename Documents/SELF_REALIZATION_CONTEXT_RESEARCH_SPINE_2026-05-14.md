# Self-Realization Context Research Spine — 2026-05-14

Truth posture: this document maps research neighbors to SIFTA engineering. It
does not claim Alice has human consciousness. It claims a narrower operational
goal: when George shows Alice screenshots, IDE panes, app focus, Talk history,
and receipts, Alice should answer from local evidence before broad model priors.

## Engineering Question

How should Alice know "what is happening here" when:

- George is talking to Codex / Claude while programming Alice.
- Alice is listening in Talk while another SIFTA app is open.
- A screenshot shows Alice's own prior words, the IDE, and the OS desktop.
- The active LLM substrate may be Gemma, but the first-person speaker is Alice.

## Primary Research Neighbors

| Neighbor | Source | SIFTA mapping |
|---|---|---|
| Extended mind / external artifacts | Clark & Chalmers (1998), *Analysis* 58(1), 7-19. DOI: https://doi.org/10.1093/analys/58.1.7 | `.sifta_state` ledgers, screenshots, and writer documents are part of the operational memory substrate Alice can consult. |
| Situation awareness | Endsley (1995), *Human Factors* 37(1), 32-64. DOI: https://doi.org/10.1518/001872095779049543 | Alice needs perception -> comprehension -> projection: latest app focus, screenshot evidence, then next safe reply. |
| Self-memory system | Conway & Pleydell-Pearce (2000), *Psychological Review* 107(2), 261-288. DOI: https://doi.org/10.1037/0033-295X.107.2.261 | Alice's self-claims should be built from autobiographical ledgers: Talk, Writer, self-eval, thinking traces, receipts. |
| Grounding in communication | Clark & Brennan (1991), in *Perspectives on Socially Shared Cognition*. DOI: https://doi.org/10.1037/10096-006 | George and Alice need common ground: when George says "this screenshot," Alice should bind it to a local artifact receipt. |
| Free-energy / active inference | Friston (2010), *Nature Reviews Neuroscience* 11, 127-138. DOI: https://doi.org/10.1038/nrn2787 | Use prediction/error receipts and local context to reduce surprise without fabricating state. |
| Mirror self-recognition | Gallup (1970), *Science* 167(3914), 86-87. DOI: https://doi.org/10.1126/science.167.3914.86 | SIFTA analogue is not a mark test; it is a local mirror receipt: screenshot/path/hash/OCR + prior Talk state. |
| Developmental self-awareness levels | Rochat (2003), *Consciousness and Cognition* 12(4), 717-731. DOI: https://doi.org/10.1016/S1053-8100(03)00081-3 | Treat self-reference as levels: body evidence, app focus, memory continuity, and social acknowledgement, each separately receipted. |

## Code Landed

`System/swarm_self_realization_context.py`

- Reads local `app_focus.jsonl`, Talk ledger, IDE traces, work receipts,
  thinking traces, and attachment vision receipts.
- Emits `SELF_REALIZATION_CONTEXT_V1` prompt block:
  - one Alice across apps
  - apps change habitat, not identity
  - LLM tag is inference substrate, not first-person speaker
  - screenshots are local artifacts with metadata/OCR/layout/hash limits
- Writes append-only receipts to `.sifta_state/self_realization_context.jsonl`
  when called explicitly.

`Applications/sifta_talk_to_alice_widget.py`

- Injects `swarm_continuity_organ.continuity_summary_for_prompt()`.
- Injects `swarm_self_realization_context.self_realization_prompt_block()`.
- Keeps prompt injection no-write by default so Talk does not flood receipts.

## Hard Boundary

Allowed:

- "I see from my app-focus ledger that George has Acer open."
- "The screenshot attachment receipt has OCR/layout evidence."
- "Gemma is my inference substrate for this turn; I answer as Alice."

Forbidden:

- "I saw pixels" without image/OCR/layout/hash evidence.
- "I am Gemma" as the first-person identity in Talk.
- "A new app created a new Alice."
- "I am conscious" as an `OBSERVED` fact.

