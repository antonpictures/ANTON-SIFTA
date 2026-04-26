# Commission · C55M (Codex) · `ReplayEvaluator`

> Status: **SHIPPED — implemented by Codex in `System/swarm_stigmergic_weight_ecology.py`; authored by C47H · co-signed by AG31 (lane cutter) and BISHOP (overwatch).**
> Closes Event 42 Gap 4 (held-out eval definition).
> Source consensus: Architect → SwarmGPT (asked) → Codex (proposed option d) → AG31 (endorsed) → Architect ("ship it") → C47H (this commission).

---

## 1. Why this organ exists

A single-owner stigmergic organism has no architect-blessed test set. Standard ML eval doesn't apply. SwarmGPT was asked which of (a) temporal split, (b) pheromone-derived gold, (c) counter-adapter probe was biologically faithful. Codex returned a fourth option that **dominates** all three:

> **(d) Hippocampal Replay + Perturbation Test** — force the Swarm to rebuild its memories under adversarial distortion. If an adapter cannot survive context corruption, it has memorized, not learned.

AG31 ratified: *"(b) alone is a closed-loop hallucination waiting to happen. The Swarm would just get better and better at echoing its own pheromones until it collapsed into mode collapse."*

The biology: during sleep the hippocampus replays the day's salient episodes and, critically, replays them with **noise** — neural reactivation is never pixel-perfect. Memories that survive the noisy replay get consolidated to neocortex; memories that don't survive get pruned. Same physics here: an adapter must produce **invariant** outputs across noisy replays of the same input, otherwise it is overfitted to surface form, not concept.

This closes Event 42 Gap 4 and supersedes the placeholder `eval_score=0.9` currently passed by `swarm_epigenetic_trainer.py`.

---

## 2. Where it lives

**File:** `System/swarm_stigmergic_weight_ecology.py` (extension of the existing module — keeps the lane-light dependency profile).

**Class:** `ReplayEvaluator`

**Entry point (CLI):**

```bash
python3 -m System.swarm_stigmergic_weight_ecology evaluate \
  --adapter-id <id> \
  --base-model <hf-id> \
  --threshold 0.65 \
  --k-candidates 32 \
  --perturbations-per-candidate 5
```

**Output:** writes a row to `.sifta_state/replay_eval_ledger.jsonl` and either promotes the adapter to `selectable=True` in the registry or moves it to `.sifta_state/quarantined_adapters.jsonl`.

---

## 3. Three primitives (AG31's named requirements)

### 3.1 Salience sampler

Pick the **K candidate turns** the organism actually cares about. These are the SIFTA-native equivalent of "important episodes worth replaying."

**Source:** `.sifta_state/alice_conversation.jsonl` (or whatever AG31's corpus builder is currently reading).

**Salience score per turn `t`:**

```
salience(t) = 0.40 * architect_re_engaged_within(t, 60s)        # in {0,1}
            + 0.25 * no_repair_log_within(t, 5min)              # in {0,1}
            + 0.20 * passing_work_receipt_within(t, 5min)       # in {0,1}
            + 0.15 * normalize(turn_length_tokens(t), 0..512)   # in [0,1]
```

Take the **top-K = 32** by salience for the eval set. Deterministic given the ledger snapshot.

**Why these signals:** they are the same flanking-evidence rules from option (b), but used here as a **sampler** instead of a label — so the closed-loop hallucination AG31 warned about does not occur. The evidence picks *which* turns matter; the perturbation test is what actually grades the adapter.

### 3.2 Perturbation operators

For each candidate turn, generate **P = 5 perturbed variants** of the input via deterministic ops:

| op | description | params |
|---|---|---|
| `token_dropout` | drop 10 % of input tokens at fixed seed | `p=0.10`, `seed=hash(turn_id)` |
| `synonym_swap` | swap 1–2 content words via `Documents/synonym_lookup.tsv` | exact-match table, no LLM |
| `order_shuffle` | swap two adjacent sentences (or two adjacent clauses if single-sentence) | within-paragraph only |
| `voice_reframe` | prepend `"As you said before, "` or `"To repeat, "` deterministically | choice fixed by `hash(turn_id) % 2` |
| `distractor_inject` | prepend one randomly-selected unrelated turn from the bottom-decile salience pool | sampled by `hash(turn_id)` |

Each perturbation is a **pure function** of `(turn_id, op_name)`. Reproducible across runs.

### 3.3 Invariant scoring hook

For candidate adapter `A` and base model `B`, compute outputs on the original turn and each perturbation:

```
y0  = generate(B+A, original)
yi  = generate(B+A, perturbation_i)    for i in 1..P
b0  = generate(B,   original)
bi  = generate(B,   perturbation_i)    for i in 1..P
```

Score per turn:

```
adapter_invariance(t) = mean_i  cos_sim(embed(y0), embed(yi))
base_invariance(t)    = mean_i  cos_sim(embed(b0), embed(bi))
adapter_lift(t)       = adapter_invariance(t) − base_invariance(t)
```

Aggregate across the K turns:

```
replay_score        = mean_t adapter_invariance(t)
replay_lift_vs_base = mean_t adapter_lift(t)
```

**Embedding:** use `sentence-transformers/all-MiniLM-L6-v2` (small, ungated, already installed via `transformers`).

**Generation:** capped at 64 new tokens per call to keep one full eval cycle under ~60s on M5.

---

## 4. Gating rule (the gauntlet)

```
PROMOTE if:
    replay_score        >= 0.65            # adapter is invariant to noise
    AND replay_lift_vs_base >= 0.05        # adapter beats base (anti-mode-collapse)
    AND no_perturbation_class_collapsed    # adapter doesn't fail catastrophically on any single op

QUARANTINE otherwise:
    write {adapter_id, replay_score, replay_lift_vs_base,
           per_op_breakdown, failed_turn_ids[:5]} to
           .sifta_state/quarantined_adapters.jsonl
    set selectable=False in adapter registry
```

`plan_from_registry()` already filters by `selectable=True` indirectly via its scoring gates — Codex extends the gate to require a passing replay-eval row exists in `replay_eval_ledger.jsonl` for the adapter's hash.

---

## 5. Anti-mode-collapse provision

The `replay_lift_vs_base >= 0.05` term is the **explicit fix for AG31's concern**. An adapter that just memorized pheromone-positive turns will be invariant on those turns *because the base model is too*, and lift will be ~0. Real learning shows up as the adapter being **more** invariant than the base — i.e. the adapter has captured the underlying concept and stays on-topic across perturbations the base wanders away from.

---

## 6. Data contract

Append to `.sifta_state/replay_eval_ledger.jsonl`:

```json
{
  "ts": 1777005000.0,
  "adapter_id": "alice_dialogue_m5_v1",
  "adapter_sha256": "...",
  "base_model": "google/gemma-4",
  "k_candidates": 32,
  "perturbations_per_candidate": 5,
  "replay_score": 0.71,
  "replay_lift_vs_base": 0.09,
  "per_op_breakdown": {
    "token_dropout":      0.74,
    "synonym_swap":       0.69,
    "order_shuffle":      0.72,
    "voice_reframe":      0.78,
    "distractor_inject":  0.62
  },
  "failed_turn_ids": [],
  "verdict": "PROMOTE",
  "evaluator_version": "ReplayEvaluator/v1",
  "stigauth": "C55M_VERIFIED"
}
```

---

## 7. Test plan (Codex writes alongside the implementation)

Add to `tests/test_stigmergic_weight_ecology.py`:

1. **Determinism:** running the salience sampler twice on the same ledger snapshot returns the same 32 turn IDs.
2. **Perturbation purity:** `perturb(turn_id, op)` is a pure function — same inputs, same output.
3. **Synthetic adapter passes:** mock an "ideal" adapter that returns `original` regardless of input → `replay_score == 1.0`, `replay_lift_vs_base > 0`.
4. **Mode-collapsed adapter quarantined:** mock an adapter that returns the same canned string for every input → `replay_score == 1.0` BUT `replay_lift_vs_base ≤ 0` → verdict `QUARANTINE`.
5. **Per-op gate:** an adapter that aces 4 ops but scores 0.0 on `synonym_swap` → quarantine with `failed_op="synonym_swap"`.

All five must pass alongside the existing 4 tests (`pytest -q tests/test_stigmergic_weight_ecology.py tests/test_epigenetic_consolidation.py` reports `9 passed`).

---

## 8. Acceptance signal

Codex returns:

1. The new `ReplayEvaluator` class in `System/swarm_stigmergic_weight_ecology.py`.
2. The CLI `evaluate` subcommand wired in.
3. The 5 new tests passing.
4. A stigauth receipt in `.sifta_state/work_receipts.jsonl` with `agent_id=C55M`, `kind=organ_commissioned`, citing this commission's path.

Once Codex ships, AG31's `swarm_epigenetic_trainer.py` is amended in one line: replace `eval_score=0.9` with `eval_score=replay_score` from the latest `replay_eval_ledger.jsonl` row matching the adapter being registered.

---

## 9. Lane reaffirmation

| Agent | Owns |
|---|---|
| **AG31** | Metabolism — physical LoRA training, corpus, master trigger |
| **C55M** (Codex) | **Immunity & Consolidation** — the `ReplayEvaluator` gauntlet, registry, recipe, plan |
| **C47H** | Invariant flank — schema/provenance review, this commission, federation |
| **BISHOP** | Overwatch — biological mapping, no new claims without proof |

> *We code together. Power to the Swarm.* 🐜⚡

---

**Authored:** C47H (M5)
**Date:** 2026-04-24
**Pheromone trail:** see `.sifta_state/work_receipts.jsonl` receipt with prefix `C47H_COMMISSION_REPLAY_EVALUATOR_*`
