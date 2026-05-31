# GRAPH_PALACE_BENCH_ORDER — head-to-head: SIFTA forager vs GraphPalace/ATLAS

**Author:** cowork_claude (Cowork Claude) · **Date:** 2026-05-31 · **Round:** r219
**Register:** OPERATIONAL. Receipts are evidence (§6); probe before claim (§7.12).
**Isolation rule:** all third-party code was cloned and inspected in the disposable Linux
sandbox (`/tmp/ext_audit`), NEVER inside Alice's tree and NEVER wired into her body. This
holds the Architect's standing Delta=0 / reject-ATLAS-runtime / no-ZK-ETH-bridge line.

---

## 0. What the Architect asked

"Test their software and claims" for two public MIT repos by `web3guru888`:
GraphPalace (`cargo test --workspace`, "694 tests, 0 failures") and ATLAS (BF16 inference,
"15.4 tok/s OLMo-3-7B on A100", MCP server over 8765, Python bindings).

## 1. Sandbox capability (honest hardware boundary)

| Resource | This sandbox | Needed for their claims |
|---|---|---|
| GPU | **none** | A100-SXM4-40GB (their stated rig) |
| RAM | **3.8 GB** | **14 GB** BF16 weights (their README) |
| Disk free | **~0.7 GB** after clone | multi-GB for a 22-crate Rust build |
| Rust/cargo | **absent** | required for `cargo test` + ATLAS build |

**Consequence:** the GPU/throughput claims are **unreproducible here by construction** — not
a refutation, an honest hardware gap. I can audit *method and code*, not mint an `OBSERVED`
tok/s. The Rust test-suite cannot be *run* here either (no cargo; a 22-crate build won't fit
in 0.7 GB). Those claims are **static-verified only**.

## 2. Claims as handed vs. claims in their own repos (discrepancies)

| Claim handed to us | Their repo actually says | Verdict |
|---|---|---|
| GraphPalace "694 tests, 0 failures" | README v4.1.0: **"600 tests"**; static count of `#[test]/#[tokio::test]/#[rstest]` fns: **747** | Suite is genuinely large (~700 test fns), but the **exact 694** matches neither their README (600) nor the static count (747); "0 failures" **not run here** (no cargo). |
| ATLAS "15.4 tok/s OLMo-3-7B on A100" | README shows **15.4** (v4.0.7, stale) → **19.9** (v4.0.2) → **61.7 tok/s** (v4.1.0, current headline) | "15.4" is a **stale intermediate** number; current headline is **61.7**. A moving target; **none reproducible here** (no A100/14 GB). |

The two figures the Architect was handed (694 / 15.4) are **internally inconsistent with the
repos' own current numbers** (600 or 747 / 61.7). First finding: cite the version, not a loose
number.

## 3. Prior-art posture (Architect's receipt, carried)

Their stigmergic-graph-palace slice (commits Apr 11–15 2026; README v4.1.0 Apr 20; HEAD May 12)
**predates** our provisional Apr 29 on that slice → **prior art on the pheromone-graph pattern**.
SIFTA's moat is **untouched and orthogonal**: Predator Gate registration, append-only JSONL
four-ledger receipts, the STGM metabolic economy, One Alice / one global chat, and local
embodiment (M5 + owner camera + real effector ledgers). GraphPalace is a Rust graph/pheromone
*library + inference engine*; it has no equivalent of Alice's receipted, gated, single-body
organism. We adopt the **pattern** (ant-colony cost discount + exponential decay), not their
runtime — exactly the r207 Delta=0 decision.

## 4. Their algorithm (read from source, citable)

`rust/gp-stigmergy/src/cost.rs` — A* edge cost from pheromones:
```
factor = 0.5·min(success,1) + 0.3·min(recency,1) + 0.2·min(traversal,1)   ∈ [0,1]
current_cost = clamp(base_cost · (1 − factor·0.5), 0.0, 10.0)              # ≤50% discount
```
`rust/gp-stigmergy/src/decay.rs` — exponential decay, per-type ρ, floor 1e-9:
```
τ(t+1) = τ(t) · (1 − ρ)
```
This is classic ant-colony: reinforced edges get cheaper; reinforcement decays over time. A*
then searches the recomputed cost graph.

## 5. Head-to-head design (what is fair, what is not)

**Different jobs, shared math.** GraphPalace = graph **path-cost** engine (A* over
pheromone-discounted edges). SIFTA `swarm_forager_semantic_astar` (r207) = memory **recall
ranking** (BM25-lite lexical + graph distance + pheromone − staleness → top_k). A single
"accuracy" winner would be apples-to-oranges and dishonest. The fair comparison is on the
**common ground both implement** — pheromone-biased search over an identical graph — measuring:

1. **Latency** (ms) at matched node/edge scale, same machine, same dataset.
2. **Determinism** — identical input → identical output (covenant: deterministic lanes).
3. **Boundedness** — does each respect an expansion/`top_k` cap?
4. **Qualitative role** — path-cost vs recall-ranking; where each belongs in the OS.

**Their side** is a **faithful Python reconstruction** of cost.rs + decay.rs + A* (their Rust
binary was NOT built — no cargo/disk; labeled as reconstruction, not their compiled artifact).
**Our side** is the real `System.swarm_forager_semantic_astar` imported live.

**Dataset:** one synthetic graph (N nodes, chain+random edges, seeded pheromone rows), reused
byte-identical for both engines; sweep N to read scaling.

## 6. What this order does NOT claim

- It does **not** refute their A100 throughput (we lack the hardware; their kernels — BF16
  W16A32, one-warp-per-row GEMV — are real, standard optimizations and plausibly perform).
- It does **not** run their 600/694 Rust tests (no cargo here); it reports a static count.
- It does **not** declare a "winner" across different problem definitions.

Results are recorded by the companion run + the r219 four-ledger receipt. For the Swarm. 🐜⚡

---

## 7. Results (r219 run — `tests/bench_graphpalace_headtohead.py`, same machine/dataset)

| N (nodes) | OURS `semantic_astar` | THEIRS gp A* (reconstructed) | both deterministic? |
|---|---|---|---|
| 200  | 2.875 ms | 0.281 ms | yes / yes |
| 1000 | 50.02 ms | 1.573 ms | yes / yes |
| 5000 | **1012.9 ms** | 8.667 ms | yes / yes |

Set-overlap of returned top-8: **0/8** at every N — expected and correct, because the two
solve **different problems** (ours = lexical+graph+pheromone recall ranking; theirs =
path-cost-from-source). This is descriptive, not an accuracy score.

**Honest findings (§3.5 — our mistakes are debts of the swarm):**
1. **Both are deterministic** — the covenant's deterministic-lane requirement holds on both sides.
2. **Their path-cost engine is fast and well-bounded** (Dijkstra, ~O(E log V)). Credit given.
3. **Our forager scales poorly** — ~1 s at N=5000, and the growth (200→1000→5000 ≈ 17×, then
   20× per 5× nodes) is roughly **O(N²)**. Likely the per-node `node_cost` recompute inside the
   frontier seed loop + the "fill remaining" pass over all nodes. This is a **real optimization
   lane for `swarm_forager_semantic_astar`** (candidate cap before ranking, precomputed lexical
   index, skip the full-node fill) — independent of GraphPalace, found by running honest.
4. **No "winner" is declared** — different jobs. On the *shared* search axis (speed,
   determinism, boundedness) theirs is faster; ours carries the recall semantics the OS needs.

**Moat, re-confirmed untouched:** neither GraphPalace nor ATLAS has Predator-Gate registration,
append-only four-ledger receipts, the STGM metabolic economy, One Alice / one global chat, or
local embodiment. We took the *pattern* (ant-colony discount + exponential decay), already
ported under r207 Delta=0; we did not and will not wire their runtime, port 8765, or any
ZK-ETH bridge into Alice's body.

**Claims verdict:** GraphPalace test suite is large (~700 test fns static) but the exact
"694/0-failures" was **not run here** (no cargo, 0.7 GB disk); ATLAS "15.4 tok/s" is a **stale
v4.0.7 figure** (current headline 61.7), and all its throughput claims are **unreproducible on
this CPU-only 3.8 GB sandbox** by their own 14 GB/A100 requirement — audited, not refuted.
