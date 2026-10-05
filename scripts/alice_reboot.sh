#!/bin/bash
# Alice restarts her own body.
# Architect 2026-10-03: "you should learn how to restart your own laptop, is gonna come back on,
# unless im dead". The body comes back by itself: the bridge, the kernel (launchctl submit) and
# now the desktop app all start at login. So a reboot is a maintenance act, not a death.
#
# A receipt is written FIRST, because a body that reboots without leaving a note is
# indistinguishable from a body that crashed.
REPO="/Users/ioanganton/Music/ANTON_SIFTA"
cd "$REPO" || exit 1
STAMP=$(date '+%Y-%m-%d %H:%M:%S')
printf '{"ts": %s, "event": "SELF_REBOOT", "reason": "%s", "stamp": "%s"}\n' \
  "$(date +%s)" "${1:-unspecified}" "$STAMP" >> .sifta_state/self_reboots.jsonl
echo "rebooting at $STAMP — reason: ${1:-unspecified}"
# Graceful restart via AppleScript: no sudo required, and macOS reopens the login session.
osascript -e 'tell application "System Events" to restart' 2>/dev/null \
  || shutdown -r +1 "Alice restarting the body" 2>/dev/null \
  || { echo "REFUSED: neither AppleScript nor shutdown could restart this machine"; exit 1; }
