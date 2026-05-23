#!/bin/bash
# tests/integration_vm_smoke.sh
# End-to-end integration test for the peripheral nervous system in a clean macOS environment.

set -e

echo "🐜 SIFTA Integration Test Running: Sensor Suite End-to-End"

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$(dirname "$DIR")"

cd "$REPO_ROOT"

# 1. Load plists
echo "1. Loading launchd plists..."
./launchd/setup_launchd.sh
sleep 5 # wait for plists to run at least once

# 2. Run composite-identity smoke
echo "2. Running composite-identity smoke..."
PYTHONPATH=. python3 System/swarm_composite_identity.py > .sifta_state/temp_smoke_output.log
cat .sifta_state/temp_smoke_output.log

# 3. Assert four organ lines
echo "3. Asserting organ lines in composite identity block..."
if grep -i "ble radar:" .sifta_state/temp_smoke_output.log; then echo "✅ BLE Radar mapped"; else echo "❌ BLE Radar missing"; exit 1; fi
if grep -i "awdl mesh:" .sifta_state/temp_smoke_output.log; then echo "✅ AWDL Mesh mapped"; else echo "❌ AWDL Mesh missing"; exit 1; fi
if grep -i "unified log:" .sifta_state/temp_smoke_output.log; then echo "✅ Unified Log mapped"; else echo "❌ Unified Log missing"; exit 1; fi
if grep -i "vocal" .sifta_state/temp_smoke_output.log; then echo "✅ Vocal Proprioception mapped"; else echo "❌ Vocal Proprioception missing"; exit 1; fi

# 4. Assert pheromone-focus line
echo "4. Asserting pheromone-focus line..."
if grep -i "pheromone focus:" .sifta_state/temp_smoke_output.log; then echo "✅ Pheromone Focus mapped"; else echo "❌ Pheromone Focus missing"; exit 1; fi

echo "🎉 All tests passed. SIFTA Swarm Integration is healthy."

# Cleanup
rm .sifta_state/temp_smoke_output.log
./launchd/teardown_launchd.sh
