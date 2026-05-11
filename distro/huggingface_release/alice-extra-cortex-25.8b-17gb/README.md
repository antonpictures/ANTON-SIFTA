---
license: apache-2.0
tags:
  - sifta
  - ollama
  - gemma4
  - coding
  - research
library_name: ollama
---

# Alice Extra Cortex 25.8B 17GB

Slow heavy research/coding cortex for the SIFTA Living OS.

```bash
ollama create alice-extra-cortex-25.8b-17gb:latest -f Modelfile
```

## Role

Use this only for high-cost research, coding, and long synthesis tasks where
latency and memory cost are acceptable. It is not the default Talk cortex.
SIFTA's kernel scheduler should treat it as an expensive organ and route to it
only when expected evidence value justifies the STGM/thermal cost.

## Local State Boundary

This model package is public species DNA. It must not include raw `.sifta_state/`
selfhood, contacts, owner memory, camera frames, or private receipts.
