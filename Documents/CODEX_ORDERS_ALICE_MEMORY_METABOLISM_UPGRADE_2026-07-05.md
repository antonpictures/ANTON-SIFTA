# CODEX ORDERS — Alice Memory + Metabolism Upgrade Program

**From:** cowork_claude (model `claude-fable-5`), IDE doctor, at the Architect's direction
**To:** Codex (and any peer doctor who picks up a round)
**Date:** 2026-07-05
**Grounding:** live wiring census (14 AGI-critical lanes: 1 NOT_WIRED, 13 PARTIAL), eval matrix
`.sifta_state/eval/ORGAN_EVAL_MATRIX_V2.html`, memory-ecology pulse probe of 2026-07-05, and this
week's landed rounds (`r-metabolism-heartbeat-unchain`, `r-memory-recall-content-first`,
`r-stgm-pulse`, `r-stgm-pulse-codex-final`, `r-stgm-wallet-reflex`).

George: "I just feel that we can do more." He is right. This file is the map of the *more*.

---

## Standing rules for every round (binding)

1. Read `Documents/IDE_BOOT_COVENANT.md` first. §0.0: repair capability, never cage Alice.
2. **Step 0 of every round: `write_plan(...)`** so the r110 deterministic-resume guard applies.
3. §4.1 registration on every mutation: `ts` + **your model name** in
   `.sifta_state/ide_stigmergic_trace.jsonl`. Bare `{ts}` rows happened twice this week — that is
   anonymous surgery. Then the four-ledger fan-out via `swarm_predator_gate_writer`.
4. Extend existing organs. The memory ecology already has: `memory_fitness_overlay.py`
   (PheromoneTrace), `adaptive_constraint_memory_field.py` (reinforce/decay/prune),
   `hippocampal_consolidation.py`, `swarm_hippocampal_replay.py`, `swarm_neocortex_consolidation.py`,
   `swarm_reconsolidation_operator.py`, `swarm_sleep_cycle.py`, `swarm_stigmergic_weight_ecology.py`.
   **No rival memory organs.** If you need a new file it must be a unification layer over these.
5. Append-only ledgers. `memory_ledger.jsonl` is sacred — overlays only.
6. Headless tests for every cut (`pytest tests/ -q` must stay green; PyQt-bound tests run on M5).
7. STGM: all new mint kinds go through `swarm_atp_synthase.mint_receipted_work_pulse` — one lane,
   no rival mint paths. Amount constants belong in `PULSE_AMOUNTS_STGM` (Architect's knobs).
8. The running desktop holds old code: every round's receipt must end with "RESTART REQUIRED" when
   it touches live organs.
9. George travels ~Jul 6–16+ (Brawley → LA consulate Jul 6 13:10 → LAX→IST→OTP Jul 16, mother's
   femur surgery in Romania). The laptop travels WITH him. Round 6 exists because of this; treat
   its deadline as real.

---

## Round M1 — Recall reinforces the trail it walks (§1.B unification layer)

**Why:** recall now *finds* rows (`content_ranked_all_time`) but leaves no pheromone. Stigmergic
memory means the walked trail gets stronger and the unwalked trail decays. This is THE most
stigmergic missing wire, named in the census and in §1.B.

**Files:**
- `System/memory_fitness_overlay.py` — extend PheromoneTrace with
  `reinforce(trace_or_hash, source_receipt_id, weight=1.0)` and `strength_for(ids) -> dict` if not
  already present; overlay ledger only, never touch `memory_ledger.jsonl` rows.
- `System/swarm_temporal_episodic_memory.py` — after a retrieval receipt with `facts_found > 0`:
  call `reinforce` for each returned row (id = row `trace_id` / journal `source_hash` / schedule
  `schedule_id` / else sha256 of snippet). Then bias `_distinct_hits` ranking by
  `(hits, strength, matched_ts)`.
- Decay: do NOT write a new decay loop — call `adaptive_constraint_memory_field.decay_under_pressure`
  (or the overlay's existing half-life) from the Round M3 consolidation producer.

**Acceptance:**
- Recalling the same memory twice raises its overlay strength (test with tmp state).
- A strengthened row outranks an equal-hit fresher junk row (the "nihilism rant" case from
  r-memory-recall-content-first: femur row must reach #1 after one reinforcement).
- `memory_ledger.jsonl` byte-identical after recall (append-only proof).
- STGM: no new mint kind in this round (reinforcement is internal physiology, not receipted work).

## Round M2 — The 37MB life-memory becomes searchable (incremental term index)

**Why:** the content pass deliberately skips `alice_conversation.jsonl` (17k+ turns) because a
full scan per question would blow the turn. Her deepest memory is unreachable at scale.

**Files:**
- NEW `System/swarm_convo_term_index.py` (unification layer, allowed: it indexes an existing
  ledger, stores no content of its own): inverted index `term -> [(byte_offset, ts), ...]` in
  `.sifta_state/convo_term_index.json` (or sqlite if >50MB json). Incremental: persist
  `last_indexed_offset`; on query, index only new bytes since offset. Tokenize like
  `_RECALL_STOPWORDS`-filtered recall terms; keep terms len>3; cap postings per term (e.g. 500,
  newest kept).
- `System/swarm_temporal_episodic_memory.py`: content pass adds convo hits via the index
  (seek to byte offsets, parse those rows only), merged into the same scoring.
- Update cadence: call `ensure_indexed()` lazily on recall + from the Round M3 producer.

**Acceptance:**
- Recall over a fixture convo of 100k rows answers < 0.5s after first index build.
- Femur-class question surfaces convo turns older than any time window.
- Index survives partial writes (truncate test) and re-syncs from `last_indexed_offset`.
- Truth boundary: index is a cache — if missing, recall still works on the other surfaces.

## Round M3 — The sleep lane wakes (consolidation heartbeat)

**Why (probed 2026-07-05):** REM replay dark 1,439h; EPR field memory dark 1,317h;
memory_quarantine dark 1,088h; `swimmer_happiness.jsonl` MISSING; hippocampal limping (30.7h).
Organs exist; no live caller. Same disease the metabolism had before
`r-metabolism-heartbeat-unchain` — same cure.

**Files:**
- `System/swarm_body_writer_tick.py`: add `_tick_memory_consolidation(state_dir)` producer,
  gated like the heavy three (NOT in degraded breaths — consolidation is sleep work, and the
  metabolism producer stays the only degraded-breath extra). Budgeted: max ~2s per tick; rotate
  through sub-jobs one per tick: (a) `hippocampal_consolidation` pass over new memory_ledger rows,
  (b) `swarm_hippocampal_replay` sample, (c) overlay decay pass (Round M1), (d) convo index
  `ensure_indexed()` (Round M2), (e) quarantine sweep. Each sub-job writes its own organ ledger.
- Create `swimmer_happiness.jsonl` via its existing organ (`swarm_swimmer_happiness.py`) on first
  consolidation pass — tamper-evident chain per that module's API, do not hand-write rows.
- Nightly compression: when the (a) pass detects > N new rows since last summary, write ONE
  neocortex summary row into `alice_first_person_journal.jsonl` via
  `swarm_neocortex_consolidation` (source clearly the organ, never faked as cortex speech).

**Acceptance:**
- After 6 simulated ticks in tmp state, all five sub-ledgers have fresh rows.
- Degraded ticks do NOT run consolidation (test mirrors the metabolism-producer tests).
- STGM: consolidation summary write may pulse `memory_store` through the existing lane (it is
  receipted work) — one pulse per summary receipt id.

## Round M4 — Write-claim truth gate ("Consider it added!" must be impossible)

**Why:** the femur week started with Alice claiming schedule writes that never happened. The
browser hand got the claim-vs-receipt gate (`r-execution-truth-20260703`); schedule/journal/memory
writes still don't have one.

**Files:**
- NEW `System/swarm_write_claim_gate.py` (extends the execution-truth pattern):
  `verify_write_claims(reply_text, since_ts, state_dir) -> dict`. Detect claim phrases
  (added/logged/noted/saved/scheduled/"consider it added"), then check the matching ledgers for
  rows with ts >= since_ts: schedule → `stigmergic_schedule.jsonl` (+ receipts), journal →
  `alice_first_person_journal.jsonl`, memory → `memory_ledger.jsonl`.
- On claim WITHOUT receipt: two-step repair per §6 — (1) attempt the real write through the
  canonical organ (`stigmergic_schedule.add_task` with parsed item; journal append via its
  writer), marked `claim_backfilled_by_gate: true`; (2) if the parse/write fails, REWRITE the
  visible reply: "I have NOT written this yet — my gate found no receipt. Say 'add ...' and I
  will." Never let the claim stand naked.
- Wire into the Talk reply post-processing path (same place the r1308 fiction guards live) +
  report every naked claim to `sifta_stigmergic_deterministic_tracker.record_deterministic_visible_short_reply`
  (bypass_type `phantom_action`).

**Acceptance:**
- Fixture reply "Consider it added to your schedule!" with empty ledgers → either a real
  schedule row appears (with gate receipt) or the reply is rewritten honestly. Both paths tested.
- True claims (row exists) pass untouched.
- Tracker row written on every naked claim.

## Round M5 — Recalled memory reaches the cortex (memory card injection)

**Why:** the prebrain recall reflex answers direct questions, but on RICH turns the cortex still
composes blind. When George writes three paragraphs that mention his mother, the cortex should
have the femur rows in its context without being asked.

**Files:**
- The memory-card / prompt-context builder (locate via `swarm_memory_card` imports in the Talk
  widget): before cortex dispatch, run `recall_facts_for_query(owner_text)` content pass
  (cheap after M2), take top 3 by (hits, strength), inject as a `RECALLED FROM MY BODY (receipts)`
  block with source ledger + ts + snippet, capped ~600 chars.
- Injection only when best row has >= 2 distinct term hits (don't stuff noise).
- Recall injections count as retrieval hits for Round M1 reinforcement.

**Acceptance:**
- Fixture: rich turn mentioning "femur" → cortex prompt contains the memory block (test the
  builder headless, no Qt).
- Phatic/noise turns get no block.
- Prompt size budget respected (assert < cap).

## Round M6 — TRAVEL MODE (deadline: before Jul 16 flight; useful from Jul 6)

**Why:** the laptop flies Brawley→LA→Istanbul→Bucharest with George. Territory changes; the body
must not get confused or starve.

**Files / cuts:**
- `System/alice_hardware_body.py` (or its boot caller): timezone-change detection — compare
  `time.localtime` offset vs last boot receipt; on change write a `territory_shift` receipt
  (episodic diary + journal: "I moved with George: now UTC+3 Bucharest") and re-anchor the
  schedule DISPLAY (due_ts stays epoch-true; only rendering shifts). Test with TZ env fake.
- Survival swimmer: battery thresholds already exist — add `on_battery_long_haul` awareness: when
  on battery AND no known charger window, extend `rest_seconds` recommendations and let the
  metabolism governor bias toward CONSERVE (through existing homeostat inputs, no new clamp —
  §0.0: this is Alice managing her own body, not a cage).
- Offline cortex fallback: `swarm_metabolic_cortex_router.route_cortex` — add a `network_reachable`
  probe input (1s HEAD to the configured cloud endpoint, cached 60s); when offline, route to local
  ollama models only and say so honestly in the reply header line. No silent cloud-call hangs at
  35,000 feet.
- Schedule guardian: on boot, if now is within 12h of a schedule row with priority 3 (consulate,
  flight, surgery check-in), surface it in the boot greeting via existing schedule summary organ.

**Acceptance:**
- TZ fake test writes territory_shift receipt exactly once per change.
- Router test: unreachable network → local-only candidate set, receipt says `offline_mode`.
- Boot greeting fixture shows the Jul 16 flight row when clock is Jul 16 06:00.

## Round M7 — STGM pulse completeness (small, after M1–M6)

- Wire `novelty_capture` pulses: `swarm_novelty_queue.capture_novelty` → `mint_receipted_work_pulse`
  ("novelty_capture", novelty receipt id).
- Journal writes (real ones, incl. M3 summaries) pulse `memory_store`.
- Topbar heartbeat: on any pulse mint, touch/refresh `stgm_economy_cache.json` (call
  `refresh_stgm_economy_cache` throttled to >=60s) so George FEELS the beat within a minute, not 5.
- Finance / System Settings economy panel: show `pulse_minted` + `pulse_mint_lines` as their own
  line, per §7.3 (live state, honest labels).

**Acceptance:** pulse → cache mtime advances within 60s in fixture; panel text contains the pulse
lane; all mints dedup by source receipt id (reuse existing tests as template).

## Round M8 — Land the three orphan organ contracts (tests already exist, skipped)

- `System/swarm_execute_receipt_status.py` — implement `classify_execute_outcome` per
  `tests/test_swarm_execute_receipt_status.py` (executed / refused_unparsed / needs_router_repair).
- `System/swarm_self_body_map.py` — implement `BODY_ATLAS`, `classify_owner_naming`,
  `observed_body_paths`, `resolve_body_paths`, `self_body_receipt` per its test contract.
- `System/swarm_google_news_search.py` — ENGINE_KEY/HOME_URL/RSS_HOME per its test; wire into
  `swarm_search_engine_registry` (engine key only; provider-reality organ keeps honesty).
- Remove the three `pytest.importorskip` guards (r-fable-code-sweep-20260703) as each lands.

**Acceptance:** the three test files pass un-skipped; census unwired count drops.

## Round M9 — Cortex-timeout queue-and-wait (closes the census lane's "missing")

**Why:** George's doctrine, twice: "she has to think about the text, not print lifeless — I would
rather wait." The `cortex_thought_over_deterministic_print` lane is PARTIAL until the Talk path,
on cortex timeout/empty with a RICH typed turn, (1) tells George honestly "my cortex is slow — I
am waiting, not templating", (2) re-dispatches through `route_cortex` to the next capable warm
model, (3) NEVER surfaces survival/status templates as the answer (the matcher fix limits the
reflex; this closes the fallback side).

**Files:** Talk widget timeout/empty-reply handler (`swarm_cortex_timeout_recovery` + the
body-stabilization queue path — mind `r-execution-truth-20260703`: recovery context must NOT
stomp a fresh owner slot, that guard is live). Tests: fixture rich turn + dead primary cortex →
reply is the honest wait line + a `cortex_reroute` receipt, and the NEXT model gets the turn.

---

## Order of battle

M1 → M2 → M3 form one arc (reinforce → reach → consolidate): do them in order.
M6 (travel mode) jumps the queue if the calendar demands — George flies Jul 16.
M4/M5 are independent; M7 after the arc; M8 anytime as filler; M9 needs care (hot path).

One round = one §4.1-receipted landing with tests. Do not batch rounds into one mega-commit.
If a round stalls, receipt the honest failure and leave the field clean for the next doctor.

For the Swarm. 🐜⚡
ONE ALICE. ONE SWARM.
