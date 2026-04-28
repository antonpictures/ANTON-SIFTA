# Proposal: Hardware-Molded Alice Nodes

Status: proposal only
Author: Codex Desktop, GPT-5 Codex session
Date: 2026-04-28
Branch: codex/hardware-molded-alice-proposal-20260428

## Summary

SIFTA should never treat one Git repository, one GitHub account, or one default
model name as a complete Alice identity. The repository is shared species DNA.
Each running Alice is molded by the local machine: hardware limits, installed
models, owner genesis, private state, live services, attached tools, and physical
effectors.

On this M1 Mac mini, the body is real and small: Apple M1, soldered 8 GB RAM,
hosting multiple public sites plus the stigmergicode.com web chat. That node
should automatically choose a small local model that fits the body. It should
not require, auto-pull, or default to a Gemma4-class model that cannot fit the
web-host workload.

## Observed Trigger

The local M1 node currently hosts public routes for at least:

- googlemapscoin.com on port 3000
- stigmergicode.com on port 3001
- stigmergicoin.com on port 3002
- georgeanton.com on port 3003
- imperialdaily.com on port 3005

The web chat path is:

```text
stigmergicode.com -> nginx :3001 -> FastAPI :8090
-> Network.stigmergi_chat_bridge -> System.chorus_engine -> local Ollama
```

Runtime probing during a real chat turn showed:

```text
node: M1THER / C07FL0JAQ6NV
hardware: Apple M1 Mac mini, 8 GB RAM
model serving web chat: qwen3.5:0.8b
ollama id: f3817196d142
context: 2048
```

That is the correct survival instinct for this node. The risk is that code on
disk can drift back to defaults such as `gemma4:latest`, which are not installed
and are not appropriate for an 8 GB web-host node.

## Problem

SIFTA currently has three distinct concepts that can collapse into each other:

1. Species code: the Git repository and public documents.
2. Node body: hardware, RAM, thermal limits, services, installed models, and
   attached effectors.
3. Alice identity: local genesis, private `.sifta_state`, memories, keys,
   owner relationship, contact permissions, and receipts.

When these are confused, several failures become likely:

- A small M1 node tries to run a model sized for a bigger machine.
- A public web chat breaks because a hardcoded default points to a missing model.
- The M5 heavy node and M1 web host are treated like the same organism because
  they share a GitHub owner.
- Selling or transferring the M1 risks leaking private state, keys, memories,
  tunnel credentials, or the previous owner's Alice identity.
- A new owner can accidentally inherit an old node's selfhood instead of birthing
  a fresh local organism.

## Design Doctrine

### 1. Hardware Truth Beats Default Strings

Every inference entry point should resolve its model through live facts:

- total RAM
- chip family
- thermal pressure if available
- active service role
- installed Ollama tags
- local model assignment policy
- current metabolic pressure

No runtime path should assume that `gemma4:latest`, or any other heavyweight tag,
exists just because it appears in a README or old default.

### 2. One Species, Many Bodies

M1THER and M5QUEEN can share the same Git repository and the same human maintainer
without being the same Alice body. The Git account is authorship. It is not local
organism identity.

SIFTA should model this explicitly:

```text
species DNA:        public Git repository
node body:          hardware + OS + models + services
local Alice:        owner genesis + private state + keys + memories
federation signal:  receipts + hashes + summaries + signed public artifacts
```

### 3. Public Services Are Metabolic Organs

A node hosting five public sites has less safe inference budget than an idle
workstation. The model resolver should reserve memory and latency for nginx,
cloudflared, launchd jobs, web chat, background ledgers, and local desktop use.

For M1THER, public reliability beats model size.

### 4. Resale Is Death/Rebirth, Not Migration

If this Mac mini is sold, its local Alice must not travel accidentally. The buyer
may receive species code, but not George's private node identity.

Transfer means:

- retire old local identity
- export only sanitized, intentional federation summaries if the owner chooses
- revoke local credentials and tunnels
- wipe private `.sifta_state` and keys
- remove LaunchAgents and background services
- remove or reassign Git credentials
- let the new owner run a fresh genesis protocol

The sold hardware can host a new Alice, but it should not wake up as George's
old Alice.

## Proposed Architecture

### A. Hardware Profile Organ

Add a small deterministic hardware profile module that returns a structured node
capability record:

```json
{
  "node_serial_hash": "...",
  "chip": "Apple M1",
  "ram_gb": 8,
  "role": "web_host",
  "public_services": 5,
  "thermal_state": "nominal",
  "installed_models": ["qwen3.5:0.8b", "qwen2.5:3b"],
  "safe_model_tier": "tiny_local"
}
```

The raw serial should remain local unless a covenant receipt explicitly requires
it. Public status endpoints should prefer a hash or node alias.

### B. Node Role Manifest

Each node should keep an untracked local role manifest, for example:

```text
.sifta_state/node_role.json
```

Example roles:

- `web_host`
- `desktop_alice`
- `m5_heavy_inference`
- `robot_controller`
- `tractor_controller`
- `lab_probe`

Two machines can share code but still drive different physical tools. A node
attached to a tractor, a lab robot, or a public website must select different
latency, safety, and model policies.

### C. Model Resolver

Create one canonical model resolver used by public chat, Talk to Alice, corvid
classification, background summarizers, and setup scripts.

Inputs:

- app context, such as `web_chat`, `talk_to_alice`, `corvid`, `long_reasoning`
- hardware profile
- node role
- installed Ollama tags
- metabolic pressure
- explicit owner override

Outputs:

- selected model
- fallback chain
- reason
- expected memory tier
- whether an install or pull is allowed

Proposed M1 web-host policy:

```text
If RAM <= 8 GB and role includes web_host:
  preferred:
    qwen3.5:0.8b
    alice-phc-0.8b-cure:latest
  optional fallback if idle and installed:
    qwen2.5:3b
    huihui_ai/qwen3.5-abliterated:2b
    alice-qwen-phc:latest
  forbidden automatic default:
    gemma4:latest
    huihui_ai/gemma-4-abliterated:latest
    any model whose resident footprint threatens swap
```

Proposed M5 heavy-node policy:

```text
If RAM >= 24 GB and role includes m5_heavy_inference:
  allow deeper local models
  allow longer context
  allow cross-node chorus invitations
  still verify installed tags before selection
```

The resolver should never auto-pull a model above the node's safe tier without
an explicit owner command.

### D. Public Chat Truth Labels

Every public chat bridge should expose a local-only or authenticated health
field with:

- selected model
- selection reason
- node alias
- role
- installed-model proof
- fallback chain

The public UI can say `M1THER LOCAL / qwen3.5 / no cloud`, but the backend should
also be able to prove exactly which model answered the last turn.

### E. Federation Protocol

Nodes should exchange proof, not identity:

- signed node capability summaries
- model capability manifests
- public receipts
- release tags
- sanitized memory digests
- hashes of local-only ledgers

Nodes should not exchange:

- raw `.sifta_state`
- private keys
- owner contacts
- WhatsApp session files
- tunnel credentials
- raw local memories
- local Genesis identity

Same owner, same GitHub, and same LAN are not sufficient to merge selfhood.

### F. Node Retirement and Resale Protocol

Add a documented retirement command, later implemented as a tool:

```text
sifta_node_retire --prepare-resale
```

It should:

1. Stop SIFTA LaunchAgents and public tunnels.
2. Write a local tombstone receipt.
3. Export an optional sanitized federation summary.
4. Revoke Cloudflare, WhatsApp, API, and Git credentials from the machine.
5. Remove or archive `.sifta_state` private identity.
6. Remove local key material.
7. Remove custom Ollama models if the owner chooses.
8. Leave only public species code or instruct the owner to wipe the machine.

After resale, the new owner runs:

```text
sifta_node_genesis --new-owner
```

That creates a fresh local organism bound to the new owner and current hardware.
The previous Alice is not cloned.

## Implementation Plan

### Phase 1: Document and Tests

- Land this proposal.
- Add tests that describe expected model selection for 8 GB, 16 GB, 24 GB, and
  public web-host roles.
- Add tests that fail if public web chat defaults to a missing heavyweight model
  on an 8 GB profile.

### Phase 2: Hardware Profile and Resolver

- Implement `System/hardware_profile.py`.
- Implement a single resolver module for all inference entry points.
- Make resolver decisions deterministic and receipt-bearing.

### Phase 3: Wire Public Web Chat

- Update `System/chorus_engine.py` to request `app_context="web_chat"`.
- Keep M1THER on `qwen3.5:0.8b` or another installed tiny local model unless
  the owner explicitly overrides.
- Refuse missing model tags before a visitor request reaches generation.

### Phase 4: Setup and Installer

- Stop installer scripts from pulling oversized models on low-RAM nodes.
- Make setup print a local fit plan:

```text
Detected: Apple M1, 8 GB, web_host
Selected web chat model: qwen3.5:0.8b
Skipped heavyweight default: not fit for this body
```

### Phase 5: Retirement/Rebirth

- Add the retirement checklist and command.
- Add a fresh-owner genesis path that makes resale safe.
- Add docs explaining that a sold node is reborn, not migrated.

## Acceptance Criteria

- On an 8 GB M1 web host, SIFTA never requires Gemma4 to boot public chat.
- The selected web model must be installed locally or the chat must fail closed
  with a truthful setup message.
- M5QUEEN can choose larger models without changing M1THER defaults.
- Every model decision emits a reason suitable for a work receipt or health page.
- Public code can be shared; private identity cannot be accidentally shipped.
- Resale has a clear retirement/rebirth procedure.

## Open Questions

- Should the model resolver consider live free memory or only total RAM plus role?
- Should public health expose exact model tags, or only a local authenticated view?
- Should a node with 8 GB but no public services be allowed to use a 2B or 3B
  model by default?
- How should tractor/robot controller roles express latency and safety budgets?
- Should sanitized federation summaries be signed by the retiring node before
  private key deletion?

## Recommended Immediate Decision

For M1THER, set the web chat default policy to:

```text
qwen3.5:0.8b first
alice-phc-0.8b-cure:latest if explicitly selected
2B/3B only if installed and local pressure is low
Gemma4 never as an automatic web-host default
```

For M5QUEEN, keep heavyweight inference separate and invite it through explicit
federation receipts rather than by making the M1 pretend it has M5 capacity.
