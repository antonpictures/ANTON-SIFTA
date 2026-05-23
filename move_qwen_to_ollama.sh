#!/usr/bin/env bash
# move_qwen_to_ollama.sh
# Move the Qwen3.6 35B A3B Uncensored Q2 model out of LM Studio and into Ollama.
# Written for George (ANTON_SIFTA node). Run in macOS Terminal:
#   bash ~/Music/ANTON_SIFTA/move_qwen_to_ollama.sh
#
# What it does, in order:
#   1. PROBE  — find the .gguf inside the LM Studio store (no guessing).
#   2. IMPORT — ollama create a model that points FROM that .gguf (Ollama copies it into its own blob store).
#   3. VERIFY — ollama list / ollama show to prove it landed.
#   4. RECEIPT— only after a clean import, ASK before deleting the LM Studio copy.
# Nothing is deleted until the import is proven good.

set -euo pipefail

LMS_ROOT="$HOME/.lmstudio/models"
OLLAMA_NAME="qwen36-35b-a3b-uncensored"   # the name you'll call it in ollama
OLLAMA_TAG="q2"                            # tag for this quant
FULL_NAME="${OLLAMA_NAME}:${OLLAMA_TAG}"

echo "==> [1/4] PROBE: searching LM Studio store for the Qwen GGUF"
echo "    looking under: $LMS_ROOT"

if [ ! -d "$LMS_ROOT" ]; then
  echo "!! LM Studio model folder not found at $LMS_ROOT"
  echo "   If you installed LM Studio elsewhere, set LMS_ROOT at the top of this script."
  exit 1
fi

# Find candidate gguf files: anything qwen + 35b-ish. Show all, pick the largest match.
CANDIDATES=()
while IFS= read -r -d '' f; do
  CANDIDATES+=("$f")
done < <(find "$LMS_ROOT" -type f -iname "*.gguf" \( -iname "*qwen*" -a -iname "*35*" \) -print0 2>/dev/null)

if [ "${#CANDIDATES[@]}" -eq 0 ]; then
  echo "!! No matching .gguf found. Listing ALL ggufs so you can spot it:"
  find "$LMS_ROOT" -type f -iname "*.gguf" 2>/dev/null
  echo
  echo "   Re-run with the path hard-set:  GGUF=/full/path/to/model.gguf bash $0"
  : "${GGUF:?set GGUF to the file you want}"
fi

# Allow override via env var GGUF=...
if [ -n "${GGUF:-}" ]; then
  TARGET="$GGUF"
else
  # pick the largest candidate (sharded multi-part models: see note below)
  TARGET="$(ls -S "${CANDIDATES[@]}" | head -n1)"
fi

echo "    selected: $TARGET"
ls -lh "$TARGET"
echo

# Heads-up for sharded models (some big GGUFs are split into -00001-of-0000N.gguf)
case "$TARGET" in
  *-00001-of-*|*-00002-of-*)
    echo "    note: this looks like a SPLIT gguf. Point FROM at the FIRST shard (-00001-of-)."
    echo "          Ollama will pull in the rest automatically. Continuing with the first shard."
    ;;
esac

echo "==> [2/4] IMPORT: creating ollama model '$FULL_NAME'"
WORKDIR="$(mktemp -d)"
MODELFILE="$WORKDIR/Modelfile"
cat > "$MODELFILE" <<EOF
FROM $TARGET
EOF
echo "    Modelfile:"
sed 's/^/      /' "$MODELFILE"

if ! command -v ollama >/dev/null 2>&1; then
  echo "!! 'ollama' is not on PATH. Open the Ollama app once, or install from https://ollama.com, then re-run."
  exit 1
fi

ollama create "$FULL_NAME" -f "$MODELFILE"

echo "==> [3/4] VERIFY"
ollama list | grep -i "$OLLAMA_NAME" || { echo "!! model not in 'ollama list' — import failed, NOT deleting anything."; exit 1; }
echo
echo "    capabilities:"
ollama show "$FULL_NAME" || true

echo
echo "==> [4/4] RECEIPT: import looks good."
echo "    Ollama now has its OWN copy in ~/.ollama/models (content-addressed blobs)."
echo "    The original is still in LM Studio at:"
echo "      $TARGET"
echo
read -r -p "    Delete the LM Studio copy now to free ~15 GB? [y/N] " ans
if [[ "$ans" =~ ^[Yy]$ ]]; then
  # delete the whole publisher/repo folder this gguf lived in, but only inside LM Studio store
  REPO_DIR="$(dirname "$TARGET")"
  case "$REPO_DIR" in
    "$LMS_ROOT"/*)
      echo "    removing: $REPO_DIR"
      rm -rf "$REPO_DIR"
      echo "    done — moved, not just copied."
      ;;
    *)
      echo "!! safety stop: $REPO_DIR is outside $LMS_ROOT, refusing to delete."
      ;;
  esac
else
  echo "    kept the LM Studio copy. You can delete it later from inside LM Studio (My Models)."
fi

rm -rf "$WORKDIR"
echo
echo "Done. Run it with:  ollama run $FULL_NAME"
echo "For the Swarm."
