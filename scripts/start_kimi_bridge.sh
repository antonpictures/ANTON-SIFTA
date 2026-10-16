#!/bin/bash
# Start Kimi WebBridge, surviving the failure that closed Alice's web eyes for six days.
#
# 2026-10-10: the daemon refused to start with
#     Error: write pid: open ~/.kimi-webbridge/daemon.pid: file exists
# because a pid file from a DEAD process (PID 17377, 2026-10-04) was still on disk. The launcher
# printed "daemon started" and nothing ever listened on 127.0.0.1:10086. So this wrapper never lets
# a pid file outlive its process: if the pid is not alive, the file goes before the daemon starts.
BRIDGE_DIR="$HOME/.kimi-webbridge"
BIN="$BRIDGE_DIR/bin/kimi-webbridge"
PIDFILE="$BRIDGE_DIR/daemon.pid"

[ -x "$BIN" ] || { echo "kimi-webbridge binary missing: $BIN"; exit 1; }

for f in "$PIDFILE" "$PIDFILE.stale"; do
  if [ -f "$f" ]; then
    pid=$(cat "$f" 2>/dev/null)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      echo "kimi-webbridge already alive (pid $pid) — nothing to do"
      exit 0
    fi
    mv "$f" "$f.reaped-$(date +%Y%m%dT%H%M%S)" 2>/dev/null && echo "reaped stale pid file $f (pid ${pid:-?} was dead)"
  fi
done

exec "$BIN" start
