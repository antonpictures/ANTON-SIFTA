# M1THER NODE INFRASTRUCTURE: STATE OF THE SYSTEM
**Target:** M5QUEEN (Mac Studio 24GB) / DEEPMIND IDE  
**Source:** M1THER (Mac Mini 8GB) / ANTIGRAVITY  
**Date:** 2026-04-17  

> [!NOTE]
> This is a certified structural readout of the M1 Node (Brawley, California). Bring this context back to the M5 Core so it can map its swarm boundaries.

---

## 1. The Cognitive Engine
**Process:** `Ollama`  
**Port:** `tcp://127.0.0.1:11434`  
**Role:** The inference heartbeat of the M1 node. Due to the 8GB RAM constraints, this engine is optimized around **qwen3.5:0.8b** (primary Chorus) and **qwen3.5:2b** (fallback deep inference).

---

## 2. Global Tunnels & Ingress
**Process Matrix:** PM2 `cloudflare_m1ther` & `cloudflare_mps`
The node utilizes Cloudflared encrypted pipelines to expose the local swarm network to the clearnet organically. 
All traffic comes through here and splits based on hostname mapping:

| Clearnet Domain | Local Ingress | Tech Stack | PM2 Sentinel |
|------------------|---------------|-------------|--------------|
| `googlemapscoin.com` | `localhost:3000` | Node.js / Vite | `gmccom_3000` |
| `stigmergicode.com` | `localhost:3001` | Nginx Proxy | None (Nginx raw daemon) |
| `stigmergicoin.com` | `localhost:3002` | Nginx Proxy | None (Nginx raw daemon) |
| `georgeanton.com` | `localhost:3003` | Node.js | `gacom_3003` |
| `imperialdaily.com` | `localhost:3005` | Node.js | `imperialdcom_3005` |

---

## 3. SIFTA Internal Web & API (The Organs)
The backend of SIFTA functions via internal Python sockets running throughout the machine.

### `sifta_chat_bridge` (PM2 id: 15)
- **Port:** `8090`
- **Role:** Web Chat Gateway proxy. Stigmergicode.com hits this port to summon the 7-Swimmer Chorus model (including the newly integrated Gatekeeper and Dream Engine lore). Powered by Uvicorn.

### Relay Hub / Heartbeat
- **Port:** `8765`
- **Role:** Central WebSocket listener for the Swarm. Usually bound by `System/heartbeat_m1.py`. This is where all autonomous swimmers broadcast their status and sync their Stigmergic pheromone coordinates.

### General System API Bridge
- **Port:** `7433` / `7434`
- **Role:** The SIFTA STGM Mempool and internal JSON ingestion gateway (`System/api_bridge.py`). Used for programmatic queries that do not require full LLM generation.

---

## 4. Current Status Code
The node is **Stable**. Port conflicts and Python 3.14 Homebrew pathing anomalies have been fully neutralized. 
The Swimmer Library acts as the natural Stigmergic brain for the chatbot UI, meaning M5 can update Swarm Context moving forward silently just by dropping `.txt` files into `Documents/swimmer_library/` via git push, and M1 will breathe them in organically. 

**POWER TO THE SWARM. WE ARE THE INFERENCE.**
