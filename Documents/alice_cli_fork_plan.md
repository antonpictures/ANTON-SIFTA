# alice-cli fork plan — r120 deliverable

**Author:** Cowork Claude (Cowork-side hands, `claude-opus-4-7`), 2026-05-28.
**Round:** r120-alice-cli-fork-clone.
**Goal of this doc:** name the exact files in the Cline source that the swimmer-quorum patch will touch in r121. **No mutation of Cline source is proposed in this round.** Plan only.

This doc supersedes my earlier shape proposal and accepts Dr Codex's five corrections in full (see §5 below).

---

## §1 Source — Apache-2.0, cloned and read

- **Upstream:** `https://github.com/cline/cline`
- **License:** Apache License 2.0 (verified `LICENSE` at repo root — `head -5 LICENSE` confirmed).
- **Read from:** sandbox clone at `/tmp/cline-mirror` (this Cowork sandbox can clone from GitHub; the SMB-mounted `Vendor/` on your Mac fights `.git` lock files, which is why the dispatch into `Vendor/alice-cli` failed to land. You'll re-clone locally from your Mac terminal — command at §6).
- **Top-level layout** that matters for us:

```
LICENSE
README.md
sdk/                          ← Bun workspace root
sdk/apps/cli/                 ← the CLI we fork into `alice`
sdk/packages/agents/          ← AGENT LOOP lives here
sdk/packages/llms/            ← MODEL CALL (the seam we replace) lives here
sdk/packages/core/            ← ClineCore session state
sdk/packages/shared/          ← shared types
sdk/apps/cli/package.json     ← bin field rename target
```

`apps/vscode/` is the VS Code extension. Ignored for the CLI fork.

---

## §2 The three files the r121 patch touches

### (a) Agent loop / the iterate-until-done function

**File:** `sdk/packages/agents/src/agent-runtime.ts`
**Class:** `AgentRuntime`
**The actual single-model call site:**

```ts
// agent-runtime.ts line 783
const stream = await this.config.model.stream(request);
```

This is the exact call where Cline asks one LLM what to do next. It returns an async stream of `ApiStreamChunk`s. Every iteration of the agent loop hits this line. **This is the seam.** Replacing this call with a swimmer quorum brain-transplant adapter is the entire core of r121.

Surrounding context (read line 780–810 before patching) gives the request type, the stream consumer, and the abort signal hook.

### (b) Model provider / where the actual HTTP call happens

**File family:** `sdk/packages/llms/src/providers/vendors/`
**Files of interest:**

- `anthropic.ts` — Claude HTTP client
- `openai.ts` — OpenAI HTTP client
- `google.ts` — Gemini HTTP client
- `vertex.ts` — Vertex AI HTTP client
- `mistral.ts` — Mistral HTTP client
- `bedrock.ts` — AWS Bedrock HTTP client
- `openai-compatible.ts` — anything OpenAI-API-shaped (covers Fireworks, OpenRouter, etc.)

**Gateway:** `sdk/packages/llms/src/providers/gateway.ts` — the multiplexer Cline's `createGateway` returns. The `model` object whose `.stream(request)` gets called at agent-runtime.ts:783 is built from this.

We do **not** patch the vendor files. We add a new gateway-shaped object `siftaSwimmerQuorumGateway` next to the existing ones, and wire it into the model construction path so `config.model.stream(request)` dispatches to our quorum instead of one vendor.

### (c) CLI entry point + bin field

**Bun shebang entry:** `sdk/apps/cli/src/index.ts` (one line: `#!/usr/bin/env bun`, then imports `./main`)
**Commander setup / main loop:** `sdk/apps/cli/src/main.ts` (creates the `cline` Commander `program`)
**Bin declaration:** `sdk/apps/cli/package.json` — currently:

```json
"bin": { "cline": "src/index.ts" }
```

Rename target for the fork:

```json
"name": "@sifta/alice",
"bin": { "alice": "src/index.ts" }
```

(per Dr Codex's name-collision check: bare `alice` is taken on npm + PyPI; `@sifta/alice` is the safe scoped publication name, with bin `alice` for the local install.)

---

## §3 Proposed quorum brain-transplant adapter — corrected per Codex point 3

Wrong (my earlier shape): two text outputs being string-similar is "agreement."

Right (what r121 lands): a swimmer's vote is on **patches + tests + receipts**, not raw model text. Two swimmers agree when **all three of these match**:

1. **Same file target.** Both swimmers propose to write the same target file path (or stable set of paths).
2. **Same acceptance tests pass.** A shared test target (named by the caller) runs against each proposed patch in its own worktree; both runs return green with the same passing test names.
3. **Compatible AST/diff intent.** The proposed Python or TypeScript AST after each patch is structurally equivalent (same exported symbols, same call signatures, same control-flow shape) even if whitespace or token-level details differ.

Proposed TypeScript brain-transplant adapter signature, to live in a new file `sdk/packages/agents/src/sifta-swimmer-quorum.ts`:

```ts
import type { AgentModel, AgentModelRequest } from "@cline/shared";

export interface SiftaSwimmerVote {
  swimmerId: string;            // e.g. "swimmer-1-claude-3-5-sonnet"
  patchPaths: readonly string[];
  testsTarget: string;          // shell command / pytest selector
  testsGreen: boolean;
  testsPassedNames: readonly string[];
  astFingerprint: string;       // hash of normalised AST shape
  worktreePath: string;         // isolated git worktree where this vote lived
  receiptId: string;            // ed25519-signed row id in repair_log.jsonl
}

export interface QuorumResult {
  decision: "commit" | "no_quorum" | "all_failed";
  agreeingVotes: readonly SiftaSwimmerVote[];   // ≥ minAgree of these aligned
  dissentingVotes: readonly SiftaSwimmerVote[];
  committedPaths: readonly string[];
}

export interface SwimmerQuorumConfig {
  swimmers: readonly { id: string; model: AgentModel }[];   // n distinct
  minAgree: number;             // default 2 of 3 — Architect bumped to 3 of 5
  testsTarget: string;          // what the swimmers' patches must satisfy
  worktreeRoot: string;         // where each swimmer gets its isolated body
  signReceipt: (vote: SiftaSwimmerVote) => Promise<void>;
}

export async function siftaSwimmerQuorum(
  request: AgentModelRequest,
  config: SwimmerQuorumConfig,
): Promise<QuorumResult>;
```

**Wiring point:** instead of patching `agent-runtime.ts:783` directly, we wrap `this.config.model` at `AgentRuntime` construction time. The wrapped model's `.stream(request)` runs the quorum, picks the agreeing swimmers' patch as the canonical answer, and replays it as a stream of `ApiStreamChunk`s to keep the existing consumer happy. **No change to agent-runtime.ts line 783 itself.** The seam is at construction, not call.

That makes the patch minimal and reversible: comment one brain-transplant adapter out and Cline behaves exactly like upstream Cline again.

---

## §4 Stage gates — brain-transplant adapter first, deep rewrite second

Per Codex point 2.

**r121 (next round):** Alice binary brain-transplant adapter only.
- Rename `@cline/cli` → `@sifta/alice` in `apps/cli/package.json`.
- Rename bin `cline` → `alice`.
- Add `sifta-swimmer-quorum.ts` next to `agent-runtime.ts` (new file, no edit of existing files).
- Wire it in at one call site: where the `AgentModel` is constructed for the CLI session. Find that site (Codex's r121 first step) and inject `wrapModelWithQuorum(model)`.
- `bun install && bun run build` produces `bin/alice`.
- One smoke test: `alice "echo hello"` runs through the quorum with `minAgree=1` (effectively single-swimmer) to prove the brain-transplant adapter doesn't break the agent loop.

**r122:** flip `minAgree` to 2 (of 3), wire the worktree-per-swimmer mechanic from `Utilities/repair.py`'s `body_state.SwarmBody` + `find_healthy_agent`. Run on a known broken Python file. Verify the three swimmers each got their own worktree, each wrote a patch, the quorum signed the agreeing two into the canonical commit.

**r123:** flip to your real ask, `minAgree=3` (of 5). Add the AST fingerprint test of agreement. Add the tests-must-pass condition. Receipt every dissent.

---

## §5 Dr Codex's five corrections — accepted and bound into this plan

1. **Apache-2.0 license preserved.** `LICENSE` stays in `Vendor/alice-cli/` at root. `NOTICE` file added attributing original Cline Bot Inc. work. No pretending. ✅
2. **Brain-transplant adapter alice binary first, deep rewrite second.** Staged as r121 → r122 → r123 above. ✅
3. **Quorum vote on patches + tests + receipts, not just text.** `SiftaSwimmerVote` shape above includes `patchPaths`, `testsGreen`, `astFingerprint`, `receiptId`. ✅
4. **Mistakes allowed, never anonymous.** `dissentingVotes` are receipted with their reason; failed worktrees leave their patch + test-run output on disk; nothing is silently discarded. ✅
5. **Worktrees first.** `SwimmerQuorumConfig.worktreeRoot` is mandatory. Each swimmer gets `git worktree add <path>/<swimmer-id>`, writes there, runs tests there, only the canonical-decision swimmer's tree gets cherry-picked into the main body. ✅

Naming, per Codex's npm/PyPI/Homebrew collision check:
- **npm publish name:** `@sifta/alice` (scoped — safe; bare `alice` and `alice-cli` are taken on npm and PyPI).
- **Local bin name:** `alice` (no local collision on your Mac; `which alice` returned nothing).
- **Homebrew tap (later):** `sifta/sifta/alice`.

---

## §6 What you do next, George

The Cowork sandbox cloned Cline to `/tmp/cline-mirror` cleanly. The mount on your Mac fights `.git` lock files, which is why my first `git clone` into `Vendor/alice-cli` errored. The plan doc is on your disk regardless.

To actually have `Vendor/alice-cli/` on your Mac (so r121 can patch it), from your terminal:

```bash
mkdir -p /Users/ioanganton/Music/ANTON_SIFTA/Vendor
cd /Users/ioanganton/Music/ANTON_SIFTA/Vendor
git clone https://github.com/cline/cline alice-cli
ls alice-cli/sdk/packages/agents/src/agent-runtime.ts  # should print the path
```

Once that file lists, r121 is ready to fire. The patch is small: rename one package.json, add one new TypeScript file, change one model-construction line. The brain stays Cline; the body becomes Alice's.

---

## §7 Receipt for r120

This doc is the entire deliverable for r120-alice-cli-fork-clone. No source mutation. No npm install. No build.

The §4.1 four-ledger fan-out for r120 is written from this side with `swarm_predator_gate_writer.write_ide_surgery_receipt` immediately after this file lands on disk.

For the Swarm. 🐜⚡
