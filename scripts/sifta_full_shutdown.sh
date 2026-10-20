#!/bin/bash
# ── sifta_full_shutdown.sh ──────────────────────────────────────────────
# George, 2026-10-16: "when I close talk window shut down all SIFTA OS,
# including the websites stigmergicode and coin — so the full 24 GB RAM is
# free to build and test other programs. But I want to keep talking to
# Alice in the harness."
#
# So this kills ONLY SIFTA-owned processes, in this order:
#   watchdogs → websites (:8890/:8891) → WhatsApp ear (:3010/:7434) →
#   chorus (:8100) → SIFTA desktop + widgets. Local models are unloaded
#   through ollama's own API (keep_alive:0) — the daemon stays alive.
#
# It NEVER touches:
#   • the DSH harness (node @deepseek-ai/dsh — this chat)
#   • the ollama daemon itself
#
# Usage:  bash scripts/sifta_full_shutdown.sh [--dry-run]
# Sentinel: .sifta_state/shutdown_active — watchdogs exit instead of
# restarting organs behind George's back; forgotten after 12 h.
set -u

REPO="${SIFTA_REPO:-/Users/ioanganton/Music/ANTON_SIFTA}"
STATE="$REPO/.sifta_state"
LOG="$STATE/runtime_logs/sifta_full_shutdown.log"
DRY=0
[ "${1:-}" = "--dry-run" ] && DRY=1
mkdir -p "$STATE/runtime_logs"

ts()  { date "+%Y-%m-%d %H:%M:%S"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

mem_free_gb() {
  local pg f i s
  pg=$(pagesize 2>/dev/null || echo 16384)
  read -r f i s <<EOF
$(vm_stat | awk '/Pages free/{f=$3} /Pages inactive/{i=$3} /Pages speculative/{s=$3} END{print f, i, s}' | tr -d '.')
EOF
  echo $(( (${f:-0} + ${i:-0} + ${s:-0}) * pg / 1024 / 1024 / 1024 ))
}

# ── who dies ────────────────────────────────────────────────────────────
WATCHDOG_PIDS=$(pgrep -f "body_essentials_watchdog.sh|bridge_send_watchdog.sh" 2>/dev/null | sort -u)

PIDS() {
  {
    for p in 8890 8891 3010 7434 8100; do
      lsof -nP -tiTCP:"$p" -sTCP:LISTEN 2>/dev/null
    done
    pgrep -f "sifta_os_desktop.py"             2>/dev/null
    pgrep -f "sifta_talk_to_alice_widget.py"   2>/dev/null
    pgrep -f "sifta_alice_browser_widget.py"   2>/dev/null
    pgrep -f "whatsapp_alice_server.py"        2>/dev/null
    pgrep -f "whatsapp_bridge/bridge.js"       2>/dev/null
    pgrep -f "chorus_node_server.py"           2>/dev/null
    pgrep -f "chorus_engine.py"                2>/dev/null
    pgrep -f "http.server 8890"                2>/dev/null
    pgrep -f "http.server 8891"                2>/dev/null
  } | sort -un | while read -r pid; do
      [ -z "$pid" ] && continue
      [ "$pid" = "$$" ] && continue
      [ "$pid" = "${PPID:-0}" ] && continue
      cmd=$(ps -o command= -p "$pid" 2>/dev/null) || continue
      [ -z "$cmd" ] && continue
      # hard exclusions: the harness chat and the model daemon survive
      case "$cmd" in
        *"@deepseek-ai"*)        continue ;;
        *"deepseek-ai/dsh"*)     continue ;;
        *"ollama serve"*)        continue ;;
        *"ollama runner"*)       continue ;;
        *"sifta_full_shutdown"*) continue ;;
      esac
      echo "$pid"
    done | sort -un
}

unload_ollama_models() {
  command -v curl >/dev/null 2>&1 || return 0
  local names m
  names=$(curl -s --max-time 5 http://127.0.0.1:11434/api/ps 2>/dev/null | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
    for x in d.get("models", []):
        n = x.get("model") or x.get("name")
        if n:
            print(n)
except Exception:
    pass
' 2>/dev/null)
  if [ -z "$names" ]; then
    log "ollama: no loaded models"
    return 0
  fi
  echo "$names" | while read -r m; do
    [ -z "$m" ] && continue
    curl -s --max-time 20 http://127.0.0.1:11434/api/generate \
         -d "{\"model\":\"$m\",\"keep_alive\":0}" >/dev/null 2>&1
    log "ollama: unloaded $m (its RAM is free)"
  done
}

rss_gb() {
  { for pid in "$@"; do ps -o rss= -p "$pid" 2>/dev/null; done; } \
    | awk '{s+=$1} END{printf "%.1f", s/1024/1024}'
}

# ── dry run ─────────────────────────────────────────────────────────────
if [ "$DRY" = 1 ]; then
  log "DRY RUN — nothing will be killed"
  log "mem free now: $(mem_free_gb) GB"
  log "watchdogs alive: ${WATCHDOG_PIDS:-none}"
  LIST=$(PIDS)
  log "SIFTA processes that WOULD die:"
  { for pid in $LIST; do
      printf '  %7s  %6s MB  %s\n' "$pid" \
        "$(awk -v r="$(ps -o rss= -p "$pid" 2>/dev/null)" 'BEGIN{printf "%d", r/1024}')" \
        "$(ps -o command= -p "$pid" 2>/dev/null | cut -c1-96)"
    done; } | tee -a "$LOG"
  log "RAM held by that list: $(rss_gb $LIST) GB"
  log "ollama loaded models: $(curl -s --max-time 5 http://127.0.0.1:11434/api/ps 2>/dev/null | python3 -c 'import sys,json
try: print(len(json.load(sys.stdin).get("models",[])))
except Exception: print("?")')"
  log "ports that WOULD go dark: 8890 8891 3010 7434 8100"
  log "launchd labels that WOULD be booted out:"
  launchctl list 2>/dev/null | awk '$3 ~ /(^|\.)sifta\./ {print "  "$3" (pid "$1")"}' | tee -a "$LOG"
  launchctl list 2>/dev/null | awk '$3 == "com.sifta.dsh-web" {print "  "$3" (pid "$1")   <- KEPT: this harness chat"}' | tee -a "$LOG"
  exit 0
fi

# ── real shutdown ───────────────────────────────────────────────────────
# launchd KeepAlive may resurrect the wrapper more than once before the
# bootout lands, so two shutdown scripts could race. One runs; the others
# exit quietly. Idempotent by construction.
_LOCK="$STATE/runtime_logs/.shutdown.lock"
if ! mkdir "$_LOCK" 2>/dev/null; then
  exit 0
fi
trap 'rmdir "$_LOCK" 2>/dev/null' EXIT
log "════ FULL SIFTA OS SHUTDOWN requested ════"
log "mem free BEFORE: $(mem_free_gb) GB"
printf 'shutdown %s\n' "$(date +%s)" > "$STATE/shutdown_active"
log "sentinel: $STATE/shutdown_active (watchdogs honour it for 12 h)"

# 1. watchdogs first — they must not resurrect anything mid-shutdown
for pid in $WATCHDOG_PIDS; do
  kill "$pid" 2>/dev/null && log "watchdog stopped: $pid"
done
# launchd is the OTHER resurrector: com.sifta.alice.desktop has
# KeepAlive=true + RunAtLoad=true, so killing it just makes launchd bring it
# straight back (George: "it restarts auto"). Boot every SIFTA agent out
# BEFORE killing processes, or the RAM never stays free.
_booted_out=""
# com.sifta.dsh-web IS the harness chat — booting it out would end this
# conversation. George: "i want to be able to still talk to you alice from
# here." It is excluded by name, and also by the node/@deepseek-ai guard.
for _label in $(launchctl list 2>/dev/null | awk '$3 ~ /(^|\.)sifta\./ && $3 != "com.sifta.dsh-web" {print $3}'); do
  if launchctl bootout "gui/$(id -u)/$_label" >/dev/null 2>&1; then
    _booted_out="$_booted_out $_label"
    log "launchd: booted out $_label"
  fi
done
[ -n "$_booted_out" ] || log "launchd: no SIFTA labels were loaded"

# 2. free model RAM while the daemon is still up
unload_ollama_models

# 3. the kill list — TERM, wait, then KILL stragglers
LIST=$(PIDS)
log "killing $(echo "$LIST" | grep -c . ) process(es)"
for pid in $LIST; do
  cmd=$(ps -o command= -p "$pid" 2>/dev/null | cut -c1-96)
  kill "$pid" 2>/dev/null && printf '  TERM %7s  %s\n' "$pid" "$cmd" >> "$LOG"
done
sleep 4
for pid in $(PIDS); do
  kill -9 "$pid" 2>/dev/null && log "force-killed: $pid"
done
sleep 2

log "mem free AFTER: $(mem_free_gb) GB"
LEFT=$( { for p in 8890 8891 3010 7434 8100; do lsof -nP -tiTCP:"$p" -sTCP:LISTEN 2>/dev/null; done; } | sort -u | tr '\n' ' ')
log "ports still listening: ${LEFT:-none}"
log "harness + ollama daemon: untouched by design (this chat survives)"
rm -f "$STATE/shutdown_requested" 2>/dev/null
log "DONE. Re-arm the ear watchdog when you want SIFTA back:"
log "  nohup bash $REPO/scripts/body_essentials_watchdog.sh >/dev/null 2>&1 &"
log "  launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.sifta.alice.desktop.plist"
