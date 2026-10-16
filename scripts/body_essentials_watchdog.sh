#!/bin/bash
# Keep the two things that make the Architect's sites reachable alive, without him touching anything.
#
# 2026-10-12: stigmergicode.com answered 530 and stigmergicoin.com 502. Two separate causes, both
# invisible until measured:
#   1. the :8100 chorus server died at import -- `from System... import` failed because Python puts
#      the SCRIPT's directory on sys.path, not the repo root (fixed in the file);
#   2. the sifta-web tunnel had ZERO registered connections, so Cloudflare could not reach origin --
#      its launchd job reports exit=78 even though the exact command runs fine by hand.
# He asked never to do this by hand again, so this supervisor checks and repairs on a loop, and
# writes one line per repair. It does not hide anything: every action is appended, not summarised.
REPO="/Users/ioanganton/Music/ANTON_SIFTA"
LOG="$REPO/.sifta_state/body_essentials.log"
RECEIPT="$REPO/.sifta_state/body_essentials_receipts.jsonl"
cd "$REPO" || exit 1

note() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1" >> "$LOG"; }
receipt() { printf '{"ts": %s, "at": "%s", "action": "%s", "detail": "%s"}\n' \
  "$(date +%s)" "$(date '+%Y-%m-%dT%H:%M:%S')" "$1" "$2" >> "$RECEIPT"; }

check_once() {
  # 1. chorus node server on :8100 -- the thing behind stigmergicode.com
  if ! lsof -nP -iTCP:8100 -sTCP:LISTEN >/dev/null 2>&1; then
    nohup ./bin/sifta-brain System/chorus_node_server.py >> "$REPO/.sifta_state/chorus_node_server.log" 2>&1 &
    note "started chorus_node_server on :8100 (pid $!)"
    receipt "chorus_start" "port 8100 was empty"

  # 2. WhatsApp bridge on :3010 -- the ear. Added 2026-10-15 after measuring that this port was
  # guarded by NOTHING while :8100 was guarded and stayed up: the body protected its voice and not
  # its ear. Consequence measured that day -- the bridge had been dead for days, nothing arrived,
  # and a friend asking "Alice, are you here?" was never answered. The existing send-failure
  # watchdog cannot see a dead bridge, because a dead bridge sends nothing: it watches the postman,
  # not the post office. A port check is the whole fix.
  if ! lsof -nP -iTCP:3010 -sTCP:LISTEN >/dev/null 2>&1; then
    ( cd "$REPO/Network/whatsapp_bridge" && \
      SIFTA_WA_PAIR_NUMBER=13232026780 SIFTA_BRIDGE_INJECT_PORT=3010 \
      SIFTA_WA_SESSION_DIR="$REPO/Network/whatsapp_bridge/whatsapp_session" \
      nohup /opt/homebrew/bin/node bridge.js >> "$REPO/.sifta_state/runtime_logs/whatsapp_bridge.out.log" 2>&1 & )
    note "started whatsapp bridge on :3010"
    receipt "whatsapp_bridge_start" "port 3010 was empty"
  fi

  # 3. WhatsApp kernel server on :7434 -- the door the bridge posts into. Same disease, same day.
  if ! lsof -nP -iTCP:7434 -sTCP:LISTEN >/dev/null 2>&1; then
    ( cd "$REPO" && PYTHONPATH="$REPO" nohup /usr/local/bin/python3 scripts/whatsapp_alice_server.py \
      >> "$REPO/.sifta_state/runtime_logs/whatsapp_kernel.out.log" 2>&1 & )
    note "started whatsapp kernel server on :7434"
    receipt "whatsapp_kernel_start" "port 7434 was empty"
  fi
  fi
  # 2. sifta-web tunnel -- the transport both domains need
  if ! pgrep -f "tunnel --config.*sifta-web.yml" >/dev/null 2>&1; then
    nohup /opt/homebrew/bin/cloudflared tunnel --config "$HOME/.cloudflared/sifta-web.yml" run sifta-web \
      >> "$REPO/.sifta_state/sifta_web_tunnel.log" 2>&1 &
    note "started sifta-web tunnel (pid $!)"
    receipt "tunnel_start" "no tunnel process for sifta-web.yml"
  fi
}

note "watchdog up (pid $$)"
while true; do check_once; sleep 60; done
