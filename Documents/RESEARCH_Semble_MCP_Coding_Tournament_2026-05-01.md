# Research — Semble + MCP for coding tournament (stigmergic nuggets)

**For the Swarm.** 🐜⚡

**Truth label:** `RESEARCH_NOT_SHIPPED` — ideas and citations for tournament / harness work; nothing here is merged runtime until **Architect GO + pytest + Predator row**.

**Primary sources (video + code):**

- Fahd Mirza, *Semble + OpenCode + Ollama: Local Code Search MCP for AI Agents* (YouTube, 2026-05-01) — demo transcript: local MCP, OpenCode terminal agent, Ollama backend, “grep burns context” narrative.
- **Semble** upstream: [github.com/MinishLab/semble](https://github.com/MinishLab/semble) — install path described as `pip install` with MCP extras in the video.

**Tournament context in-repo:** [CODING_TOURNAMENT_TRIPLE_IDE.md](CODING_TOURNAMENT_TRIPLE_IDE.md) (hill / triple-IDE honesty), [PREDATOR_TOURNAMENT_TRIPLE_IDE_ORDERS.md](PREDATOR_TOURNAMENT_TRIPLE_IDE_ORDERS.md) (Colosseum law), [Documents/BISHOP_BUNDLE_QUANTUM_SACK_2026_05_01.md](BISHOP_BUNDLE_QUANTUM_SACK_2026_05_01.md) (receipt doctrine), `System/swarm_multi_prover_verifier.py` (Event 99 quorum on claims).

---

## 1. What the video is selling (extract claims → verify later)

| Claim (as stated in transcript/comments) | Risk | Honest SIFTA stance |
|:---|:---|:---|
| ~**98% fewer tokens** than “grep whole files” | Marketing / workload dependent | **Benchmark on ANTON_SIFTA** with fixed prompts + token counter; write result to `work_receipts.jsonl`. |
| Index in **~250 ms**, query in **~1.5 ms** on CPU | Hardware + corpus dependent | Same: micro-benchmark harness, pinned repo revision. |
| **16M-parameter** “portion” embedding + **BM25** + **RRF** fusion | Plausible engineering pattern | Treat as **retrieval stack pattern**, not magic; compare against `ripgrep` + selective `read_file` for your agents. |
| Works with **OpenCode** + **MCP** + **Ollama** | Integration truth | Spike in disposable venv; do not vendor into `main` until license + NPPL review. |

---

## 2. Technical nugget — why this matters for *agents*

**Problem class:** coding agents that **linear-scan** the repo blow context, latency, and **inference economy** (joules / STGM if routed through cloud).

**Semble-shaped answer:** a **retrieval tool** returns *ranked spans* (path + line ranges + short excerpts) so the LLM consumes **evidence**, not entire files.

**SIFTA mapping:** your stack already has **MCP** (`sifta_mcp_server.py`, see [SIFTA_ONBOARDING.md](SIFTA_ONBOARDING.md) §7). A Semble-style server is a **parallel MCP tool provider** (stdio) that answers `code_search` style calls — **orthogonal** to Swarm organs, same **append-only receipt** discipline.

---

## 3. Stigmergic design — receipts for retrieval (novel tournament glue)

Treat every retrieval as a **stigmergic deposit**, not a silent cache:

```json
{
  "truth_label": "CODE_RETRIEVAL_RECEIPT",
  "query_norm": "sha256 of normalized query",
  "index_revision": "git rev-parse HEAD or semble index id",
  "top_k": [
    {"path": "System/foo.py", "line_start": 120, "line_end": 145, "score": 0.82}
  ],
  "latency_ms": 1.8,
  "tool": "semble_mcp"
}
```

**Why:** tournament judges (and **Event 99** multi-prover rows) can require **two agents** to cite **overlapping receipts** on the same `query_norm` before accepting a patch story — same spirit as Bell-style “no local hidden explanation”: you cannot fake having read `foo.py` if your receipt points elsewhere.

**Cross-link:** `swarm_multi_prover_verifier.submit_claim(..., proof={"retrieval_receipt_id": ...})` — optional extension, not implemented in this research file.

---

## 4. Novel combinations (Semble × SIFTA organs)

1. **Semble × `swarm_media_ingress_gate` metaphor:** ambient speech is *high entropy*; retrieval is *low entropy* routing into dialog. Same **honesty** pattern: classify tool output as **evidence** vs **noise**.
2. **Semble × Predator “cheap signal” enemy:** “I read the whole repo” without receipt = **unbounded bloom**-class lie. Retrieval receipt = **Zahavi-honest** cheap proof of attention (path + lines).
3. **Semble × borrowed inference ([ALICE_HARDWARE_ANATOMY.md](ALICE_HARDWARE_ANATOMY.md))):** field nodes are RAM-poor; **small local index** + **M5 Foundry** for heavy reasoning = split **index / rank** vs **synthesize** — mirrors “tractor perceives, Foundry speaks.”
4. **Semble × Ollama audit (`System/ollama_model_inventory_audit.py`):** after index rebuild, log **disk + RAM** footprint next to model inventory rows so retrieval does not **steal** the same GB as Gemma4.

---

## 5. Minimal integration sketch (when GO)

1. **Sidecar process:** `python -m semble.mcp` (exact module TBD from upstream README) run from **repo root**, stdio.
2. **Cursor / OpenCode / Antigravity:** add MCP server block pointing at that venv; **never** commit API keys (local only).
3. **`sifta_mcp_server.py`:** optional **proxy tool** `code_search_semble` that forwards JSON-RPC to child stdio — only if covenant allows child processes from MCP (review **§7.6 / governance**).
4. **`pytest`:** golden-query fixture: “where is `deposit` defined?” → expect `ide_stigmergic_bridge.py` in top-k; assert **stable** across OS in CI with **pinned** index.

---

## 6. Boundaries (NPPL + non-proliferation)

- **No** “index the whole internet” from battlefield machines without explicit scope.
- **No** using retrieval to **pull secrets** from ignored paths; respect `.gitignore` / covenant redaction.
- **No** claiming tournament victory on **unbenchmarked** token savings.

---

## 7. One-line tournament takeaway

> **Ship ranked spans + receipts, not vibes.** Semble is a pattern for **token-cheap evidence**; SIFTA wins when those hits become **ledger-backed** and **pytest-gated**.

For the Swarm. 🐜⚡
