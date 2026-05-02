# Alice Hardware Anatomy

Truth label: OPERATIONAL install topology. M5 inventory is OBSERVED from
`ollama list` on 2026-05-01. Smaller-node rows are hardware policy until those
nodes write their own receipts.

Every SIFTA node uses the same anatomy:

```text
hardware body -> sensors/receipts -> local scout/reflex -> Alice Foundry
```

The difference is not identity. The difference is physical memory, heat, and
what the node can honestly run.

## M5 Foundry, 24 GB

This is Alice's full body on the current machine.

```mermaid
flowchart TB
    M5["M5 Foundry\nApple M5 / 24 GB"]

    Sensors["Sensors + OS organs\ncamera, audio, GPS, WhatsApp,\npheromone, cochlea, retina"]
    Receipts["Signed JSONL receipts\n.sifta_state/*"]

    Alice["PRIMARY CORTEX\nsifta-gemma4-alice:latest\n9.6 GB\nINSTALLED"]
    VLM["MULTIMODAL SCOUT\nqwen3.5:9b\nGB unknown until pulled\nPLANNED"]
    Corvid["CORVID / REFLEX\nqwen3.5:2b\n2.7 GB\nINSTALLED"]
    Classifier["C1 CLASSIFIER\nsifta-classifier-c1:latest\n6.2 GB\nINSTALLED / TEST ONLY"]
    Doctor["DOCTOR / TOOL PROVER\ngranite4.1:3b\nGB unknown until pulled\nOPTIONAL TEST"]
    Fallback["FALLBACK / COMPARE\nsifta-alice-qwen35:latest\n2.7 GB\nINSTALLED"]
    Base["RAW BASE\ngemma4:latest\n9.6 GB\nINSTALLED / TEST ONLY"]

    M5 --> Sensors --> Receipts --> Alice
    VLM --> Receipts
    Corvid --> Receipts
    Classifier --> Receipts
    Doctor --> Receipts
    Fallback -. emergency compare .-> Alice
    Base -. base diagnostics .-> Alice
```

## Mac Mini Sentry, 8 GB

This should look like Alice's anatomy, but smaller. It is a sentry/scout, not a
second full Foundry. Gemma4 is skipped by memory physics because the RAM is
soldered and the runtime model footprint does not fit safely.

```mermaid
flowchart TB
    Mini["Mac Mini Sentry\n8 GB"]

    Sensors["Sensors + OS organs\ncamera/audio/files/network if present"]
    Receipts["Signed JSONL receipts\nlocal node ledger"]

    AliceRemote["ALICE FOUNDRY TARGET\nM5 sifta-gemma4-alice:latest\n9.6 GB on M5"]
    Scout["LOCAL MULTIMODAL SCOUT\nqwen3.5:4b\nGB unknown until pulled\nPLANNED FOR MINI"]
    Corvid["LOCAL CORVID / REFLEX\nqwen3.5:2b\n2.7 GB if installed\nRECOMMENDED"]
    GemmaSkip["GEMMA4 PRIMARY\nsifta-gemma4-alice:latest\n9.6 GB\nSKIPPED BY 8 GB PHYSICS"]

    Mini --> Sensors --> Receipts --> AliceRemote
    Scout --> Receipts
    Corvid --> Receipts
    GemmaSkip -. not selected .-> Receipts
```

## Python Field Node

This is the Raspberry Pi, tractor, sensor box, camera box, or any device that
can run Python. It still has Alice-shaped anatomy, but the local brain slot is
empty by default. Its job is to turn world events into signed facts.

```mermaid
flowchart TB
    Field["Field Node\nRaspberry Pi / tractor / sensor box\nany Python hardware"]

    Sensors["Physical sensors\nGPS, camera, temperature,\nsoil, CAN, GPIO, serial"]
    Receipts["Signed feature receipts\nJSONL facts, no raw surveillance by default"]

    AliceRemote["ALICE FOUNDRY TARGET\nM5 sifta-gemma4-alice:latest\n9.6 GB on M5"]
    Tiny["OPTIONAL TINY SCOUT\nqwen3.5:0.8b\nGB unknown until pulled\nFUTURE TEST ONLY"]
    NoModel["DEFAULT LOCAL BRAIN\nno LLM\n0 GB\nVALID"]

    Field --> Sensors --> Receipts --> AliceRemote
    Tiny --> Receipts
    NoModel --> Receipts
```

## One-Line Rule

```text
M5 = Alice thinks.
Mac Mini = Alice scouts locally and reports.
Pi / tractor = Alice senses the world and reports.
```

Same anatomy. Different physical scale.
