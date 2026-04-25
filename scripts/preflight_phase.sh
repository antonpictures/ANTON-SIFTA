#!/usr/bin/env bash
# scripts/preflight_phase.sh
# West Flank addition requested by Doctor Codex IDE.
# Do not proceed with major refactors if dirty phase artifacts are uncommitted.
# A basic git gate to protect the working directory.

set -e

# Verify git index and working tree are clean
if git diff --quiet && git diff --cached --quiet; then
    echo "PREFLIGHT OK: Working tree clean. Ready for surgery."
    exit 0
else
    echo "BLOCKED: uncommitted phase artifacts. Commit or stash first."
    exit 1
fi
