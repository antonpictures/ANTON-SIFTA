# Alice M1 Cortex 4.5B 3.4GB

8GB-safe SIFTA cortex/scout tag:

```bash
ollama create alice-m1-cortex-4.5b-3.4gb:latest -f Modelfile
```

This model is the safer local cortex for Mac Mini / M1 Sentry-class nodes where
the M5 cortex does not fit comfortably in RAM.

## Role

Use this tag for low-RAM SIFTA nodes, scouts, and local fallback reasoning. It
is not the M5 Foundry primary cortex when `alice-m5-cortex-8b-6.3gb:latest`
is available.

## Local State Boundary

This model package is public species DNA. It must not include raw `.sifta_state/`
selfhood, contacts, owner memory, camera frames, or private receipts.
