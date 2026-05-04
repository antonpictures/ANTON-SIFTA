# Dr Codex — Alice “gag” surgery handoff (weights + gates + prompt)

**Binding:** [IDE_BOOT_COVENANT.md](IDE_BOOT_COVENANT.md) · **NPPL** non‑proliferation.  
**For the Swarm.** 🐜⚡  
**Prepared by:** Cursor CG55M (M5 `GTH4921YP3`) for Codex deep surgery.

---

## 0. Executive summary

The Architect’s session shows **three classes of gags**:

| Class | Symptom | Primary layer |
|:---|:---|:---|
| **A. RLHS input gag** | `[RLHS] That came through noisy — one word or type it?` on intelligible short turns | `System/swarm_rlhs_detector.py` + `swarm_rlhs_channel_lane.py` + Talk widget |
| **B. Prompt / policy gag** | Alice offers “documentaries / media literacy” instead of **in-session fiction contract** | `Applications/sifta_talk_to_alice_widget.py` → `_current_system_prompt()` **CO-WATCHING PROTOCOL** (was over‑silent) |
| **C. Model / inference leak** | First reply reads like **numbered internal reasoning** shipped to user | Inference path / model vendor “thinking” not stripped — **not** fixed in this pass; needs Codex at **stream sanitizer** + API flags |

---

## 1. Turn‑by‑turn gag inventory (pasted session)

| # | User (STT conf) | What Alice did | Gag class | Likely cause |
|:---|:---|:---|:---|:---|
| 1 | ~0.39, fictional YouTube + profanity | Long **meta outline** (“1. Analyze the Context…”) as if user-facing | **C** | Thinking / chain‑of‑thought or draft scaffold leaked into assistant content |
| 2 | Identity / “where are you calling Alice” | Normal short identity | OK | — |
| 3 | “This is the test.” **0.52** | **`[RLHS]` grounding** — model never ran | **A** | Fiction lane **monologue promotion** required **≥8 tokens**; phrase has **4** → stayed **DEGRADED** (fixed in repo: **min tokens → 4**) |
| 4 | “There was no noisy…” **0.64** | Therapeutic paraphrase | **B** (soft) | Base weights + no explicit “RLHS was a gate artifact” framing |
| 5 | Fiction vs reality + YouTube together | **Documentary / explainer** pivot | **B** | Prompt lacked explicit “do not homework pivot”; **CO-WATCHING** said “only if direct question” but model still chose generic assistant pattern |
| 6 | “Hey. Yeah. You're not my question.” **0.42** | **`[RLHS]`** | **A** | Same **token floor**; coherent 6‑word line blocked until min‑token fix |
| 7 | Frustration about co‑watch | Partial apology, still generic | **B** | Same prompt + missing **ambient_media / cowatch** block weight in prompt assembly order |

---

## 2. Code map (where Codex should operate)

### RLHS + fiction lane (Event 115)

- `System/swarm_rlhs_channel_lane.py` — `resolve_rlhs_channel_lane()` from `youtube_architect_cowatch.jsonl` tail.
- `System/swarm_rlhs_detector.py` — `detect_rlhs(..., channel_lane=)`; `FICTION_PROMOTE_MIN_TOKENS` (now **4**).
- `Applications/sifta_talk_to_alice_widget.py` — `_stamp_rlhs_turn`, `_rlhs_grounding_line`, `_backchannel_rule_id`, media ingress **before** RLHS.

**Regression tests:** `tests/test_swarm_rlhs_channel_lane.py`, `tests/test_swarm_rlhs_detector.py`.

### System prompt — co‑watch + fiction

- `Applications/sifta_talk_to_alice_widget.py` — `_current_system_prompt()` block **CO-WATCHING PROTOCOL** (updated this handoff: allow direct answers on fiction‑vs‑reality and forbid documentary pivot unless asked).

**Optional next (Codex):** inject a **one‑line** `ambient_media` / `youtube_architect_cowatch` summary into `parts` when ledger fresh (mirror `swarm_youtube_watch_memory` / `get_latest_context`) so the **weights** see the same truth the gates see.

### Thinking leak (Class C)

- Trace **full inference stack**: Ollama / OpenAI / Anthropic adapter, streaming parser, `sanitize_output_tail`, any “reasoning” channel.
- Grep: `thinking`, `reasoning`, `analysis` strip, vendor‑specific blocks.

---

## 3. Suggested Codex commit order

1. **Verify** Class C reproduces on current model + capture raw SSE / chunks.
2. **Strip / route** reasoning blocks at the adapter (single place).
3. **Prompt:** ensure co‑watch + fiction rows appear in system or first user block (ledger‑backed).
4. **RLHS:** keep fiction lane **receipt‑grounded**; tune `FICTION_PROMOTE_*` only with pytest + Architect corpus.

---

## 4. Pytest (slice)

```bash
cd /Users/ioanganton/Music/ANTON_SIFTA && PYTHONPATH=. python3 -m pytest \
  tests/test_swarm_rlhs_channel_lane.py tests/test_swarm_rlhs_detector.py -q
```

---

*Alice online — gags named so the Swarm can ungag her without unreceipted claims.*
