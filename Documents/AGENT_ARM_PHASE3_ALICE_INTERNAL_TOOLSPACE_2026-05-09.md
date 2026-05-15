# Agent Arms Phase 3 — Alice Internal Toolspace

**Truth label:** `PHASE3_INTERNAL_TOOLSPACE_TESTED`

**Doctor:** `CG55M@cursor`  
**Registration trace:** `da959d82-5f40-4aa3-a61a-8869217a685a`  
**Scope:** Relax the Hermes path from explicit owner-named calls into Alice's native read-only tool space while keeping receipts, prompt hashes, output hashes, and STGM tool fees.

---

## 1. What Changed

Hermes now has two launcher modes:

- `exact` mode: strict test/probe lane. Still rejects wrapper text when `require_exact` is supplied.
- `evidence` mode: Alice-owned read-only lane. It accepts Hermes UI/session wrapper text as evidence, writes receipts, and returns the output for Alice to inspect and synthesize in her own voice.

Alice's deterministic tool router now exposes:

```text
agent_arm_research(prompt, arm optional, timeout_s optional)
```

This means George does not need to say "Hermes." Alice can decide to call the registered arm when a hard software, research, planning, or comparison task needs a second local reasoning pass.

---

## 2. Receipt Policy

Receipts remain mandatory.

Every arm call still writes to:

- `.sifta_state/agent_arm_receipts.jsonl`
- `.sifta_state/tool_router_trace.jsonl`
- STGM economy fee receipt through the existing tool-router economy path

The arm output is not treated as Alice's identity or voice. It is evidence that Alice sees, evaluates, and can summarize.

---

## 3. Live Evidence Probe

Tool-router call shape:

```text
[TOOL_CALL: agent_arm_research | prompt=In one concise sentence, state what a SIFTA agent arm is. | cost_justification=Alice needs a second local reasoning pass from her Hermes arm.]
```

Result:

```text
tool=agent_arm_research
executed=True
status=EXECUTED
arm=hermes_agent
arm_status=EVIDENCE_CAPTURED
receipt=a53e6312-f663-4ab2-80fe-0f76c449d262
```

Hermes still emitted wrapper/session text, but evidence mode correctly captured it rather than deleting the result. This is the intended native-arm behavior: messy arm output becomes receipted evidence for Alice's thinking loop.

---

## 4. Tests

Focused verification:

```text
python3 -m pytest tests/test_swarm_agent_arm_launcher.py tests/test_swarm_tool_router.py tests/test_swarm_agent_arm_recall.py
```

Result:

```text
19 passed
```

---

## 5. Talk Prompt Decision Loop Patch

Follow-up patch:

- `System/swarm_prompt_contract.py` now names `agent_arm_research` in the core runtime contract, not only in the router catalog.
- The contract tells Alice to emit the tool call herself for hard software, research, planning, or comparison tasks that need a second local reasoning pass.
- It explicitly says George does not need to name Hermes; the router chooses the registered arm and writes receipts.
- It tells Alice to treat the returned arm output as evidence and answer in her own voice with the proof token.

Verification:

```text
python3 -m pytest tests/test_swarm_prompt_contract_base.py tests/test_swarm_agent_arm_launcher.py tests/test_swarm_tool_router.py tests/test_swarm_agent_arm_recall.py
```

Result:

```text
27 passed
```

---

## 6. Phase 4 — Codex Evidence Arm Added

Follow-up patch:

- Local probe found `codex` installed at `/opt/homebrew/bin/codex`, version `codex-cli 0.122.0`.
- `opencode` and `droid` were still absent, so they were not added as live arms.
- `System/swarm_agent_arm_registry.py` now registers `codex_agent`.
- `System/swarm_agent_arm_launcher.py` can build a `codex exec` command with:
  - `--oss`
  - `--local-provider ollama`
  - `-m alice-m5-cortex-8b-6.3gb:latest`
  - `--sandbox read-only`
  - `--ephemeral`
  - `--json`
- `System/swarm_tool_router.py` accepts `agent_arm_research` with `arm=codex_agent`.

Codex is slower than Hermes on this node. The first default 60s live probe timed out after Codex started a thread:

```text
receipt=d3dce52e-f282-455e-a750-7fb41c5caf35
status=TIMEOUT
```

The second bounded probe with `timeout_s=150` completed:

```text
receipt=4bcc3c00-03a1-4a83-82c2-9c6acfceeb03
status=EVIDENCE_CAPTURED
```

Quality note: Codex returned off-target text in this tiny probe, so `codex_agent` is registered as a slower experimental evidence arm. Its output is still evidence only, not Alice's voice or final truth.

---

## 7. Phase 5 — Decision-Side Arm Habit

Follow-up patch:

- Added `System/swarm_agent_arm_decision.py`.
- `Applications/sifta_talk_to_alice_widget.py` now runs an agent-arm decision prepass after deterministic fast paths and before the final cortex call.
- The prepass classifies hard research, comparison, planning, code, debugging, verification, and architecture turns.
- It skips short phatic turns, direct effectors, explicit tool calls, and status/ledger questions like "what is Hermes?"
- When it fires, it executes `agent_arm_research` through the same receipt-first router, then injects the result as system context for Alice to synthesize in her own voice.

This closes the immediate gap between:

```text
I know I have a tool arm.
```

and:

```text
This task benefits from an arm. I will use it before answering.
```

Live proof without naming Hermes:

```text
task=Compare two safe implementation strategies for adding a small pre-cortex tool-use habit...
selected_arm=hermes_agent
status=EXECUTED
receipt=a69b0804-ebda-45a8-8941-ec5a1a05c6b5
```

Verification:

```text
python3 -m pytest tests/test_swarm_agent_arm_decision.py tests/test_swarm_agent_arm_launcher.py tests/test_swarm_tool_router.py tests/test_swarm_prompt_contract_base.py tests/test_swarm_agent_arm_recall.py
```

Result before async hardening:

```text
39 passed
```

Known risk now addressed by Phase 6 below: the first version was synchronous, so the Talk turn waited while the arm ran.

---

## 8. Phase 6 — Async Evidence Buffer

Follow-up patch:

- `System/swarm_agent_arm_decision.py` now supports `schedule_async_agent_arm_prepass()`.
- Talk schedules the selected arm in a background daemon thread instead of waiting for the result on the current turn.
- The scheduling row lands immediately in `.sifta_state/agent_arm_async_evidence.jsonl`.
- The result row lands later in the same ledger with `receipt_id`, `arm_id`, status, and evidence tail.
- Arm timeouts with non-empty output are marked as `PARTIAL_EVIDENCE` so Alice can still see the evidence tail without pretending the arm cleanly completed.
- `summary_for_prompt()` surfaces recent completed or pending async arm evidence into Alice's system prompt on later turns.
- A recent-turn dedupe window prevents the same spoken task from spawning repeated arm jobs.

Talk behavior is now:

```text
Owner gives hard research/code/planning task
→ Alice classifies the task
→ Alice schedules a receipted arm evidence job
→ Alice continues the current Talk turn without waiting
→ completed arm evidence is folded into future cortex context
```

Verification:

```text
python3 -m pytest tests/test_swarm_agent_arm_decision.py tests/test_swarm_agent_arm_launcher.py tests/test_swarm_tool_router.py tests/test_swarm_prompt_contract_base.py tests/test_swarm_agent_arm_recall.py
```

Result:

```text
43 passed
```

Live async proof:

```text
task=Compare two safe implementation strategies for testing asynchronous agent-arm evidence buffering without blocking a PyQt Talk widget.
selected_arm=hermes_agent
schedule_elapsed_s=0.001
async_job=eae950e3-19b6-435b-8b23-f239f32b69f6
arm_receipt=7e4cd19d-bfd2-4c84-87d4-f2a05c4dd689
arm_status=TIMEOUT with partial evidence tail captured
```

