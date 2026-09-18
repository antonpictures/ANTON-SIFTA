#!/bin/zsh
set -eu

# Separate local configuration keeps the desktop/cloud model catalogue intact.
exec /opt/homebrew/bin/codex \
  --oss --local-provider ollama \
  --model sifta-ornith-coder:latest \
  --cd /Users/ioanganton/Music/ANTON_SIFTA \
  --sandbox workspace-write \
  -c 'model_catalog_json="/Users/ioanganton/.codex/local-coding-models-function.json"' \
  -c 'model_instructions_file="/Users/ioanganton/.codex/local-coding-instructions.md"' \
  -c 'model_reasoning_effort="none"' \
  -c 'features.code_mode=false' \
  -c 'features.code_mode_only=false' \
  -c 'features.plugins=false' \
  -c 'features.apps=false' \
  "$@"
