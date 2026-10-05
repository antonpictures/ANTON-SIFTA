#!/bin/bash
# The WhatsApp kernel, in the shape that WORKS: a wrapper that redirects to a log, launched by a
# plist, running bin/sifta-brain (a real copy of the interpreter, not a symlink).
# History: the kernel job exited 78 (EX_CONFIG) for hours with /usr/local/bin/python3; the
# answer-lane job with bin/sifta-brain has exit=0 and came back after the Architect's reboot.
REPO="/Users/ioanganton/Music/ANTON_SIFTA"
cd "$REPO" || exit 1
export PYTHONPATH="$REPO"
if lsof -nP -iTCP:7434 >/dev/null 2>&1; then
  exit 0                      # already listening: never bind twice
fi
exec "$REPO/bin/sifta-brain" "$REPO/scripts/whatsapp_alice_server.py" \
  >> "$REPO/.sifta_state/runtime_logs/whatsapp_kernel.out.log" 2>&1
