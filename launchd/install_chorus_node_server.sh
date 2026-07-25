#!/bin/bash
# Install the M5 chorus/web listener as a per-user KeepAlive LaunchAgent.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/.." && pwd)"
PLIST_NAME="com.antonia.sifta.chorus_node_server_r1727.plist"
LABEL="com.antonia.sifta.chorus_node_server_r1727"
SOURCE="$DIR/$PLIST_NAME"
TARGET_DIR="$HOME/Library/LaunchAgents"
TARGET="$TARGET_DIR/$PLIST_NAME"
DOMAIN="gui/$(id -u)"
PORT="8100"

mkdir -p "$TARGET_DIR" "$REPO/.sifta_state"
plutil -lint "$SOURCE" >/dev/null

# Unload the prior copy before replacing it. This is harmless on first install.
launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true

# Replace only the known manual server, never an unrelated port occupant.
listener_pid="$(lsof -nP -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null | head -n 1 || true)"
if [ -n "$listener_pid" ]; then
    listener_command="$(ps -p "$listener_pid" -o command= 2>/dev/null || true)"
    case "$listener_command" in
        *System/chorus_node_server.py*)
            kill "$listener_pid"
            for _ in 1 2 3 4 5; do
                kill -0 "$listener_pid" 2>/dev/null || break
                sleep 1
            done
            ;;
        *)
            echo "Refusing to replace unrelated listener on port $PORT: pid=$listener_pid" >&2
            exit 1
            ;;
    esac
fi

# Keep the checked-in template portable if this checkout moves.
sed "s|/Users/ioanganton/Music/ANTON_SIFTA|$REPO|g" "$SOURCE" > "$TARGET"
plutil -lint "$TARGET" >/dev/null
launchctl bootstrap "$DOMAIN" "$TARGET"
launchctl enable "$DOMAIN/$LABEL" 2>/dev/null || true
launchctl kickstart -k "$DOMAIN/$LABEL"

for _ in 1 2 3 4 5 6 7 8 9 10; do
    if curl -fsS "http://127.0.0.1:$PORT/chorus/ping" >/dev/null; then
        echo "CHORUS_READY: $DOMAIN/$LABEL on port $PORT"
        exit 0
    fi
    sleep 1
done

echo "LaunchAgent loaded but the chorus health probe failed" >&2
launchctl print "$DOMAIN/$LABEL" >&2 || true
exit 1
