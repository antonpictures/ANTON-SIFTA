#!/bin/zsh

set -u

SIFTA_ROOT="/Users/ioanganton/Music/ANTON_SIFTA"
DSH_BIN="/opt/homebrew/bin/dsh"
DSH_URL="http://127.0.0.1:3080"
DSH_AUTH_MARKER="dsh web authentication required"
# Where the launchd unit's stdout lands, and where the widget reads the token
# back from. Deliberately outside $SIFTA_ROOT: a launchd job cannot open a
# TCC-protected ~/Music path for its stdio and dies with EX_CONFIG (78).
BOOT_LOG="$HOME/.dsh/logs/dsh-web.out.log"
KIMI_BIN="/Users/ioanganton/.kimi-webbridge/bin/kimi-webbridge"

say_problem() {
  print -r -- ""
  print -r -- "Alice local coding: $1"
  print -r -- "Apasă Enter pentru a închide."
  read -r
  exit 1
}

# The Session Manager plugin registers its routes through `connection.fetch.register`,
# which first ships in dsh 0.2.0. On 0.1.1-rc.2 the Settings page mounts but stays empty:
# the client half loads, the host half never does. Refuse the old build loudly rather
# than starting a body that only looks alive.
dsh_is_new_enough() {
  local v maj min
  v="$("$DSH_BIN" --version 2>/dev/null)" || return 1
  [[ -n "$v" ]] || return 1
  maj="${v%%.*}"
  min="${${v#*.}%%.*}"
  [[ "$maj" == <-> && "$min" == <-> ]] || return 1
  (( maj > 0 )) && return 0
  (( maj == 0 && min >= 2 )) && return 0
  return 1
}

# dsh >= 0.2.0 fences the UI behind a per-launch token, so a bare GET answers 401.
# `curl -f` would read that as "nothing is listening" and start a second server.
harness_is_up() {
  local body code
  body="$(curl -sS --max-time 2 -o - -w $'\n%{http_code}' "$DSH_URL/" 2>/dev/null)" || return 1
  code="${body##*$'\n'}"
  body="${body%$'\n'*}"
  [[ "$code" == "200" && "$body" == *"__DSH_BOOT__"* ]] && return 0
  [[ "$code" == "401" && "$body" == *"$DSH_AUTH_MARKER"* ]] && return 0
  return 1
}

harness_token() {
  [[ -f "$BOOT_LOG" ]] || return 0
  grep -oE '/\?token=[A-Za-z0-9_-]+' "$BOOT_LOG" 2>/dev/null | tail -1 | cut -d= -f2
}

navigate_to_harness() {
  local payload response token url
  token="$(harness_token)"
  url="$DSH_URL"
  [[ -n "$token" ]] && url="$DSH_URL/?token=$token"
  payload="{\"action\":\"navigate\",\"args\":{\"url\":\"$url\",\"newTab\":true,\"group_title\":\"Alice · Local Coding\"},\"session\":\"alice-local-coding\"}"
  response="$(curl -sS -X POST http://127.0.0.1:10086/command -H 'Content-Type: application/json' -d "$payload" 2>/dev/null || true)"
  if [[ "$response" != *'"success":true'* ]]; then
    "$KIMI_BIN" start >/dev/null 2>&1 || true
    sleep 1
    response="$(curl -sS -X POST http://127.0.0.1:10086/command -H 'Content-Type: application/json' -d "$payload" 2>/dev/null || true)"
  fi
  [[ "$response" == *'"success":true'* ]] && return 0
  print -r -- "Kimi WebBridge nu este conectat. Interfața este gata la $DSH_URL"
  return 1
}

[[ -x "$DSH_BIN" ]] || say_problem "Nu găsesc dsh la $DSH_BIN"
dsh_is_new_enough || say_problem "dsh $("$DSH_BIN" --version 2>/dev/null) este prea vechi. Session Manager are nevoie de dsh >= 0.2.0. Actualizează: npm install -g @deepseek-ai/dsh"

if ! curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  [[ -x /usr/local/bin/ollama ]] || say_problem "Ollama nu este instalat."
  mkdir -p "$SIFTA_ROOT/.sifta_state/logs"
  nohup /usr/local/bin/ollama serve >"$SIFTA_ROOT/.sifta_state/logs/ollama.log" 2>&1 &
  for _ in {1..30}; do
    curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && break
    sleep 1
  done
  curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1 || say_problem "Ollama nu a pornit în 30 de secunde."
fi

# The local daemon must be up: the ollama-cloud provider reaches Ollama Cloud
# through 127.0.0.1:11434, so cloud models need it just as local ones do.
# (The old sifta-qwenpaw-coder preflight was dropped — no provider lists that
# model any more, and its missing base would have pulled ~9GB on every launch.)

if harness_is_up; then
  print -r -- "Alice local coding rulează deja la $DSH_URL"
  navigate_to_harness || {
    print -r -- "Deschide adresa de mai sus în browser și apasă Enter după ce ai terminat."
    read -r
  }
  exit 0
fi

mkdir -p "$(dirname "$BOOT_LOG")"
: >>"$BOOT_LOG"
# A token left in the log by an earlier boot is dead, and the server is down at
# this point, so only a line written *after* now counts as this boot's.
TOKEN_LINES_BEFORE="$(grep -c '?token=' "$BOOT_LOG" 2>/dev/null || print -r -- 0)"

# The launchd unit com.sifta.dsh-web owns port 3080 and keeps it alive, so a
# second server started here would only fight it for the port (and the unit
# would win on the next KeepAlive tick). Nudge the unit instead.
launchctl kickstart -k "gui/$(id -u)/com.sifta.dsh-web" >/dev/null 2>&1 || true

print -r -- "Alice local coding"
print -r -- "Workspace: $SIFTA_ROOT"
print -r -- "Model implicit: Ollama Cloud · DeepSeek V4.1 Flash (prin daemonul ollama local)"
print -r -- "Interfață: $DSH_URL"
print -r -- ""

for _ in {1..90}; do
  (( $(grep -c '?token=' "$BOOT_LOG" 2>/dev/null || print -r -- 0) > TOKEN_LINES_BEFORE )) && break
  sleep 1
done

navigate_to_harness || {
  print -r -- "Deschide $DSH_URL în browser și apasă Enter după ce ai terminat."
  read -r
}
