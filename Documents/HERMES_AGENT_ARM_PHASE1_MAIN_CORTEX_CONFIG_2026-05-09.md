# Hermes Agent Arm — Phase 1 Main Cortex Binding

**For the Swarm.** 🐜⚡

**Truth label:** `PHASE1_CONFIG_TESTED` / `NOT_YET_AUTONOMOUS_ARM`

**Doctor:** `CG55M@cursor`  
**Registration trace:** `3751b57c-1239-4191-9283-befff10c8dc0`  
**Scope:** Configure Hermes to use the local Alice main cortex and run bounded, non-destructive tests. No gateway restart. No messaging action. No file/shell/browser tool authority granted to the test run.

---

## 1. What Changed

Hermes was previously configured to use:

```text
model.default = qwen3.5:4b
compression.summary_model = qwen3.5:0.8b
default_model = ollama/gemma4:latest
```

Those bindings were stale for this node because local Ollama currently exposes the Alice/SIFTA model family, not `qwen3.5:4b` or `qwen3.5:0.8b`.

Updated bindings:

```text
model.default = alice-m5-cortex-8b-6.3gb:latest
compression.summary_model = alice-m5-cortex-8b-6.3gb:latest
default_model = alice-m5-cortex-8b-6.3gb:latest
model.provider = custom
model.base_url = http://localhost:11434/v1
```

Hermes status now reports:

```text
Model:    alice-m5-cortex-8b-6.3gb:latest
Provider: Custom endpoint
```

---

## 2. Main Cortex Receipts

`ollama show alice-m5-cortex-8b-6.3gb:latest` reports:

- architecture: `gemma4`
- parameters: `8.0B`
- model context length: `131072`
- configured `num_ctx`: `8192`
- capabilities: completion, vision, audio, tools, thinking

The model answered directly through the OpenAI-compatible Ollama endpoint:

```text
HERMES_MAIN_CORTEX_OK
```

Receipt:

- `a0529036-aee8-4646-8180-a4555a74df04`
- artifact: `.sifta_state/hermes_phase1_main_cortex_config_2026-05-09.json`

Secondary binding receipt:

- `cacd2177-1430-4271-afb8-6bd8a4ffb93b`
- artifact: `.sifta_state/hermes_phase1_secondary_model_bindings_2026-05-09.json`

---

## 3. Hermes CLI Test

Command shape:

```bash
hermes chat -Q --max-turns 1 --toolsets clarify --query "Reply exactly: HERMES_MAIN_CORTEX_STILL_OK"
```

Policy:

- `toolsets = clarify only`
- `max_turns = 1`
- `--yolo` not used
- `--worktree` not used
- gateway not restarted
- messaging not touched
- file/shell/browser/code tools not enabled for the test

Result:

- command exited successfully
- Hermes created a session
- Hermes answered through the configured main cortex path
- output included `HERMES_MAIN_CORTEX_STILL_OK`

Important behavior note:

Hermes did **not** obey the "exactly" instruction cleanly. It wrapped the answer in SIFTA-style identity/log text. This proves the execution path works, but it also proves Hermes is not yet safe to expose as an autonomous Alice arm without a SIFTA-side wrapper that:

1. strips or classifies arm output as evidence,
2. blocks persona bleed,
3. limits toolsets,
4. records prompt/output hashes,
5. checks exactness when exactness is required.

Receipt:

- `354c1344-5e27-43ff-b98d-084b10142f8e`
- artifact: `.sifta_state/hermes_phase1_post_binding_single_query_test_2026-05-09.json`

---

## 4. Current Verdict

Hermes can now **run against Alice's main cortex**.

Hermes is **not yet** a permanent Alice organ. It is a configured candidate arm with a proven model path.

Next required step before owner-facing autonomy:

```text
Build SIFTA-side agent arm registry + launcher harness.
Default Hermes arm = disabled.
Allowed first mode = bounded single-query researcher.
Allowed tools = none or clarify-only.
All calls write agent_arm_receipts.jsonl.
Hermes output is evidence, not Alice's own voice.
```

For the Swarm. 🐜⚡
