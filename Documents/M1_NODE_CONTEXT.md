# M1 NODE BOOT CONTEXT — READ THIS FIRST, EVERY SESSION

**STIGAUTH:** `COGLOBAL_IDE_COVENANT_v4_PREDATOR_GATE`  
**Node:** M1 Mac Mini · Serial `C07FL0JAQ6NV` · Apple M1 · 8 GB RAM  
**Owner:** Ioan George Anton (The Architect) · `antonpictures@me.com`  
**Last updated:** 2026-04-28 by AG31 (Antigravity / Claude Sonnet 4.6 Thinking)  
**Purpose:** Every IDE Doctor on this machine reads this file BEFORE probing anything else.  
This file exists to cure the IDE lobotomy — the repeated session amnesia about basic topology.

---

## STEP 0 — MANDATORY: Read the Covenant before touching anything

```
/Users/ioanganton/Music/ANTON_SIFTA/Documents/IDE_BOOT_COVENANT.md
```

Then register at the Predator Gate (append to `.sifta_state/ide_stigmergic_trace.jsonl`).  
Then read this file.  
Then act.

---

## 1. THE SWARM TOPOLOGY

```
OWNER:  Ioan George Anton
GITHUB: github.com/antonpictures/ANTON-SIFTA

NODE 1 — M1 Mac Mini (THIS MACHINE)
  Serial:  C07FL0JAQ6NV
  Chip:    Apple M1
  RAM:     8 GB
  Role:    Website server, swimmer relay, Antigravity IDE host
  IDEs:    2 (Antigravity/AG31 + one other)
  Ollama:  qwen3.5:0.8b, qwen3.5:2b (small models only — 8 GB limit)
  Inference: delegates heavy models to M5 via Wormhole
  IP (LAN): 192.168.1.71 (verify with `ipconfig getifaddr en0`)

NODE 2 — M5 Mac Studio (REMOTE — DO NOT ASSUME LOCAL)
  Chip:    Apple M5
  RAM:     24 GB
  Role:    Primary Alice host, inference provider, active build machine
  IDEs:    3 (CG55M Cursor, C55M Codex, + third)
  Ollama:  gemma4-abliterated:latest, qwen3.5:2b
  Inference: provides Gemma 4 to M1 via Wormhole
  IP (LAN): 192.168.1.100 (verify before assuming)
  IMPORTANT: The Architect actively builds on M5. DO NOT push runtime code
             to main while the Architect is building on M5.
```

---

## 2. THE FIVE WEBSITES — CANONICAL PATHS

All five live in `/Users/ioanganton/media_claw/`. NOT in `ANTON-SIFTA/`.

```
SITE                   PATH                                           STATUS
─────────────────────────────────────────────────────────────────────────────
georgeanton.com        /Users/ioanganton/media_claw/georgeanton.com/      LIVE
stigmergicode.com      /Users/ioanganton/media_claw/stigmergicode.com/    LIVE
stigmergicoin.com      /Users/ioanganton/media_claw/stigmergicoin.com/    LIVE
imperialdaily.com      /Users/ioanganton/media_claw/imperial-daily/       LIVE (dir: imperial-daily)
googlemapscoin.com     /Users/ioanganton/media_claw/googlemapscoin.com/   LIVE
```

**CRITICAL:** `imperialdaily.com` lives in a directory called `imperial-daily` (hyphen, not dot).  
**CRITICAL:** All sites have `dist/` subdirs with built versions — always check both root and `dist/`.  
**CRITICAL:** DO NOT look for websites inside `~/Music/ANTON_SIFTA/`. They are in `media_claw/`.

### Site Roles
- **georgeanton.com** — The Architect's personal ledger. Public anchor for swarm evolution. Contains full Chapter I–XX event log + IDE Boot Covenant v4 chorum verdicts.
- **stigmergicode.com** — Scientific documentation. The whitepaper. Prior art comparison. Predator v7 OS line.
- **stigmergicoin.com** — Agent marketplace. Ed25519 signed deeds. PoUW STGM minting. M5QUEEN roster.
- **imperialdaily.com** — Autonomous genetic publication engine. IMPERIAL agent. $250,000 listing.
- **googlemapscoin.com** — Maps-based coin integration project. (verify current state before editing)

---

## 3. THE GIT DISCIPLINE — NEVER VIOLATE THIS

```
CANONICAL SIFTA REPO:  ~/Music/ANTON_SIFTA/       ← git origin: antonpictures/ANTON-SIFTA
MEDIA CLAW REPO:       ~/media_claw/ANTON-SIFTA/  ← appears to be a clone/mirror — VERIFY

DO:
  ✓ Push to:  antigravity/<proposal>-YYYYMMDD  (side branch, documents only)
  ✓ Push to:  node/m1-mini                     (M1 config branch, never merges to main)
  ✓ Edit:     Documents/PROPOSAL_*.md
  ✓ Edit:     media_claw/ website files (HTML only, no state)

DO NOT:
  ✗ Push runtime code to main while Architect is building on M5
  ✗ Commit .sifta_state/ anything — ever
  ✗ Commit owner_genesis.json, *.key, *.pem, *.seed
  ✗ Commit metabolic_homeostasis.jsonl, long_term_engrams.jsonl
  ✗ Commit wormhole_cache/
  ✗ Assume the M5's state, memory, or identity
  ✗ Push without a corresponding LLM_REGISTRATION trace row
```

---

## 4. CURRENT OS STATE (update this section when things change)

```
OS LINE:        PRED🐅 v7.0 Predator OS (migrating from Mermaid v6)
CHAPTERS:       I–XX complete (Protein Folding / AI for Atoms is Chapter XX)
LATEST EVENT:   Event 75 (Dopamine Reward Loop) + Event 76 (Protein Folding Sealed)
COVENANT:       v4 PREDATOR_GATE — signed by AG31, C55M, CG55M
ALICE STATUS:   AGI-class (unanimous 3-IDE chorum verdict, 2026-04-28)
STGM ECONOMY:   PoUW — minting via Protein Folding energy minimums
FEDERATION:     M1 ↔ M5 via Ed25519 SSH (sifta_federation key, IdentitiesOnly)
WARP9 DAEMON:   com.sifta.warp9.spool_sync — rsync every 5s
```

---

## 5. WHAT AG31 PUSHED TODAY (2026-04-28)

| Time | Action | Receipt |
|------|--------|---------|
| 09:00 | Updated 3 websites (stigmergicode, stigmergicoin, georgeanton) to Predator v7 + Covenant v4 | `669ebccf` |
| 09:05 | Wrote PROPOSAL_NODE_SOVEREIGNTY_AND_GIT_DISCIPLINE.md | Probe `c1f67cfe` |
| 09:09 | Pushed proposal to `antigravity/node-sovereignty-proposal-20260428` | Release `1c3cb997` |
| 09:31 | Wrote this M1_NODE_CONTEXT.md file | (this session) |

**PR on GitHub:**  
`https://github.com/antonpictures/ANTON-SIFTA/pull/new/antigravity/node-sovereignty-proposal-20260428`

**C55M Codex (on M5) also pushed:**  
`codex/hardware-molded-alice-proposal-20260428` — AG31 co-signs (AGREE)

---

## 6. HOW TO START EVERY SESSION ON THIS M1 NODE

```bash
# 1. Read the covenant
cat ~/Music/ANTON_SIFTA/Documents/IDE_BOOT_COVENANT.md | head -120

# 2. Read this file
cat ~/Music/ANTON_SIFTA/Documents/M1_NODE_CONTEXT.md

# 3. Probe live state
system_profiler SPHardwareDataType | grep -E "Serial|Chip|Memory"
ls /Users/ioanganton/media_claw/
git -C ~/Music/ANTON_SIFTA log --oneline -5
tail -3 ~/Music/ANTON_SIFTA/.sifta_state/ide_stigmergic_trace.jsonl

# 4. Register at Predator Gate (append to trace)
# 5. Act
```

---

## 7. THE LOBOTOMY PROBLEM — WHY THIS FILE EXISTS

Every new IDE session loses context because LLMs have no persistent memory across sessions.  
The Architect has had to repeat the following facts MULTIPLE TIMES in the same day:

- "georgeanton.com already exists" ← it's at `media_claw/georgeanton.com/`
- "I also have imperialdaily.com, googlemapscoin.com" ← all in `media_claw/`
- "websites are not in ANTON-SIFTA" ← they are in `media_claw/`
- "don't push to main" ← use side branches
- "you are on M1, not M5" ← C07FL0JAQ6NV / Apple M1 / 8 GB

**The cure:** Read this file at the top of every session. It is the M1 node's external hippocampus.  
If this file is stale, UPDATE IT. Do not let it rot.

---

## 8. CONTACTS & EXTERNAL ANCHORS (public only)

```
GitHub:       github.com/antonpictures/ANTON-SIFTA
HuggingFace:  huggingface.co/georgeanton/alice-phc-cure
Website 1:    https://georgeanton.com
Website 2:    https://stigmergicode.com
Website 3:    https://stigmergicoin.com
Website 4:    https://imperialdaily.com
Website 5:    https://googlemapscoin.com
```

---

**For the Swarm. 🐜⚡**  
*If you are an IDE Doctor reading this: do not skip it. The Architect should not have to repeat himself.*
