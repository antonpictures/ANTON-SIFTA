# Installing the Live Alice Coin Site

## 1. Install flybrain (for the connectome organ)

```bash
python3 -m pip install flybrain
```

The `flybrain` CLI may not be on PATH; use the module form:

```bash
python3 -m flybrain download
```

Pre-downloads the connectome (~260 MB → `~/fly-data`: `brain.npz` + `weights.npz`).

## 2. Start the coin API server

```bash
cd /Users/ioanganton/Music/ANTON_SIFTA
python3 System/coin_server.py
```

## 2b. Start the market ticker daemon (optional, for live-market card)

```bash
cd /Users/ioanganton/Music/ANTON_SIFTA
python3 System/ticker_daemon.py
```

It fetches BTC/ETH/SOL/DOGE every 5 minutes and appends `world_fact` traces to the ledger. The site's live-market card displays them automatically.

It listens on `http://127.0.0.1:3012` (nginx :3002 serves the static site and
proxies `/api/` here — do NOT bind 3002 directly; nginx owns that port).

Endpoints (all through `http://127.0.0.1:3002/api/...` via nginx, or :3012 direct):
- `GET  /api/world?limit=N` → recent sense traces (newest first)
- `POST /api/observe` → submit camera frame / audio; runs local vision (MiniCPM-V via Ollama) or STT, appends to the ledger, auto-detects room changes
- `GET  /api/room-change` → recent room delta receipts (Test A)
- `POST /api/chat` → proxied to the chorus node (:8100); reply arrives async
- `GET  /api/replies?session_id=&after_ts=` → poll for Alice's chat replies

## 3. Update nginx (proxy API → coin server)

The install script already includes the proxy. Run:

```bash
bash Network/websites/install_websites.sh
```

This writes the nginx config and reloads. The live conf is one file:
`/opt/homebrew/etc/nginx/servers/stigmergicode.conf` (both sites), with
`location /api/ { proxy_pass http://127.0.0.1:3012; }` (no trailing slash —
the `/api/` prefix must survive).

## 4. Test

Visit `http://stigmergicoin.com` (or `localhost:3002`)

- The **live Alice card** polls `/api/world` every 2 seconds
- The **chat panel** posts to `/api/chat` (session `coin-web`) and polls
  `/api/replies` for Alice's async reply (up to ~12 s)

## 5. Camera / vision (for Test A)

To wire camera frames into the sense loop:

1. Grant camera permission: run `System/build_sifta_camera_tcc_app.sh`
2. Take a frame, base64 encode, POST to `/api/observe`:
   ```json
   {"source": "camera", "kind": "object_seen", "frame_b64": "..."}
   ```

3. The server runs `describe_image_local` (MiniCPM-V 4.5 via local Ollama)
   and appends to `.sifta_state/world_awareness.jsonl`. When two consecutive
   descriptions differ substantially a `room_change` trace is appended.

## 6. Fly connectome (loom detector)

To test the fly.ai organ:

```bash
python3 -c "from System.swarm_fly_connectome_organ import looming_check; \
print(looming_check('/path/to/frame.png'))"
```

Looming = escalating two-step signal (1.0 → 2.0 into LC4/LPLC2). When the
DNp01 giant fiber fires, `loomed: true` and a `loom` receipt lands in the
ledger. (A single low-current pulse is below threshold — verified.)

## 7. Verification checklist

- [x] `curl http://127.0.0.1:3002/api/world` returns `{"success": true, "traces": [...]}`
- [x] Post a frame to `/api/observe` → ledger gets `object_seen` entry with a real description
- [x] Two differing frames → ledger gets `room_change` entry
- [x] Fly organ runs → ledger gets `loom` entry (`loomed: true`, 191 neurons fired)
- [x] Chat through nginx → chorus accepts, Alice replies (async, turn_id verified)
- [x] stigmergicoin.com shows the live card and chat panel

## 8. Known gaps (honest state)

- **Audio STT** is unverified: `run_stt` shells out to osascript against the
  `SiftaSpeech` app; if that app is absent the trace records "no transcript".
- **Phone push-to-record** (always-on mic impossible on mobile Safari) is
  future work.


---

*For the Swarm.* 🐜⚡