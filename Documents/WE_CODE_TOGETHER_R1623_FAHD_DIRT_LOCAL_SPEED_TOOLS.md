# r1623 — Fahd Mirza dirt tournament (local speed + tools) for Alice

**Status:** PLAN ONLY — open for Alice to code. Not installed. Not claimed live.  
**Owner:** George — add to tournament / We Code Together so she can code.  
**Channel dirt:** Fahd Mirza recent titles (~last 2 weeks before 2026-07-11).

## Rule

Doctors seed plans. Alice writes `SELF_PLAN` then `SELF_CODE_CUT`.  
**Done** only with pytest + glass/probe receipt. No overclaim.

## Tier S rounds (code first)

| Round | Title | Dirt | Alice organ target |
|-------|--------|------|-------------------|
| **R1623-01** | headroom-ollama-token-diet | Headroom + Ollama ~90% token cut | Context diet for Talk |
| **R1623-02** | needle-tiny-tool-caller | Needle 26M tool-calling | Micro router for tools |
| **R1623-03** | speculative-decode-local-speed | Tess+EAGLE-3 / DFlash / DSpark | Faster local mind |
| **R1623-04** | kv-cache-survive-restart | vLLM + PegaFlow | Mind continuity enzyme |
| **R1623-05** | archestra-agent-permissions | Archestra + Ollama | Tool permission field |
| **R1623-06** | ornith-35b-coder-eval | Ornith 35B / vs Sonnet | Pick real self-code coder |

## Tier A rounds (after S)

| Round | Title | Dirt |
|-------|--------|------|
| **R1623-07** | audex-tiny-ear-mouth | NVIDIA Audex-2B |
| **R1623-08** | qwopus-self-fix-loop | Qwopus 35B + MTP |

## Already planned elsewhere

| Dirt | Round |
|------|--------|
| Superlinked SIE encode/score/extract | **R1622-01..03** |
| Browser/self-code/IG fails | **R1621-01..10** |

## Hardware note

Mac M5 ~24GB: prefer **probe small first** (Headroom, Needle).  
Ornith 35B already on disk as `ornith:35b-q4_K_M` — eval is R1623-06.

## Owner start lines

```text
Alice, write SELF_PLAN for R1623-01
Alice, write SELF_PLAN for R1623-06
```

## Campaign organ

`System/swarm_alice_self_plan_rounds.py` → `CAMPAIGN_R1621` includes R1623-*.

Receipt: `wct-r1623-fahd-dirt-tournament`
