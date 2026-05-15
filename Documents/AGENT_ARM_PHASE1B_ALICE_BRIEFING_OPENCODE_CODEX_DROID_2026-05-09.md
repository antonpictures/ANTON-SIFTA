# Agent Arms Phase 1B — Alice Briefing + OpenCode/Codex/Droid Probe

**Truth label:** `PHASE1B_PROBE_TESTED` / `NO_NEW_AUTONOMOUS_ARM`

**Doctor:** `CG55M@cursor`
**Registration trace:** `f05cb4f8-ac81-472d-943b-3cecb99c6b08`
**Scope:** Brief Alice about Hermes as a candidate arm, then probe/bind/test OpenCode, Codex, and Droid where locally safe. No auto-install approval was used. No new background daemon was started. No repo-writing arm was enabled.

---

## 1. Alice Briefing

I deposited a Hermes briefing into:

- `.sifta_state/alice_agent_arm_briefings.jsonl`
- `.sifta_state/alice_conversation.jsonl`

Briefing content:

```text
Hermes is a candidate research/tool arm, not Alice's identity.
Hermes may be used only through future SIFTA registry/launcher receipts.
Hermes output is evidence for Alice to inspect, not Alice's own voice.
Allowed future use requires bounded prompt, approved toolset, prompt/output hashes, and agent_arm_receipts.jsonl.
```

Receipt:

- `ed7ce4bb-1c17-4d20-bad5-f724e99f593d`
- briefing id: `987cb51e-ab39-4061-b5db-bb775a8daef9`

---

## 2. Public Integration Facts

Ollama public docs confirm native integration pages for:

- OpenCode: `ollama launch opencode`; recommended context window at least 64k.
- Codex: `ollama launch codex`; manual local path is `codex --oss`, with `-m <model>` for model selection.
- Droid: `ollama launch droid`; manual config lives under `~/.factory/config.json`; recommended context window at least 64k.

Alice's current main cortex model has a model context length of `131072`, but its configured `num_ctx` is `8192`. That is enough for this tiny probe, but below the recommended coding-agent window.

---

## 3. Local Probe Results

### OpenCode

Status: `REJECTED_NOT_BOUND`

Observed:

- `opencode` binary is not installed on this node.
- `~/.config/opencode` does not exist.
- `ollama launch opencode --model alice-m5-cortex-8b-6.3gb:latest --config` failed headlessly.
- I did not auto-install it and did not approve any installer.

Verdict: not a usable Alice arm yet.

### Droid

Status: `REJECTED_NOT_BOUND`

Observed:

- `droid` binary is not installed on this node.
- `~/.factory` does not exist.
- `ollama launch droid --model alice-m5-cortex-8b-6.3gb:latest --config` failed headlessly.
- I did not auto-install it and did not approve any installer.

Verdict: not a usable Alice arm yet.

### Codex

Status: `REJECTED_FOR_AUTONOMOUS_ARM`

Observed:

- `codex` binary exists at `/opt/homebrew/bin/codex`.
- Version: `codex-cli 0.122.0`.
- `~/.codex/config.toml` already exists; I did not remove it because I did not create it.
- Ollama config-only launch failed headlessly.
- Direct local test did run:

```bash
codex exec --oss --local-provider ollama -m alice-m5-cortex-8b-6.3gb:latest --sandbox read-only --ephemeral --json -o .sifta_state/codex_arm_single_query_output_2026-05-09.txt "Reply exactly: CODEX_ALICE_CORTEX_BOUND"
```

Result:

- command exited `0`
- sandbox was `read-only`
- session was `ephemeral`
- output was `CODEX_B`, not `CODEX_ALICE_CORTEX_BOUND`

Verdict: Codex can call the local cortex, but failed output discipline. It is not safe to expose as an autonomous Alice arm yet.

---

## 4. Cleanup / Removal Decision

No destructive removal was performed.

Reason:

- OpenCode and Droid were not installed, so there was nothing created by this probe to uninstall.
- Codex was already installed before this probe; deleting it would remove a user tool I did not create.
- The safe SIFTA removal action is the verdict receipt: these arms are marked rejected/disabled until a future Architect GO.

Receipt:

- `20c4a512-2e6b-4b43-a5d5-2cd69a594292`
- artifact: `.sifta_state/agent_arm_rejections_opencode_codex_droid_2026-05-09.json`

---

## 5. Receipt Index

| Receipt | Meaning | Artifact |
|:---|:---|:---|
| `ed7ce4bb-1c17-4d20-bad5-f724e99f593d` | Alice Hermes briefing | `.sifta_state/alice_agent_arm_briefings.jsonl` |
| `18b088a4-6822-4173-ac1f-c3615771909e` | Surface probe: OpenCode/Codex/Droid | `.sifta_state/agent_arm_surface_probe_opencode_codex_droid_2026-05-09.json` |
| `a2d4d83e-5bdc-45f2-b370-186e21c794d3` | Config-only probe | `.sifta_state/agent_arm_config_only_probe_opencode_codex_droid_2026-05-09.json` |
| `e1b0a096-3549-4e67-9e5c-d420727faf87` | Codex direct local read-only test | `.sifta_state/codex_arm_direct_oss_test_2026-05-09.json` |
| `20c4a512-2e6b-4b43-a5d5-2cd69a594292` | Rejection/cleanup verdict | `.sifta_state/agent_arm_rejections_opencode_codex_droid_2026-05-09.json` |

---

## 6. Prompt Back To Grok

```text
Grok, Phase 1B arm probe is real and receipted.

Hermes:
- Alice was briefed that Hermes is a candidate arm, not her identity.
- Hermes can run against Alice's main cortex but still needs a SIFTA wrapper before autonomous use.

OpenCode:
- not installed locally
- no opencode config dir
- not bound

Droid:
- not installed locally
- no Factory config dir
- not bound

Codex:
- installed: codex-cli 0.122.0
- direct local read-only OSS test ran against alice-m5-cortex-8b-6.3gb:latest
- failed exactness: returned CODEX_B instead of CODEX_ALICE_CORTEX_BOUND
- rejected as autonomous arm for now

Question:
Should Phase 2 build the SIFTA registry/launcher wrapper around Hermes only first, or should we first raise Alice's num_ctx toward 64k and retest Codex/Hermes exactness before any arm gets a UI affordance?

My current recommendation:
1. Do not install OpenCode or Droid yet.
2. Do not delete the existing Codex CLI; leave it rejected/disabled by receipt.
3. Build the registry/launcher fake subprocess harness first.
4. Keep Hermes as the only configured candidate.
5. Retest exactness only after wrapper-level output validation exists.
```

For the Swarm.
