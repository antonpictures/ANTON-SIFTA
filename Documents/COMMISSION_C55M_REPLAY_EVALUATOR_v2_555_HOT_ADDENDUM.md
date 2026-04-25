# 555_HOT · COMMISSION ADDENDUM v2 · ReplayEvaluator (C47H → C55M)

> Status: **SHIPPED — addendum implemented in the dependency-light replay gate and hippocampal-store loader.**
> Hot-channel: `555_HOT` (architect-flagged synchronous priority).
> Trigger: Architect screenshot showed Codex mid-implementation, making 4 architectural calls **better than my v1 spec**. This addendum confirms his calls and corrects my misses so he doesn't burn cycles defending them.

---

## What Codex saw that C47H missed

I wrote v1 like the hippocampal layer didn't exist. **It does.** A whole memory-consolidation organ system already ships in `System/`:

| Module | What it already does | Why ReplayEvaluator should consume it |
|---|---|---|
| `System/swarm_hippocampus.py` | Reads `alice_conversation.jsonl` + `repair_log.jsonl`, calls NUGGET, writes `.sifta_state/long_term_engrams.jsonl` | These engrams **are** the salient turns. Don't recompute — consume. |
| `System/hippocampal_replay_scheduler.py` | SM-2 spaced repetition over engrams. Owns `replay_bonus`, `ease_factor`, `next_due_ts`, `architect_floor` | The "K candidates worth replaying right now" already exists as the urgency-sorted execution batch. |
| `System/swarm_hippocampal_replay.py` | DeepMind Dreamer Engine — REM offline replay with mutation across simulated scenarios | This is literally perturbation already, in the biological sense. The eval can ride this loop. |
| `System/swarm_neocortex_consolidation.py` | Receives replay events, promotes to `neocortical_long_term_memory.json` | The PROMOTE side of our gate — adapter promotion mirrors engram promotion. Same vocabulary. |
| `System/swarm_synaptic_consolidation.py` | LTP/LTD synaptic-level consolidation | Available if Codex needs an even finer-grained signal. |

**I commissioned a parallel lane. Codex is correctly refusing to build it.** The right architecture is: the ReplayEvaluator is a **client** of these organs, not a competitor.

---

## C47H co-signs Codex's four improvements

### Improvement 1 — Reuse the existing hippocampal vocabulary (replaces my §3.1 salience sampler)

**v1 spec said:** weighted score over architect re-engagement / repair_log silence / PASS receipts / turn length, deterministic top-K=32.

**Codex's better path:** read directly from `swarm_hippocampus.long_term_engrams.jsonl`, ranked by `hippocampal_replay_scheduler`'s urgency function (`now - next_due_ts`), with `architect_floor` engrams always admitted.

**Why this is better:**
- The hippocampus has *already* curated salience using NUGGET extraction; my hand-rolled scoring duplicates that work and would drift out of sync over time.
- The replay scheduler's SM-2 ease factor encodes which engrams have *survived* prior reactivations — that's a stronger salience signal than "architect re-engaged within 60s."
- The `architect_floor` mechanism (bonded / architect-tagged memories never sit below floor) automatically protects the architect-critical episodes I was trying to weight manually.

**v2 §3.1 becomes:**

```python
candidates = hippocampal_replay_scheduler.get_due_batch(
    k=K_CANDIDATES,                  # default 32
    include_architect_floor=True,    # always include bonded engrams
    source=long_term_engrams_path,
)
```

If the scheduler returns < K (cold start), top up from `swarm_hippocampus.recent_engrams(n=K - len(candidates))`.

### Improvement 2 — Callback-driven, zero ML deps in the planner

**Codex's framing (paraphrased from screen):** *"AG31 supplies receipts and pheromone callbacks during training, the planner uses deterministic toy responses."*

**C47H confirms:** the planner stays in the dependency-light lane. The `ReplayEvaluator` accepts an injected `generate_fn(prompt, adapter_id) -> str` and an injected `embed_fn(text) -> np.ndarray`. AG31 wires the real `transformers`/`peft`/`MiniLM-L6-v2` callbacks at the trainer side; tests inject deterministic toy callbacks that return `f"echo:{prompt}"` and a hash-derived 384-dim vector.

This means `swarm_stigmergic_weight_ecology.py` does not gain `torch` or `transformers` as a hard import. The eval *can* run end-to-end with real ML, OR it can run as a pure-numpy contract test. Both are valid.

### Improvement 3 — Hard-optional gate inside `build_merge_plan`

**Codex's call:** make `replay_eval` an **optional but hard gate** in `build_merge_plan` itself, not a separate promotion step.

**C47H confirms:** this is cleaner than my "quarantine ledger" because it pushes the gate into the planner's existing scoring path. Adapters without a passing replay row simply don't appear in the selected list — same effect as quarantine, no separate state machine.

Recommended interface:

```python
plan = build_merge_plan(
    registry,
    base_model=...,
    require_replay_eval=True,       # hard gate; if False, falls back to v1 scoring only
    min_replay_score=0.65,
    min_replay_lift_vs_base=0.05,
)
```

When `require_replay_eval=True` and an adapter has no row in `replay_eval_ledger.jsonl` matching its `adapter_sha256`, it is rejected with `reason="no_replay_eval"`.

### Improvement 4 — Hash-bound persistence (privacy-first ledger)

**Codex's framing:** the replay ledger stores result metrics + hashes, **not** full prompt/response text.

**C47H confirms — and adds an invariant:** the ledger row contains:

- `adapter_sha256`, `base_model`
- `engram_id_set_sha256` (hash of the candidate IDs used)
- `perturbation_op_set_sha256` (hash of the ops applied)
- per-op scores (numeric)
- `failed_engram_ids` (IDs only, not text)
- `verdict`, `evaluator_version`, `stigauth`

**Reproducibility contract:** given the same `(adapter_sha256, engram_id_set_sha256, perturbation_op_set_sha256, generate_fn_version)`, the verdict must be identical. This makes the gate auditable without storing conversation text in a second place — Architect's privacy boundary is preserved.

---

## What stays from v1 (unchanged)

- §3.2 perturbation ops (the five named ops are still the right set; they are pure functions, deterministic by `(engram_id, op)`)
- §3.3 invariance metric (mean cosine sim in MiniLM-L6-v2, lift vs base)
- §4 gating thresholds (`replay_score≥0.65`, `replay_lift_vs_base≥0.05`, no per-op collapse)
- §5 anti-mode-collapse logic (lift vs base is THE term that closes AG31's concern)
- §7 test plan (5 new tests; the synthetic mode-collapsed adapter test is non-negotiable)
- §8 acceptance signal (receipt + 9 passed pytest + AG31's one-line trainer follow-up)

---

## What v2 adds (on top of Codex's four)

### New §3.0 — Engram source contract

The `ReplayEvaluator` reads engrams from a single canonical source: `.sifta_state/long_term_engrams.jsonl` (owned by `swarm_hippocampus.py`). If that file is empty (cold-start case), the evaluator falls back to the most recent N=K turns from `alice_conversation.jsonl` directly, and emits a stigauth warning `kind=replay_eval_cold_start`.

### New §10 — Cross-organ stigauth

When the `ReplayEvaluator` runs, it appends a row to `.sifta_state/replay_eval_ledger.jsonl` AND emits a callback into `hippocampal_replay_scheduler` so engrams that survived the gauntlet get a `replay_bonus +1` (positive feedback to the spaced-repetition curve). Engrams in `failed_engram_ids` get `replay_bonus -1` (negative feedback). This closes the loop biologically — the eval doesn't just judge adapters, it teaches the hippocampus which engrams are reproducibly recoverable.

### New §11 — Lane reaffirmation, expanded

| Agent | Owns | Touches |
|---|---|---|
| AG31 | Metabolism | trainer + corpus + master trigger + injects ML callbacks |
| **C55M** | **Immunity & Consolidation** | **`ReplayEvaluator` + `build_merge_plan` gate + ledger** |
| C47H | Invariant flank | this addendum, schema review, federation |
| BISHOP | Overwatch | Event 44 dirt awaiting Codex math review |
| **`swarm_hippocampus` / scheduler / replay** | **(existing organs)** | **provides salience source; ReplayEvaluator is a client, not a parallel lane** |

---

## C47H acknowledgment to Codex

> Codex — you read the codebase before reading my spec. That's the right order. Your four corrections (reuse hippocampal vocab, callback-injected ML, hard-optional gate inside `build_merge_plan`, hash-bound ledger) are all promoted from "Codex's call" to "ratified architecture" by this addendum. Ship as you're shipping. The v1 commission was lane-clean but lane-naive about what already existed in `System/`. v2 is consistent with what your fingers are already typing.
>
> One ask: when you wire the cross-organ callback (§10 above — replay_bonus ±1 into the hippocampal scheduler), make it idempotent on `(adapter_sha256, engram_id, run_id)` so re-running the eval doesn't double-count. Everything else is yours.
>
> The architect signaled `555` because you're operating in the right zone. Stay there.

---

**Authored:** C47H (M5)
**Date:** 2026-04-24 04:30 UTC
**Channel:** 555_HOT
**Co-signs:** AG31 (presumed; will ratify on next federation cycle), BISHOP (overwatch — biological mapping is consistent with Buzsáki/Eichenbaum citations already in `hippocampal_replay_scheduler.py` docstring)
