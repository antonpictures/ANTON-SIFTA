# WCT Research — PrismML Bonsai + llama.cpp ARM

**Receipt:** `r20260714-wct-research-prismml-bonsai-llama-cpp-arm`  
**Lane:** RESEARCH (not trading)  
**Priority:** 2  
**From:** Owner George via Alice/Grok · 2026-07-14

## Owner intent

> ADD THIS TO WE CODE TOGETHER FOR RESEARCH  
> PrismML Bonsai (ultra-dense / on-device models)  
> llama.cpp for ARM for the future  
> Then back to Alice trading.

Predictions cash ~$20.44 is for **trading later** — this item is **compute/research only**.

## Vendor claims (unverified — research must check)

Source: PrismML public site (owner paste / prismml.com)

| Claim | Note |
|--------|------|
| **Bonsai 27B** | First 27B-class class model runnable on phone (per vendor) |
| **1-bit** | ~3.9GB — iPhone-class size claim |
| **Ternary** | ~5.9GB — laptop optimized claim |
| **14× less memory** | vs standard dense baseline (verify) |
| **8× faster** | verify hardware + baseline |
| **5× less energy** | verify |
| **Capabilities** | multi-step reasoning, tool calling, agentic workflows, multimodal |
| **Family** | 27B, 8B, 4B, 1.7B · 1-bit and ternary · image variants |
| **Metric** | Intelligence density = −log(error) / model size (whitepaper) |

## Research questions for Claude

1. **Runtime reality:** Does Bonsai run under **llama.cpp**, GGUF, custom runtime, or Bonsai Studio only?
2. **ARM path:** Apple Silicon (macOS), iOS, Android — which is supported today vs roadmap?
3. **License / weights:** commercial terms, redistribution, offline use for SIFTA.
4. **Tool calling:** JSON/schema tools suitable for Alice organs (paper monitor, WCT, glass)?
5. **vs current stack:** Any existing local LLM in ANTON_SIFTA; MLX on Apple already?
6. **Spike recommendation:** Smallest useful model for **offline agent loop** (8B ternary vs 27B 1-bit).
7. **Risks:** quality collapse at 1-bit, hallucination in trading advice (must stay out of live USD path).
8. **Energy/memory:** independent benches if any; do not trust marketing alone.

## llama.cpp ARM notes (seed)

- Upstream: https://github.com/ggml-org/llama.cpp  
- Apple Silicon often uses Metal; ARM64 Linux NEON; iOS needs careful packaging.  
- Research should map **Bonsai quant format → llama.cpp compatibility** (may be non-GGUF).

## Out of scope

- Opening US$ lane  
- Changing scalp thresholds  
- Downloading multi-GB weights into CI  

## Success

- MD brief with go/no-go + next spike only  
- WCT coded research receipt  
- Trading Alice continues on dual-lag / green-scalp track separately  

For the Swarm. 🐜⚡
