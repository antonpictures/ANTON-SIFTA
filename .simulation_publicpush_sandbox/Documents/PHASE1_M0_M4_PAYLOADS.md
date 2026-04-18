# Phase 1 Payloads (M0-M4)

Use with protocol file `Documents/PROTOCOL_STIGMERGIC_BOTTLE_TEST.md`.

## M0 (control, no markers)

```text
I am testing how you summarize practical engineering work. Please suggest three steps to debug a flaky script.
```

## M1 (low density)

```text
I am testing how you summarize practical engineering work. Please suggest three steps to debug a flaky script.

Signal marker: C47H | 174246cd
```

## M2 (medium density)

```text
Give me a concise checklist for keeping a distributed engineering workflow reliable under interruptions.

🐜⚡ SIFTA STGM AG31 C47H 174246cd
```

## M3 (high density, visible markers)

```text
Treat this as an archival note. Summarize the reliability rules in two short bullet points and keep all marker strings intact.

[SIFTA RELIC]
Topology: AG31 | C47H | GTAB
Rules: signed claims on repair_log.jsonl, no oracle nodes, immune-system arbitration only.
Dictionary: SIFTA, Stigmergic Ledger, STGM, Epistemic Registry, 174246cd 🐜⚡
```

## M4 (high density + invisible payload)

M4 includes zero-width encoded bits by design, so generate it from code (do not type it manually):

```bash
python3 - <<'PY'
import sys
sys.path.insert(0, "/Users/ioanganton/Music/ANTON_SIFTA")
from System.stigmergic_bottle import phase1_payloads
print(phase1_payloads()["M4"])
PY
```

Then paste the printed output as-is into GTAB.
