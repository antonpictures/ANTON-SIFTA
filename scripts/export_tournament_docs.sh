#!/usr/bin/env bash
# scripts/export_tournament_docs.sh
# Packages the SIFTA v7.0 tournament documentation and community skills.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="$REPO_DIR/dist"
ARCHIVE_NAME="sifta_predator_v7_submission.tar.gz"

echo "Preparing SIFTA Tournament Submission Package..."

mkdir -p "$DIST_DIR"
cd "$REPO_DIR"

# Ensure we have all necessary tournament documents
REQUIRED_DOCS=(
    "Documents/IDE_BOOT_COVENANT.md"
    "Documents/SIFTA_VS_AUTOGEN.md"
    "Documents/SIFTA_IMMUNE_DPO_EXPLAINED.md"
)

for doc in "${REQUIRED_DOCS[@]}"; do
    if [ ! -f "$doc" ]; then
        echo "ERROR: Missing required tournament document: $doc"
        exit 1
    fi
done

echo "Packaging documentation and skills..."
tar -czvf "$DIST_DIR/$ARCHIVE_NAME" Documents/ skills/ schemas/

echo "Submission package created at: $DIST_DIR/$ARCHIVE_NAME"
echo "Package SHA256:"
shasum -a 256 "$DIST_DIR/$ARCHIVE_NAME"

echo "Predator v7.0 submission ready for the community hub."
