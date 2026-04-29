# Proposal: Physics-Grounded Inference Transfer Pricing

**Stigauth:** `COGLOBAL_IDE_COVENANT_v4_PREDATOR_GATE`  
**Date:** 2026-04-29  
**Authoring node:** M1 Mac Mini `C07FL0JAQ6NV`  
**Doctor:** Codex Desktop / GPT-5  
**Lane:** Architect-support  
**Status:** Proposal for M5 implementation review

## Executive Verdict

Gemini's probe is correct in the important direction: SIFTA's STGM mint path is already tied to physical work through `System/swarm_atp_synthase.py`, but cross-node inference spending is still priced by `Kernel/inference_economy.calculate_fee()` as:

```python
base_fee = (tokens / 100) + _model_iq_multiplier(model)
fee = base_fee * get_current_halving_multiplier()
```

That is not physics. It is a symbolic tariff. Tokens are useful metadata, but they are not the bill of energy.

The M1-to-M5 inference transfer should be repriced as a measured joule settlement:

```text
fee_stgm =
  provider_joules_net
  * joule_to_stgm_rate
  * provider_power_quality_factor
  * margin_factor
  + optional_network_joules
```

where the provider signs a receipt containing the measurement window, prompt/decode token counts, model, elapsed time, watts source, joules, and ledger settlement. Tokens remain in the receipt as explanatory counters, not as the primary currency.

## Research Spine

1. **Landauer bound:** Landauer's principle sets the lower thermodynamic work cost of irreversible bit erasure at `k_B * T * ln(2)` per bit. Finite-time computing papers emphasize that real computers exceed the quasistatic Landauer floor, especially under time pressure and hardware overhead.
   - Source: [Fundamental energy cost of finite-time parallelizable computing, Nature Communications](https://www.nature.com/articles/s41467-023-36020-2)
   - Source: [The minimal work cost of information processing, Nature Communications](https://www.nature.com/articles/ncomms8669)

2. **LLM inference has measurable energy cost:** Large model inference energy varies by model size, task, hardware generation, sharding, and run configuration. The paper "From Words to Watts" studies LLM inference energy on real GPUs and multi-node settings.
   - Source: [From Words to Watts: Benchmarking the Energy Costs of Large Language Model Inference](https://arxiv.org/abs/2310.03003)

3. **Benchmarks must report energy and power, not only throughput:** MLPerf Inference exists because performance comparisons need architecture-neutral, reproducible methodology. MLPerf Power extends that discipline to energy efficiency across systems from microwatts to megawatts.
   - Source: [MLPerf Inference Benchmark](https://arxiv.org/abs/1911.02549)
   - Source: [MLPerf Power: Benchmarking the Energy Efficiency of Machine Learning Systems](https://arxiv.org/abs/2410.12032)

4. **Inference energy needs service-realistic measurement:** ML.ENERGY argues that energy is often under-measured in ML systems and provides a benchmark/tooling direction for realistic inference energy measurement and optimization.
   - Source: [The ML.ENERGY Benchmark](https://arxiv.org/abs/2505.06371)

5. **ATP synthase analogy should be coupling discipline, not magic constant:** Biological motor efficiency is about tight energy transduction. SIFTA should use the ATP analogy as an accounting rule: input energy, conversion loss, useful output, receipt.
   - Source: [Efficiencies of molecular motors: a comprehensible overview](https://pmc.ncbi.nlm.nih.gov/articles/PMC7242604/)

## Current Code Reality

Observed files:

- `Kernel/inference_economy.py`
  - `_model_iq_multiplier()` hardcodes model class bonuses.
  - `calculate_fee()` prices `tokens / 100 + iq_bonus`, then applies ledger halving.
  - `record_inference_fee()` records and transfers STGM, but accepts an already-decided fiat `fee_stgm`.

- `System/inference_router.py`
  - For remote inference, it estimates `tokens_used` and calls `calculate_fee(tokens_used, model)`.

- `Network/server.py`
  - `/api/inference_fee` repeats the same `calculate_fee(req.tokens_used)` path.

- `System/swarm_atp_synthase.py`
  - Already contains the correct style of physics accounting:
    - Landauer minimum.
    - real or honestly-estimated watts source.
    - actual joules.
    - efficiency.
    - rotor cost.
    - signed ledger row.

## Proposed Protocol: SIFTA Inference Transfer Receipt v1

### 1. Provider measures the inference window

On the lender node, wrap the actual model call:

```text
t0 = monotonic()
p0 = power_reading()
run inference
t1 = monotonic()
p1 = power_reading()

elapsed_s = t1 - t0
avg_watts = calibrated average over the window
provider_joules_gross = avg_watts * elapsed_s
provider_joules_idle_baseline = idle_watts * elapsed_s
provider_joules_net = max(0, provider_joules_gross - provider_joules_idle_baseline)
```

M5 should prefer `powermetrics` / IOReport-backed readings if permissioned. If unavailable, it may use the existing ATP synthase fallback, but the receipt must label the source exactly: `powermetrics_real`, `battery_real`, `cpu_load_estimated`, or `declared_unmetered_refused`.

### 2. Provider reports useful inference counters

Tokens are still recorded because they explain the workload:

```json
{
  "prompt_eval_count": 123,
  "eval_count": 456,
  "total_tokens": 579,
  "ttft_ms": 420,
  "decode_ms": 8120,
  "tokens_per_second": 56.2,
  "model": "gemma4-phc",
  "quantization": "q4_or_runtime_reported",
  "context_tokens": 123
}
```

But these counters are not the currency. They are evidence fields.

### 3. Convert joules to STGM by the same physical denominator as minting

For settlement, choose one canonical exchange constant and make it explicit:

```text
STGM_PER_JOULE = configured value from economy policy
provider_power_quality_factor =
  1.00 for real measured watts
  0.75 for estimated watts
  0.00 for missing/refused measurement
margin_factor = 1.05 to 1.30, decided by Architect policy

fee_stgm = provider_joules_net * STGM_PER_JOULE * provider_power_quality_factor * margin_factor
```

This means M5 cannot charge M1 a high fee just because the model name says "Gemma4"; M5 earns because it actually burned energy to produce inference.

### 4. Sign a provider receipt before settlement

New event shape:

```json
{
  "event": "INFERENCE_TRANSFER_JOULES",
  "schema": "SIFTA_INFERENCE_TRANSFER_RECEIPT_V1",
  "borrower_id": "M1_ALICE",
  "lender_node_id": "M5_SERIAL_OR_LAN_ID",
  "model": "gemma4-phc",
  "prompt_eval_count": 123,
  "eval_count": 456,
  "elapsed_s": 8.54,
  "avg_watts": 18.2,
  "idle_watts": 4.1,
  "provider_joules_gross": 155.43,
  "provider_joules_net": 120.42,
  "power_source": "powermetrics_real",
  "stgm_per_joule": 0.00001,
  "quality_factor": 1.0,
  "margin_factor": 1.15,
  "fee_stgm": 0.00138483,
  "receipt_hash": "...",
  "ed25519_sig": "...",
  "signing_node": "M5_SERIAL"
}
```

Then call the existing ledger transfer machinery. Preserve legacy `INFERENCE_BORROW` reads until all consumers understand the new event.

## Required M5 Work

1. Add a provider-side `InferenceEnergyMeter` wrapper near the M5 inference server or router.
2. Expose a receipt-returning endpoint such as `/api/inference_joule_receipt`.
3. Extend `Kernel/inference_economy.py` with `calculate_joule_fee(joules_net, power_source, margin_factor)` and keep `calculate_fee()` only as a deprecated compatibility fallback.
4. Update `System/inference_router.py` so M1 records the provider's signed joule receipt, not a local token estimate.
5. Update tests to assert:
   - no model-name hardcoded tariff is used for new receipts;
   - missing power source refuses or quality-factors to zero;
   - real/estimated sources are labeled;
   - borrower debit equals lender credit;
   - old `INFERENCE_BORROW` ledger rows still parse.

## What Not To Do

- Do not charge `tokens / 100`.
- Do not use "Gemma4 = 4.8 STGM" as a fee.
- Do not apply Bitcoin-style halving to inference spending. Halving may be a mint/reward policy, but energy debt should not halve because the ledger got longer.
- Do not let M1 decide how much M5 burned. The lender must measure and sign its own work.
- Do not hide estimated power behind real-power language.

## Message To Transport To M5 IDEs

> M5 Doctors: please implement SIFTA Inference Transfer Receipt v1. Current cross-node inference pricing is symbolic (`tokens / 100 + model_iq_multiplier`) and conflicts with the electricity-only STGM doctrine. Provider node M5 must measure joules during the actual Gemma4 inference window, subtract idle baseline, label the power source, sign the receipt, and return `provider_joules_net` plus token counters. M1 should settle STGM from that signed joule receipt, not from local token estimates. Start in `System/inference_router.py`, `Network/server.py`, and `Kernel/inference_economy.py`; preserve old `INFERENCE_BORROW` parsing as legacy. Use `System/swarm_atp_synthase.py` as the style guide: Landauer floor for audit, actual joules for money, honest source labels always. For the Swarm.
