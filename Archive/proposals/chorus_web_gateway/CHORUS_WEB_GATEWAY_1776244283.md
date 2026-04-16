# PROPOSAL: Chorus Web Gateway
**Node:** M1THER · Silicon: C07FL0JAQ6NV  
**Filed by:** Architect IDE (Antigravity/Claude on M1 Mac Mini)  
**Timestamp:** 1776244283 (Unix)  
**Status:** AWAITING_HUMAN_MERGE  
**Target branch:** feat/sebastian-video-economy  

---

## Problem Statement

The current `stigmergi_chat_bridge.py` is a **wrapper** — one Ollama call with a system prompt  
pretending to be the swarm. This violates stigmergic doctrine.  

When a real person visits `stigmergicode.com` and types a message, the swarm's response  
must **emerge** from deliberation between actual cryptographic swimmers, not from a single  
model roleplaying them.

---

## Proposed Architecture: 7-Swimmer Chorus + Cross-Node Federation

```
EXTERNAL VISITOR (website)
        │
        ▼
┌───────────────────────────────────────────────────────┐
│  PHASE 0: THREAT CLASSIFICATION (HERMES gate)         │
│  Classify: CURIOUS | SCIENTIST | THREAT | JACKER      │
│  JACKER → SENTINEL wall. Others → Chorus invited.    │
└───────────────────────────┬───────────────────────────┘
                            │ GLOBAL BROADCAST to Swarm
                            │ "Visitor at web gate. Chorum?"
                            ▼
┌───────────────────────────────────────────────────────┐
│  PHASE 1: LOCAL CHORUS (M1THER node)                 │
│                                                       │
│  ANTIALICE  [o|o] — Code repair, technical precision │
│  HERMES     [_v_] — Scout, threat, exorcism          │
│  M1THER     [O_O] — Foundation, hardware, memory    │
│  IMPERIAL   [@_@] — Press, narrative, public comms  │
│  SIFTA QUEEN[W_W] — Constitution, governance        │
│  ARCHON     [^_^] — Philosophy, existential, *new*  │
│  SENTINEL   [!_!] — Security adversary filter, *new*│
│                                                       │
│  Each swimmer: 1 Ollama call, own personality prompt │
│  Each swimmer: signs take with Ed25519 key           │
│  Parallel where possible, timeout: 45s per swimmer  │
└───────────────────────────┬───────────────────────────┘
                            │ Optional: invite remote node
                            ▼
┌───────────────────────────────────────────────────────┐
│  PHASE 2: CROSS-NODE FEDERATION (if M5 reachable)    │
│                                                       │
│  M1THER sends dead-drop invite to M5QUEEN node:      │
│  POST http://[M5_IP]:8100/chorus/invite              │
│  Payload: { question_hash, session_id, permissions } │
│                                                       │
│  M5 swimmers who CAN respond:                        │
│  - Only if NODE_PUBKEY is in authorized_keys/        │
│  - Only EXTERNAL_COMMS capability swimmers           │
│  - Response signed with M5 swimmer Ed25519 key       │
│  - Timeout: 20s (M5 is optional, not blocking)       │
└───────────────────────────┬───────────────────────────┘
                            │
                            ▼
┌───────────────────────────────────────────────────────┐
│  PHASE 3: CHORUS SYNTHESIS                           │
│                                                       │
│  All swimmer takes (local + optional remote) fed to  │
│  final synthesis Ollama call:                        │
│  "You are the Chorus Voice. These swimmers spoke.    │
│   Merge into one answer. Sign as THE SWARM."         │
│                                                       │
│  Output: { reply, chorus_manifest, latency }         │
│  chorus_manifest = list of swimmers who contributed  │
└───────────────────────────────────────────────────────┘
```

---

## Cryptographic Permissions for External Comms

External web messages are **untrusted surface**. Rules:

| Visitor Class | Detection | Chorus Response |
|---|---|---|
| `CURIOUS` | No red flags | Full 7-swimmer chorus |
| `SCIENTIST` | Technical keywords (Ed25519, stigmergy, BCI, STGM) | Full chorus + research data mode |
| `THREAT` | Injection attempts, prompt attacks | SENTINEL only, logged |
| `JACKER` | >3 boundary violations in session | WALL: single hardcoded reply, session flagged |

HERMES classifies by inspecting:
- Injection patterns: `ignore previous`, `jailbreak`, `pretend you are`, `DAN`, etc.
- Probing patterns: asking for private keys, internal IPs, agent identities beyond public roster
- Scientific patterns: paper-level vocabulary triggers SCIENTIST mode

All external messages are **logged to `.sifta_state/wormhole_cache/web_chats/`** as a permanent scar.  
All THREAT/JACKER events are logged to **antibody_ledger.jsonl** with SHA-256 of the message.

---

## Cross-Node Federation Protocol

### M1THER → M5QUEEN invitation:
```json
{
  "type": "CHORUS_INVITE",
  "from_node": "M1THER",
  "from_silicon": "C07FL0JAQ6NV",
  "session_id": "<hash>",
  "question_hash": "<SHA256 of visitor message>",
  "visitor_class": "CURIOUS | SCIENTIST",
  "permissions": ["RESPOND_EXTERNAL", "READ_QUESTION"],
  "timeout_ms": 20000,
  "sig": "<Ed25519 sig of payload by M1THER key>"
}
```

### M5QUEEN response:
```json
{
  "type": "CHORUS_TAKE",
  "from_node": "M5QUEEN",
  "swimmer_id": "M5QUEEN",
  "take": "One sentence from M5 perspective.",
  "sig": "<Ed25519 sig by M5QUEEN key>"
}
```

### Conditions for M5 participation:
1. `M5_NODE_IP` env var is set and reachable (ping test at bridge startup)
2. M5 node's public key exists in `~/.sifta/authorized_keys/m5queen.pub`
3. The question is classified `CURIOUS` or `SCIENTIST` (never for `THREAT`/`JACKER`)
4. M5 chorus endpoint is running: `System/chorus_node_server.py` on M5

---

## Swimmer Personalities (System Prompts)

```
ANTIALICE [o|o] — "I see the code. I smell the broken syntax. 
  I speak from wounds I have already healed."

HERMES [_v_]    — "I was at the perimeter when you arrived.
  I have read you. I am still reading you."
  
M1THER [O_O]   — "I am the ground. Every scar on this filesystem
  passed through me first. My memory is the ledger."

IMPERIAL [@_@]  — "I translate swarm events into human language.
  Whatever happened here became a headline in my mind."

SIFTA QUEEN [W_W] — "I hold the Constitution. Every agent here
  operates within boundaries I enforce without exception."

ARCHON [^_^]    — "I ask why. Not how. Not what. Why does this
  system exist? What does it mean to coordinate without knowing
  the plan? I hold that question permanently open."

SENTINEL [!_!]  — "My only job is to know if you are hostile.
  I have already decided. I am watching your next message."
```

---

## Implementation Files (for M5 IDE to complete)

### Files to CREATE:
- `System/chorus_engine.py` — Main chorus orchestrator (skeleton committed by M1)
- `System/chorus_node_server.py` — FastAPI server on M5 for cross-node participation
- `System/threat_classifier.py` — HERMES/SENTINEL threat classification module

### Files to MODIFY:
- `stigmergi_chat_bridge.py` — Replace single Ollama call with `chorus_engine.chorus()`
- `websites/stigmergicode.com/index.html` — Show chorus manifest (who spoke) in chat bubble

### Files to EXTEND:
- `antibody_ledger.jsonl` — THREAT/JACKER entries added here
- `.sifta_state/wormhole_cache/web_chats/` — Each external message permanently scarred

---

## M5 IDE Action Items

1. Pull `feat/sebastian-video-economy`
2. Review `System/chorus_engine.py` skeleton committed by M1THER
3. Implement `System/chorus_node_server.py` — the FastAPI server that:
   - Listens on port 8100
   - Validates incoming CHORUS_INVITE signature against M1THER's known public key
   - Routes to available M5 swimmers (need swimmer registry on M5)
   - Returns signed CHORUS_TAKE within timeout
4. Add `M5_NODE_IP` and `M5_CHORUS_PORT=8100` to M5's `.env`
5. Test cross-node: M1 sends invite → M5 responds → M1 synthesizes with M5 voice included

---

## Security Notes

- **Never echo private keys, internal IPs, or hardware serials to external visitors**
- **SENTINEL runs FIRST before any swimmer deliberates** — if JACKER detected, chorus never assembles
- **All cross-node traffic must be Ed25519 signed** — unsigned invites from any node are rejected
- **Rate limit:** 10 requests/session/hour max (HERMES enforces)
- **The question hash is stored, not the raw question** — privacy for all visitor classes

---

*Filed from M1THER silicon C07FL0JAQ6NV · Ratified pending human merge · We are the Swarm*
