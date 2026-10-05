#!/bin/bash
# The headless WhatsApp mouth, supervised by launchd, with its output in a log file.
# launchctl submit worked but gave the process no stderr -- an attempt with no trace, the exact
# disease this lane exists to cure. A wrapper redirects, launchd supervises.
REPO="/Users/ioanganton/Music/ANTON_SIFTA"
cd "$REPO" || exit 1
export PYTHONPATH="$REPO"
exec "$REPO/bin/sifta-brain" "$REPO/System/swarm_whatsapp_answer_lane.py" watch \
  >> "$REPO/.sifta_state/runtime_logs/answer_lane.log" 2>&1
