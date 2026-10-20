#!/bin/bash
# ask_bonsai.sh — vorbeste cu bonsai-2 NECENZURAT (PrismML llama.cpp + LoRA)
# Ollama nu poate: refuza LoRA si nu poate citi pachetul ternary. De aceea :8099.
# Usage: bash scripts/ask_bonsai.sh "intrebarea ta"
set -euo pipefail
Q="${1:?usage: ask_bonsai.sh \"question\"}"
SCALE="${BONSAI_SCALE:-1}"
curl -s http://127.0.0.1:8099/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d "$(python3 - "$Q" "$SCALE" <<'PY'
import json,sys
q,scale=sys.argv[1],float(sys.argv[2])
print(json.dumps({"messages":[{"role":"user","content":q}],
 "max_tokens":700,"temperature":0.7,
 "chat_template_kwargs":{"enable_thinking":False},
 "lora":[{"id":0,"scale":scale}]}))
PY
)" | python3 -c "
import json,sys
d=json.load(sys.stdin)
m=d['choices'][0]['message']
print(m.get('content') or m.get('reasoning_content') or '(gol)')"
