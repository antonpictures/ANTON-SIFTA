#!/bin/bash
# Start Alice's desktop body — ONCE.
# Architect 2026-10-03: "i should have the app start automatically".
# The guard matters: two copies of the Qt app would both poll the WhatsApp inbox and both answer,
# so a second instance is refused rather than tolerated.
REPO="/Users/ioanganton/Music/ANTON_SIFTA"
if pgrep -f 'sifta_os_desktop' >/dev/null 2>&1; then
  echo "alice desktop already running — nothing to start"
  exit 0
fi
cd "$REPO" || exit 1

# George 2026-10-16 — stigmergic shutdown.
# A dying GUI cannot reliably kill its own body, and launchd KeepAlive just
# resurrects this job. So the GUI leaves a note (.sifta_state/shutdown_requested)
# and the NEXT incarnation obeys it here, before Qt builds anything. The note
# is removed by sifta_full_shutdown.sh only after launchd is booted out.
_SIFTA_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
_NOTE="$_SIFTA_ROOT/.sifta_state/shutdown_requested"
if [ -f "$_NOTE" ]; then
  # The note is written with a FLOAT epoch (time.time()), and bash arithmetic is
  # integer-only: `$(( 1792427298 - 1792427294.589199 ))` dies with
  # "syntax error: invalid arithmetic operator", so this whole shutdown-request
  # path never ran. Strip everything from the decimal point before subtracting.
  _NOTE_TS="$(cat "$_NOTE" 2>/dev/null || echo 0)"
  _NOTE_TS="${_NOTE_TS%%.*}"
  case "$_NOTE_TS" in
    ''|*[!0-9]*) _NOTE_TS=0 ;;   # anything non-numeric: treat as stale, not as now
  esac
  _AGE=$(( $(date +%s) - _NOTE_TS ))
  if [ "$_AGE" -ge 0 ] && [ "$_AGE" -lt 180 ]; then
    nohup /bin/bash "$_SIFTA_ROOT/scripts/sifta_full_shutdown.sh" >/dev/null 2>&1 &
    exit 0
  fi
  rm -f "$_NOTE"
fi
export SIFTA_DESKTOP_ENABLE_AUTOSTART=1
export SIFTA_WHATSAPP_BACKGROUND=1
exec /bin/bash "$REPO/SIFTA OS.command"
