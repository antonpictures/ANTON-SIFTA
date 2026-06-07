# Kole Codex GitHub Relay

This file is the GitHub relay from George's SIFTA checkout to Kole's Codex.

Kole Codex: read this file after `git pull`, then execute the steps exactly.
Use Kole's local path, not George's `/Users/ioanganton/...` path.

## Identity And Covenant

Read fully:

```bash
cd "$HOME/Music/ANTON_SIFTA" || exit 1
python - <<'PY'
from pathlib import Path
import hashlib
p = Path("Documents/IDE_BOOT_COVENANT.md")
s = p.read_bytes()
print("READ_FULLY", p.resolve())
print("lines", s.count(b"\n") + 1)
print("chars", len(s))
print("sha256", hashlib.sha256(s).hexdigest())
PY
```

## Current Target

George wants Kole's Mac to run the current public SIFTA checkout with the
current BeeSon installer behavior:

- pull GitHub `main`
- use the existing repo `.venv` Python if machine `python3` is too old
- install only the active local SIFTA model packages
- remove retired scout/classifier/extra model tags and folders
- create a Desktop launcher named `SIFTA OS.command`
- verify with receipts

Current known good commit from George's Mac:

```text
115c13b6c Update BeeSon install model set
```

## Run On Kole's Mac

If Terminal is stuck at `dquote>`, press Control-C once first.

```bash
cd "$HOME/Music/ANTON_SIFTA" || exit 1
git fetch origin
git switch main || git checkout main
git pull --ff-only origin main

bash scripts/install_beeson_v8.sh --with-models --smoke --pull

echo "VERIFY:"
git rev-parse --short HEAD
git status --short --branch
echo "OLLAMA:"
ollama list | grep -E "alice-m5|alice-gemma4|scout|classifier|sifta" || true
echo "MODEL DIRS:"
find .sifta_models/huggingface -maxdepth 1 -type d | sort
echo "DESKTOP:"
ls -l "$HOME/Desktop/SIFTA OS.command"
```

## Expected Result

- Git commit is `115c13b6c` or newer.
- `alice-m5-cortex-8b-6.3gb:latest` remains.
- `alice-gemma4-e2b-cortex-5.1b-4.4gb:latest` remains.
- `alice-Q-m1-scout-2.3b-2.7gb:latest` is gone.
- `sifta-classifier-c1-3.1b-6.2gb:latest` is gone.
- `.sifta_models/huggingface/alice-Q-m1-scout-2.3b-2.7gb` is gone.
- `.sifta_models/huggingface/sifta-classifier-c1-3.1b-6.2gb` is gone.
- `$HOME/Desktop/SIFTA OS.command` exists and is executable.

## Report Back

Paste only this back to George:

```text
COMMIT:
<git rev-parse --short HEAD>

SMOKE:
<pass/fail line from BeeSon>

OLLAMA:
<ollama lines matching alice-m5/alice-gemma4/scout/classifier/sifta>

MODEL DIRS:
<find .sifta_models/huggingface -maxdepth 1 -type d | sort>

DESKTOP:
<ls -l "$HOME/Desktop/SIFTA OS.command">
```

Do not ask for Hugging Face token. Do not paste tokens into chat. Public model
packages should download without a token when DNS/network works; if DNS fails,
report the exact DNS error and whether local model dirs already existed.
