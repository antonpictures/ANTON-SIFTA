# Hermes Agent Arm — Phase 0 Probe

**For the Swarm.** 🐜⚡

**Truth label:** `PHASE0_PROBE_ONLY` / `RESEARCH_NOT_SHIPPED`

**Doctor:** `CG55M@cursor`  
**Registration trace:** `e14e16f8-a70f-4d86-b8f7-1506474c615e`  
**Scope:** Inspect Hermes/Ollama local state, daemon status, configuration surface, and receipt paths. No Hermes task was executed. No persistent daemon was started by this probe.

---

## 1. Phase 0 Result

Hermes is already installed on the machine and already has a gateway daemon running.

Observed:

- `ollama` binary: `/usr/local/bin/ollama`
- `hermes` binary: `/Users/ioanganton/.local/bin/hermes`
- Ollama serve daemon: PID `65950`, `ollama serve`
- Hermes gateway daemon: PID `1180`, launchd label `ai.hermes.gateway`
- Hermes version: `Hermes Agent v0.7.0 (2026.4.3)`
- Hermes project path: `/Users/ioanganton/.hermes/hermes-agent`
- Hermes Python: `3.11.14`
- Hermes config path: `/Users/ioanganton/.hermes/config.yaml`
- Hermes env path: `/Users/ioanganton/.hermes/.env`

Probe policy:

- `persistent_daemon_started = false`
- `hermes_task_executed = false`
- `mutating_flags_used = false`
- commands used `stdin=DEVNULL` and timeouts where needed

---

## 2. Ollama State

`ollama --version` reports:

- server version: `0.20.5`
- client warning: `client version is 0.23.2`

`ollama list` exposed these models:

- `alice-m1-cortex-4.5b-3.4gb:latest`
- `alice-m1-scout-2.3b-2.7gb:latest`
- `alice-m5-cortex-8b-6.3gb:latest`
- `sifta-classifier-c1-3.1b-6.2gb:latest`
- `alice-extra-cortex-25.8b-17gb:latest`

OpenAI-compatible Ollama endpoint `http://127.0.0.1:11434/v1/models` was reachable and returned the same Alice/SIFTA model family.

Current loaded model from `ollama ps`:

- `alice-m5-cortex-8b-6.3gb:latest`
- processor: `100% GPU`
- active context: `8192`

`ollama show alice-m5-cortex-8b-6.3gb:latest` reports:

- architecture: `gemma4`
- parameters: `8.0B`
- model context length: `131072`
- configured `num_ctx`: `8192`
- capabilities: completion, vision, audio, tools, thinking

Phase 0 implication: the weight can support a large context window, but current runtime config is only `8192`. Hermes/Ollama docs recommend large context for agentic coding lanes; Phase 1 should explicitly set/receipt context before trusting Hermes as an arm.

---

## 3. Hermes State

`hermes doctor` passed core environment checks:

- Python venv active
- OpenAI SDK, Rich, dotenv, PyYAML, HTTPX installed
- Hermes config and `.env` exist
- directory structure exists
- `state.db` exists with `1771` sessions
- terminal/file/vision/skills/browser/cronjob/tts/todo/memory/session_search/clarify/code_execution/delegation/messaging tools are present

Warnings:

- config version outdated: `v10 -> v11`
- Nous Portal auth not logged in
- OpenAI Codex auth logged in
- Docker not found
- `agent-browser` dependency audit: `0 critical, 13 high, 6 moderate`
- WhatsApp bridge dependency audit: `2 critical, 2 high, 1 moderate`
- `tinker-atropos` submodule not found
- web/MOA/image/RL/Home Assistant toolsets have missing keys or system dependencies
- Skills Hub not initialized
- Honcho and Mem0 not configured

`hermes status --all` reports:

- Provider: `Custom endpoint`
- Model: `qwen3.5:4b`
- OpenAI provider key label: `ollama`
- Telegram configured
- WhatsApp configured
- gateway service loaded under launchd
- 1 active scheduled job
- 1 active session

Critical mismatch:

Hermes status says its current model is `qwen3.5:4b`, but the local Ollama API did **not** expose `qwen3.5:4b` in `/v1/models`. It only exposed the Alice/SIFTA models. This means Hermes is installed and running, but the current local model binding may be stale or invalid until reconfigured.

---

## 4. `ollama launch hermes --config` Probe

Command:

```bash
ollama launch hermes --config
```

Result:

```text
Error: model selection requires an interactive terminal; use --model to run in headless mode
```

Interpretation:

`--config` exists and is non-launching, but headless config needs an explicit `--model`. Phase 0 deliberately did not run `--model ... --config` because that would mutate Hermes/Ollama configuration. The next safe step needs an explicit Architect GO and a chosen model.

Candidate command for Phase 1 config-only, if approved:

```bash
ollama launch hermes --model alice-m5-cortex-8b-6.3gb:latest --config
```

Do not run that until the config mutation is approved and the context window policy is decided.

---

## 5. Receipts

Append-only receipts were written to `.sifta_state/agent_arm_receipts.jsonl`.

| Receipt | Meaning |
|:---|:---|
| `6573ab51-0927-457a-b883-be2277186fea` | Phase 0 binary/Ollama/launch-config probe |
| `b805f7f9-0707-4aeb-9f57-f8f999ce4092` | Hermes daemon + doctor + Ollama OpenAI endpoint inspect |
| `efd06621-43ef-4859-a915-a57f5fd0bacb` | Hermes config/tool/help + Alice model inspect |
| `4770a965-f2c7-4709-938d-a0cf6ffcc66b` | Hermes tools summary + version inspect |
| `34d8f589-b67e-4fd3-b2d7-db4af19d8399` | Hermes redacted status inspect |

Probe artifacts:

- `.sifta_state/hermes_phase0_probe_2026-05-09.json`
- `.sifta_state/hermes_phase0_daemon_inspect_2026-05-09.json`
- `.sifta_state/hermes_phase0_config_inspect_2026-05-09.json`
- `.sifta_state/hermes_phase0_followup_inspect_2026-05-09.json`
- `.sifta_state/hermes_phase0_status_inspect_2026-05-09.json`

---

## 6. Phase 1 Gate

Hermes should **not** become an Alice arm yet.

Required before Phase 1:

1. Decide whether Hermes should use `alice-m5-cortex-8b-6.3gb:latest` or another installed model.
2. Decide context policy: current `num_ctx=8192` is low for agentic coding; target should be receipted before use.
3. Run config migration or decide to leave Hermes config at v10 temporarily.
4. Address or sandbox the gateway surface: Telegram and WhatsApp are configured, so Alice must not inherit Hermes messaging powers without a SIFTA policy gate.
5. Do not allow browser, terminal, file, code execution, delegation, or cron tools to act as Alice arms until `swarm_agent_arm_registry` and launcher receipts exist.
6. Keep Hermes output as evidence only, not Alice's voice or final truth.

---

## 7. Prompt Back To Grok

Copy/paste to Grok:

```text
Grok, Phase 0 Hermes probe is real and receipted.

Observed on George's M5 SIFTA node:
- Hermes is installed: /Users/ioanganton/.local/bin/hermes
- Hermes Agent v0.7.0, project at /Users/ioanganton/.hermes/hermes-agent
- Hermes gateway daemon is already running under launchd as ai.hermes.gateway, PID 1180
- Ollama serve is running, PID 65950
- Ollama exposes these local models: alice-m1-cortex, alice-m1-scout, alice-m5-cortex, sifta-classifier-c1, alice-extra-cortex
- Hermes status says Provider=Custom endpoint and Model=qwen3.5:4b, but qwen3.5:4b is NOT exposed by the local Ollama API
- alice-m5-cortex has model context length 131072 but current num_ctx is 8192
- `ollama launch hermes --config` in headless mode fails with: "model selection requires an interactive terminal; use --model to run in headless mode"
- Hermes has terminal/file/browser/code_execution/delegation/messaging/cron/memory tools available, so this is powerful and must be gated before Alice can call it
- Telegram and WhatsApp are configured in Hermes, so SIFTA must not inherit those powers without separate receipts and policy

Question:
What is the safest Phase 1 sequence to turn Hermes into Alice's first persistent octopus arm without giving it unbounded repo, shell, browser, messaging, or cron authority?

My proposed next sequence:
1. Do not touch the running gateway yet.
2. Build a SIFTA-side `swarm_agent_arm_registry` with Hermes disabled by default.
3. Build a fake launcher/test harness first.
4. Only after pytest, run config-only with an explicit available model, probably `alice-m5-cortex-8b-6.3gb:latest`, and receipt the context window.
5. Keep Hermes read-only and evidence-only until it passes one dry-run task and one timeout/failure task.

Please critique this. What am I missing?
```

For the Swarm. 🐜⚡
