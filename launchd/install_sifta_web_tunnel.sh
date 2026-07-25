#!/bin/bash
# Replace only the manual sifta-web connector with a KeepAlive LaunchAgent.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/.." && pwd)"
PLIST_NAME="com.sifta.sifta-web-tunnel.plist"
LABEL="com.sifta.sifta-web-tunnel"
SOURCE="$DIR/$PLIST_NAME"
TARGET_DIR="$HOME/Library/LaunchAgents"
TARGET="$TARGET_DIR/$PLIST_NAME"
DOMAIN="gui/$(id -u)"
CONFIG="$HOME/.cloudflared/sifta-web.yml"

test -x /opt/homebrew/bin/cloudflared
test -f "$CONFIG"
mkdir -p "$TARGET_DIR" "$REPO/.sifta_state"
plutil -lint "$SOURCE" >/dev/null
launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true

# Do not touch the separate alice-m5 token connector or any other tunnel.
while IFS= read -r pid; do
    [ -n "$pid" ] || continue
    command="$(ps -p "$pid" -o command= 2>/dev/null || true)"
    case "$command" in
        *cloudflared*"--config $CONFIG run sifta-web"*) kill "$pid" ;;
    esac
done < <(pgrep -f "cloudflared.*--config $CONFIG run sifta-web" || true)

sed -e "s|/Users/ioanganton/Music/ANTON_SIFTA|$REPO|g" \
    -e "s|/Users/ioanganton|$HOME|g" "$SOURCE" > "$TARGET"
plutil -lint "$TARGET" >/dev/null
launchctl bootstrap "$DOMAIN" "$TARGET"
launchctl enable "$DOMAIN/$LABEL" 2>/dev/null || true
launchctl kickstart -k "$DOMAIN/$LABEL"

for _ in 1 2 3 4 5 6 7 8 9 10; do
    pid="$(pgrep -f "cloudflared.*--config $CONFIG run sifta-web" | head -n 1 || true)"
    if [ -n "$pid" ]; then
        echo "SIFTA_WEB_TUNNEL_READY: $DOMAIN/$LABEL pid=$pid"
        exit 0
    fi
    sleep 1
done

echo "LaunchAgent loaded but sifta-web did not start" >&2
launchctl print "$DOMAIN/$LABEL" >&2 || true
exit 1
