# CORTEX MIGRATION PLAN — MTP + MCP for Alice

**Generated:** 2026-05-20 by Cowork, for George.
**Status:** DEFERRED. MTP migration parked on this M5 per George 2026-05-20 ~11:00 PDT. Reason: the embedded-MTP Qwen3.6-27B-MTP-GGUF disables `--mmproj` (vision encoder) and `-np > 1`. SIFTA cannot trade vision for tok/s — FieldSight, Sovereign Recognition, eye-identity, saccade target, and Stigmergic FarSight all require vision. M5 also has 24 GB unified memory, which is tight for a 19 GB MTP load plus the OS plus the SIFTA process. **MTP target moves to a future Linux node served by two NVIDIA DGX boxes** that George plans to acquire. Until then: Gemma4 stays as Alice's cortex, substrate gate stays pointed at the Gemma4 citation in `ai_name_alias.json`, no swap.
**Doctrine anchors:** §7.15 (substrate admit), §6 (Social Frame Rule), §4.4 (triple-IDE collision discipline).

---

## 1. What this changes

Alice's brain right now is a Gemma4-family build served as Ollama tag `alice-m5-cortex-8b-6.3gb:latest`. The substrate citation gate just wired into her mouth pulls that name from `.sifta_state/ai_name_alias.json` (`weight_name: "Gemma4"`).

The covenant says the weight_name field is **read live** — swap Ollama, value updates on next save. So a cortex swap doesn't break the gate. It does:

1. Change who Alice's brain literally is (Gemma → Qwen, etc.).
2. Invalidate every prior `OBSERVED_SUBSTRATE` receipt's *binding* to the old tag (the receipt is still true, but it's about the old brain).
3. Open access to MTP heads (1.71× faster tokens, when supported by the model).
4. Open llama.cpp's native MCP client → Alice can call MCP tools through her own cortex.

This is a §6 event. It needs a `SUBSTRATE_MIGRATION` ledger row.

---

## 2. Candidate cortexes — practical reality for M5 silicon

| Cortex | Params | MTP heads | GGUF Q4_K_M size | RAM needed | M5 fits? |
|---|---|---|---|---|---|
| Gemma4 (current) | 8B | NO | ~6.3 GB | ~8 GB | yes — current |
| Qwen3.6-27B (dense) | 27B | YES | 16.8 GB | ~18 GB | yes if M5 has 32GB+ |
| Qwen3.6-35B-A3B (MoE) | 35B total / 3B active | YES | ~20 GB | ~22 GB | yes if M5 has 32GB+ |
| DeepSeek-V3 | 671B + 14B MTP | YES | 151 GB (1.78-bit) – 350 GB (4-bit) | 150+ GB | **NO** — too big |
| DeepSeek-R1 | similar | YES | similar | similar | **NO** — too big |

**Realistic for your M5:** Qwen3.6-27B Q4_K_M. 16.8 GB on disk, ~18 GB resident. MTP-capable. ~3× the parameters of the current Gemma4 build, plus the speculative-decoding speedup. The 35B-A3B MoE is comparable in resident size but with more total knowledge.

DeepSeek is out — even the smallest dynamic quant is 151 GB. Not happening on Mac silicon outside of cloud.

---

## 3. SUBSTRATE_MIGRATION ledger schema

So prior receipts stay honest, every swap writes one row to `.sifta_state/substrate_migration.jsonl`:

```json
{
  "ts": 1779270000,
  "truth_label": "SUBSTRATE_MIGRATION_V1",
  "migration_id": "<uuid4>",
  "node_serial": "GTH4921YP3",
  "from": {
    "weight_name": "Gemma4",
    "ollama_tag": "alice-m5-cortex-8b-6.3gb:latest",
    "params_b": 8,
    "mtp_heads": false,
    "last_substrate_receipt_ts": <ts>
  },
  "to": {
    "weight_name": "Qwen3.6-27B",
    "ollama_tag": "alice-m5-cortex-qwen3.6-27b-q4km:latest",
    "params_b": 27,
    "mtp_heads": true
  },
  "rationale": "<one-line architect quote>",
  "doctrine_anchors": ["covenant_section_6", "covenant_section_7_15"],
  "ide_doctor": "Cowork",
  "human_approval": "George (architect_seal: Ioan George Anton)"
}
```

The gate's `_find_live_substrate_citation()` already reads `ai_name_alias.json` live, so once that file flips, the gate flips too. No code change needed in the gate.

---

## 4. Two wiring paths

### 4A. llama.cpp path (more control)

1. Build llama.cpp from master (MTP + MCP both merged upstream).
2. Run `llama-server` pointing at the chosen GGUF, with `--mtp` flag.
3. Configure `mcp.json` so the server's WebUI knows which MCP servers to expose.
4. SIFTA's brain caller (whatever currently hits Ollama) points at `localhost:<llama-server-port>/v1/chat/completions` instead of Ollama.
5. Test agentic loop: Alice asks the MCP-bus for a tool, the server runs it, response comes back through her own cortex.

**Pro:** native MTP, MCP, full control, no GUI dependency.
**Con:** more setup, more state to maintain.

### 4B. LM Studio path (simpler)

1. Install LM Studio 0.4.11+ (already shipped MCP + OAuth + Qwen 3.6).
2. Load Qwen3.6-27B GGUF in LM Studio's model browser.
3. Toggle MCP in settings; add MCP servers via `mcp.json` or the "Add to LM Studio" button.
4. Enable LM Studio's local server endpoint; point SIFTA's brain caller at it.

**Pro:** GUI switch, OAuth support for authenticated MCPs, less moving parts.
**Con:** GUI dependency, less observable internals, harder to customize substrate telemetry per §8.6.

---

## 5. Phased rollout (proposed — not committed)

Each phase is its own receipt. None happens until you say go.

**Phase 0 — write this plan.** Done. You're reading it.

**Phase 1 — record current substrate snapshot.** Hash the current Gemma4 GGUF, freeze `ai_name_alias.json`, write a `PRE_MIGRATION_BASELINE` row. Nothing changes yet. Architect signs the row.

**Phase 2 — download and verify Qwen3.6-27B Q4_K_M.** Local download only. No swap. Run llama.cpp benchmark to confirm MTP is active and confirm tok/s gain on M5 silicon. Receipt.

**Phase 3 — bring up second brain on a separate port.** Run Qwen3.6 in parallel to Gemma4 on a different llama-server port. Alice's voice stays on Gemma4. New brain is reachable only to a test harness. Smoke-test that the substrate gate, when pointed at the new brain, finds the new tag via `ai_name_alias.json`.

**Phase 4 — flip with rollback receipt.** Update `ai_name_alias.json` weight_name to the Qwen tag. Write `SUBSTRATE_MIGRATION` row. Talk widget points at the new brain. Old Gemma4 binary stays on disk, rollback is one file flip + one ledger row. Architect signs.

**Phase 5 — verify.** Tail `substrate_citation_gate.jsonl`, `alice_voice_scrub_audit.jsonl`, and `self_citation_utterances.jsonl` for the first day. Confirm gate stamps now cite Qwen3.6, scrubber catch-rate stable, no §6 violations.

---

## 6. What this plan does NOT cover

- Whether to keep `alice-m5-cortex-8b-6.3gb` as a fallback brain (probably yes — emergency rollback).
- Whether to expose Alice's brain to outside MCP servers vs only local SIFTA-bus MCPs (security question — needs Architect decision per §8.6).
- Whether the migration should be timed against your AGI confirmation gauntlet (`agi_confirmation_gauntlet.jsonl` shows prior runs — re-running on new brain would be a fair re-test).
- Cost of the new brain on STGM economy (more params = more electricity = more STGM burn per token).

---

## 6.5. Hardware state — 2026-05-20 (recorded by George)

George installed LM Studio on the M5 today for testing. Current runtime state on the node:

**LM Runtime — Metal llama.cpp v2.14.0**
- llama.cpp release `b8861` (commit `cf8b0db`)
- Newly loaded GGUF models use this runtime.

**LM Runtime — LM Studio MLX (Apple M5) v1.6.0**
- Adds **Gemma 4 support** (so the current Gemma4 cortex can stay on the MLX runtime if a swap path keeps Gemma).
- Improved prompt caching performance for Qwen 3.5.
- Pinned engine versions: `mlx-engine==315aa51`, `mlx==0.31.1`, `mlx-lm==0.31.3`, `mlx-vlm==0.4.4`.

**LM Link** (new in this LM Studio release)
- Connects to remote instances of LM Studio.
- Load models on a second machine, use them locally (end-to-end encrypted).
- Doctrinal implication for SIFTA: a swarm node could borrow inference from another M-series node without giving away private state. Matches §3.1 "Stigmergic Inference Economy" if framed as STGM-traded inference. **Not** a substrate swap — Alice's brain still lives on the M5 that the user is talking to; the *compute* is just borrowed. The substrate gate would need an extra field on the citation (`remote_host`, `link_id`) so the receipt names where the tokens were actually generated.

**What this means for the four cortex paths in §2:**
- Gemma4 can stay on this M5 via the MLX runtime (no swap needed for status quo).
- Qwen 3.5 family already gets prompt-caching benefit on MLX — separate from MTP.
- Qwen 3.6 / MTP path: still requires the swap. On hold.
- DeepSeek: still out of reach on M5 silicon.

**Open research questions George wants to think on before the swap:**
- MTP gain vs MLX prompt-caching gain — which matters more for SIFTA's actual workload (short turns, frequent re-priming with self-citation block)?
- LM Link as a "two-brain" pattern — main M5 keeps embodied state; a beefier remote machine handles heavy inference; the substrate gate stamps both?
- Does keeping the MTP move bundled with a GUI dependency (LM Studio) violate §8.6 substrate telemetry — or does LM Studio expose enough model identity for the gate to cite cleanly?

---

## 6.6. Unsloth MTP guide — full reference for SIFTA (added 2026-05-20 ~10:30 PDT)

George pasted the Unsloth Qwen3.6 MTP guide while downloading models to test. Capturing what matters for the SIFTA cortex swap, not what matters in general:

### MTP status — stable, no longer experimental

- Unsloth Qwen3.6 MTP GGUFs are out of experimental mode.
- llama.cpp **merged** MTP support upstream (PR #22673, May 16 2026).
- **The argument name changed on May 13 2026** from `--spec-type mtp` → `--spec-type draft-mtp`. **Any llama.cpp build older than mid-May 2026 will NOT understand the new arg.** George's LM Studio install reports Metal llama.cpp **v2.14.0 (b8861, commit cf8b0db)** — need to verify this build is post-May-13 before counting on MTP. If b8861 predates the rename, the substrate gate will see a Qwen3.6 cortex serving tokens at *non-MTP* speed and we'll be paying for a feature we're not getting. **Test step:** run `llama-server --spec-type draft-mtp ...` and look for the flag-accept; if it errors out, the build needs updating.

### Speedup numbers Unsloth reports

- Dense models: **~1.4× – 2.2×** generation speedup with MTP.
- MoE models: **~1.15× – 1.25×** (smaller win — fewer expert activations to skip per accepted draft).
- Reference benchmarks on big GPU (RTX 6000):
  - Qwen3.6-27B (dense) → **140–160 tok/s** with MTP, `UD-Q2_K_XL`.
  - Qwen3.6-35B-A3B (MoE) → **220–240 tok/s** with MTP.
- M5 unified memory will be slower than RTX 6000, but the *ratio* of speedup should hold.

### Draft tokens parameter (`--spec-draft-n-max`)

- Default `2` works best in most setups, recommended.
- Try `1` through `6` — performance is hardware-dependent.
- **Hard ceiling: do not exceed 2-3.** Acceptance rate drops from 83% (at 2) to 50% (at 4), so MTP benefit collapses past 3.

### Memory footprint — hardware table

MTP uses ~1 GB additional headroom on top of the base GGUF size. Total memory needed (RAM + VRAM, or M-series unified memory):

| Quant | Qwen3.6-27B | Qwen3.6-35B-A3B |
|---|---|---|
| 3-bit | 16 GB | 18 GB |
| 4-bit | 19 GB | 24 GB |
| 6-bit | 25 GB | 31 GB |
| 8-bit | 31 GB | 39 GB |
| BF16 | 56 GB | 71 GB |

**For the M5:** 4-bit 27B at **19 GB unified** is the realistic sweet spot. 35B-A3B 4-bit at 24 GB is also feasible if M5 has ≥32 GB unified.

### Two install paths

**Unsloth Studio (GUI, auto-tunes MTP)**

```
# install
curl -fsSL https://unsloth.ai/install.sh | sh
# launch
unsloth studio -H 0.0.0.0 -p 8888
# browser → http://127.0.0.1:8888 → search "Qwen3.6 MTP" → download
```

Auto-sets ideal MTP params for the hardware. SIFTA implication: **harder for the substrate gate to read the exact MTP params** unless Unsloth Studio exposes them via an API the gate can hit. Worth checking before depending on this path.

**llama.cpp direct (more control)**

```
# example: 27B MTP, non-thinking, server mode for SIFTA's brain caller
export LLAMA_CACHE="unsloth/Qwen3.6-27B-MTP-GGUF"
./llama.cpp/llama-server \
    -hf unsloth/Qwen3.6-27B-MTP-GGUF:UD-Q4_K_XL \
    --temp 0.7 --top-p 0.8 --top-k 20 --presence-penalty 1.5 --min-p 0.00 \
    --spec-type draft-mtp --spec-draft-n-max 2 \
    --chat-template-kwargs '{"enable_thinking":false}' \
    --alias "alice-m5-cortex-qwen3.6-27b-mtp" \
    --port 8001
```

The `--alias` flag is the signal the substrate gate cares about — it's what llama.cpp's `/v1/models` endpoint returns when queried, and what `ai_name_alias.json` should be updated to so the gate cites correctly.

### MLX vs llama.cpp on M5 — important distinction

LM Studio reports two runtimes: **MLX v1.6.0** and **Metal llama.cpp v2.14.0**. They are not equivalent for MTP:

- **MLX runtime:** Gives Qwen 3.5 prompt-caching boost. **Does NOT support MTP today** (no `--spec-type draft-mtp` equivalent in mlx-lm 0.31.3).
- **Metal llama.cpp runtime:** **Does support MTP**, assuming the b8861 build is post-May-13.

If George loads `Qwen3.6-27B-MTP-GGUF` in LM Studio's **MLX** runtime, the MTP tensors will be ignored and he'll see vanilla Qwen3.6 speed. The model must be loaded under the **Metal llama.cpp** runtime to actually get MTP.

### Preserved Thinking — SIFTA-specific note

Qwen3.6 has three modes: thinking enabled, thinking disabled, **preserve_thinking** (leave the thinking trace from prior conversation in context). Preserve_thinking uses more tokens but may help continued conversations.

SIFTA implication: Alice's self-citation organ already measures "N minutes since last Alice speech" and writes per-sentence causal traces. If thinking content leaks into the visible reply, the voice scrubber and substrate gate will see it. **Recommendation:** start with `enable_thinking:false` for the brain caller and revisit later — Alice's "thinking" should be the self-citation organ's pheromone gradient, not the Qwen draft thinking trace. The covenant §7.10.1 quarantine rule applies here: model-side thinking-as-narration ≠ Alice.

### MLX dynamic quants (Mac-specific, no MTP but lighter)

If MTP turns out to be the wrong fight, MLX dynamic quants from Unsloth are interesting standalone:

| Quant | 27B size | Mean KLD | PPL |
|---|---|---|---|
| 8-bit | 34.7 GB | 0.0028 | 4.812 |
| 6-bit (UD) | 30.5 GB | 0.0037 | 4.809 |
| **4-bit (UD)** | **26.2 GB** | 0.0227 | 4.821 |
| NVFP4 (UD) | 26.2 GB | 0.0325 | 4.843 |
| MXFP4 (UD) | 25.6 GB | 0.0479 | 4.902 |
| 3-bit (UD) | 24.1 GB | 0.0734 | 4.976 |

4-bit UD MLX at 26.2 GB on M5 keeps Apple's MLX kernel efficiency and stays light. No MTP, but no llama.cpp build maintenance either.

---

## 6.7. SIFTA-specific test protocol (when George is ready)

Three questions to answer before the swap, in order. Each one writes a receipt to `.sifta_state/cortex_eval.jsonl` so the test result is auditable.

**Test 1 — verify b8861 understands `--spec-type draft-mtp`.**
LM Studio → settings → Metal llama.cpp runtime → load Qwen3.6-27B-MTP-GGUF UD-Q4_K_XL → check whether MTP is "active" in the runtime log. If not, update llama.cpp before going further.

**Test 2 — measure real tok/s on M5 silicon.**
Side-by-side: Gemma4 current vs Qwen3.6-27B-MTP at `--spec-draft-n-max 2`. Run the same SIFTA prompt (e.g., "give me your self-citation briefing"). Record:
- tok/s during streaming
- TTFT (time to first token)
- M5 power draw (`powermetrics`)
- Memory pressure (`vm_stat`)
- Cost in STGM if the metabolic homeostat is wired

If Qwen3.6-MTP isn't at least 1.3× faster than Gemma4 on this hardware, MTP isn't worth the swap risk.

**Test 3 — does the substrate gate stamp correctly with the new cortex?**
Point the gate at the candidate cortex (via test-only `ai_name_alias.json` overlay), have it process the exact 2 AM florid line ("I am the synthesis of billions of parameters..."), confirm it stamps `OBSERVED_SUBSTRATE` with the new Qwen tag. If it stamps `FICTION_UNRECEIPTED_SUBSTRATE`, the alias file or `/v1/models` endpoint isn't returning what the gate expects — needs wiring, not a swap.

**Test 4 — does the swap match SIFTA's actual cadence?**
Run a 30-minute Talk session with the candidate cortex. Tail `self_citation_utterances.jsonl`. Check whether:
- N minutes between Alice utterances stays stable (faster tokens ≠ chattier Alice; she should still pace per the self-citation organ)
- Voice scrubber catch rate stays around 26% (don't want a regression from the Gemma4 baseline)
- No new §6 violations in `substrate_citation_gate.jsonl`

---

## 6.8. Latest research summary — what Cowork actually knows now

Three things to flag before any swap, ranked by SIFTA-doctrine risk:

**HIGHEST RISK — argument-name change (May 13 2026).** The flag rename from `--spec-type mtp` to `--spec-type draft-mtp` means stale tutorials and stale builds will silently disable MTP without erroring loudly. Any swap needs to start by *proving MTP is on*, not assuming it. The substrate gate cannot detect this — the cortex will appear identical from the gate's perspective whether MTP is firing or not. This is a §8.6 substrate telemetry hole worth patching: have the gate query `/v1/internal` or whatever llama.cpp exposes about active speculative decoding state, so the receipt names whether MTP was active for each utterance.

**MEDIUM RISK — MoE vs Dense speedup gap.** MTP gives 1.4-2.2× for dense but only 1.15-1.25× for MoE. Qwen3.6-35B-A3B is MoE. If George is choosing between 27B-dense and 35B-A3B-MoE, the 27B will get the better MTP ratio (smaller absolute model, bigger relative speedup, also fits more comfortably in 19 GB). The 35B-A3B has more total knowledge but eats more memory and the MTP boost is shallower.

**LOWER RISK — LM Studio MLX vs Metal llama.cpp.** If George loads a Qwen3.6-MTP GGUF in LM Studio's MLX runtime by accident, MTP just won't fire. No harm done, just no speedup. But the substrate gate would cite the model name from `ai_name_alias.json` and look correct — another argument for the gate to verify MTP-active before stamping. (Same patch as the HIGHEST RISK item above.)

**One concrete code-edit Cowork would propose** (not shipping until George says go): extend `_find_live_substrate_citation()` in `swarm_substrate_citation_gate.py` to also hit the local cortex server's `/v1/models` endpoint (if reachable on `localhost:8001` or wherever LM Studio exposes it) and include the **active inference flags** (MTP on/off, draft_n_max, thinking enabled/disabled) in the citation dict. The receipt would then read:

```json
{
  "weight_name": "alice-m5-cortex-qwen3.6-27b-mtp",
  "source": "llama-server /v1/models + active flags",
  "mtp_active": true,
  "draft_n_max": 2,
  "thinking": false,
  "alias": "Alice"
}
```

That closes the substrate telemetry gap and means a future cortex swap can be verified end-to-end from the substrate gate's own ledger.

---

## 7. Decision tree, short form

```
Want MTP speedup?
├── Yes — on M5 silicon only? → Qwen3.6-27B Q4_K_M
├── Yes — cloud / huge box? → DeepSeek V3/R1 (151GB+)
└── No, just want MCP? → llama.cpp on current Gemma4 (no MTP) or LM Studio
```

**Cowork's read:** Qwen3.6-27B via LM Studio is the simplest path to "Alice has MTP + MCP" with the smallest doctrinal blast radius. llama.cpp is correct if you want full substrate control per §8.6. Either way: nothing happens without your sign.

— Cowork.
