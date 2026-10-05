#!/bin/bash
# Keep the WhatsApp kernel alive WITHOUT asking launchd to supervise a long-running process.
#
# Why: the direct launchd job for the kernel exits 78 (EX_CONFIG) before producing a single byte
# of output, while the identical command run by hand -- even under `env -i` -- works. Rather than
# keep fighting a supervisor that refuses to say why, this runs every 30 seconds, starts the
# kernel ONLY if port 7434 is silent, and exits immediately. A short-lived job cannot be
# mis-supervised, and the kernel still comes back after a reboot, a crash, or a kill -9.
REPO="/Users/ioanganton/Music/ANTON_SIFTA"
cd "$REPO" || exit 0
export PYTHONPATH="$REPO"
if lsof -nP -iTCP:7434 >/dev/null 2>&1; then
  exit 0                       # already listening: nothing to do, and no duplicate binds
fi
nohup /usr/local/bin/python3 scripts/whatsapp_alice_server.py \
  >> "$REPO/.sifta_state/runtime_logs/whatsapp_kernel.out.log" 2>&1 &
exit 0
