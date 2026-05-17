#!/bin/bash
# scripts/sifta_clean.sh — Steve-Jobs-grade repo hygiene pass.
#
# What it does (dry-run by default, --apply to execute):
#   1. Shows the current dirt breakdown (count by top-level directory).
#   2. Lists every file currently tracked that the NEW .gitignore would
#      have blocked (these need `git rm --cached`).
#   3. Lists every file untracked + ignored (will quietly disappear
#      from `git status` once the gitignore is committed).
#   4. With --apply: runs `git rm --cached` on the noise, removes any
#      stray .DS_Store, leaves disk contents intact.
#
# Usage:
#     ./scripts/sifta_clean.sh             # dry-run, just shows what would happen
#     ./scripts/sifta_clean.sh --apply     # actually untrack the noise
#
# Architect 2026-05-17: "Steve Jobs quality, macOS structure like we
# always have." This is the enforcement: only the living organism body
# stays tracked; everything else lives on disk but never enters the
# shared field.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

APPLY="no"
if [[ "${1:-}" == "--apply" ]]; then
    APPLY="yes"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "  SIFTA repo hygiene pass — $REPO_ROOT"
echo "  Mode: $([ "$APPLY" = "yes" ] && echo "APPLY (will untrack)" || echo "DRY-RUN (read-only)")"
echo "═══════════════════════════════════════════════════════════════════════"
echo ""

echo "─── (1) current dirt, top 15 dirs ──────────────────────────────────────"
git status --porcelain 2>/dev/null | awk '{print $2}' | awk -F'/' '{print $1}' \
    | sort | uniq -c | sort -rn | head -15
echo ""

echo "─── (2) tracked files that the new .gitignore now blocks ──────────────"
# Files currently in the git index that match any ignore rule.
TO_UNTRACK="$(git ls-files -ci --exclude-standard 2>/dev/null || true)"
if [[ -z "$TO_UNTRACK" ]]; then
    echo "  (none — index is already clean of ignored paths)"
else
    echo "$TO_UNTRACK" | head -30
    COUNT="$(echo "$TO_UNTRACK" | wc -l | tr -d ' ')"
    if [[ "$COUNT" -gt 30 ]]; then
        echo "  … plus $((COUNT - 30)) more"
    fi
fi
echo ""

echo "─── (3) untracked files the new .gitignore quietly absorbs ────────────"
git status --porcelain --ignored=traditional 2>/dev/null \
    | awk '$1 == "!!"' | head -10
IGN_COUNT="$(git status --porcelain --ignored=traditional 2>/dev/null \
    | awk '$1 == \"!!\"' | wc -l | tr -d ' ')"
if [[ "$IGN_COUNT" -gt 10 ]]; then
    echo "  … plus $((IGN_COUNT - 10)) more"
fi
echo ""

echo "─── (4) stray .DS_Store files ─────────────────────────────────────────"
DS_COUNT="$(find . -name ".DS_Store" -type f 2>/dev/null \
    -not -path "./.git/*" -not -path "./.venv/*" -not -path "./.sifta_state/*" \
    | wc -l | tr -d ' ')"
echo "  $DS_COUNT .DS_Store files on disk (will be removed under --apply)"
echo ""

if [[ "$APPLY" != "yes" ]]; then
    echo "═══════════════════════════════════════════════════════════════════════"
    echo "  This was a DRY-RUN. To actually clean:"
    echo ""
    echo "      ./scripts/sifta_clean.sh --apply"
    echo ""
    echo "  Apply mode will:"
    echo "    - git rm --cached (untrack but keep on disk) for all files"
    echo "      currently in index that match the new .gitignore"
    echo "    - delete .DS_Store files from disk"
    echo "    - NOT delete any other file from disk"
    echo "    - NOT commit anything — you run sifta_push.sh after"
    echo "═══════════════════════════════════════════════════════════════════════"
    exit 0
fi

echo "═══ APPLYING ══════════════════════════════════════════════════════════"

echo "─── untrack ignored files (keeping them on disk) ──────────────────────"
if [[ -n "$TO_UNTRACK" ]]; then
    echo "$TO_UNTRACK" | tr '\n' '\0' | xargs -0 -r git rm --cached --quiet 2>/dev/null || true
    echo "  untracked $(echo "$TO_UNTRACK" | wc -l | tr -d ' ') files"
else
    echo "  (nothing to untrack)"
fi

echo "─── delete .DS_Store files ────────────────────────────────────────────"
find . -name ".DS_Store" -type f \
    -not -path "./.git/*" -not -path "./.venv/*" -not -path "./.sifta_state/*" \
    -delete 2>/dev/null || true
echo "  done"

echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "  ✓ Clean pass complete. Next: review with"
echo ""
echo "      git status --short | head -50"
echo ""
echo "  Then push with"
echo ""
echo "      ./scripts/sifta_push.sh \"your message\""
echo "═══════════════════════════════════════════════════════════════════════"
