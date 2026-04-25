#!/bin/bash
# launchd/setup_launchd.sh
# Bootstraps the Stigmergic sensory cortex daemons (non-privileged).
#
# Usage:
#   launchd/setup_launchd.sh             # actually install + bootstrap
#   launchd/setup_launchd.sh --dry-run   # show what would happen, change nothing
#   launchd/setup_launchd.sh --status    # report current bootstrap state
#
set -euo pipefail

DRY_RUN=0
STATUS_ONLY=0
for arg in "$@"; do
    case "$arg" in
        --dry-run|-n) DRY_RUN=1 ;;
        --status|-s)  STATUS_ONLY=1 ;;
        --help|-h)
            sed -n '1,12p' "$0"
            exit 0
            ;;
    esac
done

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO="$( cd "$DIR/.." && pwd )"
PLISTS="stig_ble_radar_v5.plist stig_awdl_mesh_v5.plist stig_unified_log_v5.plist stig_vocal_proprioception_v5.plist stig_sense_loop_v5.plist stig_iphone_gps_v5.plist"
TARGET_DIR="$HOME/Library/LaunchAgents"
DOMAIN="gui/$(id -u)"

if [ "$STATUS_ONLY" -eq 1 ]; then
    echo "Currently bootstrapped SIFTA agents in $DOMAIN:"
    launchctl list | awk 'NR==1 || /antonia\.sifta/' | sed 's/^/  /'
    echo
    echo "Installed plist files in $TARGET_DIR:"
    ls -la "$TARGET_DIR"/stig_*_v5.plist 2>/dev/null | sed 's/^/  /' || echo "  (none)"
    exit 0
fi

mkdir -p "$TARGET_DIR"
mkdir -p "$REPO/.sifta_state"

if [ "$DRY_RUN" -eq 1 ]; then
    echo "🔍 DRY-RUN — no files written, no agents bootstrapped."
else
    echo "🐜 Bootstrapping Alice's sensory nervous system..."
fi

for plist in $PLISTS; do
    src="$DIR/$plist"
    dst="$TARGET_DIR/$plist"
    if [ ! -f "$src" ]; then
        echo "  ⚠️  source plist missing, skip: $src"
        continue
    fi
    label="$(/usr/libexec/PlistBuddy -c 'Print :Label' "$src" 2>/dev/null || echo "?")"

    if [ "$DRY_RUN" -eq 1 ]; then
        echo "  [dry] would install $plist (label=$label)"
        echo "  [dry]   -> $dst"
        echo "  [dry]   launchctl bootout/bootstrap $DOMAIN"
        continue
    fi

    if [ "$plist" = "stig_iphone_gps_v5.plist" ] \
       && lsof -nP -iTCP:8765 -sTCP:LISTEN >/dev/null 2>&1; then
        echo "  -> Skipping $plist (port 8765 already has an iPhone GPS receiver)"
        continue
    fi

    echo "  -> Loading $plist (label=$label)"
    # Keep source plists readable in-repo, but install with the checkout
    # path that is actually running. Avoids stale hardcoded
    # WorkingDirectory paths after a distro move.
    sed "s|/Users/ioanganton/Music/ANTON_SIFTA|$REPO|g" "$src" > "$dst"
    launchctl bootout "$DOMAIN" "$dst" 2>/dev/null || launchctl unload "$dst" 2>/dev/null || true
    launchctl bootstrap "$DOMAIN" "$dst" 2>/dev/null || launchctl load -w "$dst"
    launchctl enable "$DOMAIN/$label" 2>/dev/null || true
done

if [ "$DRY_RUN" -eq 0 ]; then
    echo
    echo "⚡ Sensory cortices online. Trace activity in $REPO/.sifta_state."
    echo "   Status:    launchd/setup_launchd.sh --status"
    echo "   Teardown:  launchd/teardown_launchd.sh"
fi
