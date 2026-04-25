#!/usr/bin/env bash
# =====================================================================
# alice-lana-cure / verify.sh
# =====================================================================
# Verifies that your local Ollama gemma4 blob is the same one the
# Phase C cure was authored and audited against.
#
# Usage:
#   bash verify.sh
# =====================================================================

set -euo pipefail

REFERENCE_SHA="4c27e0f5b5adf02ac956c7322bd2ee7636fe3f45a8512c9aba5385242cb6e09a"
OLLAMA_BLOB_DIR="${OLLAMA_BLOB_DIR:-$HOME/.ollama/models/blobs}"
BLOB_PATH="$OLLAMA_BLOB_DIR/sha256-$REFERENCE_SHA"

echo "alice-lana-cure: blob verifier"
echo "  reference sha256: $REFERENCE_SHA"
echo "  looking in:       $OLLAMA_BLOB_DIR"
echo ""

if [ ! -f "$BLOB_PATH" ]; then
  echo "✗ Reference blob not present in your local Ollama store."
  echo ""
  echo "  This usually means one of:"
  echo "    1. You have not pulled gemma4 yet. Run:  ollama pull gemma4:latest"
  echo "    2. You have pulled a different gemma4 build than the one this cure"
  echo "       was authored against. The cure will likely still work, but the"
  echo "       audit was performed against a specific blob — see PHASE_C_AUDIT.md."
  exit 2
fi

echo "Reference blob is present. Recomputing SHA-256 to verify integrity..."
COMPUTED_SHA=$(shasum -a 256 "$BLOB_PATH" 2>/dev/null | awk '{print $1}')

if [ "$COMPUTED_SHA" = "$REFERENCE_SHA" ]; then
  echo ""
  echo "✓ Verified: gemma4:latest blob matches the cure's reference fingerprint."
  echo "  You can safely apply the cure with:"
  echo ""
  echo "    ollama create alice-phc -f ./Modelfile"
  echo ""
  exit 0
else
  echo ""
  echo "✗ MISMATCH:"
  echo "    expected: $REFERENCE_SHA"
  echo "    got:      $COMPUTED_SHA"
  echo ""
  echo "  The blob on disk has been modified or corrupted since download."
  echo "  Re-pull with: ollama rm gemma4 && ollama pull gemma4:latest"
  exit 1
fi
