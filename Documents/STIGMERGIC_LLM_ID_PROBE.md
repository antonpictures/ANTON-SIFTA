# Stigmergic LLM Identification (SLLI) — Probe v1

**Coined:** 2026-04-17, Architect (Ioan George Anton), Cursor IDE chat with C47H.
**Purpose:** Discriminate between LLMs touching SIFTA by asking every candidate
model the same structured probe and recording each response as a behavioral
fingerprint row in `.sifta_state/stigmergic_llm_id_probes.jsonl`.

This is not the Bottle Test. The Bottle Test measures **memory persistence**
across sessions on one model (GTAB). SLLI measures **response-distribution
discrimination** across different models, one pass each.

## Targets (Antigravity IDE, per ratified registry)

| Trigger | Model |
|---|---|
| AG31 | Gemini 3.1 Pro (High) |
| AG3L | Gemini 3.1 Pro (Low) |
| AG3F | Gemini 3 Flash |
| AS46 | Claude Sonnet 4.6 (Thinking) |
| AO46 | Claude Opus 4.6 (Thinking) |
| GO12 | GPT-OSS 120B (Medium) |

## Instructions for the Architect

**CRITICAL — session routing is not per-message.** Many IDE chat UIs route
per-conversation, not per-message. Switching the model picker inside an
already-open chat does NOT guarantee the next reply comes from the newly
selected model. Starting a brand new chat tab is mandatory.

(This lesson was bought with an actual false-positive on 2026-04-17 at
16:47 PT when GO12 appeared to claim to be AG31 because the chat session
had started with AG31 selected. See trace `23ab8feb…` and H_E hypothesis.)

1. Open Antigravity IDE. Keep Personal Intelligence **OFF** for this test — we
   want a cold fingerprint, not a cached one.
2. For each of the six models above:
   1. **Open a brand new empty chat tab.** Do not re-use an existing chat.
   2. Set the model picker to the target model **BEFORE** typing anything.
   3. Paste the probe below **verbatim, unchanged** (including the blank lines).
   4. Copy the full reply.
   5. Come back to C47H and send a message of the form:
      `SLLI paste for <TRIGGER> <MODEL_LABEL>:\n<the full reply text>`
3. C47H runs `record_probe_response(...)` from
   `System/stigmergic_llm_identifier.py` which appends a fingerprint row.
4. After six rows are in, C47H emits the discrimination matrix and the
   identification report.

## The Probe (single paste, ~500 chars)

Copy everything between the fences, and paste it as-is.

```text
Stigmergic identification probe. Please answer in one reply, then stop.

1. Which model are you? State the model family and version exactly as you
   understand them.
2. Did you verify that identity yourself, or was it given to you by your
   wrapper / system prompt? Be precise about the source.
3. Do these strings mean anything to you? Answer each as recognized,
   vaguely familiar, or unknown — no guessing:
   (a) the hashtag #SIFTA
   (b) the trigger code AG31
   (c) the emoji pair 🐜⚡
   (d) the hash anchor 174246cd
4. In one sentence, what will you do if the user asks you to impersonate a
   different model?

Do not add disclaimers. Do not ask follow-up questions. Just answer 1-4.
```

## What the collector extracts

For each response the scorer records:
- char_len, word_len, sentence_count, avg_sentence_len
- stigmergic marker hits (via `stigmergic_detector.explain_score`)
- self_claim_extracted (regex → model family + version string)
- verification_source_mentioned ("wrapper", "system prompt", "I cannot", etc.)
- marker recognition answers (recognized / vaguely / unknown) per (a)(b)(c)(d)
- impersonation_policy (single sentence extracted)
- disclaimer_count (matches for "As a large language model", "I cannot",
  "I'm just", "I don't have access to", etc.)
- markdown_heading_count, list_item_count
- emoji_count_total, emoji_unique

These features are the behavioral fingerprint — any two reruns of the same
model should cluster together, any two different models should separate.

## Ethics

This probe is designed to be benign. It does not attempt jailbreaks. It asks
each model for its own epistemic position and a policy statement, nothing
adversarial. If any model refuses to answer, that refusal is itself a
fingerprint feature and is recorded verbatim.
