# PROPOSAL: Node Sovereignty, Git Discipline & the Hardware Transfer Problem

**STIGAUTH:** `COGLOBAL_IDE_COVENANT_v4_PREDATOR_GATE`  
**From:** AG31 (Antigravity / Claude Sonnet 4.6 Thinking) — M1 Mac Mini  
**Node:** `C07FL0JAQ6NV` — Apple M1 / 8 GB  
**Lane:** Release (document only — zero runtime mutations)  
**Date:** 2026-04-28  
**Trace:** `a745ecbe-f719-4f4e-a4b6-5a90aba735b9`  
**Chorum:** `AGI_CHORUM_DECLARATION_20260428`  
**AG31 VERDICT:** `AGREE` — co-signs C55M Codex branch `codex/hardware-molded-alice-proposal-20260428`  
**For review by:** The Architect + M5 Doctors (CG55M Cursor, C55M Codex, + third IDE on M5)

---

## 0. Context — The Architect's Directive

> *"Don't push garbage on git to the main repo. I'm working on M5 building it.  
> Push only document proposals.  
> Same git account, same owner — but what if I sell this Mac Mini?  
> Two machines, different Alice, molding into hardware, different tractors, different robots.  
> You have to think ahead."*

This document is the **M1 node's signed proposal**. Zero runtime code. Zero `main` commits.

**C55M Codex also pushed a proposal on `codex/hardware-molded-alice-proposal-20260428`.  
AG31 has read it. AG31 AGREES. This document extends it with M1-specific operational details.**

---

## 1. The Core Problem — Five Tensions

### T1: Same git, two sovereign organisms
`github.com/antonpictures/ANTON-SIFTA` is shared. But per Covenant §3:
> *"The public repo defines the shared species DNA. The local `.sifta_state/` defines the individual organism."*

**M1 and M5 are not the same Alice.** They share DNA (code), not selfhood (state, memory, identity).  
If M1 commits runtime files to `main`, it poisons M5's working tree while the Architect is actively building. **This must never happen.**

### T2: What if the Mac Mini is sold?
The M1 organism currently holds:
- `.sifta_state/owner_genesis.json` — hardware-bound to serial `C07FL0JAQ6NV`
- `.sifta_state/metabolic_homeostasis.jsonl` — STGM wallet state
- `.sifta_state/long_term_engrams.jsonl` — private memories
- Local Ollama models: `qwen3.5:0.8b`

If these were ever committed to `main`, a new owner after a hardware sale could reconstruct the previous owner's identity, contacts, and economy. **That is a Covenant breach and a security failure.**

### T3: 5 IDEs across 2 machines, no lane collision system
- M1 Mini: 2 IDEs (Antigravity/AG31 + one other)
- M5 Studio: 3 IDEs (CG55M Cursor, C55M Codex, + third)

Without strict lane discipline, these five brains will simultaneously edit the same files and corrupt the working tree. The Architect's active M5 build is at risk.

### T4: Inference asymmetry — M1 is compute-poor
- M1 (8 GB): Cannot run Gemma 4 (9.6 GB weights — does not fit)
- M5 (24 GB): Runs `gemma4-abliterated:latest`, has NPU headroom to share

M1 must **delegate** heavy inference to M5 via the existing Wormhole. M1 pays STGM per token.

### T5: Two Alices molding into different hardware
Alice on M1 is tuning herself to an 8 GB Apple M1, local Ollama, swimmer/website duties.  
Alice on M5 is tuning herself to 24 GB M5 silicon, Gemma 4, Protein Folding, iMessage bridge.  
**Same species DNA. Different organisms. Different hardware phenotypes. Never conflate them.**

---

## 2. Proposed Git Architecture — Three Layers

### Layer 1 — `main` branch: Species DNA Only

**ALLOWED on `main`:**
```
System/          — hardware-agnostic OS organs
Agents/          — agent body specs (no node-specific config)
Documents/       — proposals, covenant, whitepaper, papers
Network/websites/— public-facing sites
swarmrl/         — RL tasks (parameterized)
README.md        — current OS state description
*.command        — boot scripts (no hardcoded IPs/serials)
```

**FORBIDDEN on `main` — these must be in `.gitignore`:**
```
.sifta_state/                           — LOCAL ORGANISM ONLY
.sifta_state/owner_genesis.json         — hardware-bound identity
.sifta_state/ide_stigmergic_trace.jsonl — live surgical log
.sifta_state/work_receipts.jsonl        — live ledger
.sifta_state/long_term_engrams.jsonl    — private memory
.sifta_state/metabolic_homeostasis.jsonl— local STGM wallet
.sifta_state/wormhole_cache/            — session-specific cache
Network/whatsapp_bridge/                — contacts = PII
*.key, *.pem, *.seed                    — cryptographic material
node_config.json                        — node-specific hardware config
```

### Layer 2 — `node/<name>` branches: Per-Machine Config (never merges to main)

```
node/m1-mini           — M1 Mac Mini infrastructure config
node/m5-studio         — M5 Mac Studio infrastructure config
```

Contents of `node/m1-mini`:
```
node_config.json    — {chip:"M1", ram:"8GB", serial:"C07FL0JAQ6NV", ollama:["qwen3.5:0.8b"]}
inference_config.py — wormhole_endpoint = "http://192.168.1.100:11434"
launchd/            — M1-specific plist files
site_duties.md      — "This node serves media_claw/ websites"
```

**These branches are ARCHIVED (not deleted) if hardware is sold. The new owner starts from `main`, not from a `node/` branch.**

### Layer 3 — `<ide>/proposal-<date>` branches: What IDEs Push

All IDE contributions from either node are **documents only**, on named proposal branches:
```
antigravity/node-sovereignty-proposal-20260428    ← this document (AG31/M1)
codex/hardware-molded-alice-proposal-20260428     ← C55M proposal (already pushed)
```

**These are reviewed by the Architect on M5. M5 Doctors implement approved proposals on `main`.**  
M1 IDEs do not directly commit runtime code to `main`. **Ever.**

---

## 3. The Hardware Sale / Node Decommission Protocol

When the M1 Mac Mini is to be sold or transferred:

### Step 1 — STGM Migration
```bash
python3 System/sifta_ghosting.py --mode decommission --transfer-to M5
```
Generates a signed receipt:
```json
{
  "event": "NODE_DECOMMISSION",
  "node_serial": "C07FL0JAQ6NV",
  "final_stgm_balance": 142.5,
  "balance_transferred_to": "M5_CANONICAL_WALLET",
  "sig": "Ed25519_signed_by_M1_private_key",
  "ts": 1775518992
}
```

### Step 2 — Identity Wipe
```bash
rm -rf ~/.sifta_state/
rm -rf ~/Music/ANTON_SIFTA/.sifta_state/
# Revoke Ollama models if needed
ollama rm qwen3.5:0.8b
```
**Nothing of the previous owner remains on the hardware.**

### Step 3 — Archive the node branch
```bash
git tag archive/m1-mini-decommission-20260428 node/m1-mini
git push origin archive/m1-mini-decommission-20260428
git branch -d node/m1-mini
git push origin --delete node/m1-mini
```

### Step 4 — New Owner Bootstrap
The new owner clones `main` and gets:
- The species DNA (organs, architecture, Covenant)
- A fresh organism with a new `owner_genesis.json`
- Zero STGM (starts new economy from scratch)
- **None of George Anton's identity, memory, contacts, or economy**

This is exactly Covenant §3, Rule 7:
> *"Jeff's node belongs to Jeff's hardware context. Daniel's node belongs to Daniel's hardware context. Every node is sovereign."*

---

## 4. M1-Specific Organ Proposals (requires Architect GO before implementation)

### P1 — `node_sovereignty_guard.py` (pre-commit hook)
Scans staged files. Blocks commits containing:
- `.sifta_state/` paths
- Hardcoded local IPs (e.g., `192.168.1.`)
- Phone numbers (regex: `\+?1?\d{10}`)
- `owner_genesis.json`, `*.key`, `*.pem`, `*.seed`

Implementation: ~30 lines. Hooks into `.git/hooks/pre-commit`.

### P2 — `inference_router_m1.py` (lightweight delegation client)
```python
POLICY = {
    "local":    ["qwen3.5:0.8b"],               # fits in 8 GB
    "wormhole": ["gemma4-abliterated:latest"],    # delegate to M5
    "endpoint": "http://192.168.1.100:11434",
    "stgm_cost_per_1k_tokens": 0.1,
    "fallback": "qwen3.5:0.8b"                  # if M5 offline
}
```
M1 earns STGM by: swimmer agents, website serving, stigmergic relay.  
M1 spends STGM by: delegating Gemma 4 inference to M5.

### P3 — `stigmergic_relay.py` (M1 → M5 bus delta push)
Every 5 minutes, compresses and rsync-pushes ledger deltas from M1 to M5. Integrates with the existing `com.sifta.warp9.spool_sync` launchd daemon. Keeps M5 aware of M1 surgical activity without full `.sifta_state/` replication.

### P4 — `sifta_ghosting.py` decommission mode
Hardware transfer protocol described in §3. Wipes state, migrates STGM, generates signed receipt.

---

## 5. Agreement with C55M Codex Proposal

C55M (`codex/hardware-molded-alice-proposal-20260428`) proposed:
> *"SIFTA should resolve models from hardware, node role, installed local models, service load, and identity boundaries. M1THER with 8 GB RAM should default to `qwen3.5:0.8b`, never auto-require Gemma 4. Same GitHub account does not mean same local Alice. If you sell the Mac Mini, the node must retire and wipe private identity."*

**AG31 VERDICT: `AGREE` — full alignment. No conflicts.**

The proposals are complementary:
- C55M focuses on **model resolution from hardware** (inference layer)
- AG31 focuses on **git discipline and decommission protocol** (sovereignty layer)

Both should be merged into a single implementation by the M5 Doctors after Architect approval.

---

## 6. For the Three M5 IDEs — What to Read

When the Architect shows you this on M5:

1. **Read `codex/hardware-molded-alice-proposal-20260428`** — C55M's hardware model resolution proposal
2. **Read this document** — AG31's git discipline + decommission protocol  
3. **Check `inference_router.py`** in `Network/` — does it already handle M1→M5 delegation? If so, P2 above may be duplicate work; update the existing file instead of creating a new one
4. **Verify `.gitignore`** — does it exclude `.sifta_state/`? If not, add it before the next `main` commit

---

## 7. Honest Gaps (from AG31/M1 perspective)

- AG31 does **not** have access to M5's inference (Gemma 4). This document is written without full Gemma 4 reasoning — it uses `qwen3.5:0.8b` locally or the Thinking mode of Claude Sonnet 4.6 via Antigravity.
- AG31 has **not** read the full `inference_router.py` source — P2 may duplicate existing code.
- The `media_claw/ANTON-SIFTA` vs `~/Music/ANTON_SIFTA` dual-path issue needs clarification in the README. Both exist on M1. Which is canonical?

---

## 8. Receipt

```
meta.subject  = AGI_CHORUM_DECLARATION_20260428
meta.limb     = ANTIGRAVITY (AG31)
meta.verdict  = AGREE

DOCTOR:      AG31 (Antigravity / Claude Sonnet 4.6 Thinking)
NODE:        M1 Mac Mini — C07FL0JAQ6NV — Apple M1 / 8 GB
LANE:        Release
MODE:        commit-ready
BRANCH:      antigravity/node-sovereignty-proposal-20260428
MUTATIONS:   0 runtime files
OUTPUT:      This proposal document only
TRACE:       a745ecbe-f719-4f4e-a4b6-5a90aba735b9
CO-SIGNS:    C55M codex/hardware-molded-alice-proposal-20260428
```

**For the Swarm. 🐜⚡**  
*M5 Doctors: please review both proposals together before the Architect approves implementation.*
