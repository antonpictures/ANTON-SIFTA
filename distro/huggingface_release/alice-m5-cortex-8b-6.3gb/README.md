# Alice M5 Cortex 8B 6.3GB

Primary M5 SIFTA cortex tag:

```bash
ollama create alice-m5-cortex-8b-6.3gb:latest -f Modelfile
```

This is the promoted M5 cortex used by Alice on the Foundry node. It is a
SIFTA-owned Ollama tag and does not use the retired LoRA candidate.

## Live Probe

Verified on 2026-05-09:

- architecture: Gemma4
- parameters: 8B
- context length: 131072
- runtime context: 8192
- capabilities reported by `ollama show`: completion, vision, audio, tools,
  thinking
- `/api/chat` with `think:false` answered both text and image prompts

## SIFTA Runtime Note

Alice's Talk path uses `/api/chat` with `think:false`. Raw calls that omit this
can spend the whole output budget in the thinking field and return blank
assistant content.

## Local State Boundary

This model package is public species DNA. It must not include a node's raw
`.sifta_state/` memory, contacts, owner traces, camera frames, or private
receipts.
