#!/bin/bash
# r743 — HF model swap. George's law (2026-06-07): "IF LLMS NOT HERE DELETE THEM
# FROM HUGGINGFACE" — every osmapi repo with no local twin dies; local latest push.
#
# Local twins on this Mac (the survivors):
#   models/osmQwopus-3.6-27B-OptiQ-3.7bpw-mlx  (June-2 rebuild, 14.9G, 4 shards)
#   models/gemma-4-e2b-it                       (vision eye)
#
# Kill list (no local twin):
#   osmapi/osmQwopus-3.6-27B-V2-heretic-abliterated-uncensored-8-bit-mlx
#   osmapi/osmQwopus-3.6-27B-V2-heretic-abliterated-uncensored-6-bit-mlx
#   osmapi/osmQwopus-3.6-27B-V2-heretic-abliterated-uncensored-8-bit-GGUF
#   osmapi/osmQwopus-3.6-27B-V2-heretic-abliterated-uncensored-6-bit-GGUF
#   osmapi/osmQwopus-3.6-27B-V2-heretic-abliterated-uncensored-TQ3_4s-GGUF
#   osmapi/osmQwopus-3.6-27B-V2-heretic-abliterated-uncensored-TQ3_1s-GGUF
#   osmapi/osmQwopus-3.6-27B-V2-heretic-abliterated-uncensored-Q4_K_M-GGUF
#
# Kept + overwritten with the June-2 build:
#   osmapi/osmQwopus-3.6-27B-V2-heretic-abliterated-uncensored-OptiQ-3.7bpw-mlx
# Created/updated:
#   osmapi/gemma-4-e2b-it
#
# Run on the Mac:  bash tools/hf_swap_models.sh
# Token source: $HF_TOKEN env, else ~/.cache/huggingface/token (hf auth login).

set -euo pipefail
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TOKEN="${HF_TOKEN:-$(cat "$HOME/.cache/huggingface/token" 2>/dev/null || true)}"
if [ -z "$TOKEN" ]; then
  echo "NO TOKEN: export HF_TOKEN=hf_... or run: hf auth login" >&2
  exit 1
fi
export HF_TOKEN="$TOKEN"

python3 -m pip install -q -U huggingface_hub hf_transfer || true
export HF_HUB_ENABLE_HF_TRANSFER=1

KILL=(
  "osmapi/osmQwopus-3.6-27B-V2-heretic-abliterated-uncensored-8-bit-mlx"
  "osmapi/osmQwopus-3.6-27B-V2-heretic-abliterated-uncensored-6-bit-mlx"
  "osmapi/osmQwopus-3.6-27B-V2-heretic-abliterated-uncensored-8-bit-GGUF"
  "osmapi/osmQwopus-3.6-27B-V2-heretic-abliterated-uncensored-6-bit-GGUF"
  "osmapi/osmQwopus-3.6-27B-V2-heretic-abliterated-uncensored-TQ3_4s-GGUF"
  "osmapi/osmQwopus-3.6-27B-V2-heretic-abliterated-uncensored-TQ3_1s-GGUF"
  "osmapi/osmQwopus-3.6-27B-V2-heretic-abliterated-uncensored-Q4_K_M-GGUF"
)

echo "== DELETING ${#KILL[@]} repos with no local twin =="
python3 - "$@" <<'PY'
import os, sys
from huggingface_hub import HfApi
api = HfApi(token=os.environ["HF_TOKEN"])
kill = [
  "osmapi/osmQwopus-3.6-27B-V2-heretic-abliterated-uncensored-8-bit-mlx",
  "osmapi/osmQwopus-3.6-27B-V2-heretic-abliterated-uncensored-6-bit-mlx",
  "osmapi/osmQwopus-3.6-27B-V2-heretic-abliterated-uncensored-8-bit-GGUF",
  "osmapi/osmQwopus-3.6-27B-V2-heretic-abliterated-uncensored-6-bit-GGUF",
  "osmapi/osmQwopus-3.6-27B-V2-heretic-abliterated-uncensored-TQ3_4s-GGUF",
  "osmapi/osmQwopus-3.6-27B-V2-heretic-abliterated-uncensored-TQ3_1s-GGUF",
  "osmapi/osmQwopus-3.6-27B-V2-heretic-abliterated-uncensored-Q4_K_M-GGUF",
]
for rid in kill:
    try:
        api.delete_repo(repo_id=rid, repo_type="model")
        print("DELETED", rid)
    except Exception as e:
        print("SKIP", rid, "->", type(e).__name__, str(e)[:120])
PY

echo "== DELETING 10 April-era georgeanton repos (George GO 2026-06-07 10:11 PDT) =="
echo "== KEPT supply line: m5-cortex-8b, m1-cortex-4.5b, classifier-c1, gemma4-e2b-cortex, Q-m1-scout, extra-cortex-25.8b =="
python3 - <<'PY'
import os
from huggingface_hub import HfApi
api = HfApi(token=os.environ["HF_TOKEN"])
kill = [
  "georgeanton/alice-lana-cure",
  "georgeanton/alice-phc-cure",
  "georgeanton/lana-cure",
  "georgeanton/sifta-corvid-qwen35",
  "georgeanton/alice-cortex-v1",
  "georgeanton/alice-cortex-v1-lora",
  "georgeanton/alice-classifier-v2",
  "georgeanton/alice-classifier-v2-lora",
  "georgeanton/sifta-gemma4-alice",
  "georgeanton/sifta-living-os",
]
for rid in kill:
    try:
        api.delete_repo(repo_id=rid, repo_type="model")
        print("DELETED", rid)
    except Exception as e:
        print("SKIP", rid, "->", type(e).__name__, str(e)[:120])
PY

echo "== PUSHING June-2 OptiQ rebuild over the kept repo =="
hf upload "osmapi/osmQwopus-3.6-27B-V2-heretic-abliterated-uncensored-OptiQ-3.7bpw-mlx" \
  "$REPO_DIR/models/osmQwopus-3.6-27B-OptiQ-3.7bpw-mlx" . --repo-type model \
  || huggingface-cli upload "osmapi/osmQwopus-3.6-27B-V2-heretic-abliterated-uncensored-OptiQ-3.7bpw-mlx" \
       "$REPO_DIR/models/osmQwopus-3.6-27B-OptiQ-3.7bpw-mlx" . --repo-type model

echo "== PUSHING gemma-4-e2b-it =="
python3 - <<'PY'
import os
from huggingface_hub import HfApi
api = HfApi(token=os.environ["HF_TOKEN"])
api.create_repo("osmapi/gemma-4-e2b-it", repo_type="model", exist_ok=True)
print("repo ready: osmapi/gemma-4-e2b-it")
PY
hf upload "osmapi/gemma-4-e2b-it" "$REPO_DIR/models/gemma-4-e2b-it" . --repo-type model \
  || huggingface-cli upload "osmapi/gemma-4-e2b-it" "$REPO_DIR/models/gemma-4-e2b-it" . --repo-type model

echo "== DONE — verify: https://huggingface.co/osmapi =="
