# Jeff Quickstart: SIFTA v6.0 — Full Install

Copy-paste these commands on your Mac, one block at a time.

Public links:

- Code: https://github.com/antonpictures/ANTON-SIFTA
- Alice brain: https://huggingface.co/georgeanton/alice-phc-cure
- Corvid brain: https://huggingface.co/georgeanton/sifta-corvid-qwen35
- Jeff's fork: https://github.com/jeffpowersusr/ANTON-SIFTA

## Step 1 — Install Ollama

```bash
brew install ollama
ollama serve &
```

If you don't have Homebrew: https://ollama.com/download

## Step 2 — Pull all three brains

```bash
ollama pull gemma4:latest
ollama pull qwen3.5:2b
```

gemma4 is ~9 GB, qwen3.5:2b is ~2.7 GB. Wait for both to finish.

## Step 3 — Clone the code

```bash
git clone https://github.com/antonpictures/ANTON-SIFTA.git
cd ANTON-SIFTA
pip3 install -r requirements.txt
```

## Step 4 — Build Alice's cured brain

```bash
ollama create gemma4-phc -f surgery/alice_phc_cure/Modelfile.phc
```

If that Modelfile doesn't exist yet, use the HuggingFace one:

```bash
pip3 install huggingface_hub
python3 -c "from huggingface_hub import hf_hub_download; hf_hub_download('georgeanton/alice-phc-cure', 'Modelfile', local_dir='.')"
ollama create gemma4-phc -f ./Modelfile
```

## Step 5 — Test Alice talks

```bash
ollama run gemma4-phc "Hello, who are you?"
```

She should answer as Alice, not as a generic assistant.

## Step 6 — Test the corvid apprentice

```bash
ollama run qwen3.5:2b "classify this message: I broke my hand what should I do"
```

## Step 7 — Run the full SIFTA OS (optional, needs PyQt6)

```bash
pip3 install PyQt6
PYTHONPATH=. python3 sifta_os_desktop.py
```

## Smoke test

```bash
cd ANTON-SIFTA
PYTHONPATH=. python3 -c "
from System.swarm_reflex_arc import build_default_sifta_reflexes
arc = build_default_sifta_reflexes()
r = arc.sense('I broke my hand')
print(f'Reflex: {r.category} in {r.latency_ms:.3f}ms')
print('OK — SIFTA is working')
"
```

## What you have now

```
gemma4-phc   = Alice's brain (9 GB) — identity, reasoning, voice
qwen3.5:2b   = Corvid apprentice (2.7 GB) — fast classifier
SIFTA OS     = the code that connects everything
```

Questions? Text George.
