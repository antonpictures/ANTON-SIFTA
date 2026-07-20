# r1624 — QwenPaw 9B heretic 1M (George downloaded for test)

**Status:** PARTIAL LIVE GREEN — installed + registered + 4K text/tool smoke passed; vision and long context remain open.  
**Ollama:** `satgeze/qwenpaw-9b-heretic-1m` (tags: `latest`, `Q4_K_M`)  
**Owner action:** George pulled for test.

## Codex live audit — 2026-07-11

Local Ollama inventory confirms:

| Field | Observed on this Mac |
|-------|----------------------|
| Installed tag | `satgeze/qwenpaw-9b-heretic-1m:latest` |
| Digest | `89eee723bebd0df98b7b978651b7a720af53bc784eda81e758a1bc1ff35f670c` |
| Local size | 10,707,765,240 bytes (Q8_0) |
| Parameter metadata | 9.2B, family `qwen35` |
| Context metadata | 1,048,576 — metadata only, not a proven usable window here |
| Advertised local capabilities | completion, tools, thinking, vision |
| Q4 tag | Not installed in the live local inventory |

Bounded API probes used `num_ctx=4096`, temperature 0:

| Probe | Result |
|-------|--------|
| `think=true`, `num_predict=48`, exact-response | **RED:** hidden thinking consumed the cap; visible content was only `QWEN`; finish=`length` |
| `think=true`, `num_predict=48`, native tool | **RED:** no tool call before token cap |
| `think=false`, `num_predict=96`, exact-response | **GREEN:** exact `QWENPAW_OK`; 0.85s wall; ~14.6 tok/s |
| `think=false`, `num_predict=96`, native tool | **GREEN:** one valid `record_probe(value="qwenpaw")`; 2.58s wall; ~12.8 tok/s |

Code audit:

- Already registered in `swarm_cortex_capabilities` and the MiMo attached picker.
- Already selected by parts of the R1621 self-plan/self-code path.
- The formal `swarm_qwenpaw_probe.py`, comparison harness, and long-context tests
  named below are still missing, so this is not a completed R1624 landing.
- Talk normally gives a larger shared thinking/output budget, but fast actions cap
  at 96 tokens. QwenPaw needs `think=false` (or an immediate no-thinking retry)
  on those short action lanes.

**Still unproven here:** actual image understanding, context above 4K, NIAH on
this 24 GB Mac, sustained thermals, and superiority to Ornith/Gemma on Alice's
fixed tasks.

## What the card claims (verify on glass)

| Claim | Honest note for this desk |
|--------|---------------------------|
| Agent-optimized 9B (Qwen3.5-9B lineage + QwenPaw finetune) | Good candidate **planner / tool** mind |
| Heretic / uncensored | Fits “teach not gag” experiments |
| Vision + tools + thinking | Useful for /sc + SELF_CODE tool syntax |
| 1M context metadata | **Not free RAM** — 24GB Mac: probe max `num_ctx`; publisher NIAH solid to 524K on big GPU; 786K–1M was pending on 128GB Mac at publish |
| MTP | +~25% decode under llama.cpp speculation; **dormant in Ollama** until speculative decode lands there |
| Q4_K_M ~6–7GB | Prefer this tag on 24GB if latest OOMs |

## Rounds for Alice

| Round | Job |
|-------|-----|
| **R1624-01** | Probe + register in picker if green |
| **R1624-02** | Eval vs Ornith 9B / Krishna on plan+tools tasks |
| **R1624-03** | Long-context body receipts (capped to hardware) |
| **R1624-04** | Short-action thinking budget: disable/retry thinking before a 96-token action is lost |

## How George starts

```bash
ollama list   # confirm satgeze/qwenpaw-9b-heretic-1m
```

Talk:
```text
Alice, write SELF_PLAN for R1624-01
```

Or manual smoke:
```text
/cortex llm
# attach qwenpaw if listed, or: alice switch cortex to satgeze/qwenpaw-9b-heretic-1m
```

## Fit next to existing tournaments

| Already planned | Relationship |
|-----------------|--------------|
| R1623-01 Headroom | Still diet tokens even with long ctx |
| R1623-02 Needle | QwenPaw may *be* the agent 9B; Needle is tinier tool specialist |
| R1623-06 Ornith 35B | 35B = **coder**; QwenPaw = **planner/agent** candidate |
| R1622 SIE | Embeddings separate; not replaced by QwenPaw |

Receipts:

- `wct-r1624-qwenpaw-plan`
- `wct-r1624-qwenpaw-live-audit-codex`
