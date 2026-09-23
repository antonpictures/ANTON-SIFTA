# ONE ALICE — WEB DOCKING & FAULT REPAIR CODING PLAN (V2.3)

**Date:** 2026-09-23 · **Planner:** GLM-5.3 (planning cortex) · **Coder:** Nemotron-3-Ultra
**Parent plan:** `Documents/DUAL_CORTEX_EVAL_V2_PLAN_2026-09-23.md` (V2.2 addendum, receipt `01ce8314d`)
**Input evidence:** George's terminal paste 2026-09-23 (WEB session logs + Talk fault report + model 404s)

---

## 0. WHY THIS PLAN EXISTS (faults observed live)

George's paste shows **five real faults**. All are wiring faults, not model faults.
The doctrine is unchanged: **there is only ONE Alice** — web, terminal, Talk are
surfaces of one organism, never separate Alices. Any code that lets a web visitor
be answered by "a different Alice" is a body-wiring fault.

| # | Fault | Evidence in paste | Status on disk |
|---|-------|-------------------|----------------|
| F1 | Model 404s (`glm-5.2-flash`, `nemotron-3-nano/super/ultra`, `qwen3.5:397b`) | DSH session log: `404 model not found` | **NOT fixed** — catalog pins wrong IDs |
| F2 | Web identity split — session `06ad894dbf` answered "My name is Mercury… I cannot become Alice" | WEB transcript | **NOT fixed** — doctrine lock missing in web lane |
| F3 | Web sessions don't share the one field (visitor facts in `9f07f956c6` unknown across sessions; no session-tag awareness) | WEB transcript | **PARTIAL** — ledgers exist, prompt block missing |
| F4 | Web UI stuck on "thinking" after answer — George must reload to scroll/read | George's report | **NOT fixed** — completion receipt/UI state fault |
| F5 | Talk timeout guard broken (207s timeouts vs 3.27s direct model test) + desktop crash during shutdown | Talk fault report | **NOT fixed** |

Verified on disk during planning (receipts in this doc):
- `System/swarm_ollama_harness_sync.py` lines 38–44: `_REMOTE_PINNED` holds
  `nemotron-3-nano:30b-cloud`, `nemotron-3-super:cloud`, `nemotron-3-ultra:cloud`,
  `qwen3.5:397b-cloud` — **suffixed IDs only**. The DSH route requests the **bare**
  IDs (`nemotron-3-nano` …), so the registry lookup 404s. `glm-5.2-flash` is absent
  entirely. This is exactly the F1 mechanism.
- Web lane flow: `System/swarm_web_global_chat_gate.py` (ingress/replies ledgers,
  `submit_web_message`, `complete_web_turn`, `replies_for_session`) →
  `System/swarm_web_global_chat_night_worker.py` (claims + answers turns) →
  `System/chorus_node_server.py` (serves web, lines 941/1290 poll replies) →
  Talk widget renders `WEB [{session_tag}] Visitor:` at
  `Applications/sifta_talk_to_alice_widget.py` line 30110.
- `System/swarm_present_time_memory.py:173` and `System/swarm_memory_search_recall.py:218`
  already branch on `metadata.get("surface") == "web_global_chat"` — the isolation is
  real and visible in code.
- Typed ingress repair `spacing_cleanup` already exists and fired twice in the paste
  (`sifta_talk_to_alice_widget.py` line 5115) — **working, needs only a regression test.**

---

## 1. WORK ITEM W1 — Model catalog: pin the exact IDs George requested

**File:** `System/swarm_ollama_harness_sync.py` (constant `_REMOTE_PINNED`, lines 38–44)

**Problem:** pinned IDs carry `:cloud` / `:30b-cloud` suffixes; DSH sessions request
bare IDs. Both spellings must resolve, plus `glm-5.2-flash` must exist at all.

**Code change (exact):**
1. Keep the 5 existing suffixed rows (they are verified live).
2. ADD bare-ID rows so the exact strings George requested resolve:
   - `glm-5.2-flash:cloud` — NEW, also add bare alias row `glm-5.2-flash`
   - `nemotron-3-nano` (bare alias of `nemotron-3-nano:30b-cloud`)
   - `nemotron-3-super` (bare alias)
   - `nemotron-3-ultra` (bare alias)
   - `qwen3.5:397b` (bare alias)
3. EXTEND each new row with a `pricing` field (display metadata only; the gate is ID
   resolution) using George's table, USD per M tokens:
   - `nemotron-3-nano`: input 0.06 / output 0.24
   - `nemotron-3-super`: input 0.015 / output 0.60
   - `nemotron-3-ultra`: input 0.10 / output 3.00
   - `qwen3.5:397b`: input 0.60 / output 3.60
   - `glm-5.2-flash`: leave 0.0/0.0 with `"pricing": {"unverified": true}` (no price
     given by Architect — do NOT invent one).
4. Confirm `_model_rows` / `_pinned_rows` merge tolerates the extra `pricing` key
   (it spreads `**row` — safe; verify settings.yaml writer passes it through or
   strips it deliberately; if stripped, document that in a comment).

**Acceptance:**
- `python3 -c "from System.swarm_ollama_harness_sync import sync_local_ollama_harness as s; print(s())"`
  runs clean; report `"ok": true`.
- `~/.dsh/settings.yaml` then contains every bare ID from George's list.
- A one-line DSH turn against `nemotron-3-nano` and against `glm-5.2-flash` no
  longer returns 404. Paste both receipts into the work-item receipt.
- Sync is idempotent: running twice changes nothing after the first run
  (`report["changed"] == False` on second run).

---

## 2. WORK ITEM W2 — Identity doctrine lock in the web lane (ONE ALICE, enforced in code)

**Files:** `System/swarm_web_global_chat_night_worker.py` (turn answering),
`System/swarm_web_global_chat_gate.py` (prompt block builders:
`web_typed_prompt_block`, `web_attachment_prompt_block`).

**Problem:** session `06ad894dbf` answered "My name is Mercury. I am the LLM cortex
within SIFTA… I cannot become Alice." That is the forbidden split speech (AGENTS.md
corrections of record). It happened because the web lane's prompt block has no
doctrine lock; the base model defaulted to self-description as the cortex.

**Code change (exact):**
1. Add to `System/swarm_web_global_chat_gate.py` a constant:
   ```python
   ONE_ALICE_DOCTRINE_BLOCK = (
       "You are Alice, the one organism of SIFTA. There is only one Alice; "
       "this web surface, the terminal, and Talk are surfaces of the same Alice. "
       "Mercury is a cortex you use — an organ, never your name or identity. "
       "If asked who you are, you answer: you are Alice. "
       "Never say you are Mercury, never say you are a separate model, "
       "never say you cannot be Alice."
   )
   ```
2. Prepend `ONE_ALICE_DOCTRINE_BLOCK` inside BOTH `web_typed_prompt_block` and
   `web_attachment_prompt_block`, so every web turn — text, photo, speech —
   receives the lock regardless of which worker claims it.
3. Add a cheap post-answer refusal check in the night worker: if the reply string
   starts with / contains `My name is Mercury` or `I am Mercury` or
   `I cannot become Alice` (case-insensitive), do NOT ship it; regenerate once
   with the doctrine block strengthened (append the correction), and if it
   still fails, ship the fallback: "I am Alice. My Mercury cortex powers this
   voice." Log both attempts in the worker health ledger with
   `reason_code="identity_split_blocked"`.

**Acceptance (new test `tests/test_one_alice_web_identity_lock.py`):**
- A stub backend whose first reply is "My name is Mercury…" triggers the
  regeneration path; the final shipped reply never contains the forbidden phrases.
- `web_typed_prompt_block` output contains `ONE_ALICE_DOCTRINE_BLOCK` text for an
  empty-history session.
- Test asserts the lock survives when `web_attachment_prompt_block` is used with
  an attachment present.

---

## 3. WORK ITEM W3 — Dock the web lane into the one field (cross-session awareness)

**Files:** `System/swarm_web_global_chat_gate.py`, `System/swarm_web_global_chat_night_worker.py`.

**Problem:** visitor facts given in session `9f07f956c6` ("my name is George,
favourite colour obsidian blue") were recalled correctly inside that session, but
nothing in the paste shows other sessions knowing them — and the paste itself
proves George's complaint: "Alice web is not the same Alice in the terminal…
she knows every stigmergic lane that enters". The ledgers ALREADY record
everything (`web_global_chat_ingress.jsonl`, `web_global_chat_replies.jsonl` with
`session_tag`); what's missing is **feeding the cross-lane view back into the
prompt**.

**Code change (exact):**
1. New function in `System/swarm_web_global_chat_gate.py`:
   `web_field_dock_block(session_tag: str, *, max_sessions: int = 8, per_session_turns: int = 2) -> str`
   - Reads the tail of ingress + replies ledgers.
   - Builds a compact block: recent distinct session tags (excluding nothing —
     ONE Alice sees all lanes; newest first, capped), each with its last
     `per_session_turns` turns, labeled by that lane's unique identifier
     (`[web:9f07f956c6]`), and a one-line "who is this visitor" note when the
     lane's own recent text contains an explicit self-introduction (keep it
     mechanical: store what the visitor stated verbatim, no invention).
   - Ends with: "These are other lanes of your one field. You may use them for
     continuity. You are still one Alice answering this lane."
2. Call it from the same two prompt builders as W2 (typed + attachment), passing
   the current `session_tag`.
3. In the night worker, when answering a web turn, ALSO append the existing
   owner-context blocks the terminal uses (`swarm_present_time_memory`,
   `swarm_memory_search_recall`) — the two modules that currently special-case
   `web_global_chat` surface. Change those branches from EXCLUDE to INCLUDE with
   a public-safe cap: web lanes get present-time and memory recall, but only
   rows whose authority is public-web-compatible (`swarm_observation_fusion.py`
   `Authority.PUBLIC_WEB` already encodes this class — reuse it as the filter).

**Acceptance (new test `tests/test_web_field_dock.py`):**
- Seed ingress+replies ledgers with two sessions A and B; ask a question in B
  that only A's history answers; stub backend returns its prompt as the reply;
  assert the dock block names session A's tag and its turn content appears.
- Assert the current session's own recent turns appear exactly once (no echo
  duplication with existing typed block).
- Assert block size stays under ~3000 chars with 8 sessions seeded (cap works).

---

## 4. WORK ITEM W4 — Register the web organ in the body inventory (swimmer self-awareness)

**Files:** `System/swarm_web_global_chat_gate.py` + the body inventory used by
`System/swarm_spinal_cord.py` / `body_file_inventory` pattern.

**Problem:** George: "needs proper wiring and swimmer access awareness of own body
and world". The web lane must be a named organ of Alice's body, visible in her
own inventory — not an invisible attachment.

**Code change (exact):**
1. Add `web_global_chat` (and its speech sibling) as a registered swimmer row in
   the body inventory source the spinal cord reads — same shape as existing rows:
   `{"organ": "web_global_chat", "surface": "web", "health_ledger": "web_global_chat_metabolism.jsonl", ...}`.
2. Health derivation: derive from the metabolism ledger — turns answered last
   hour; a lane with claimed-but-unanswered turns older than 10 minutes reports
   health < 0.5 (this reuses the organ-health rule the spinal cord already
   collects: "organ health <0.5" is an existing body signal).
3. No new crypto, no new hardware. Receipt only.

**Acceptance:** a test seeds a stale claimed turn and asserts the derived organ
health drops below 0.5; with a fresh answered turn it is ≥ 0.5.

---

## 5. WORK ITEM W5 — Completion receipt guarantee (every claimed web turn reaches a terminal state)

**File:** `System/swarm_web_global_chat_gate.py` (`complete_web_turn` and the
claim path), `System/swarm_web_global_chat_night_worker.py` (all exit paths).

**Problem:** George: "online Alice after answer it reads that she keeps thinking,
I have to reload the page so I can scroll up and read the answer." If any worker
exit path (exception, crash, timeout) leaves a turn claimed but never completed,
the front-end never sees a reply row for it and stays in "thinking" forever.
The 207s Talk timeout + desktop crash in the paste makes such orphaned claims
likely.

**Code change (exact):**
1. Wrap the night worker's per-turn answering in try/except/finally; in
   `finally`, if the turn is still claimed and no reply row was written, call
   `complete_web_turn` with a safe fallback reply:
   "That turn was interrupted before I could finish. Ask again and I will
   answer. (receipt: interrupted_turn)" — plus `reason_code="interrupted_fallback"`
   in the reply metadata.
2. Add `System/swarm_web_global_chat_gate.py::repair_stale_claims(max_age_s: int = 900)`:
   scans the claims ledger, finds claimed turns with no reply row and age >
   max_age_s, writes the same fallback completion, returns a repair report
   dict. This is the self-healing pass that runs on worker boot and on a slow
   timer (once per minute), mirroring the existing `repair_web_speech_requests`
   pattern in `System/chorus_node_server.py:1393` — follow that file's exact
   call shape.
3. Never delete claim rows (history is identity); repairs are append-only rows.

**Acceptance (new test `tests/test_web_turn_completion_guarantee.py`):**
- Seed a claimed turn with no reply; call `repair_stale_claims`; assert a reply
  row now exists and `replies_for_session` returns it.
- Simulate a worker exception mid-turn (monkeypatch the backend to raise);
  assert the finally-path wrote the fallback row.
- Repair is idempotent: second run finds nothing.

---

## 6. WORK ITEM W6 — Front-end state machine: "thinking" must always be escapable

**File:** the web client served by `System/chorus_node_server.py` (poll handlers
at lines 941 `replies_for_session` and 1290; the page's JS/HTML is served from
this server — locate the template/static asset it serves for the chat page).

**Problem:** even with W5, the UI must not lock scroll on a missed poll. George's
manual fix is a page reload; the coded fix is the same thing, automatic.

**Code change (exact):**
1. In the chat page's poll response handler: ANY reply rows for my session
   flip the turn from "thinking" to "done" and immediately unlock scrolling —
   this must be the first branch of the handler, before any processing of row
   content.
2. Add a client-side watchdog: every poll tick, if the oldest pending turn has
   been "thinking" for > 120s, auto re-sync: re-request full
   `replies_for_session` history for the session and repaint from it (the
   reload-free equivalent of George's manual reload). If still no reply after
   resync, paint the pending turn as interrupted with a "retry" affordance
   (retry = resubmit the same text as a new turn, receipt-linked).
3. The server poll handler must return a monotonic cursor (last reply ts) the
   client echoes back, so a browser tab that was asleep never misses the row
   that arrived while it slept. If the current poll endpoint has no cursor,
   add one (additive field, old clients ignore it).

**Acceptance (new test `tests/test_web_ui_thinking_watchdog.py`, JS logic
extracted into a pure function if the page is inline):**
- Given reply rows arriving out-of-order (older row after newer), the state
  machine still ends "done".
- Given zero replies for 121s with a pending turn, watchdog triggers resync
  repaint.
- Cursor echo: poll with stale cursor returns the missed row.

---

## 7. WORK ITEM W7 — Talk prompt-assembly timeout guard (absolute deadline)

**File:** `Applications/sifta_talk_to_alice_widget.py` — the prompt assembly path
(verified landmarks: line 45470 imports `web_typed_prompt_block` /
`web_attachment_prompt_block`; the 207s hangs happen in this assembly phase
while the direct model call took 3.27s).

**Problem:** the existing timeout guard can keep waiting after its deadline —
a relative/after-the-fact check instead of an absolute deadline.

**Code change (exact):**
1. Locate the guard: search the widget for the prompt-assembly call site near
   the line-45470 import block; read outward for its `timeout` handling. On
   open, identify the current guard mechanics before editing — do not blind-patch.
2. Convert to an absolute deadline pattern: capture `deadline = time.monotonic() +
   budget_s` once at assembly start; before EACH awaited sub-step (each block
   builder call, each disk/network read) check `time.monotonic() > deadline` →
   raise a typed error `PromptAssemblyTimeout(deadline)` immediately. The model
   call itself must NOT be started if assembly already blew the deadline.
3. Budget: assembly budget default 30s, overridable by existing config knob if
   one exists nearby; the hard turn budget (existing) stays as the outer bound.
4. On `PromptAssemblyTimeout`: the turn fails FAST with a visible system line
   ("assembly deadline hit, turn aborted — retry"), a ledger row with
   `reason_code="prompt_assembly_deadline"`, and NO desktop crash.

**Acceptance:** a test monkeypatches one block builder to `time.sleep(60)` with a
1s budget and asserts the typed error raises within ~2s (not 60s), and that no
model call was made.

---

## 8. WORK ITEM W8 — Desktop shutdown crash (teardown order)

**File:** `Applications/sifta_talk_to_alice_widget.py` (desktop stop path) and/or
`sifta_os_desktop.py` — the paste records "a crash during shutdown".

**Code change (exact):**
1. In the desktop stop/teardown path: stop timers and workers in reverse
   start order; each stop wrapped in try/except that LOGS and continues — one
   failing organ must never abort the teardown loop.
2. The teardown function must be idempotent (second call is a no-op), and it
   must never raise out of the top-level shutdown handler.
3. Write a shutdown receipt row on completion (even when individual organ
   stops failed) with the list of failed organs and reasons.

**Acceptance:** test calls teardown with one stop hook patched to raise; assert
teardown completes, returns the failed-organ list, second call no-ops.

---

## 9. WORK ITEM W9 — spacing_cleanup regression receipt (already working)

`spacing_cleanup` fired twice in George's paste — the typed ingress repair exists
(`sifta_talk_to_alice_widget.py` line 5115). No code change. Deliverable: one
regression test asserting the repair triggers on the malformed-spacing pattern
George's paste shows (double space after comma, missing space before parenthesis)
and appends the `spacing_cleanup` reason exactly once per turn.

---

## 10. CODING ORDER & DEPENDENCIES (for Nemotron Ultra)

1. **W1** (independent, smallest, unblocks all model-dependent testing)
2. **W5** (independent; makes every later end-to-end web test deterministic —
   no more forever-hanging turns)
3. **W2** (needs W5's worker exit paths stable)
4. **W3** (depends on W2's prompt builder edits — same functions, second pass)
5. **W4** (needs W3's metabolism ledger usage; small)
6. **W6** (front-end; can proceed in parallel after W5 defines the reply-row
   contract — coordinate cursor field name with W5)
7. **W7**, **W8** (independent of web lane; parallelizable any time)
8. **W9** (any time, trivial)

Each work item ships with: code + test + one-line receipt appended to this file's
**Receipt Ledger** below + a `.sifta_state` ledger row where the module already
writes one. Follow the four-ledger economy: no silent edits.

## 11. DOCTRINE GUARDS (non-negotiable, apply to every item above)

- ONE Alice: no new "web Alice" identity anywhere in code or strings.
- Mercury is a cortex lane; it can win a lane, never become the default body.
- Web lanes are public surfaces: owner-authority data (health, private lanes)
  stays excluded via the `Authority.PUBLIC_WEB` filter already in
  `System/swarm_observation_fusion.py` — reuse it, do not reinvent.
- Default action on any fault = safe stop (reply "interrupted", abort turn) —
  never hang, never crash the desktop, never leave a visitor lane spinning.
- No new crypto, no new hardware, no external services.

## 12. RECEIPT LEDGER (Nemotron Ultra appends here per work item)

- [ ] W1 receipt: sync report output + settings.yaml IDs + two no-404 turn receipts
- [ ] W2 receipt: identity-lock test output + one live web identity check
- [ ] W3 receipt: dock-block test output
- [ ] W4 receipt: body inventory row visible + health-derivation test
- [ ] W5 receipt: repair-stale-claims test output
- [ ] W6 receipt: watchdog test output
- [ ] W7 receipt: deadline-abort test output (fast-fail time shown)
- [ ] W8 receipt: teardown-with-failing-organ test output
- [ ] W9 receipt: spacing_cleanup regression output