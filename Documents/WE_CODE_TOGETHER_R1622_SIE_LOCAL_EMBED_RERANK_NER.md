# r1622 — Superlinked SIE dirt (Fahd Mirza 2026-07-11) → Alice borg plan

**Status:** PLAN ONLY — Alice codes later. Not installed. Not claimed live.  
**Source dirt:** Fahd Mirza — *Local Embedding Server with 150 AI Models | Superlinked SIE* (Jul 11, 2026)  
**Code:** https://github.com/superlinked/sie  

## What it is (clean)

| Piece | Meaning for Alice |
|-------|-------------------|
| **SIE** | Superlinked Inference Engine — **one Docker** serving many small models |
| **encode** | Text → embedding vector (e.g. 1024-d) for vector memory |
| **score** | Rerank candidates vs query (better order than bare cosine) |
| **extract** | Zero-shot NER — person / org / place from free text (**optional feeder only**) |
| **Port** | Typically **8080** |
| **SDK** | Python client: encode / score / extract |

**Problem it solves:** RAG usually needs separate embedding + rerank + NER servers (cost, VRAM, latency). SIE packs ~85–150 preconfigured models into one container.

**Not:** a chat cortex. **Not** a replacement for Ornith/Gemma. **Support organ** for the **soul memory field**.

## What Alice can borg (honest fit)

| Borg target | Why it matches her body |
|-------------|-------------------------|
| Journal / convo **recall** | Embed tails → retrieve → rerank before cortex speaks |
| WCT / doctor dirt | Rank relevant plan rows without loading whole oceans |
| **People/places** | extract → **propose** deposits into **existing** `concept_human_anchor` (we already have human anchors — SIE does not replace them) |
| Local independence | Docker local = works when cloud OAuth is empty |
| Receipts | Every encode/score/extract call can write JSONL row |

## What she should **not** do

- Claim SIE is running without probe receipt  
- Pull 150 models at once on 24GB Mac (pick **one** embed + **one** rerank + **one** NER)  
- Replace stigmergic ledgers with vectors only — vectors **index** receipts, don’t delete them  

## Hardware note (this desk)

George’s Mac M5 24GB: Docker Desktop possible; many embed models are small (video: “don’t need huge GPU”).  
**R1622-01** = probe first (CPU ok). GPU host optional later.

## Alice rounds

| Round | Title | Done when |
|-------|--------|-----------|
| **R1622-01** | sie-local-embedding-server-probe | Bridge organ + dry-run tests; optional Docker up + receipt |
| **R1622-02** | sie-wire-memory-recall | “remember X” uses encode+score + evidence list |
| **R1622-03** | sie-wire-entity-extract | NER as **feeder** into existing human anchors (not a second system) |

## Already have human anchors (George 2026-07-11)

**Yes.** `System/swarm_concept_human_anchor.py` + temporal epoch pins.

SIE **extract** is optional automation to *suggest* new surfaces — **not** to reinvent anchors.  
Priority for SIE is **encode + score** (recall). Extract is nice-to-have.

## Owner paste to start Alice

```text
Alice, write SELF_PLAN for R1622-01
```

Then after plan + Docker if she has it:

```text
Alice, go — code R1622-01 with SELF_CODE_CUT only on listed files
```

## Doctor duty

Seed only. **No “Alice has SIE”** without `sie_probe` receipt + glass/logs.

Receipt: `wct-r1622-sie-dirt-plan`
