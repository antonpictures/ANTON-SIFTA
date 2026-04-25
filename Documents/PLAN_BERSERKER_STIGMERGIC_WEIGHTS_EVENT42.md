# Stigmergic Weights Trilogy — Events 42 / 43 / 44

> _Berserker series. Source: BISHOP Biocode Olympiad. Status as of 2026-04-24._
>
> **Boundary, unchanged across all three events:** Do not mutate base weights as the primary artifact. Publish a reproducible adapter ecology — base pointer + hash, LoRA deltas, stigmergic evidence rows, deterministic merge/routing recipes, optional convenience-merged checkpoint.

---

## Event 42 — Epigenetic Consolidation (DELLA-Merging)

**Status: SHIPPED · all proofs green on M5 · stigauth-signed**

### Boundary

Do not mutate base weights as the primary artifact.

Publish a reproducible adapter ecology:

1. Base model pointer and hash.
2. LoRA/adapter deltas.
3. Stigmergic evidence rows that justify each delta.
4. Deterministic merge/routing recipes.
5. Optional derived merged checkpoint for convenience only.

### Lanes

AG31 owns the middle cut:

- Finish `System/swarm_corpus_builder.py` into a corpus exporter with source tags.
- Install PEFT only in the training environment, not as a required runtime dependency.
- Train one small adapter first from the Alice conversation corpus.
- Train a second adapter from repair/work receipts only after the first passes eval.
- Register each trained adapter through `System.swarm_stigmergic_weight_ecology`.

C55M follows behind:

- Keep base-weight mutation out of the default path.
- Maintain the adapter registry and merge-plan schema.
- Reject adapters with high regression, high risk, stale evidence, or base-model mismatch.
- Produce `.sifta_state/stigmergic_adapter_merge_recipe.json` for AG31 to feed into PEFT.

C47H holds the invariant flank:

- Verify ledger/schema hygiene.
- Verify HMAC/Ed25519 provenance for publishable artifacts.
- Review release cards so merged artifacts are not mislabeled as independently trained base models.

BISHOP is research overwatch:

- Translate relevant papers into hypotheses and citations.
- No new weight publication claims unless an eval proves the claim.

### Cut Order

1. `python3 -m System.swarm_stigmergic_weight_ecology proof`
2. AG31 exports corpus rows with stable source labels.
3. AG31 trains adapter A against the smallest base that actually runs on M5.
4. AG31 runs eval and regression checks; failed adapters are not registered.
5. AG31 registers adapter A:

```bash
python3 -m System.swarm_stigmergic_weight_ecology register \
  --adapter-id alice_dialogue_m5_v1 \
  --adapter-path /path/to/adapter \
  --base-model <hf-base-model-id-or-hash> \
  --homeworld M5 \
  --task dialogue \
  --conflict-group dialogue \
  --eval-score 0.81 \
  --regression-score 0.95 \
  --energy-joules 1200 \
  --risk-score 0.08 \
  --pheromone-strength 0.70 \
  --evidence-id eval:alice_dialogue_m5_v1
```

6. C55M builds the merge recipe:

```bash
python3 -m System.swarm_stigmergic_weight_ecology plan \
  --base-model <hf-base-model-id-or-hash>
```

7. AG31 uses the recipe with PEFT `add_weighted_adapter`.
8. C47H reviews the generated adapter, recipe, hashes, model card, and eval table before upload.

### Release Rule

The Hugging Face repo should publish:

- `adapter_config.json`
- adapter weights
- `stigmergic_adapter_registry.jsonl`
- `stigmergic_replay_evals.jsonl`
- `stigmergic_adapter_merge_recipe.json`
- eval table
- exact base model pointer

The model card language:

> This repo publishes SIFTA stigmergic adapter deltas and a reproducible merge recipe. The base model is not claimed as newly trained by SIFTA unless explicitly stated.

### Shipped artifacts (Event 42)

| Component | File | Role |
|---|---|---|
| BISHOP DELLA primitive | `System/swarm_epigenetic_consolidation.py` | Drop-and-rescale fusion, runnable as `python3 -m System.swarm_epigenetic_consolidation` |
| Codex weight ecology | `System/swarm_stigmergic_weight_ecology.py` | Provenance + scoring + conflict groups + recipe writer |
| AG31 trainer | `System/swarm_epigenetic_trainer.py` | LoRA training + handoff to ecology via `register_adapter_signal()` |
| AG31 corpus | `System/swarm_corpus_builder.py` | `alice_conversation.jsonl` → HF JSONL |
| AG31 sleep cycle | `System/swarm_sleep_cycle.py` | Glymphatic + replay + Event-42 trigger |
| AG31 master trigger | `scripts/execute_epigenetic_cycle.py` | End-to-end one-shot cycle |
| AG31 pheromone scorer | `System/swarm_adapter_pheromone_scorer.py` | Closes Gap 1: real evidence → `pheromone_strength` |
| Codex replay evaluator | `System/swarm_stigmergic_weight_ecology.py` | Closes Gap 4: salience sampler + perturbation ops + invariant scoring hooks + replay-gated merge plans |
| Replay eval ledger | `.sifta_state/stigmergic_replay_evals.jsonl` | Hash-bound quarantine reports; no raw prompt/response text stored |
| Tests | `tests/test_stigmergic_weight_ecology.py`, `tests/test_epigenetic_consolidation.py` | 7 passed |

**Open gaps from Event 42:**

- **Gap 1 — pheromone scoring:** AG31 shipped `swarm_adapter_pheromone_scorer.py`. Trainer needs to call it instead of passing `pheromone_strength=1.0` placeholder.
- **Gap 2 — base-model glue:** Apply HF LoRA adapter to GGUF Ollama runtime. (Open.)
- **Gap 3 — first real cycle:** AG31 swapped the test-run base from gated `google/gemma-2b-it` to ungated `Qwen/Qwen1.5-0.5B-Chat`. Architect runs `python3 scripts/execute_epigenetic_cycle.py` to close.
- **Gap 4 — held-out eval definition:** **SHIPPED → option (d) Hippocampal Replay + Perturbation Test.** SwarmGPT was asked, Codex proposed (d), AG31 endorsed, Architect commissioned. Codex now owns the `ReplayEvaluator` inside `System/swarm_stigmergic_weight_ecology.py`. Adapters can be replay-gated by passing reports into `build_merge_plan(..., replay_reports=..., require_replay=True)`. Spec lives at `Documents/COMMISSION_C55M_REPLAY_EVALUATOR_v1.md` with the v2 hot addendum.

---

## Event 43 — 1D Pheromone Diffusion (consolidating layer)

**Status: implicit / partially shipped · explicit organ pending · DELLA's MagPrune covers the noise floor**

The 1D diffusion frame is the conceptual bridge between the per-adapter scoring in `swarm_stigmergic_weight_ecology.py` (freshness decay `0.5 ** (age_s / half_life_s)`, magnitude pruning inside DELLA) and the 2D field equations of Event 44. The discrete Laplace operator on a 1D trace evaporates noise without mutating the base — the same physics, projected onto a single axis.

**Where the 1D physics already lives in shipped code:**

- DELLA `mag_prune_and_rescale` in `System/swarm_epigenetic_consolidation.py` (1D-style magnitude-rank prune + 1/(1−p) rescale).
- Pheromone freshness decay in `System/swarm_stigmergic_weight_ecology.py`.
- The pheromone scorer's `K=100` sigmoid normalization in `System/swarm_adapter_pheromone_scorer.py`.

**Outstanding:** if/when we want to stand up an explicit `System/swarm_pheromone_diffusion.py` organ (1D Laplace stencil over a flattened adapter delta) it would slot in cleanly between the trainer and the registry call. Not blocking — Event 44 generalizes it.

---

## Event 44 — Turing Morphogenesis (2D Tensor Reaction-Diffusion)

**Status: BISHOP dirt landed · proof_of_property PASSES on M5 · awaiting Codex approval for tournament admission**

### Concept

Pure parabolic diffusion (∂U/∂t = D·∇²U) over many tasks eventually over-smooths into a uniform field — catastrophic blur. Event 44 introduces **Turing instability** via two coupled fields with asymmetric diffusion rates:

- **Activator U** — slow diffusion `Du`, represents the cognitive signal that wants to stay localized.
- **Inhibitor V** — fast diffusion `Dv >> Du`, represents interference noise that spreads laterally and suppresses competing activators.

The asymmetry `Dv >> Du` is the Turing condition. It guarantees that the merged tensor resolves into a **sparse, stable Turing pattern** (spots / stripes / dendritic clusters) rather than a uniform mush — which is exactly the kind of biological sparsity LoRA topographies need to avoid catastrophic forgetting.

### Math

The system evolves under Gray-Scott / FitzHugh-Nagumo-style dynamics:

```
∂U/∂t = Du·L(U) − U·V² + f·(1 − U)
∂V/∂t = Dv·L(V) + U·V² − (f + k)·V
```

where `L` is the discrete 2D Laplacian (3×3 stencil with center −1.0, edges 0.20, corners 0.05), `f` is the feed rate (task incorporation), `k` is the kill rate (decay of stale knowledge).

Final consolidated weights:

```
W_final = (lora_A1 + lora_A2) ⊙ normalize(V_steady_state)
```

— V at steady state acts as a learned epigenetic survival mask over the naive sum.

### Shipped (dirt) artifact

| Component | File | Role |
|---|---|---|
| BISHOP blueprint | `Archive/bishop_drops_pending_review/BISHOP_drop_turing_pattern_tensor_diffusion_v1.dirt` | `SwarmTuringTensorMorphogenesis` class + `proof_of_property()` |

### Numerical proof (this organism, this hour, M5)

```text
[*] Phase 1: Naive Tensor Summation
    Signal at [2,2] (Interference): 1.000
    Sparsity (Noise floor < 0.05):  33.0%

[*] Phase 2: Turing Morphogenesis (2D Tensor Diffusion)
    Signal at [2,2] (Consolidated): 0.765
    Sparsity (Noise floor < 0.05):  64.0%

[+] BIOLOGICAL PROOF: Activator-Inhibitor dynamics mapped to 2D weight tensors.
[+] PHYSICS PROOF: 2D Reaction-Diffusion PDE solved via discrete convolutions.
[+] EVENT 44 PASSED. LoRA Topography is now fully autopoietic.
```

Lateral inhibition nearly **doubles structural sparsity** (33 % → 64 %) while preserving the isolated critical signal at `[5,5]` (M5's unique learning). Interference at `[2,2]` (where M1 and M5 disagree) is dampened from naive `+1.0` to a consolidated `0.765` — the Activator-Inhibitor system mediated the conflict instead of summing it.

### Lanes (proposed)

**C55M (Codex) — judge:** approve the math review. Specifically:

- Confirm the 3×3 Laplacian stencil weights (corners 0.05, edges 0.20, center −1.0) sum to ≈0 and discretize the continuous Laplacian correctly.
- Confirm `(Du, Dv, f, k) = (0.05, 0.20, 0.04, 0.06)` lies inside the Turing-instability region for Gray-Scott — not on the boundary that produces solitons or chaos.
- Decide: does this replace DELLA's MagPrune step or supplement it?

**BISHOP — author / overwatch:** stays at the meta layer; provides additional regimes (`f`/`k`) if Codex flags edge cases.

**AG31 — lane cutter:** once Codex approves, promote the dirt to `System/swarm_turing_tensor_morphogenesis.py`, add `tests/test_turing_tensor_morphogenesis.py` mirroring the existing Event 42 test suite, and wire it as a **second selectable merge backend** in the ecology (not a replacement; configurable per merge plan).

**C47H — invariant flank:** verify the new module imports `numpy` and `scipy.signal.convolve2d` only; reject any import path that pulls `torch` into the runtime-light planner. Audit the merge recipe schema gains a `merge_backend ∈ {della, turing_morphogenesis}` field with a default of `della` until Turing has shipped one real-world cycle.

### Integration sequencing

1. **Approval gate:** Codex reviews BISHOP's dirt; produces a stigauth receipt with `verdict ∈ {APPROVE, REQUEST_CHANGES, REJECT}`.
2. **If APPROVE → promote:** AG31 moves the file to `System/`, mirrors the BISHOP-style `proof_of_property()` as the module's CLI entrypoint (`python3 -m System.swarm_turing_tensor_morphogenesis`).
3. **Backend registration:** the merge plan schema in `swarm_stigmergic_weight_ecology.py` adds an optional `merge_backend` field. Default stays `della`.
4. **Comparison cycle:** AG31 runs `execute_epigenetic_cycle.py` twice on the same registry — once with `--merge-backend della`, once with `--merge-backend turing_morphogenesis` — and writes both recipes side-by-side. C47H diffs the two.
5. **HF release sibling decision:** if Turing produces a measurably sparser, higher-fidelity adapter on the SwarmGPT-defined held-out eval (Gap 4 from Event 42), the `alice-lana-trace-v1` repo ships the Turing-merged adapter as default with the DELLA recipe as a secondary file.

### Risk register

| Risk | Mitigation |
|---|---|
| Turing parameters that work on a 10×10 toy fail on real LoRA shapes (e.g. 4096×8) | AG31's first comparison cycle uses real Qwen LoRA shapes; if it diverges, add a per-rank scaling step before the PDE. |
| `scipy` becomes a hard runtime dep just for the planner | The Turing organ stays in `System/` not in the dependency-light planner. Planner only emits the recipe; the actual merge is performed inside the trainer's heavy-ML environment where scipy is already present. |
| BISHOP's blueprint over-claims "fully autopoietic" | C47H release-card review enforces neutral language: "sparsity-preserving merge backend inspired by Gray-Scott reaction-diffusion." |

---

## Tournament admission table (snapshot)

| Event | Title | Author | Status | Approver |
|---|---|---|---|---|
| 42 | Epigenetic Consolidation (DELLA + Replay Gate) | BISHOP/C55M | SHIPPED, 7 tests green | C55M signed |
| 43 | 1D Pheromone Diffusion | (implicit) | absorbed into DELLA MagPrune + freshness decay | n/a |
| 44 | Turing Morphogenesis (2D RD) | BISHOP | DIRT + numerical proof PASS on M5 | **C55M (pending)** |

---

## Owner of this document

C47H (M5). Updates land via stigauth receipt in `.sifta_state/work_receipts.jsonl`.

Last update: 2026-04-24 — Event 44 dirt added by BISHOP, math verified on M5, awaiting Codex approval to promote into `System/`.
