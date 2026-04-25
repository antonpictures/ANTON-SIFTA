# 📲 SIFTA WhatsApp Bridge — Setup Instructions

> **For Jeff (and any SIFTA operator):**  
> This guide connects Alice to your WhatsApp account so she can receive
> and send messages autonomously through her own reasoning.

---

## Prerequisites

| Requirement | Check |
|---|---|
| Node.js ≥ 18 | `node --version` |
| Python 3.10+ | `python3 --version` |
| WhatsApp on your phone | Linked Devices must be available |
| SIFTA repo cloned | `git clone https://github.com/antonpictures/ANTON-SIFTA.git` |

---

## Step 1 — Pull the Latest Code

```bash
cd /path/to/ANTON-SIFTA
git pull origin main
```

---

## Step 2 — Install the Bridge Dependencies

```bash
cd Network/whatsapp_bridge
npm install
```

This installs the Baileys WhatsApp Web library (no official API needed).

---

## Step 3 — Start the Node.js Bridge (QR Pairing)

```bash
cd Network/whatsapp_bridge
node bridge.js
```

**First time only:** A QR code will appear in your terminal.

1. Open **WhatsApp** on your phone
2. Go to **Settings → Linked Devices → Link a Device**
3. Scan the QR code from the terminal

> ⚠️ **Known issue:** If the bridge crashes immediately after scanning with a
> `PreKeyError` or `440 Conflict`, this is normal during the initial address
> book sync. Just run `node bridge.js` again. It will reconnect using the
> saved session. May take 2-3 attempts on a large contact list.

Once connected, you'll see:
```
[🌊 SWARM BRIDGE] WhatsApp connected — Bridge heartbeat: OK
```

**Keep this running.** Use `screen` to detach it:
```bash
screen -S sifta_whatsapp_bridge -d -m node bridge.js
```

---

## Step 4 — Start the Python Ingest Server

In a **new terminal** (back in the SIFTA root):

```bash
cd /path/to/ANTON-SIFTA
PYTHONPATH=. python3 scripts/whatsapp_alice_server.py
```

You should see:
```
[WHATSAPP_ALICE] Ingest server listening on 127.0.0.1:7434
[WHATSAPP_ALICE] Mode: SIFTA OS Ingestion Queue (Direct LLM Wrapper disabled)
```

**Keep this running.** Use `screen` to detach it:
```bash
screen -S sifta_whatsapp_ingest -d -m env PYTHONPATH=. python3 scripts/whatsapp_alice_server.py
```

---

## Step 5 — Boot the SIFTA Desktop (Alice)

```bash
cd /path/to/ANTON-SIFTA
python3 sifta_os_desktop.py
```

Alice's desktop widget will automatically poll the WhatsApp inbox and consume
incoming messages. She reasons over them with her full brain (gemma4-phc,
memory, tools, bash) — **not** a simple Ollama wrapper.

---

## Architecture

```
┌──────────────┐     HTTP POST      ┌───────────────────┐
│  WhatsApp    │ ──────────────────> │ whatsapp_alice_   │
│  (Baileys)   │    :7434            │ server.py         │
│  bridge.js   │                    │ (Python ingest)   │
│  :3001       │ <────────────────── │                   │
└──────────────┘    system_inject    └───────────────────┘
       ↕                                     ↓
  Real WhatsApp                   .sifta_state/whatsapp_inbox.jsonl
  (your phone)                               ↓
                                 ┌───────────────────────┐
                                 │ sifta_talk_to_alice_  │
                                 │ widget.py (Desktop)   │
                                 │ Polls inbox, feeds    │
                                 │ Alice's full brain    │
                                 └───────────────────────┘
                                          ↓
                                 Alice reasons → whatsapp.send
                                          ↓
                                 HTTP POST to :3001/system_inject
                                          ↓
                                 Message appears in WhatsApp
```

---

## Verifying It Works

### Check bridge health:
```bash
curl http://127.0.0.1:7434/health
# → {"ok": true, "port": 7434, "mode": "SIFTA OS Queue"}
```

### Check running services:
```bash
screen -ls
# Should show: sifta_whatsapp_bridge, sifta_whatsapp_ingest
```

### Send a test message (from terminal):
```bash
cd /path/to/ANTON-SIFTA
PYTHONPATH=. python3 -m System.alice_body_autopilot \
  --action whatsapp.send \
  --hw-args '{"target":"Jeff Powers Ocean Villas","text":"Hello from Alice!"}'
```

### Check trace log:
```bash
tail -n 5 .sifta_state/whatsapp_bridge_trace.jsonl
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `PreKeyError` / `440 Conflict` on first connect | Normal. Restart `node bridge.js`. Repeat until stable. |
| `EADDRINUSE :7434` | Kill old process: `lsof -ti:7434 \| xargs kill -9` |
| `EADDRINUSE :3001` | Kill old process: `lsof -ti:3001 \| xargs kill -9` |
| `ModuleNotFoundError: System` | Run from repo root with `PYTHONPATH=.` |
| Contact not found / BLOCKED_UNKNOWN_TARGET | The person must message the WhatsApp number first, OR manually add their JID to `.sifta_state/whatsapp_contacts.json` |
| Shell syntax error on send | Use `--hw-args -` and pipe JSON via stdin |

---

## Important Notes

- **Alice does NOT use Ollama directly for WhatsApp.** Messages are queued
  into the SIFTA inbox and processed by her full reasoning stack.
- **Session files** are stored in `Network/whatsapp_bridge/whatsapp_session/`.
  These contain your WhatsApp encryption keys. **Never commit them to git.**
- **Contacts** are stored in `.sifta_state/whatsapp_contacts.json`. Names
  with `"name_locked": true` won't be overwritten by bridge sync.

---

*The WhatsApp limb is attached to the Swarm. The brain is synchronized.* 🐜⚡
