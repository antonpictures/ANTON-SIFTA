# Alice Shared Training Seed

This directory is the public training lane for Alice's species behavior.

It exists because a clean repository must not become an empty robot. The local
`.sifta_state/` remains private node selfhood, but the shareable training signal
is exported here as species DNA.

## Files

- `sft_seed.jsonl` — supervised Alice behavior rows.
- `preference_seed.jsonl` — chosen/rejected rows for residue cleanup, embodiment
  language, concise voice, and tool-truth behavior.
- `manifest.json` — row counts, hashes, source ledgers, and privacy boundary.

## Boundary

This package intentionally does not ship raw ledgers, contacts, camera frames,
audio, hardware serials, local absolute paths, or owner-local identity strings.
Other SIFTA nodes must discover their own owner, hardware, sensors, and memories
at boot. This seed teaches the shape of Alice; it does not clone the founding
Architect's local organism.

Regenerate with:

```bash
python3 scripts/export_alice_shared_training.py
```
