# WCT Plan — Cortex tags become variables (2026-09-18)

Owner: George. Trigger: watchdog reported a model that no longer exists
(`alice-m5-cortex-8b-6.3gb:latest`) because Talk's resolver silently swapped
the missing tag for the smallest installed model (SmolVLM 0.5 GB, vision-only),
and all `alice-*` SIFTA cortex tags are gone from the Ollama store. George
tries new cortexes all the time; names must never be hardcoded.

## Decisions (owner, 2026-09-18)

- `krishairnd/Gemma-4-Uncensored:latest` is renamed to `krishairnd/G4U` and
  becomes the default local cortex.
- The alice-* legacy tags (`alice-m5-cortex-8b-6.3gb`,
  `alice-gemma4-e2b-cortex-5.1b-4.4gb`, `alice-m1-cortex-4.5b-3.4gb`,
  `alice-extra-cortex-25.8b-17gb`) are dead history: they are deleted from
  live routing, preference ladders and the `missing_legacy_canonical`
  reporting. Receipts/history docs that mention them stay as history.
- The default is one variable, overridable by
  `SIFTA_DEFAULT_OLLAMA_MODEL` env or
  `.sifta_state/swimmer_ollama_assignments.json`. No module hardcodes a tag.

## Execution steps

1. Ollama store: `ollama cp krishairnd/Gemma-4-Uncensored:latest krishairnd/G4U`,
   then `ollama rm krishairnd/Gemma-4-Uncensored:latest`. Same blob, zero
   download. Old name survives in old receipts via alias coercion.
2. `System/sifta_inference_defaults.py`:
   - one variable `CANONICAL_OLLAMA_DEFAULT = "krishairnd/G4U:latest"`;
   - every legacy `CANONICAL_OLLAMA_*` constant becomes a shim to it;
   - `_LEGACY_LOCAL_PREFERENCE` = only the current default variable;
   - `_is_non_dialogue_ollama_default_candidate` rejects vision-only tags
     (smolvlm, minicpm-v, llava, -vlm, moondream, embed) so size-first ranking
     can never hand Talk a non-dialogue model;
   - alias coercion `krishairnd/gemma-4-uncensored` -> `krishairnd/g4u`;
   - boot inventory stops reporting the dead `missing_legacy_canonical` list.
3. `.sifta_state/swimmer_ollama_assignments.json`: default + per-app rows
   move to `krishairnd/G4U:latest`.
4. `System/swarm_cortex_aliases.py` fallback constants point at the one
   variable.
5. Talk widget: `_CANONICAL_TALK_M5_MODEL` becomes the imported default
   variable; watchdog message reports `requested=` and `resolved=`.
6. Tests updated to the variable, focused suite green; WCT receipts; a
   DeepSeek test job doc for independent verification.
