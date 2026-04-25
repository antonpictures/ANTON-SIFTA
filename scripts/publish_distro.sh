#!/usr/bin/env bash
# scripts/publish_distro.sh
#
# Publishes the SIFTA Castle through the canonical publish daemon.
# Dry-run is the default. Pass --allow-publish only for a real external push.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DISTRO_DIR="$REPO_DIR/.distro_build"

if [ ! -d "$DISTRO_DIR" ]; then
    echo "ERROR: .distro_build directory not found. Have you run scripts/distro_scrubber.py?"
    exit 1
fi

if [ "$#" -eq 0 ]; then
    cat >&2 <<'USAGE'
Usage:
  scripts/publish_distro.sh --mirror mock://dry-run
  scripts/publish_distro.sh --mirror github://OWNER/REPO --allow-publish

The script delegates to System.swarm_publish_daemon, which performs:
  - Castle homeostasis check
  - PII audit
  - dry-run by default
  - transport preflight
  - idempotent skip
  - canonical STIGMERGIC_PUBLISH_RECEIPT ledger write
USAGE
    exit 2
fi

cd "$REPO_DIR"

echo "Running SIFTA Castle Publish Daemon (Event 46)..."
python3 -m System.swarm_publish_daemon publish "$@"
