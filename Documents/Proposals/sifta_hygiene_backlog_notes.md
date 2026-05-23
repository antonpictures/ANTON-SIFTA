# SIFTA Hygiene Backlog Notes

Status: triage notes from the next hygiene pass.

## Artifact Ingestion

- `Documents/Proposals/epiphenomenal_sign_language.md` already exists in the
  repo and matches the Antigravity artifact at
  `/Users/ioanganton/.gemini/antigravity/brain/622c5acb-7fd9-4d16-a485-a5f1a23e4169/artifacts/epiphenomenal_sign_language.md`.
- Verified SHA-256 for both copies:
  `553b97e3a526561a3bf7b49f5913b088aec3f9130e00568f5fa6a1f57868bd89`.
- No copy is needed unless the artifact changes.

## Memory And Prompt Wiring

- Talk-widget recall is already wired through
  `StigmergicMemoryBus.recall_context_block()` inside the Talk to Alice context
  builder.
- Pheromone Symphony still needs a targeted
  `StigmergicMemoryBus.remember()` call for meaningful creative/chat activity.
  Do not write every heat tick; store only owner-visible creative events.
- `SwarmEpistemicGradient` exists in `System/swarm_theory_of_mind.py`, but it is
  not yet injected into every Talk-widget turn. Future work should add a small
  prompt directive and tests around mixed narrative/real-action prompts.

## Test Loop

- The reported `pytest --collect-only` segfault remains unverified. No matching
  local receipt or issue note was found in the repo search.
- Reproduce before patching: run collection with `PYTHONFAULTHANDLER=1`, capture
  the crashing module, then isolate imports rather than broad-skipping tests.
