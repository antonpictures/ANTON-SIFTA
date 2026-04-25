#!/bin/bash
# launchd/install_thermal_helper.sh
# Requires a single sudo cosign from the Architect to unlock smc/powermetrics without TCC prompts.
set -euo pipefail

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO="$( cd "$DIR/.." && pwd )"
PLIST="stig_thermal_helper.plist"
TARGET="/Library/LaunchDaemons/$PLIST"

echo "🔥 INSTALLING SIFTA PRIVILEGED THERMAL HELPER"
echo "This will install a LaunchDaemon to run \"powermetrics --samplers smc\" in the background."
echo "This crosses the sudo boundary to provide accurate fan RPM, ANE wattage, and die temps."
echo "Press CTRL-C to abort if you do not grant Alice this physical access."
echo ""

mkdir -p "$REPO/.sifta_state"
tmp="$(mktemp)"
sed "s|/Users/ioanganton/Music/ANTON_SIFTA|$REPO|g" "$DIR/$PLIST" > "$tmp"
sudo cp "$tmp" "$TARGET"
rm -f "$tmp"
sudo chown root:wheel "$TARGET"
sudo chmod 644 "$TARGET"

sudo launchctl bootout system "$TARGET" 2>/dev/null || sudo launchctl unload -w "$TARGET" 2>/dev/null || true
sudo launchctl bootstrap system "$TARGET" 2>/dev/null || sudo launchctl load -w "$TARGET"
sudo launchctl enable "system/$(/usr/libexec/PlistBuddy -c 'Print :Label' "$DIR/$PLIST")" 2>/dev/null || true

echo "✅ Privileged thermal helper installed and booted."
