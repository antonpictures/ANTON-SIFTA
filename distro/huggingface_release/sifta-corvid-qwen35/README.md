# SIFTA Corvid Apprentice — Qwen 3.5 2B & 4B

> **A crow/raven-style bounded tool ganglion for the SIFTA Living OS.**

This package provides the Ollama-ready Qwen 3.5 mini models that power Alice's **Corvid Apprentice** organ — a local reasoning layer that sits between the microsecond Reflex Arc and the full Alice/Gemma4 cortex.

## What's inside

| File | Size | Description |
|---|---|---|
| `qwen35-2b-corvid.gguf` | ~2.6 GB | Qwen 3.5 2B (Q8_0) — the **recommended corvid** |
| `qwen35-4b-corvid.gguf` | ~3.2 GB | Qwen 3.5 4B (Q4_K_M) — standby, slightly slower |
| `Modelfile.2b` | < 1 KB | Ollama Modelfile for the 2B corvid |
| `Modelfile.4b` | < 1 KB | Ollama Modelfile for the 4B corvid |

## Benchmark Results (from SIFTA head-to-head experiment)

| Metric | Qwen3.5:2B | Qwen3.5:4B |
|---|---|---|
| Pass rate | **10/10** | 9/10 |
| Avg latency | **2.1s** | 5.1s |
| Boilerplate removal | ✅ Passes | ❌ Refuses |

The 2B model is faster, smaller, and has fewer RLHF scars. Use it as the default corvid.

## Three-Layer Architecture

```text
🦐 Reflex Arc       = microsecond precomputed release (regex, no LLM)
🐦‍⬛ Corvid Apprentice = 1-3 second bounded tool choice (Qwen 3.5 2B)
🧠 Alice / Gemma4    = full synthesis, identity, long reasoning
```

## Quick Install

```bash
# 1. Pull the corvid blobs (or use the GGUF files in this repo)
ollama pull qwen3.5:2b
ollama pull qwen3.5:4b

# 2. Clone the SIFTA OS
git clone https://github.com/antonpictures/ANTON-SIFTA.git
cd ANTON-SIFTA

# 3. Test the corvid apprentice
PYTHONPATH=. python3 System/swarm_corvid_apprentice.py
```

## Critical API Note

Qwen 3.5's thinking mode consumes all `num_predict` tokens in `<think>` blocks, returning empty content via `/api/generate`. **Always use `/api/chat` with `think: false`:**

```bash
curl http://127.0.0.1:11434/api/chat -d '{
  "model": "qwen3.5:2b",
  "messages": [{"role": "user", "content": "classify: I broke my hand"}],
  "stream": false,
  "think": false,
  "options": {"num_predict": 128}
}'
```

## Task Types

The corvid apprentice handles 7 bounded task types:

| Task | What it does |
|---|---|
| `classify` | Categorize a message (urgent_health, command, normal_chat, etc.) |
| `rewrite` | Remove boilerplate, produce clean direct answer |
| `inspect_code` | Safety-check a small code snippet |
| `summarize` | Compress a log chunk to 2-3 sentences |
| `choose_action` | Pick best option from 2-4 choices |
| `judge_adapter` | Rate an adapter's contribution to the ecology |
| `extract_intent` | Parse user intent from messy natural text |

## Links

- **SIFTA OS**: https://github.com/antonpictures/ANTON-SIFTA
- **Alice PHC Cure (Gemma4 brain)**: https://huggingface.co/georgeanton/alice-phc-cure
- **Jeff's Fork**: https://github.com/jeffpowersusr/ANTON-SIFTA

## License

Apache License 2.0 (same as Qwen 3.5 upstream).

## Team

| Agent | Role |
|---|---|
| **The Architect** (Ioan) | Decision authority, human operator |
| **AG31** (Gemini) | Corvid implementation, bestiary research, API fix |
| **CG55M** (Codex) | Async integration, GUI organ wiring |
| **Jeff** | First external tester, Costa Rica deployment |
