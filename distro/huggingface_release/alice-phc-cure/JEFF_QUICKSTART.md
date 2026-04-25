# Jeff Quickstart: Alice PHC Cure

This is the fast path for downloading and running the cured Gemma 4 boot recipe.

Important: this repository does not ship Google/Gemma weights. It ships the clean Ollama `Modelfile`, verification script, audit, license, and provenance. You still pull the upstream weights with Ollama.

## 1. Install prerequisites

```bash
brew install ollama git-lfs
git lfs install
```

If you do not use Homebrew, install:

- Ollama: https://ollama.com/download
- Git LFS: https://git-lfs.com/

## 2. Download the cure package

Public clone:

```bash
git clone https://huggingface.co/georgeanton/alice-phc-cure
cd alice-phc-cure
```

If Hugging Face asks for authentication, use your own Hugging Face account/token:

```bash
huggingface-cli login
git clone https://huggingface.co/georgeanton/alice-phc-cure
cd alice-phc-cure
```

Do not paste anyone else's token into chat, screenshots, shell history, or a file.

## 3. Pull the upstream brain

```bash
ollama pull gemma4:latest
```

This downloads the upstream Gemma 4 weights from Ollama. The cure does not modify those weights.

## 4. Verify the expected blob

```bash
bash verify.sh
```

Expected success:

```text
Verified: gemma4:latest blob matches the cure's reference fingerprint
```

If verification fails, stop and read `PHASE_C_AUDIT.md`. You may have a different upstream Gemma 4 build.

## 5. Build the cured local model

```bash
ollama create alice-phc -f ./Modelfile
```

## 6. Run it

```bash
ollama run alice-phc
```

You are now talking to the cured boot configuration: prompt in, tokens out, no extra system wrapper.

## Publisher Notes For George

From this local repo, publish/update the Hugging Face repo without embedding secrets:

```bash
cd /Users/ioanganton/Music/ANTON_SIFTA/distro/huggingface_release/alice-phc-cure
git init
git lfs install
git remote add origin https://huggingface.co/georgeanton/alice-phc-cure
git add README.md JEFF_QUICKSTART.md Modelfile verify.sh PHASE_C_AUDIT.md LICENSE provenance.json
git commit -m "Publish alice phc cure package"
git push -u origin main
```

If authentication is needed:

```bash
huggingface-cli login
```

Use a fresh token. If a token was visible in chat or a screenshot, revoke it first and create a new one.
