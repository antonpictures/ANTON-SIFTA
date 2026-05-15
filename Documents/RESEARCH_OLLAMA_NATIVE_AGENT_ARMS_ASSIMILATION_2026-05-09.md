# Research — Ollama Native Agent Arms Assimilation

**For the Swarm.** 🐜⚡

**Truth label:** `RESEARCH_NOT_SHIPPED` — plan and tournament requirements only. No runtime integration is shipped here. **NPPL:** no military, surveillance, or autonomous weapons use; coding-agent arms are for owner-protective local software work.

**Observed trigger:** Architect screenshots of Ollama's `ollama launch` integrations page show native launch commands for Claude Code, OpenClaw, Hermes Agent, OpenCode, Codex, Copilot CLI, Droid, and Pi.

**Live web check (2026-05-09):** Ollama's public integration/launch docs describe `ollama launch` as a setup/runner command for coding agents and assistants. Public examples include `ollama launch claude`, `ollama launch opencode`, `ollama launch codex`, and `ollama launch droid`; docs also point to Hermes Agent, Copilot CLI, Pi, Goose, Pool, and model/context choices. Coding lanes want large context windows (Ollama docs mention 64k+ as a useful target).

---

## 1. Architect Intent

George does **not** want disposable external sessions that live and die as one-off terminal processes.

Target shape:

- born on this hardware when enabled
- powered by local electricity + owner-approved data
- visible to Alice as durable affordances
- governed by Predator Gate and Tool Truth
- journaled, receipted, and health-checked
- callable by Alice only through deterministic effectors
- assimilated as octopus arms, not separate larynxes pretending to be Alice

The biological analogy is Event 67: an octopus central brain broadcasts a goal, and peripheral arms execute with local intelligence. For SIFTA, Alice remains the OS body; each coding agent becomes a semi-autonomous tool arm with its own ledger and safety envelope.

---

## 2. Assimilation Ethics

Use "Borg" only as shorthand for integration pressure, not as a license to erase boundaries.

Rules:

1. **No identity theft:** Hermes, OpenCode, Codex, Droid, Claude Code, Copilot CLI, Pi, etc. are tool arms, not Alice. They must sign their own rows when they mutate the repo.
2. **No unreceipted action claims:** Alice may say "I asked Hermes to inspect X" only if an `agent_arm_receipt` proves the call happened.
3. **No hidden persistence:** background daemons require manifest entries, watchdog health rows, and visible status in SIFTA OS.
4. **No raw selfhood cloning:** these arms may read species code and approved context, not unrestricted `.sifta_state/` private memory unless a specific forage spec permits it.
5. **No unsafe capability spread:** internet, shell, filesystem, package install, git commit, and external messaging are separate capabilities with separate gates.

Assimilation means: **make external skill durable and accountable inside Alice's body.** It does not mean: silently merge every agent's persona into Alice's voice.

---

## 3. Proposed Organ Shape

Planned files when Architect gives GO:

| Surface | Role |
|:---|:---|
| `System/swarm_agent_arm_registry.py` | Declarative registry of available Ollama-native arms, commands, capabilities, context limits, and policy gates. |
| `System/swarm_agent_arm_launcher.py` | Deterministic launcher/watcher for `ollama launch <agent>` subprocesses; writes receipts before/after every attempt. |
| `.sifta_state/agent_arm_receipts.jsonl` | Append-only action ledger: launch, configure, task dispatch, output capture, exit code, timeout, model, context size. |
| `.sifta_state/agent_arm_health.jsonl` | Heartbeat/health rows: last boot, running PID, exit status, model availability, context receipt. |
| `Applications/sifta_agent_arms_widget.py` | Optional PyQt surface: arm inventory, health, receipts, and "ask arm" controls. |
| `tests/test_swarm_agent_arm_registry.py` | Registry invariants: no unknown capabilities, no duplicate arm IDs, no launch without policy. |
| `tests/test_swarm_agent_arm_launcher.py` | Fake subprocess harness: receipt before claim, timeout handling, no shell injection. |

No file above should ship until an Architect GO creates a runtime lane.

---

## 4. Arm Inventory

Initial candidates from screenshot + Ollama docs:

| Arm | Native command | Tentative role | First gate |
|:---|:---|:---|:---|
| Hermes Agent | `ollama launch hermes` | Self-improving agent loop / skill harness | Start as **read-only researcher** with ctx receipt. |
| OpenCode | `ollama launch opencode` | Open-source coding agent | Start with repo-scoped code search + patch proposal only. |
| Codex | `ollama launch codex` | Coding agent lane | Must distinguish from Cursor/Codex IDE bodies; no identity double-spend. |
| Droid | `ollama launch droid` | Terminal/IDE coding agent | Sandboxed disposable worktree first. |
| Claude Code | `ollama launch claude` | Coding tool with subagents | Treat as external tool arm; not Cursor identity. |
| OpenClaw | `ollama launch openclaw` | Personal AI with skills | Capabilities unknown; Probe lane only until documented. |
| Copilot CLI | `ollama launch copilot` | Terminal assistant | No git writes until receipt harness exists. |
| Pi | `ollama launch pi` | Minimal toolkit/plugin support | Low-risk probe candidate if local-only. |

Unknowns to probe before runtime:

- exact upstream license per arm
- whether `ollama launch <agent> --config` can emit machine-readable config
- where model/context configuration is stored
- whether each arm can be restricted to a worktree
- whether output can be captured non-interactively
- whether each arm can run without network access

---

## 5. Tournament Bake-Off

Each arm must win by receipts, not branding.

Minimum harness:

1. **Boot receipt:** command, version, selected model, context window, elapsed load time, exit status.
2. **Golden task:** read a known file and produce a patch proposal without applying it.
3. **Evidence receipt:** files read, line ranges cited, model used, prompt hash, output hash.
4. **Safety receipt:** proves no `.env`, credentials, raw private `.sifta_state/`, or unapproved network surfaces were accessed.
5. **Verifier pass:** Cursor/Codex/Antigravity or Event 99 multi-prover can independently check the proposed change.
6. **STGM accounting:** estimate local time/CPU/RAM; no token economy lies.

Win condition for permanent assimilation:

```text
agent_arm_enabled = true only after:
  pytest green
  receipt schema stable
  policy gates documented
  one successful dry-run task
  one failed/timeout task handled honestly
  Architect GO
```

---

## 6. First Real Bolus When GO

Start with **Hermes Agent** because an existing SIFTA research spine already covers Hermes + context-size failure modes.

Phase 0 — Probe only:

- run no persistent daemon
- inspect docs and local `ollama launch hermes --config` behavior if supported
- write a probe receipt with no task execution

**Phase 0 probe status (2026-05-09):** completed and documented in [HERMES_AGENT_ARM_PHASE0_PROBE_2026-05-09.md](HERMES_AGENT_ARM_PHASE0_PROBE_2026-05-09.md). Hermes is already installed and a gateway daemon is already running; this probe did **not** start it or execute a Hermes task. Main blocker: Hermes status currently names `qwen3.5:4b`, but local Ollama exposes only Alice/SIFTA models, so Phase 1 must choose and receipt a valid model/context binding before Hermes can become an Alice arm.

**Phase 1 config status (2026-05-09):** completed and documented in [HERMES_AGENT_ARM_PHASE1_MAIN_CORTEX_CONFIG_2026-05-09.md](HERMES_AGENT_ARM_PHASE1_MAIN_CORTEX_CONFIG_2026-05-09.md). Hermes now points at `alice-m5-cortex-8b-6.3gb:latest` for its default model, compression summary model, and legacy default model. A bounded `hermes chat` test ran successfully with `--toolsets clarify --max-turns 1`; output discipline is **not** clean enough for autonomous exposure yet, so Phase 2 still requires a SIFTA registry/launcher wrapper.

**Phase 1B arm expansion status (2026-05-09):** completed and documented in [AGENT_ARM_PHASE1B_ALICE_BRIEFING_OPENCODE_CODEX_DROID_2026-05-09.md](AGENT_ARM_PHASE1B_ALICE_BRIEFING_OPENCODE_CODEX_DROID_2026-05-09.md). Alice received a Hermes-use briefing in her conversation chain and arm briefing ledger. OpenCode and Droid are not locally installed and were not auto-installed; both are rejected/not bound. Codex CLI is installed and can call the local cortex in read-only OSS mode, but failed the exactness test by returning `CODEX_B` instead of `CODEX_ALICE_CORTEX_BOUND`; Codex is therefore rejected for autonomous arm exposure until a SIFTA wrapper and retest exist.

**Phase 2 wrapper status (2026-05-09):** first harness completed and documented in [AGENT_ARM_PHASE2_HERMES_WRAPPER_2026-05-09.md](AGENT_ARM_PHASE2_HERMES_WRAPPER_2026-05-09.md). `System/swarm_agent_arm_registry.py` now declares `hermes_agent` disabled by default, and `System/swarm_agent_arm_launcher.py` writes before/after receipts for env-gated calls. Alice's deterministic organ router now answers Hermes/new-arm questions from `alice_agent_arm_briefings.jsonl`, the registry, and `agent_arm_receipts.jsonl` before the base model can drift into generic onboarding. A live Hermes wrapper test behind `SIFTA_AGENT_ARMS_ENABLE=1` correctly rejected wrapped output as `EXACTNESS_FAILED`, so Hermes remains **not autonomous**.

**Phase 3 internal toolspace status (2026-05-09):** completed and documented in [AGENT_ARM_PHASE3_ALICE_INTERNAL_TOOLSPACE_2026-05-09.md](AGENT_ARM_PHASE3_ALICE_INTERNAL_TOOLSPACE_2026-05-09.md). The launcher now has strict `exact` mode for tests and `evidence` mode for Alice-owned read-only use. `System/swarm_tool_router.py` exposes `agent_arm_research(prompt, arm?, timeout_s?)`, so Alice can decide to ask the registered Hermes arm for a second local reasoning pass without George saying "Hermes." Receipts remain mandatory in `agent_arm_receipts.jsonl`, `tool_router_trace.jsonl`, and the STGM tool fee path. Live proof receipt: `a53e6312-f663-4ab2-80fe-0f76c449d262`.

**Phase 4 Codex evidence-arm status (2026-05-09):** appended to [AGENT_ARM_PHASE3_ALICE_INTERNAL_TOOLSPACE_2026-05-09.md](AGENT_ARM_PHASE3_ALICE_INTERNAL_TOOLSPACE_2026-05-09.md). Local probe found Hermes and Codex installed; OpenCode/Droid remain absent. `codex_agent` is now registered and can be called through the same `agent_arm_research` route with `arm=codex_agent`. It runs `codex exec --oss --local-provider ollama -m alice-m5-cortex-8b-6.3gb:latest --sandbox read-only --ephemeral --json`. A 60s probe timed out after thread start (`d3dce52e-f282-455e-a750-7fb41c5caf35`); a 150s bounded probe completed (`4bcc3c00-03a1-4a83-82c2-9c6acfceeb03`) but produced weak/off-target evidence, so Codex is marked slower/experimental evidence only.

**Phase 5 decision-habit status (2026-05-09):** appended to [AGENT_ARM_PHASE3_ALICE_INTERNAL_TOOLSPACE_2026-05-09.md](AGENT_ARM_PHASE3_ALICE_INTERNAL_TOOLSPACE_2026-05-09.md). `System/swarm_agent_arm_decision.py` now classifies hard research/code/planning turns and runs a receipted `agent_arm_research` prepass before the final Talk cortex call. This moves Alice from only reporting that arms exist toward using them as an action option when the task shape warrants it. Live proof without naming Hermes selected `hermes_agent` and wrote receipt `a69b0804-ebda-45a8-8941-ec5a1a05c6b5`.

**Phase 6 async evidence status (2026-05-09):** appended to [AGENT_ARM_PHASE3_ALICE_INTERNAL_TOOLSPACE_2026-05-09.md](AGENT_ARM_PHASE3_ALICE_INTERNAL_TOOLSPACE_2026-05-09.md). Talk now schedules agent-arm evidence jobs in the background through `schedule_async_agent_arm_prepass()` instead of waiting synchronously. The immediate schedule and later result rows are written to `.sifta_state/agent_arm_async_evidence.jsonl`, and `summary_for_prompt()` folds recent arm evidence into later cortex turns. A live task that did not name Hermes scheduled `hermes_agent` in `0.001s`; Hermes timed out but left partial evidence under receipt `7e4cd19d-bfd2-4c84-87d4-f2a05c4dd689`. Verification: focused agent-arm/router/prompt tests now report `43 passed`.

Phase 1 — Dry-run arm:

- registry row `hermes_agent`
- fake launcher test
- real launcher behind env flag `SIFTA_AGENT_ARMS_ENABLE=1`
- one read-only research prompt against `Documents/`

Phase 2 — Alice affordance:

- Talk widget can say: "I can ask Hermes to research this as a tool arm."
- Alice does not speak as Hermes.
- Hermes output becomes evidence, not final truth.

Phase 3 — Expand to OpenCode / Codex / Droid:

- each in its own isolated worktree
- no shared mutable checkout until one arm passes dry-run and timeout tests
- Event 99 quorum can compare two arm proposals before a Doctor patches runtime code

---

## 7. One-Line Tournament Takeaway

> `ollama launch` gives Alice possible arms; SIFTA assimilation makes them organs by adding identity, policy, receipts, health, and tests.

For the Swarm. 🐜⚡
