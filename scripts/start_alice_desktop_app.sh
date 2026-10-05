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
export SIFTA_DESKTOP_ENABLE_AUTOSTART=1
export SIFTA_WHATSAPP_BACKGROUND=1
exec /bin/bash "$REPO/SIFTA OS.command"
