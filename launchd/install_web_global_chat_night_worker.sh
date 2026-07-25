#!/bin/bash
# Install Alice's headless WEB TYPED fallback and prevent idle system sleep.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/.." && pwd)"
PLIST_NAME="com.sifta.web-global-chat-night-worker.plist"
LABEL="com.sifta.web-global-chat-night-worker"
SOURCE="$DIR/$PLIST_NAME"
TARGET_DIR="$HOME/Library/LaunchAgents"
TARGET="$TARGET_DIR/$PLIST_NAME"
DOMAIN="gui/$(id -u)"

test -x /usr/bin/caffeinate
test -x /usr/local/bin/python3
mkdir -p "$TARGET_DIR" "$REPO/.sifta_state"
plutil -lint "$SOURCE" >/dev/null
launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
sed -e "s|/Users/ioanganton/Music/ANTON_SIFTA|$REPO|g" \
    -e "s|/Users/ioanganton|$HOME|g" "$SOURCE" > "$TARGET"
plutil -lint "$TARGET" >/dev/null
launchctl bootstrap "$DOMAIN" "$TARGET"
launchctl enable "$DOMAIN/$LABEL" 2>/dev/null || true
launchctl kickstart -k "$DOMAIN/$LABEL"

for _ in 1 2 3 4 5 6 7 8 9 10; do
    pid="$(pgrep -f 'swarm_web_global_chat_night_worker.py' | head -n 1 || true)"
    if [ -n "$pid" ]; then
        echo "WEB_NIGHT_WORKER_READY: $DOMAIN/$LABEL pid=$pid"
        exit 0
    fi
    sleep 1
done

echo "LaunchAgent loaded but the overnight worker did not start" >&2
launchctl print "$DOMAIN/$LABEL" >&2 || true
exit 1
