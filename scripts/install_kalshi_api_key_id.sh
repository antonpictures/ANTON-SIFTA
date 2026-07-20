#!/bin/bash
# Install ONLY the Kalshi API Key ID (not the private key — already on disk).
# Usage:
#   ./scripts/install_kalshi_api_key_id.sh 'paste-key-id-here'
# Or interactive:
#   ./scripts/install_kalshi_api_key_id.sh
set -e
cd "$(dirname "$0")/.."
KEY_ID="${1:-}"
if [ -z "$KEY_ID" ]; then
  echo "Paste your Kalshi API Key ID (from Profile → API Keys), then Enter:"
  read -r KEY_ID
fi
SIFTA_KALSHI_KEY_ID="$KEY_ID" python3 - <<'PY'
import os
from System.kalshi_credentials import install_api_key_id, credentials_status
install_api_key_id(os.environ.get("SIFTA_KALSHI_KEY_ID", ""))
print(credentials_status())
print("Next: python3 System/kalshi_portfolio_read.py")
PY
