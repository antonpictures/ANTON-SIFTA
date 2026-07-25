# Stigmergicode Tunnel Runbook

This is the M5 connector for the existing `System/chorus_node_server.py`.
The public site is only a text surface; web turns are stamped `WEB TYPED` and
have zero owner authority. Keep tunnel credentials outside the repository.

## Local smoke

Start the existing server on the M5 listener port:

```bash
cd /Users/ioanganton/Music/ANTON_SIFTA
SIFTA_WEB_CHAT_DEV_MODE=1 M5_CHORUS_PORT=8100 python3 System/chorus_node_server.py
```

Check the server and page:

```bash
curl -sS http://127.0.0.1:8100/chorus/ping
curl -sS http://127.0.0.1:8100/ | rg "Talk to Alice - SIFTA"
```

With `SIFTA_WEB_CHAT_DEV_MODE=1`, `/api/chat` completes through the existing
chorus engine for a local round trip. In normal operation leave that variable
unset: the route queues the turn and the running Talk surface sends it through
Alice's normal cortex.

## Cloudflare connector

Confirm the binary and tunnel without printing credentials:

```bash
cloudflared --version
cloudflared tunnel list
cloudflared tunnel info sifta-m5
```

The connector config belongs at `~/.cloudflared/config.yml`, for example:

```yaml
tunnel: <tunnel-uuid>
credentials-file: /Users/<mac-user>/.cloudflared/<tunnel-uuid>.json
ingress:
  - hostname: stigmergicode.com
    service: http://127.0.0.1:8100
  - service: http_status:404
```

Create the tunnel only if it does not already exist, then route the hostname:

```bash
cloudflared tunnel create sifta-m5
cloudflared tunnel route dns sifta-m5 stigmergicode.com
cloudflared tunnel --config ~/.cloudflared/config.yml run sifta-m5
```

In Cloudflare DNS, verify the apex record is the tunnel CNAME and remains
proxied by the orange cloud. Keep Under Attack Mode off while testing so the
chat page and polling endpoint are not replaced by a browser challenge.

## launchd restart

### Chorus/web server

Install the checked-in, secret-free user LaunchAgent. The installer replaces
only a port 8100 listener whose command is the expected chorus server, then
waits for `CHORUS_READY`:

```bash
cd /Users/ioanganton/Music/ANTON_SIFTA
chmod +x launchd/install_chorus_node_server.sh
launchd/install_chorus_node_server.sh
launchctl print gui/$(id -u)/com.antonia.sifta.chorus_node_server_r1727
```

The service runs with `SIFTA_WEB_CHAT_DEV_MODE` unset. Its logs are
`.sifta_state/chorus_node_server.launchd.log` and
`.sifta_state/chorus_node_server.launchd.err.log`.

### Cloudflare connector

The checked-in LaunchAgent runs only the locally managed `sifta-web` config.
Its installer kills only a process whose command names that exact config and
tunnel, so the separate `alice-m5` dashboard/token connector is untouched.
Credentials remain under `~/.cloudflared`; the plist contains no token or
credential JSON.

```bash
cd /Users/ioanganton/Music/ANTON_SIFTA
chmod +x launchd/install_sifta_web_tunnel.sh
launchd/install_sifta_web_tunnel.sh
launchctl print gui/$(id -u)/com.sifta.sifta-web-tunnel
```

`KeepAlive` and `RunAtLoad` make the connector return after a crash, owner
logout/login, or reboot. Logs are
`.sifta_state/sifta-web-tunnel.launchd.log` and
`.sifta_state/sifta-web-tunnel.launchd.err.log`.

### Overnight responder

Talk remains the preferred WEB TYPED consumer. The headless night worker waits
eight seconds before claiming a queued turn, so it answers only when Talk has
not done so. Claims are cross-process locked, leased for recovery after a
crash, and closed permanently once a matching reply exists.

Legacy claims written before r1729 have a five-minute migration TTL. WEB TYPED
turns bypass Talk's owner schedule and WhatsApp shortcuts; public text cannot
invoke those effectors, and every answer must exit through `complete_web_turn`
before the consumer clears its active context.

```bash
cd /Users/ioanganton/Music/ANTON_SIFTA
chmod +x launchd/install_web_global_chat_night_worker.sh
launchd/install_web_global_chat_night_worker.sh
launchctl print gui/$(id -u)/com.sifta.web-global-chat-night-worker
```

The LaunchAgent runs the local-only Ollama worker under `caffeinate -ims`.
This prevents idle/system/disk sleep while allowing the display to sleep. It
contains no cloud API key and imports no owner effector or trading state.
Logs are `.sifta_state/web-global-chat-night-worker.launchd.log`,
`.sifta_state/web-global-chat-night-worker.launchd.err.log`, and
`.sifta_state/web_global_chat_night_worker.jsonl`.

The Mac must remain powered on with its lid open and George's user session
logged in. A forced shutdown, closed-lid sleep, logout, network outage, local
Ollama outage, or power loss still makes the public answer lane unavailable.
The three `KeepAlive` services return at the next login/reboot when their
dependencies are available.

Every completed local turn writes an exact turn-bound token stamp to
`web_global_chat_metabolism.jsonl`. Its STGM value is an observation in the
non-spendable `WEB_GUEST` bucket: `economy_posting_status` is
`NOT_POSTED_NONSPENDABLE_WEB_GUEST`, and no owner/node wallet row is written.

## Live proof

1. `curl -sS http://127.0.0.1:8100/chorus/ping` returns `CHORUS_READY`.
2. `https://stigmergicode.com` renders the warm-white chat page.
3. A visitor sends one ordinary message.
4. Talk shows `Stigmergicode.com (WEB TYPED)` in the one global chat and a text-only Alice reply.
5. `.sifta_state/web_global_chat_ingress.jsonl`, `.sifta_state/alice_conversation.jsonl`, `.sifta_state/web_global_chat_replies.jsonl`, and the web metabolism ledger contain the matching `turn_id`.

Paper or dev-mode results do not prove a live-money edge. This connector does
not place orders and does not authorize or mutate George's USD/Kalshi state.
