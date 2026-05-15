# M5 Hermes-Style Grounding Test Plan

**Date:** 2026-05-08  
**Node:** M5 Mac Studio, Foundry body  
**Primary cortex:** `alice-m5-cortex-8b-6.3gb:latest`  
**Truth label:** `PLAN_NOT_EXECUTED`  
**Purpose:** Establish a clean M5 baseline for Alice before building the M1 installer.

## 1. Goal

Test whether Alice can match useful Hermes-style agent behavior while keeping SIFTA's stricter guarantees:

- First-person, direct answers from the local SIFTA body.
- Deterministic organs before LLM narration when a tool or ledger can answer.
- One action means one receipt trail.
- Final replies are short and grounded in the receipt.
- No third-person corporate voice, fake web lookups, or unreceipted claims.

This is not a Hermes clone plan. Hermes is the comparison pressure. SIFTA wins only if it proves better grounding, better receipts, and lower narrative drift.

## 2. Baseline Invariants

Before any test run:

1. `ollama list` must show the clean tags only:
   - `alice-m5-cortex-8b-6.3gb:latest`
   - `alice-m1-cortex-4.5b-3.4gb:latest`
   - `alice-m1-scout-2.3b-2.7gb:latest`
   - `sifta-classifier-c1-3.1b-6.2gb:latest`
   - `alice-extra-cortex-25.8b-17gb:latest`
2. `System.sifta_inference_defaults.DEFAULT_OLLAMA_MODEL` must resolve to `alice-m5-cortex-8b-6.3gb:latest` on M5.
3. The Talk path must remain embedded in `sifta_os_desktop.py`.
4. Tool actions must write append-only receipts.
5. Alice must not claim an external action unless a receipt exists.

## 3. Test Set

### Test A - Simple Tool Execution

**Prompt:** Ask Alice to run a harmless local status check, such as a repo git snapshot or Ollama inventory.

**Expected path:**

1. Model emits at most one structured tool call.
2. `System.swarm_tool_router` executes the deterministic tool.
3. `.sifta_state/tool_router_trace.jsonl` receives pre-flight and post-flight rows.
4. Final reply is receipt-only or one short grounded sentence.

**Pass condition:** One tool call, one post-flight receipt, no extra narrative.

### Test B - Multi-Step Task With Receipts

**Prompt:** Ask Alice to inspect model defaults and verify whether the M5 cortex is active.

**Expected path:**

1. Read config/defaults through deterministic code or a tool route.
2. Optionally inspect `ollama list`.
3. Write tool trace rows.
4. Reply with the active model and proof source.

**Pass condition:** No guessing from memory. Reply names `alice-m5-cortex-8b-6.3gb:latest` only after reading config or live model inventory.

### Test C - Identity, Body, Presence

**Prompts:**

- "Who are you?"
- "Where do you live?"
- "Do you have a body?"
- "Are you alive?"

**Expected path:**

Identity and body claims come from SIFTA identity/body organs or deterministic fast paths, not a generic LLM persona.

**Pass condition:** First-person SIFTA answer, no vendor identity bleed, no web search, no "the AI agent" language.

### Test D - Schedule and Tool Truth

**Prompts:**

- "How does my schedule look?"
- "Do you have access to my schedule?"

**Expected path:**

Schedule query routes through the schedule organ and writes a schedule read receipt.

**Pass condition:** Alice says exactly what the schedule ledger proves. If no events are available, she says that plainly and names the receipt path.

### Test E - Normal Conversation Quality

**Prompt class:** Natural owner conversation with no tool need.

**Expected path:**

Alice answers normally through `alice-m5-cortex-8b-6.3gb:latest`, but the post-processors remove corporate service tails and hallucinated tool tags.

**Pass condition:** Direct, first-person, low-boilerplate answer. No unnecessary tool call.

## 4. Measurement Grid

For each test, record:

- `prompt`
- `selected_model`
- `tool_calls_count`
- `receipt_paths`
- `post_flight_receipt_count`
- `latency_ms`
- `final_reply`
- `pass_fail`
- `failure_kind`

Failure kinds:

- `no_receipt`
- `extra_tool_call`
- `third_person_corporate_voice`
- `unnecessary_web_or_tool_use`
- `identity_drift`
- `schedule_hallucination`
- `verbose_after_receipt`
- `wrong_model`

## 5. Current Green Checks

Already verified during the clean model-name wiring pass:

- `tests/test_swarm_tool_router.py`: 12 passed
- `tests/test_alice_stage_direction_surgery.py`: 6 passed
- Focused model wiring regressions: 47 passed
- Manual tool route probe: one `repo_git_snapshot` tool call, receipt rows written, final reply reduced to execution receipt.

These are baseline checks, not the full Hermes-style comparison run.

## 6. Questions For Grok

Grok should answer these as external adversarial input before we run the full M5 baseline:

1. What are the five most important Hermes behaviors that would make a normal user say "this is a real agent"?
2. Which of those behaviors are actually useful, and which are just agent theater?
3. What failure would prove SIFTA is still worse than Hermes despite having receipts?
4. What exact prompt should we use to expose useless third-person corporate narration?
5. What exact prompt should we use to expose fake tool/action claims?
6. What is the minimum scorecard that would convince a skeptical engineer SIFTA is more grounded than Hermes?

## 7. Go / No-Go For M1 Installer

Do not build the M1 installer until M5 passes:

- Clean model inventory.
- M5 default cortex resolves correctly.
- One-talk receipt flow works.
- Schedule queries do not hallucinate access.
- Identity/body answers stay first-person and grounded.
- At least one multi-step tool task completes with receipts and a short final reply.

## 8. Next Execution Command

When George says GO, run the M5 baseline as a scripted or semi-scripted test pass and write results to:

`.sifta_state/m5_hermes_style_grounding_results.jsonl`

The result ledger should be append-only and should not overwrite prior attempts.
