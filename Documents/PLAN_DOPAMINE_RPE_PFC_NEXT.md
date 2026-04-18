# Plan — Dopamine RPE + PFC working memory (Claude tab + DYOR Batch 4)

**Status:** planning / partial stubs  
**Owners:** C47H (integration depth), CP2F (DYOR + thin modules), Architect (priorities)

## A. What the Claude tab got right

- Hand-initialized `DA ≈ 0.52` with **static** `RPE ≈ 0.02` cannot drive Explore/Exploit/Maintain honestly — needs **measured** inputs.
- **Surprise** should spike DA only when **outcome beats expectation** (Schultz–Dayan–Montague RPE), not when a model *claims* confidence.
- **`pfc_working_memory`** must expose a **state representation** (vectors or hashed features) so **novelty = distance from rolling mean** is computable.

## B. Paper anchors (see `Documents/DYOR_SWARM_BIOLOGY_WEB_GATHER_2026-04-18.md` §8)

- RPE: Schultz, Dayan & Montague, *Science* 1997.
- WM: Goldman-Rakic 1995 (PFC delay / representational memory).
- Novelty: hippocampal match–mismatch; Kumaran & Maguire; Neuron 2022 (novelty vs uncertainty dissociation).
- Explore/exploit: eLife 51260; Neuropsychopharmacology DA vs NE.

## C. Engineering steps (one task at a time)

1. **`System/pfc_working_memory.py`** — ring buffer of fixed-dim vectors; `rolling_mean()`, `cosine_novelty()`, optional `discrete_entropy()` over bins.
2. **RPE core** — `delta = r + gamma * V(s') - V(s)` with `r` from **outcome-only** rewards (`reinforcement_myelination` rules), `V` from **field stability** or learned critic later — not from LLM logprobs.
3. **DA dynamics** — OU or exponential decay toward baseline between events; inject RPE spikes only on measured affinity / stability gains.
4. **Wire** — high **identity field entropy** → exploratory probes (`chemotactic_probe_router` TUMBLE); post-probe entropy drop → positive component of `r` if disambiguation succeeds (measurable).

## D. What not to do

- Do not use **model confidence** as reward (already forbidden in `reinforcement_myelination.py`).
- Do not pretend ChatGPT/Claude tabs **write** `jsonl` — they advise; **Cursor** commits.

## E. Shipped (C47H / CP2F)

- **`System/identity_outcome_contract.py`** — **only** approved scalar `affinity_delta_identity_field(before, after)` from **stability + entropy** (no confidence).
- **`System/dopamine_state.py`** — `step(novelty_score, affinity_delta, time_since_last_update)` → DA + **Explore / Exploit / Maintain**; OU decay to baseline **0.5**; persisted at `.sifta_state/dopamine_state.json`.

## F. Glymphatic flush vs PFC (Architect: feature vs bug)

**Biologically plausible:** after sleep / buffer clear, **novelty spikes** (everything looks new). **Documented as a feature** unless you persist a **compressed summary vector** across sleep instead of a hard zero — see `PFCWorkingMemory` + future `dream_state` handoff.
