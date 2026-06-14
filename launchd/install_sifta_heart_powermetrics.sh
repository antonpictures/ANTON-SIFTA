#!/bin/bash
# launchd/install_sifta_heart_powermetrics.sh
# Narrow Architect cosign: install privileged thermal helper OR grant powermetrics read.
# r1013-C3 acceptance: /heart names a real watt tier when helper ledger is live.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/.." && pwd)"

echo "SIFTA heart metabolism installer"
echo "Repo: $REPO"
echo ""
echo "Option A (recommended): install LaunchDaemon thermal helper"
echo "  sudo bash $DIR/install_thermal_helper.sh"
echo ""
echo "Option B: one-shot powermetrics probe (requires sudo password)"
echo "  sudo powermetrics --samplers cpu_power,thermal,gpu_power,ane_power -n 1 -i 250"
echo ""
echo "After install, verify:"
echo "  python3 -m System.swarm_hardware_heart"
echo "  /heart  # in Talk — should name sensor_tier privileged_helper_cache or privileged_power_thermal"
echo ""
read -r -p "Install thermal helper now? [y/N] " ans
if [[ "${ans,,}" == "y" ]]; then
  exec bash "$DIR/install_thermal_helper.sh"
fi

echo "Skipped. Heart will stay on unprivileged/helper-cache tiers until you cosign."