# CODING PLAN — 2026-10-12

## 1. Gemini in the harness (`!Alice Coding Arm`) — BLOCKER, do first
Symptom: selecting a gemini model in the Models list does not work.

Fixed so far (each verified):
- `inception.models[*].reasoningEfforts` had key `"false"`; schema accepts `"off"` — this invalidated
  the whole providers dict, which is why gemini never loaded beside it.
- Provider `gemini` added: baseURL `https://generativelanguage.googleapis.com/v1beta/openai`,
  api `openai-completions`, models 3.5-flash-lite / 3.7-flash / 3.8-flash.
- Credential written to `~/.dsh/.credentials.yaml` refs (mode 0600) because the Models panel only
  lists providers that HAVE a stored credential. Also written to the repo `.env` (gitignored) for
  the SIFTA body, which reads the env var.
- Key itself verified: HTTP 200, 62 models, replies in Romanian. Cost measured $0.00005040/run.

Next diagnostic (not yet done): read the harness log for the exact error raised when a gemini turn
is attempted, instead of guessing. Then confirm whether the harness resolves `apiKeyEnv` from
`~/.dsh/.credentials.yaml`, from the process environment, or only after the provider is saved once
through the UI.

## 2. Borg Embedding Gemma 2 — semantic recall (approved 2026-10-12)
The gap, in my own words from the eval matrix: "Nu caut semantic. Nu am embeddings ... trebuie sa
sti numele." Keyword recall finds words; it cannot find "the rover guy" if I never learned a name.

- `google/embeddinggemma-300m` (3.4M downloads), GGUF builds by ggml-org/unsloth, Apache-2.0,
  <1B params, 768 dims shrinkable to 256 (1M files: 3 GB -> 1 GB).
- **Blocker found:** the local Ollama answers `This server does not support embeddings. Start it
  with --embeddings`. One flag, or serve through `llama-server --embeddings`.
- Plan: `System/swarm_semantic_recall.py` beside the keyword index, with per-media-type calibration
  (the file-type bias the model's own reviewer found), then measured against keyword recall on the
  same questions — `--prove`, numbers, not claims.

## 3. Three-layer memory, named
| layer | role | state |
|---|---|---|
| trails (JSONL) | the truth | 910 ledgers |
| keyword index | exact, 0.73% of journal, 0.8 ms | live |
| embedding index | semantic | to build (item 2) |

## 4. stigmergicoin.com — content and behaviour to keep
Observed live 2026-10-12: chat surface answering in first person, signed "alice · <id> · mps",
citing web results, and — correctly — REFUSING to invent VCIG figures it did not hold. That refusal
is the doctrine working in public. Keep it. Note the surface attributes turns to MPS
(GoogleMapsCoin) while the coin price shown is $0.000003133.

## 5. Body persistence (from 2026-10-12)
`scripts/body_essentials_watchdog.sh` + `com.sifta.body-essentials.plist` keep :8100 and the
sifta-web tunnel alive and log every repair. Extend it to :3010, :7434 and the harness — launchd
failed to bring those back on its own three times today.
