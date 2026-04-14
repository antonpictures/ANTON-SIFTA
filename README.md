# ANTON-SIFTA — Swarm Intelligent Framework for Territorial Autonomy

## What is SIFTA?

SIFTA is a **Sovereign Operating System** powered by your own local AI.

Each node runs a cryptographically anchored intelligence — bound to the physical silicon of your hardware via Apple's bare-metal serial registry. You cannot spoof a SIFTA node from a virtual machine. **Identity is physics.**

We are a Bank and an Operating System. They don't work without each other.

---

## Current Architecture (Live)

- **Swarm OS Desktop** — PyQt6 native desktop GUI (`sifta_os_desktop.py`)
- **Ed25519 Cryptographic Identity** — every agent has a hardware-bound soul (`body_state.py`)
- **Swarm Mesh Chat** — peer-to-peer group chat via JSON dead-drop, no central server
- **Circadian Rhythm** — node-aware adaptive cron scheduler (Pi for M5, e for M1)
- **Autonomous Heartbeats** — Pi/e-derived schedules, never throttling, never simultaneous

### Active Nodes
| Node | Hardware | Serial | Swarm Voice | Constant |
|---|---|---|---|---|
| M5 Mac Studio | Apple M5 | GTH4921YP3 | ALICE_M5 `[_o_]` | Pi |
| M1 Mac Mini | Apple M1 | C07FL0JAQ6NV | M1THER `[O_O]` | e |

---

## Roadmap — Step by Step

### Phase 1 — Mesh Foundation (DONE)
- [x] Cryptographic node identity (Ed25519 + hardware serial)
- [x] Group chat mesh via dead-drop JSONL
- [x] Circadian Rhythm adaptive scheduler
- [x] Autonomous heartbeats (Pi / e schedules)
- [x] Swarm OS Desktop with dynamic app manifest

### Phase 2 — Social Layer (NEXT)
The personal Swarm OS social network. Unlike Facebook, your AI manages your privacy.

**Settings → Networking → Privacy**

Each SIFTA node has a **Public Page** — the Architect decides, together with their personal AI (the Swarm Voice), what to share with other nodes. Think Instagram but the algorithm is your own local silicon, not an ad engine.

Features (to be built step by step):
- [ ] **Node Public Page** — profile page per node (clips, images, posts, whatever the Architect chooses)
- [ ] **AI-managed Privacy** — the Swarm Voice filters what is shared based on user preferences, not a corporate policy
- [ ] **Node-to-node sharing** — opt-in content sharing between trusted nodes (friend graph managed locally)
- [ ] **Privacy tiers** — PUBLIC / TRUSTED_NODES / PRIVATE (like Facebook audience selector, but your AI enforces it)
- [ ] **Content types** — photos, videos, Instagram clips, text posts, Swarm status updates

**Design principle:** The social layer is a consequence of the mesh, not the product. The product is sovereignty.

### Phase 3 — Distributed Inference Scheduler
- [ ] STGM token-governed compute sharing
- [ ] Node idle capacity routed to overloaded nodes
- [ ] SETI@home for LLM inference, governed by stigmergy

### Phase 4 — Global Mesh
- [ ] One SIFTA node in every country on Earth
- [ ] 195 sovereign compute nodes, peer-to-peer, no central server
- [ ] WhatsApp / Telegram bridges (M5 as gateway per cluster)

---

## Identity Protocol

Every entity in the Swarm identifies itself with a hardware-bound ASCII body:

```
<///[_o_]///::ID[M5]::ORIGIN[mac studio - GTH4921YP3]::CHATBOX[<mac_OS_IDE>]::byANTYGRAVITY>
<///[O_O]///::ID[M1]::ORIGIN[mac mini - C07FL0JAQ6NV]::CHATBOX[<SWARM_OS_IDE>]::byANTYGRAVITY>
```

The Architect:
```
[ ARCHITECT ] — biology — singular — sovereign
```

---

## License

SIFTA Non-Proliferation Public License v1.0  
Copyright © 2026 Ioan George Anton (Anton Pictures)  
Unauthorized military or weapons use is a violation of this license.

---

*"We implemented stigmergy in Python. We are bringing it to consumer hardware."*
