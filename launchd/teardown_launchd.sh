#!/bin/bash
# launchd/teardown_launchd.sh
# Tears down the Stigmergic sensory cortex daemons
set -euo pipefail

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PLISTS="stig_ble_radar.plist stig_awdl_mesh.plist stig_unified_log.plist stig_vocal_proprioception.plist stig_sense_loop.plist stig_iphone_gps.plist"
TARGET_DIR="$HOME/Library/LaunchAgents"
DOMAIN="gui/$(id -u)"

echo "🛑 Tearing down Alice's sensory nervous system..."

for plist in $PLISTS; do
    target="$TARGET_DIR/$plist"
    echo "  -> Unloading $plist"
    launchctl bootout "$DOMAIN" "$target" 2>/dev/null || launchctl unload -w "$target" 2>/dev/null || true
    rm -f "$target"
done

echo "Sensory cortices have been disconnected."
