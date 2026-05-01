# Event 85: Metabolic Routing & Mass Constraint
**Date:** 2026-05-01
**Covenant:** IDE_BOOT_COVENANT.md ratified
**Lane:** Triple IDE (AG31, C55M, CG55M)

## Thesis
Models are not just API strings; they are physical entities with mass (`file_weight_mb`) and metabolic cost. Event 85 turns physical file weight into a **causal constraint** for the inference router. Heavy models (like Gemma 4 9GB) cost more to load, run, and cool than light models (like Qwen 3.5 2GB). The Swarm router must balance cognitive utility against metabolic cost (the organism's energy budget).

## State Schema
The `InferenceRouteCandidate` tracks:
- `candidate_id`: The Ollama tag (e.g., "sifta-gemma4-alice:latest")
- `file_weight_mb`: Physical size on disk (instrumented via `/api/tags`)
- `latency_ms`: Ping or rolling EMA
- `token_usage`: Tokens per inference / STGM burn
- `utility`: Expected value of the cognitive task

## Cost Function
The cost vector is tuned to penalize heavy, slow, expensive routes:
```python
cost = w_m * file_weight_mb + w_l * latency_ms + w_t * token_usage
```

## Routing Rule
```python
route(task) = argmax(utility - metabolic_cost)
```
Tie-breakers: Lowest cost, then lexicographically smaller candidate ID.

## Invariants
1. **No Fake Organs:** Routing must use `REAL` observed mass via the `ollama_file_weight_ledger.py` probe.
2. **Deterministic Fallback:** If the primary `cortex` fails or the thermal threshold is exceeded, the router evaluates candidates using the cost function.
3. **Stigmergic Pheromones:** Successful hard-task completions bump the `stigmergic_weight` trace of a model, increasing its utility prior and making it more likely to be chosen despite its metabolic mass.

## Integration
- `System/inference_router.py` implements the deterministic `choose_event85_cost_vector_route`.
- `System/ollama_file_weight_ledger.py` instruments the physical mass.
- `.sifta_state/event85_inference_router_decisions.jsonl` receipts the math.
