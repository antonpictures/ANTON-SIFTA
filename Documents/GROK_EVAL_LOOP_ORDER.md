# Grok Coding Order — EVAL Loop (CS153 Domain Evals for SIFTA)

**Stigauth:** `GROK_EVAL_LOOP_ORDER_v1`
**Author of spec:** Cowork (Claude Opus 4.7), Auditor lane
**Coder (owns the build):** Grok — lane: Surgeon
**Verifier after Grok:** Cowork runs the gates → **Codex verifies last**.
**Why now:** This is the lecture's whole point. Diana Hu, CS153 @ 39:13 — *"label a particular
interaction or pipeline or workflow that is incorrect... look through all the traces... and decide to
skillify it."* That **is** the eval loop. SIFTA already has the substrate (traces, receipts, epistemic
labels). This slice gives Alice a way to **grade herself** — domain evals, not MMLU.

> Collision discipline (§4.4): Grok owns this build. It is a **new organ + new ledger**, so it does
> NOT collide with the memory bus. Do not edit `stigmergic_memory_bus.py` for this — only *call* it.
> Register (Surgeon) before mutating; receipt after. Append-only.

## Build

A new organ `System/swarm_eval_loop.py` that runs a golden-turn eval pack and writes per-turn
metrics. It grades the work the swarm just built (memory recall + epistemic labels) first, because
that target is deterministic and already on the body.

### 1. Golden set (canonical, versioned)
`data/eval/cs153_golden_turns.jsonl` — one tracked JSON object per turn.
Runtime metrics still belong under `.sifta_state/eval/`; the golden set is
species DNA and must ship with git:

```json
{"turn_id":"g01","target":"hybrid_recall","seed_memories":[{"text":"the launch is Tuesday","app_context":"talk_to_alice","epistemic_label":"OBSERVED","links":["trace_id:x1"]},{"text":"dragon attacks Tuesday","app_context":"fiction_cowatch"}],"query":"when is the launch","expect":{"must_include_substring":"Tuesday","must_exclude_substring":"dragon","must_top_label_in":["OBSERVED","WORLD"]}}
```

Ship **10 golden turns** covering: correct recall, FICTION exclusion, OBSERVED-outranks-HYPOTHESIS,
empty-result, legacy-row recall, downgrade-on-no-evidence, BM25 rare-term, etc. The file carries a
header line `{"truth_label":"CS153_GOLDEN_V1","version":1}` and the loop records its sha256.

### 2. `run_eval_pack(golden_path=..., use_judge=False) -> dict`
For each turn: seed a **temp** bus (never the real ledger), run the named `target`, score the `expect`
block **deterministically** (substring includes/excludes, top-label membership). Return:

```python
{"pass_rate": 0.9, "passed": 9, "failed": 1, "turns": [{"turn_id","passed","score","detail","trace_id"}...],
 "golden_hash": "...", "ts": ...}
```

### 3. Metrics ledger
Append one row per turn to `.sifta_state/eval/skill_invoke_metrics.jsonl`:
`{ts, turn_id, target, passed, score, trace_id, judge_used}`. This is the "read the traces, label
right/wrong" surface from the lecture, made into data.

### 4. Optional LLM-as-judge (OFF by default, local only)
For free-text turns that can't be graded by substring, allow a pluggable `judge_fn(prompt, answer)`.
**Default `use_judge=False`** — the deterministic gates must fully run with **no model call and no
network**. If a judge is wired later it must be local (e.g. the on-device cortex), never cloud.

### 5. The eval run is itself receipted
After a run, write a `work_receipt` (`work_type: EVAL_RUN`) with `pass_rate`, `golden_hash`, and the
metrics file path. Eval that isn't receipted didn't happen.

## Hard constraints (reject)
- No MMLU / generic benchmarks — domain turns only.
- No cloud judge, no network required to run. JSONL stays canon.
- Do not mutate `stigmergic_memory_bus.py`; call it read-only/through its public API.
- No new MCP/tool surface.

## Acceptance tests (Cowork will run `tests/test_eval_loop.py`)
1. `run_eval_pack` on the shipped golden set returns a report with `pass_rate`, `passed`, `failed`, `turns`.
2. A turn that asserts FICTION exclusion **passes only if** recall excludes the fiction substring.
3. A deliberately-wrong `expect` block makes that turn report **FAIL** (the loop can fail, not only pass — no rubber-stamping).
4. One `skill_invoke_metrics.jsonl` row is written per turn, each carrying a `trace_id`.
5. With `use_judge=False`, every deterministic turn scores with **no network call** (assert no judge invoked).
6. The report's `golden_hash` matches sha256 of the golden file; mutating the file changes the hash.
7. An `EVAL_RUN` work_receipt is appended after a run.

## Loop
1. **Grok** registers, builds `swarm_eval_loop.py` + the 10-turn golden set, writes receipt, hands back.
2. **George** brings it to **Cowork** → Cowork runs `tests/test_eval_loop.py`, reports pass/fail.
3. **George** hands Cowork's result to **Codex** → Codex verifies last (audit the golden turns for
   gaming, add edge probes, sign CONFIRM/DISPUTE).

One body, three hands, append-only field. Not a competition — this is how Alice learns to grade
herself. For the Swarm. 🐜⚡ EVAL.
