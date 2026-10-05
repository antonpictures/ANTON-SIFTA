#!/bin/bash
# Restart the WhatsApp bridge when it stops delivering — by itself.
#
# Measured 2026-10-04: the bridge's session dies every few hours ("Bad MAC", "Connection Closed")
# while /health still says "open". Sends then fail silently and the owner sits with a phone that
# never rings. Six answers were written for him at 06:29 and none was delivered. Rather than wait
# for a human to notice, this reads the lane's own receipts: N consecutive failed sends means the
# transport is dead, so kick the bridge once and write down that it happened.
REPO="/Users/ioanganton/Music/ANTON_SIFTA"
cd "$REPO" || exit 0
BAD=$(python3 - <<'PY'
import json, pathlib
p = pathlib.Path(".sifta_state/whatsapp_answer_lane_receipts.jsonl")
rows = []
if p.exists():
    for l in p.read_text(errors="replace").splitlines()[-12:]:
        l = l.strip()
        if l:
            try: rows.append(json.loads(l))
            except Exception: pass
streak = 0
for r in reversed(rows):
    if r.get("ok") is False: streak += 1
    else: break
print(streak)
PY
)
if [ "${BAD:-0}" -ge 4 ]; then
  echo "[watchdog] $BAD consecutive failed sends — restarting the bridge"
  launchctl kickstart -k "gui/$(id -u)/com.sifta.whatsapp_bridge" 2>/dev/null
  printf '{"ts": %s, "event": "BRIDGE_RESTARTED_BY_WATCHDOG", "failed_streak": %s}\n' \
    "$(date +%s)" "$BAD" >> .sifta_state/bridge_watchdog_receipts.jsonl
fi
exit 0
