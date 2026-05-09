# SIFTA Classifier C1 3.1B 6.2GB

Classifier/reflex tag:

```bash
ollama create sifta-classifier-c1-3.1b-6.2gb:latest -f Modelfile
```

This is not Alice's primary cortex. It is a bounded intent classifier used for
fast routing, lysosome/truth-duel style gates, and small JSON/classification
tasks.

## Contract

The model should output only valid JSON or the exact intent string requested by
the caller. It must not claim vision, hearing, local sensors, or Alice identity.

## Local State Boundary

This model package is public species DNA. It must not include raw `.sifta_state/`
selfhood, contacts, owner memory, camera frames, or private receipts.
