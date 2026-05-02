# Research — Moonshot “Prefill-as-a-Service” (PRF) × SIFTA (tournament + stigmergy)

**For the Swarm.** 🐜⚡

**Truth label:** `RESEARCH_NOT_SHIPPED` — infrastructure paper walkthrough; **no cross-datacenter KV shipping** in SIFTA until Architect GO + **privacy / DP law** review + reproduced numbers.

**Primary sources (video + paper):**

- Fahd Mirza, *Moonshot AI Just Dropped a Gem That Makes Long-Context Models 54% Faster & Cheaper* (YouTube, 2026-04-19) — narrative: **prefill** (build KV / “read the world”) vs **decode** (token-by-token generation) today **co-located** on one expensive cluster → **rigid utilisation**; Moonshot proposal **splits** heavy prefill onto a **dedicated compute cluster** and ships a **small hybrid KV / cache artifact** over **cheap WAN** to a **decode-optimised** cluster (**PRF / “PRFaas”** framing); **~54% faster & cheaper** headline (verify on paper figures + your workload); **hybrid cache** reuse across requests; comment thread flags **privacy / data-residency** when KV leaves jurisdiction.
- **Paper (canonical HTML):** [arxiv.org/html/2604.15039v1](https://arxiv.org/html/2604.15039v1) — also resolve [arxiv.org/abs/2604.15039](https://arxiv.org/abs/2604.15039) for citekey / PDF export.

**Related SIFTA research:** [RESEARCH_DIRT_INDEX.md](RESEARCH_DIRT_INDEX.md), [RESEARCH_DeepSeek_V4_DeepEP_TileKernels_SIFTA_Tournament_2026-05-01.md](RESEARCH_DeepSeek_V4_DeepEP_TileKernels_SIFTA_Tournament_2026-05-01.md) (long-context economics), [ALICE_HARDWARE_ANATOMY.md](ALICE_HARDWARE_ANATOMY.md) (**borrowed inference** = natural prefill/decode split across Foundry vs field), [RESEARCH_Semble_MCP_Coding_Tournament_2026-05-01.md](RESEARCH_Semble_MCP_Coding_Tournament_2026-05-01.md) (context is money).

---

## 1. Stigmergic nuggets

1. **Thermodynamic honesty:** long-context “free lunch” is usually **prefill cost moved elsewhere** — receipts must split **`t_prefill_s`**, **`t_decode_s`**, **`bytes_moved`**, **`vram_prefill_peak`**, **`vram_decode_peak`**.
2. **Borrowed inference isomorphism:** Foundry runs **heavy prefill** (index Semble, embed corpus, run omni encoders); Sentry / Pi **decodes short replies** — same *shape* as PRF without trusting a third-party datacenter.
3. **Semble synergy:** retrieval **shrinks prefill** before the LM sees the repo — same battle as PRFaaS but **local-first**.
4. **Legal / NPPL:** cross-border KV transfer is **not a math problem only** — tournament docs must carry **`data_residency`** and **consent scope** fields if any design mimics PRF.

---

## 2. Tournament experiments (Architect GO)

| Experiment | Pass criterion |
|:---|:---|
| Reproduce one **table / figure** from the paper on open weights | Numbers within stated tolerance; log hardware SKU |
| A/B: **monolithic serve** vs **simulated split** (two processes, synthetic network latency) | Wall time + $ proxy (joules × tariff) written to `work_receipts.jsonl` |
| Privacy red-team | If `bytes_moved` crosses WAN, require **`legal_ok: true`** receipt line |

---

## 3. One-line tournament takeaway

> **PRFaass sells cheaper long-context in the cloud; SIFTA sells the same split with a shorter wire — receipts beat slogans.**

For the Swarm. 🐜⚡
