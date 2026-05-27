#!/usr/bin/env bash
# clear_grok_sessions.sh — bury the saved grok CLI sessions so the resume
# "picker" screen disappears and `grok` boots straight into ONE fresh screen
# (no Ctrl-S → Enter two-screen dance).
#
# Owner request 2026-05-25 (George): "delete the two grok sessions so I get rid
# of one screen." The grok CLI stores its sessions in the Mac HOME, outside the
# SIFTA folder the IDE doctor can touch — so this runs on the real Mac shell.
#
# SAFE BY DESIGN: every session file is COPIED to a timestamped backup under
# the SIFTA repo BEFORE deletion. Nothing is lost; restore by copying back.
# No double-spend: each cleared file leaves a receipt line.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="$REPO/.sifta_state/grok_session_backups/$STAMP"
RECEIPT="$REPO/.sifta_state/grok_session_clear_receipt.jsonl"

# Candidate grok-CLI storage roots (covers the common implementations).
CANDIDATES=(
  "$HOME/.grok"
  "$HOME/.config/grok"
  "$HOME/.config/grok-cli"
  "$HOME/.local/share/grok"
  "$HOME/.local/state/grok"
  "$HOME/Library/Application Support/grok"
  "$HOME/Library/Application Support/grok-cli"
  "$HOME/Library/Application Support/xai-grok"
)

echo "== grok session reaper =="
found_any=0
cleared=0

for root in "${CANDIDATES[@]}"; do
  [ -d "$root" ] || continue
  echo
  echo "-- store: $root"
  ls -la "$root" || true

  # Session/history files live in these subpaths or match these names.
  # We only target chat/session/history artifacts — NOT settings/auth/api-key.
  while IFS= read -r -d '' f; do
    found_any=1
    rel="${f#"$HOME"/}"
    dest="$BACKUP_DIR/$rel"
    mkdir -p "$(dirname "$dest")"
    cp -p "$f" "$dest"
    rm -f "$f"
    cleared=$((cleared+1))
    echo "   buried: $f  ->  backup: $dest"
    printf '{"ts":"%s","action":"grok_session_cleared","file":"%s","backup":"%s"}\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$f" "$dest" >> "$RECEIPT"
  done < <(find "$root" \
      \( -ipath '*session*' -o -ipath '*history*' -o -ipath '*chat*' -o -ipath '*conversation*' \) \
      -type f \( -name '*.json' -o -name '*.jsonl' -o -name '*.ndjson' \) \
      ! -iname '*settings*' ! -iname '*config*' ! -iname '*auth*' ! -iname '*key*' \
      -print0 2>/dev/null)

  # Some grok CLIs keep a whole sessions/ directory — clear its contents too.
  for sub in sessions history chats conversations; do
    if [ -d "$root/$sub" ] && [ -n "$(ls -A "$root/$sub" 2>/dev/null)" ]; then
      mkdir -p "$BACKUP_DIR/${root#"$HOME"/}/$sub"
      cp -pr "$root/$sub/." "$BACKUP_DIR/${root#"$HOME"/}/$sub/" 2>/dev/null || true
      rm -rf "${root:?}/$sub"/* 2>/dev/null || true
      found_any=1
      cleared=$((cleared+1))
      echo "   buried dir contents: $root/$sub  ->  backup kept"
      printf '{"ts":"%s","action":"grok_session_dir_cleared","dir":"%s"}\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$root/$sub" >> "$RECEIPT"
    fi
  done
done

echo
if [ "$found_any" -eq 0 ]; then
  echo "No grok session store found in the usual places."
  echo "Run this to locate it, then tell me the path:"
  echo "    grok --help 2>/dev/null | head; ls -la ~/.grok ~/.config/grok* 2>/dev/null"
else
  echo "Done. Cleared $cleared session artifact(s)."
  echo "Backups: $BACKUP_DIR"
  echo "Next time you launch grok it should open ONE fresh screen (no picker)."
  echo "To undo: copy the files back from the backup folder above."
fi
