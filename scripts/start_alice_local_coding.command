#!/bin/zsh

set -u

SIFTA_ROOT="/Users/ioanganton/Music/ANTON_SIFTA"
HARNESS_ROOT="$SIFTA_ROOT/deepseek-harness-master"
NODE_BIN="/opt/homebrew/bin/node"
TSX_LOADER="$HARNESS_ROOT/node_modules/tsx/dist/esm/index.mjs"
DSH_BIN="$HARNESS_ROOT/apps/cli/src/bin.ts"
DSH_URL="http://127.0.0.1:3080"
KIMI_BIN="/Users/ioanganton/.kimi-webbridge/bin/kimi-webbridge"
LOCAL_MODEL="sifta-qwenpaw-coder:latest"
LOCAL_MODELFILE="$SIFTA_ROOT/scripts/Modelfile.qwenpaw-alice"

say_problem() {
  print -r -- ""
  print -r -- "Alice local coding: $1"
  print -r -- "Apasă Enter pentru a închide."
  read -r
  exit 1
}

navigate_to_harness() {
  local payload response
  payload='{"action":"navigate","args":{"url":"http://127.0.0.1:3080","newTab":true,"group_title":"Alice · Local Coding"},"session":"alice-local-coding"}'
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

[[ -x "$NODE_BIN" ]] || say_problem "Node.js nu există la $NODE_BIN"
[[ -f "$TSX_LOADER" ]] || say_problem "Lipsesc dependențele harness-ului. Rulează pnpm install în $HARNESS_ROOT"
[[ -f "$DSH_BIN" ]] || say_problem "Nu găsesc dsh la $DSH_BIN"

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

if ! /usr/local/bin/ollama show "$LOCAL_MODEL" >/dev/null 2>&1; then
  print -r -- "Pregătesc modelul local SIFTA (o singură dată)..."
  /usr/local/bin/ollama create "$LOCAL_MODEL" -f "$LOCAL_MODELFILE" || say_problem "Nu am putut crea $LOCAL_MODEL"
fi

if curl -fsS "$DSH_URL" >/dev/null 2>&1; then
  print -r -- "Alice local coding rulează deja la $DSH_URL"
  navigate_to_harness || {
    print -r -- "Deschide adresa de mai sus în browser și apasă Enter după ce ai terminat."
    read -r
  }
  exit 0
fi

(
  for _ in {1..90}; do
    if curl -fsS "$DSH_URL" >/dev/null 2>&1; then
      navigate_to_harness || true
      exit 0
    fi
    sleep 1
  done
) &

cd "$SIFTA_ROOT" || say_problem "Nu pot intra în $SIFTA_ROOT"
export TSX_TSCONFIG_PATH="$HARNESS_ROOT/tsconfig.json"
export DSH_TELEMETRY_DISABLED=1

print -r -- "Alice local coding"
print -r -- "Workspace: $SIFTA_ROOT"
print -r -- "Model implicit: SIFTA QwenPaw 9B Q8, context 16K, output 8K (probat pe cei 24 GB)"
print -r -- "Interfață: $DSH_URL"
print -r -- "Oprești serverul cu Control-C."
print -r -- ""

exec "$NODE_BIN" --import "$TSX_LOADER" "$DSH_BIN" web --no-open --port 3080
