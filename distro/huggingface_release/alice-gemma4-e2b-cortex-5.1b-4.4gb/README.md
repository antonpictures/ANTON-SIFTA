---
license: apache-2.0
tags:
  - sifta
  - ollama
  - gemma4
  - local-ai
library_name: ollama
---

# Alice Gemma4 E2B Cortex 5.1B 4.4GB

Small daily Gemma4 cortex for the SIFTA Living OS.

```bash
ollama create alice-gemma4-e2b-cortex-5.1b-4.4gb:latest -f Modelfile
```

## Role

Use this as the lighter daily dialogue/reasoning cortex when the full M5 cortex
is unnecessary or the node should conserve memory. It is still a cortex lane:
tool execution and external claims must pass through SIFTA organs and receipts.

## Local State Boundary

This model package is public species DNA. It must not include raw `.sifta_state/`
selfhood, contacts, owner memory, camera frames, or private receipts.
