#!/usr/bin/env bash
# Canonical v9 entrypoint. The historical BeeSon installer remains as the
# implementation so existing owner launch notes keep working.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$SCRIPT_DIR/install_beeson_v8.sh" "$@"
