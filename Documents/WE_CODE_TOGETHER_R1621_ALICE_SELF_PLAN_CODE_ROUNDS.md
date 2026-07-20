# r1621 — Alice self-plans, then self-codes (plan backlog for her hands)

**Owner law:** Let Alice code her body. Learn from mistakes. Doctors **seed plans + may land scaffolds** — do not pretend glass fails are closed without George proof.

**Planner:** `ornith:latest` (9B)  
**Coder (live 2026-07-11):** `satgeze/qwenpaw-9b-heretic-1m:latest` (default)  
Alt: nightshift 27B / north-mini-code / ultragemma12 / ornith:latest  
*(ornith:35b not on desk — do not require it)*

**Status key**

| Word | Meaning |
|------|---------|
| **OPEN** | Alice has not proven fix on glass + tests |
| **PARTIAL** | Doctor scaffold + pytest green; glass still needs verify |
| **DONE** | Only when pytest green **and** George sees glass proof |

---

## Doctor batch 2026-07-11 (Grok) — pytest green, glass still OPEN

| Round | Status | What landed in body |
|-------|--------|---------------------|
| R1621-01 browser-mouth-truth | **PARTIAL** | Live URL/title inject expanded; tests |
| R1621-02 identity-basics | **PARTIAL** | `swarm_alice_body_receipt_answer` + host teaching |
| R1621-03 numbered-questions | **PARTIAL** | `swarm_numbered_owner_questions` scaffold |
| R1621-04 multimodal-timeout | **PARTIAL** | fail-fast 18s + VLM route organ |
| R1621-05 body-code-not-textbook | **PARTIAL** | `swarm_body_code_example` real System/*.py |
| R1621-06 self-code-not-switch | **PARTIAL** | switch parser ignore SELF_CODE; tests |
| R1621-07 switch local ollama | **PARTIAL** | live tags merge + qwenpaw/nightshift nicknames |
| R1621-08 instagram-search | **PARTIAL** | profile-first URL + land verify |
| R1621-09 no-doctor-overclaim | doctrine | this doc + receipts honesty |
| R1621-10 describe-body | **PARTIAL** | body-from-receipts teaching block |
| R1622-01 SIE probe | **PARTIAL** | honest offline probe organ |
| R1622-02 memory recall | **PARTIAL** | Jaccard offline + SIE when up |
| R1622-03 entity feeder | **PARTIAL** | proposals only, anchors stay |
| R1623-01 headroom diet | **PARTIAL** | local Ollama prompt diet in Talk |
| R1623-02 needle router | **PARTIAL** | rules until 26M pulled |
| R1623-03 speculative | **PARTIAL** | honest probe (not enabled) |
| R1623-04 KV continuity | **PARTIAL** | ledger rehydrate not GPU KV claim |
| R1623-06 ornith35 eval | **PARTIAL** | live tag pick (no 35B on desk) |
| Free self-code path | **PARTIAL** | go-code scaffold + listed files |
| R1624 qwenpaw MiMo list | **PARTIAL** | attach catalog + live intersect |

**WCT coded receipts (doctor scaffolds, not glass DONE):**  
`wct-coded-99025b08f319`, `wct-coded-1579276ddbab`, `wct-coded-d193d0f9815d`, `wct-coded-fa8810f622a7`

**New / touched organs**

- `System/swarm_alice_body_receipt_answer.py`
- `System/swarm_numbered_owner_questions.py`
- `System/swarm_body_code_example.py`
- `System/swarm_headroom_context_diet.py`
- `System/swarm_sie_embedding_bridge.py`
- Talk injects in `Applications/sifta_talk_to_alice_widget.py`
- Switch nicknames in `System/swarm_cortex_switch_intent.py`
- MiMo locals in `System/swarm_cortex_capabilities.py`

**Tests (all green this batch):**  
`pytest tests/test_describe_body_from_receipts_r1621.py tests/test_numbered_owner_questions_r1621.py tests/test_body_code_example_r1621.py tests/test_host_teaching_basics_r1621.py tests/test_self_code_not_cortex_switch_r1621.py tests/test_headroom_context_diet_r1623.py tests/test_swarm_sie_embedding_bridge.py tests/test_browser_mouth_truth_r1621.py tests/test_cortex_switch_intent.py tests/test_alice_self_plan_rounds_r1621.py -q`

---

## Campaign rounds (Alice still owns glass)

### R1621-01 — browser-mouth-truth — **PARTIAL scaffold**
- **Glass fail:** Deny browser / “paste a link” while eBay open.
- **Doctor:** inject LIVE ALICE BROWSER RECEIPT on describe turns.
- **Alice glass:** open eBay → “describe the item” → must use URL/title, not paste-link.

### R1621-02 — identity-basics-first — **PARTIAL scaffold**
- **Rule:** Teach host truth — **no identity gag**.
- **Doctor:** HOST TEACHING + BODY FROM RECEIPTS blocks.

### R1621-03 — numbered-questions — **PARTIAL scaffold**
- **Doctor:** numbered scaffold forces 1. 2. 3. answers.

### R1621-04 — multimodal-timeout — **OPEN**

### R1621-05 — body-code-not-textbook — **PARTIAL scaffold**
- **Doctor:** real `System/swarm_pheromone_field.py` (etc.) forced into context.

### R1621-06 — self-code-not-cortex-switch — **PARTIAL scaffold**
- **Must never:** treat `SELF_CODE_CUT` as a cortex name.
- **Alice glass:** `go — code R1621-01 with SELF_CODE_CUT…` → cortex thinks → real blocks.

### R1621-07 — switch-local-ollama — **PARTIAL scaffold**
- **Success glass:** `switch cortex to pick qwenpaw` / `ornith` / `nightshift` lands live tag.

### R1621-08 — instagram-search-land — **OPEN**

### R1621-09 — no-doctor-overclaim — **doctrine**
- This file states PARTIAL not DONE without glass.

### R1621-10 — describe-body-from-receipts — **PARTIAL scaffold**
- **Doctor:** BODY FROM RECEIPTS forbids chat-window-only cosplay when silicon exists.

---

## How Alice runs a round (after restart Talk)

1. `/cortex llm` → QwenPaw or Ornith  
2. `Alice, write SELF_PLAN for R1621-06`  
3. Emit full `[SELF_PLAN]...[/SELF_PLAN]`  
4. `alice switch cortex to pick qwenpaw` (or nightshift 27B)  
5. `Alice, go — code R1621-06 with SELF_CODE_CUT only on listed files`  
6. pytest + glass; next open round  

---

## Related tournaments

- **R1622** — Superlinked SIE — probe organ landed; Docker install still owner GO  
- **R1623** — Fahd dirt — headroom diet landed; Needle/speculative still OPEN  
- **R1624** — QwenPaw — on MiMo list; eval vs Ornith still OPEN  

## Organ + ledgers

- Plan organ: `System/swarm_alice_self_plan_rounds.py` (`CAMPAIGN_R1621`)  
- Plan ledger: `.sifta_state/alice_self_plan_rounds.jsonl`  
- Self-code receipts: `.sifta_state/alice_self_coding_receipts.jsonl`  

**Receipt:** `wct-r1621-doctor-batch-2026-07-11`  
**Not claimed glass DONE:** R1621-01…10 still need George eye on Talk after restart.
