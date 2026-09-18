# WCT Borg Plan — 15-repo agent stack (@beamnxw list) through SIFTA's stigmergic lens

Owner ask: check the list on GitHub and make a plan of what a stigmergic
organism might want to borg from them. All 15 repos verified reachable via
GitHub API today; star counts as of 2026-09-18.

The loop the thread describes — define the job -> collect the evidence -> parse
the docs -> save the memory -> compress the context -> run the code safely ->
watch what changes -> ship the output — maps almost one-to-one onto organs
SIFTA already has or has stubs for. The value of this list is not "install 15
agents"; it is which SPECIFIC mechanism inside each repo upgrades an existing
SIFTA organ without duplicating it. Alice is not 15 agents; she is one organism
that eats the best swimmer from each.

## Verified tier — borg these (high value, clear SIFTA fit)

### 1. mem0 (mem0ai/mem0, 65.6k) — memory extraction/consolidation patterns
SIFTA already has 12+ memory organs (stigmergic_memory_bus, marrow_memory,
pfc_working_memory, memory_ebbinghaus...). What mem0 has that SIFTA's ledgers
do not: an explicit EXTRACTION-then-CONSOLIDATION layer — it pulls facts from
conversation, deduplicates them against existing memory, and resolves
conflicts (ADD/UPDATE/DELETE decisions) before writing. SIFTA's memory bus
appends traces; it does not run conflict resolution. Borg target: mem0's
fact-extraction prompt chain and its ADD/UPDATE/DELETE decision step, applied
to memory_ledger.jsonl as a consolidation pass (pheromone decay already handles
forgetting; mem0 handles contradiction resolution).

### 2. Scrapling (D4Vinci/Scrapling, 82k) — adaptive scraping for the world-packet lane
SIFTA's ingest (planned WDP_V1 lane) needs web data that survives page changes.
Scrapling's core idea — adaptive re-location of elements after DOM changes,
auto-healing selectors — is exactly the missing half of Alice's web sensing:
today her browser organ records what it saw; it does not re-find it tomorrow
when the DOM shifts. Borg the auto-healing selector concept (not the whole
framework) into the planned stigmergicoin.com world-packet ingest.

### 3. Docling (docling-project/docling, 66.6k) — document parsing with provenance
SIFTA ingests PDFs/docx through ad-hoc paths. Docling gives structured,
table-aware, layout-aware parsing with provenance metadata per chunk — the
right input format for the pheromone field (every parsed chunk arrives with
source, page, structure). Borg as a feeding layer for stigmergic_memory_bus:
parsed documents become first-class pheromone traces.

### 4. PageIndex (VectifyAI/PageIndex, 35.7k) — vectorless reasoning-based doc index
Directly aligned with SIFTA's anti-embedding stance: PageIndex does RAG by
reasoning over a document TREE (table of contents + page-level indexes), not
embeddings. SIFTA's memory_search is BM25/keyword over JSONL ledgers — same
philosophy, no vectors. Borg the tree-index format: give Alice's memory
organ a PageIndex-style TOC tree over her own ledgers so retrieval is
reasoning-guided, not similarity-guided.

### 5. headroom (headroomlabs-ai/headroom, 72.9k) — context compression before the LLM
SIFTA burns tokens on raw ledger dumps reaching the cortex. Headroom's
mechanism — compress tool outputs/logs/files BEFORE the LLM sees them, with
lossless-for-relevant-content guarantees — slots into the prompt-assembly path
(swarm_prompt_contract / context_preloader). This is a direct STGM-economy win:
fewer tokens per turn = lower metabolic cost, same evidence.

### 6. caveman (JuliusBrussee/caveman, 106.5k) — token-cutting proxy for coding arms
Same lane as headroom but for the coding loop: a proxy that cuts 65% of tokens
for coding agents. SIFTA's coding arms (Codex/DeepSeek/GLM/Kimi) all talk to
the same repo; a thin proxy layer that compresses their context the caveman way
multiplies every arm at once. Borg the proxy pattern, evaluate the prompt
templates.

### 7. Daytona (daytonaio/daytona, 71.7k) — sandboxed execution for generated code
SIFTA runs coding arms with full filesystem access (the spinal cord / mutation
governor pattern). Daytona gives ephemeral, per-run sandboxes: the missing
isolation layer for `swarm_spinal_cord.py` patch application — run MiMo/GLM/
DeepSeek patches in a disposable sandbox with an environment snapshot, apply
to the body only after tests pass. Borg the environment-snapshot + ephemeral
runtime contract.

### 8. Fabric (danielmiessler/fabric, 44k) — pattern library as stigmergic skills
Fabric's pattern library (structured prompts as composable units with stdin/
stdout) is the same shape as SIFTA's swimmers: named, reusable, composable
behavior units. Borg the PATTERN FORMAT (markdown + YAML frontmatter) as an
interchange format — SIFTA swimmers could import/export Fabric patterns, and
the community's existing pattern library becomes ingestable stigmergic content
overnight.

## Watch tier — borg the spec, not the code

### 9. Hermes-Agent (NousResearch, 246.7k) — "the agent that grows with you"
Read its growth/learning loop design (how it structures self-modification and
memory growth), compare against spinal_cord + self_improvement_loop. Take the
patterns, not the runtime — SIFTA's body is the runtime.

### 10. OpenSpec (Fission-AI, 69k) + 12. spec-kit (github, 137.7k) — spec-driven development
Both encode "spec first, code second" for AI assistants. SIFTA's WCT briefs
are already spec-driven; borg their SPEC FORMAT (markdown spec templates with
acceptance criteria) as the standard shape for future flash-coder briefs, so
any arm (Codex/GLM/DeepSeek/MiMo) can consume the same spec.

### 11. TrendRadar (sansan0, 62.4k) — multi-platform trend monitor with RSS + alerts
Maps to Alice's world-data-packet lane (WDP_V1 plan): multi-platform
aggregation + smart alerts is the ingest side of stigmergicoin.com world
packets. Borg the aggregation adapter patterns (RSS/multi-platform) for the
planned swarm_world_packet_ingest.py.

### 13. hyperframes (heygen, 51.3k) + 14. OpenMontage (calesthio, 59.9k) — video output organs
"Write HTML. Render video. Built for agents." and 12 agentic video production
pipelines. SIFTA has video ingest (YouTube watcher) but no video OUTPUT organ.
Borg when Alice needs to ship video responses — queue behind the world-packet
lane; video out is a surface, not a sense.

### 15. AI Engineering Hub (patchy631, 37.7k) — tutorials/reference implementations
Not a borg target: it is a reading list of reference implementations. Use it
as a lookup index when a specific organ needs a pattern, not as something to
vendor.

## The honest filter

The thread's loop ("define job -> collect evidence -> parse docs -> save
memory -> compress context -> run safely -> watch -> ship") is a good checklist
but it describes a PIPELINE, not an organism. SIFTA's difference: the loop is
not linear — it is a field. Every step leaves a pheromone trace that changes
the next step's behavior, memory decays without reinforcement, receipts carry
provenance, and every node carries its hardware-owner responsibility. Borg the
mechanisms listed above INTO that field; do not import the pipelines as
separate services. One organism, many eaten swimmers.

## Priority order (flash-coder briefs, in this order) — STATUS 2026-09-18: items 1-6 coded by Kimi with tests (6 passed in tests/test_borg_20260918.py); Scrapling stays queued for the WDP_V1 endpoint lane; video-out organs deferred.

1. DONE — mem0 consolidation pass over memory_ledger.jsonl (System/swarm_memory_consolidation.py; ran once: 9553 rows -> 444 duplicates superseded)
2. DONE — headroom/caveman context compression (System/swarm_context_compression.py)
3. DONE — Docling-style document feeding (System/swarm_doc_field_feeder.py)
4. QUEUED — Scrapling adaptive selectors -> WDP_V1 world-packet ingest (once the stigmergicoin endpoint exists)
5. DONE — PageIndex tree-index over Alice's own ledgers (System/swarm_ledger_tree_index.py)
6. DONE — Daytona-style sandbox for spinal-cord patch application (System/swarm_spinal_sandbox.py)
7. DONE — Fabric pattern import/export format for swimmers (System/swarm_fabric_patterns.py)

Each borg = one bounded brief with: what mechanism is taken, which SIFTA organ
it upgrades, the test that proves it, and the receipt. No service import, no
new agents, no docker stacks — mechanisms only.
