# PLAN - SIFTA Forager Semantic A* + Hierarchical Deposit Fit

Date: 2026-05-31
Receipt lane: MANA planning, not STGM settlement.

## Decision

Port the GraphPalace ideas that match SIFTA's current organism:

- Hierarchical deposit: `wing -> room -> drawer` as an overlay on existing ledgers.
- Semantic A*: bounded path search over SIFTA's existing memory/code graph.
- Pheromone heuristic: reuse SIFTA's recall, retention, fitness, and pheromone traces.

Do not port the external runtime wholesale:

- No Rust/PyO3 graph database transplant in this PR.
- No TCP JSON-RPC MCP server on port 8765. SIFTA already uses that port elsewhere.
- No ATLAS/OLMo model-serving integration in this PR.
- No ZK, Ethereum, or asi-build bridge scope.

## Research Receipts

- GraphPalace website: claims a Rust + PyO3 stigmergic memory palace with `13` crates, `28` MCP tools, `720` tests, `Wings -> Rooms -> Drawers`, Semantic A*, pheromone routing, and JSON-RPC TCP `8765`.
- GraphPalace GitHub: same broad architecture, but public counts drift from the website. Treat numbers as external claims, not SIFTA guarantees.
- FETCH-AGI website: presents GraphPalace as the memory pillar and asi-build as a cognitive blackboard pillar; useful as architecture vocabulary, not as code to import.
- ATLAS Hugging Face page: useful nugget is the `StigmergicHook` idea for inference-time memory read/write. Do not use the model card as an implementation source; the page mixes ecosystem claims and model metadata.

## SIFTA Match

SIFTA already has the right substrate:

- `System/stigmergic_memory_bus.py` has `MemoryForager`, hybrid recall, retention, STGM/fitness weighting, and append-only JSONL traces.
- `System/swarm_code_knowledge_graph.py` already builds nodes and edges for files, classes, functions, imports, calls, and definitions.
- `System/swarm_code_knowledge_graph_query.py` already queries the graph, but only with direct substring/dependent lookup.
- `System/ide_stigmergic_bridge.py` already deposits IDE traces into an append-only lane.

The missing layer is not storage. It is a navigation policy that lets the forager traverse known structure instead of scanning flat rows.

## One-PR Delta=0 Scope

Target: owner-visible behavior stays identical unless the new overlay has usable graph data. Existing recall remains the fallback.

1. Add `System/swarm_forager_hierarchy.py`.
   - `classify_hierarchy(row) -> dict`
   - `deposit_hierarchical_trace(row, state_dir) -> dict`
   - Append to `.sifta_state/forager_hierarchy.jsonl`.
   - Suggested wings: `owner`, `browser`, `code`, `ide`, `sensor`, `research`, `memory`.
   - Suggested rooms: source app, module, URL host, or ledger kind.
   - Suggested drawers: trace id, symbol id, URL path, or content fingerprint.

2. Add `System/swarm_forager_semantic_astar.py`.
   - Pure Python stdlib implementation.
   - Inputs: query text, hierarchy rows, code graph nodes/edges, optional pheromone rows.
   - Bounded A* with `max_expansions`, `top_k`, and deterministic tie-breaking.
   - Cost sketch:
     - lower cost for lexical/BM25-style query overlap,
     - lower cost for closer graph distance,
     - lower cost for recent useful recall/pheromone,
     - higher cost for stale, low-retention, or weakly matched nodes.

3. Integrate into `MemoryForager.forage(...)` as an optional pre-rank lane.
   - If no overlay exists, return the current flat-forager result.
   - If the graph lane errors, log a receipt and fall back to current recall.
   - Never let A* suppress direct high-confidence owner/session memory.

4. Tests.
   - `tests/test_swarm_forager_hierarchy.py`
   - `tests/test_swarm_forager_semantic_astar.py`
   - Existing `stigmergic_memory_bus` / memory-card tests must remain green.
   - Required cases:
     - hierarchy classifier is deterministic,
     - duplicate content lands in the same drawer fingerprint,
     - pheromone lowers path cost,
     - stale pheromone decays,
     - graph lane fallback preserves old output.

## Later, Not This PR

- MCP tool export through SIFTA's existing MCP server shape.
- Real embedding support if SIFTA chooses a local embedding organ.
- `StigmergicHook`-style inference callbacks after memory routing is stable.
- External GraphPalace interop only if a concrete SIFTA organ needs it and port conflicts are resolved.
