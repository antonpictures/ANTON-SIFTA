#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${SIFTA_REPO_URL:-https://github.com/antonpictures/ANTON-SIFTA.git}"
TARGET_DIR="${SIFTA_TARGET_DIR:-$HOME/Music/ANTON_SIFTA}"
WITH_MODELS=0
RUN_SMOKE=1
FORCE_PULL=0

usage() {
  cat <<'EOF'
BeeSon v8.1 installer

Usage:
  bash scripts/install_beeson_v8.sh [--with-models] [--no-smoke] [--target DIR] [--pull]

Options:
  --with-models   Download public Hugging Face cortex packages and create Ollama tags when possible.
  --no-smoke      Skip the focused release smoke test.
  --target DIR    Clone/install into DIR when not already inside a SIFTA checkout.
  --pull          Fast-forward an existing clean checkout before installing.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-models) WITH_MODELS=1 ;;
    --skip-models) WITH_MODELS=0 ;;
    --smoke) RUN_SMOKE=1 ;;
    --no-smoke) RUN_SMOKE=0 ;;
    --pull) FORCE_PULL=1 ;;
    --target)
      shift
      TARGET_DIR="${1:?missing target directory}"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

banner() {
  printf '\033[1;33m'
  cat <<'EOF'
  ================================================
       BeeSon v8.1 installer - SIFTA Living OS
       Fresh Mac path: code, venv, receipts, smoke
  ================================================
EOF
  printf '\033[0m'
}

banner

if [[ -f "./sifta_os_desktop.py" && -d "./System" && -d "./Applications" ]]; then
  REPO_DIR="$(pwd)"
  echo "[beeson] using current checkout: $REPO_DIR"
else
  REPO_DIR="$TARGET_DIR"
  if [[ -d "$REPO_DIR/.git" ]]; then
    echo "[beeson] checkout exists: $REPO_DIR"
    if [[ "$FORCE_PULL" == "1" ]]; then
      if [[ -n "$(git -C "$REPO_DIR" status --porcelain)" ]]; then
        echo "[beeson] checkout is dirty; skipping pull to preserve local work"
      else
        git -C "$REPO_DIR" pull --ff-only
      fi
    fi
  else
    echo "[beeson] cloning $REPO_URL -> $REPO_DIR"
    mkdir -p "$(dirname "$REPO_DIR")"
    git clone "$REPO_URL" "$REPO_DIR"
  fi
  cd "$REPO_DIR"
fi

PYTHON_BOOT="${PYTHON_BOOT:-}"
if [[ -z "$PYTHON_BOOT" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BOOT="$(command -v python3)"
  fi
  if [[ -x ".venv/bin/python" ]]; then
    if [[ -z "$PYTHON_BOOT" ]] || ! "$PYTHON_BOOT" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
    then
      PYTHON_BOOT=".venv/bin/python"
      echo "[beeson] using existing repo venv python because machine python3 is too old"
    fi
  fi
fi

if [[ -z "$PYTHON_BOOT" ]] || ! command -v "$PYTHON_BOOT" >/dev/null 2>&1; then
  echo "ERROR: python3 not found. Install Xcode command line tools or Homebrew Python first." >&2
  echo "Try: xcode-select --install" >&2
  exit 1
fi

"$PYTHON_BOOT" - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit(f"Python 3.11+ required; found {sys.version.split()[0]}")
print(f"[beeson] python {sys.version.split()[0]} OK")
PY

if [[ ! -d ".venv" ]]; then
  echo "[beeson] creating .venv"
  "$PYTHON_BOOT" -m venv .venv
fi

# shellcheck source=/dev/null
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if [[ -f "System/bootstrap_pki.py" ]]; then
  echo "[beeson] bootstrapping local Ed25519 identity if needed"
  PYTHONPATH=. python -m System.bootstrap_pki || {
    echo "[beeson] bootstrap_pki failed; continuing because older checkouts may initialize on first boot"
  }
fi

chmod +x "SIFTA OS.command" 2>/dev/null || true
chmod +x scripts/beeson_smoke_test.sh 2>/dev/null || true
xattr -c "SIFTA OS.command" scripts/beeson_smoke_test.sh 2>/dev/null || true

if [[ "$WITH_MODELS" == "1" ]]; then
  echo "[beeson] installing Hugging Face client"
  python -m pip install "huggingface_hub>=0.23"
  MODEL_ROOT="$REPO_DIR/.sifta_models/huggingface"
  mkdir -p "$MODEL_ROOT"
  python - <<'PY'
from __future__ import annotations
import inspect
from pathlib import Path
from huggingface_hub import snapshot_download

models = [
    ("georgeanton/alice-m5-cortex-8b-6.3gb", "alice-m5-cortex-8b-6.3gb"),
    ("georgeanton/alice-gemma4-e2b-cortex-5.1b-4.4gb", "alice-gemma4-e2b-cortex-5.1b-4.4gb"),
]
root = Path(".sifta_models/huggingface")
for repo_id, name in models:
    target = root / name
    print(f"[beeson] HF download {repo_id} -> {target}")
    kwargs = dict(
        repo_id=repo_id,
        local_dir=str(target),
        ignore_patterns=["*.md.tmp", ".git/*"],
    )
    if "local_dir_use_symlinks" in inspect.signature(snapshot_download).parameters:
        kwargs["local_dir_use_symlinks"] = False
    snapshot_download(**kwargs)

retired = (
    "alice-Q-m1-scout-2.3b-2.7gb",
    "sifta-classifier-c1-3.1b-6.2gb",
    "alice-extra-cortex-25.8b-17gb",
)
for name in retired:
    target = root / name
    if target.exists():
        print(f"[beeson] removing retired local model dir {target}")
        import shutil
        shutil.rmtree(target)
PY
  if command -v ollama >/dev/null 2>&1; then
    if ollama list >/dev/null 2>&1; then
      ollama rm "alice-Q-m1-scout-2.3b-2.7gb:latest" >/dev/null 2>&1 || true
      ollama rm "sifta-classifier-c1-3.1b-6.2gb:latest" >/dev/null 2>&1 || true
      ollama rm "alice-extra-cortex-25.8b-17gb:latest" >/dev/null 2>&1 || true
      for model_dir in "$MODEL_ROOT"/*; do
        [[ -f "$model_dir/Modelfile" ]] || continue
        tag="$(basename "$model_dir"):latest"
        echo "[beeson] ollama create $tag"
        (cd "$model_dir" && ollama create "$tag" -f Modelfile) || {
          echo "[beeson] WARN: ollama create failed for $tag"
        }
      done
    else
      echo "[beeson] Ollama is installed but not responding. Start Ollama, then rerun with --with-models."
    fi
  else
    echo "[beeson] Ollama not found. Install from https://ollama.com, then rerun with --with-models."
  fi
fi

mkdir -p .sifta_state
BEESON_WITH_MODELS="$WITH_MODELS" python - <<'PY'
from __future__ import annotations
import json, os, time, uuid
from pathlib import Path

row = {
    "ts": time.time(),
    "trace_id": str(uuid.uuid4()),
    "kind": "BEESON_V8_INSTALL_RECEIPT",
    "repo_dir": str(Path.cwd()),
    "with_models": os.environ.get("BEESON_WITH_MODELS", "0") == "1",
    "launcher": "SIFTA OS.command",
    "smoke_script": "scripts/beeson_smoke_test.sh",
}
path = Path(".sifta_state/beeson_v8_install_receipts.jsonl")
with path.open("a", encoding="utf-8") as f:
    f.write(json.dumps(row, sort_keys=True) + "\n")
print(f"[beeson] install receipt {row['trace_id']} -> {path}")
PY

if [[ -d "$HOME/Desktop" ]]; then
  cat > "$HOME/Desktop/SIFTA OS.command" <<'SH'
#!/bin/zsh
cd "$HOME/Music/ANTON_SIFTA" || exit 1
exec "$HOME/Music/ANTON_SIFTA/SIFTA OS.command"
SH
  chmod +x "$HOME/Desktop/SIFTA OS.command"
  xattr -c "$HOME/Desktop/SIFTA OS.command" 2>/dev/null || true
  echo "[beeson] Desktop launcher ready: $HOME/Desktop/SIFTA OS.command"
fi

if [[ "$RUN_SMOKE" == "1" ]]; then
  bash scripts/beeson_smoke_test.sh
fi

cat <<EOF

[beeson] Install complete.

Next:
  open ~/Desktop/"SIFTA OS.command"

macOS permissions to grant on first boot:
  - Microphone
  - Camera
  - Accessibility, if you want desktop control
EOF
