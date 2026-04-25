#!/bin/bash
# launchd/uninstall_thermal_helper.sh
set -euo pipefail

TARGET="/Library/LaunchDaemons/stig_thermal_helper.plist"

echo "🛑 UNINSTALLING SIFTA PRIVILEGED THERMAL HELPER"

sudo launchctl bootout system "$TARGET" 2>/dev/null || sudo launchctl unload -w "$TARGET" 2>/dev/null || true
sudo rm -f "$TARGET"

echo "✅ Thermal helper uninstalled."
