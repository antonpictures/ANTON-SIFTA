#!/bin/bash
# scripts/sifta_push.sh — SIFTA-native push helper.
#
# Usage:
#   ./scripts/sifta_push.sh "Your commit message here"
#   ./scripts/sifta_push.sh "..." --force      # skip the dirt-count guard
#
# Always cds into the repo, shows what would be added, refuses to push
# if more than 200 files would be staged (a sign the .gitignore is
# leaking again), then adds + commits + pushes to origin main.
#
# Architect 2026-05-17: "Steve Jobs quality, macOS structure like we
# always have." The guard protects the body from accidental mass-noise
# pushes the next time a runtime directory leaks into the index.

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

if [ -z "$1" ]; then
    echo "Usage: $0 \"commit message\" [--force]"
    echo "Example: $0 \"Ace: automatic habit shift when owner focuses on the organ\""
    exit 1
fi

MESSAGE="$1"
FORCE="no"
if [[ "${2:-}" == "--force" ]]; then
    FORCE="yes"
fi

echo "🐜⚡ Pushing from: $REPO_ROOT"
echo "Commit message: $MESSAGE"
echo ""

# Pre-flight: how dirty is the working tree right now?
CHANGED=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
echo "─── pre-flight: $CHANGED working-tree changes ───"
git status --porcelain | awk '{print $2}' | awk -F'/' '{print $1}' \
    | sort | uniq -c | sort -rn | head -10
echo ""

# Guard: refuse to silently push a flood. The Architect's body
# should never carry 500+ noise files into the shared field by
# accident.
GUARD_LIMIT=200
if [[ "$CHANGED" -gt "$GUARD_LIMIT" && "$FORCE" != "yes" ]]; then
    echo "✗ REFUSING TO PUSH: $CHANGED changes exceeds guard limit ($GUARD_LIMIT)."
    echo ""
    echo "  This usually means the .gitignore is leaking. Run the hygiene"
    echo "  pass first:"
    echo ""
    echo "      ./scripts/sifta_clean.sh           # dry-run"
    echo "      ./scripts/sifta_clean.sh --apply   # untrack the noise"
    echo ""
    echo "  Then re-run this push. To override anyway:"
    echo ""
    echo "      ./scripts/sifta_push.sh \"$MESSAGE\" --force"
    exit 1
fi

echo "─── git add -A ───"
git add -A

if git diff --cached --quiet; then
    echo "Nothing to commit."
    exit 0
fi

# Show what's actually being committed before the network call.
echo ""
echo "─── staged for commit ───"
git diff --cached --stat | tail -5
echo ""

echo "─── git commit ───"
git commit -m "$MESSAGE"

echo "─── git push origin main ───"
git push origin main

echo ""
echo "✅ Pushed. Field updated."
echo "   HEAD: $(git log --oneline -1)"
