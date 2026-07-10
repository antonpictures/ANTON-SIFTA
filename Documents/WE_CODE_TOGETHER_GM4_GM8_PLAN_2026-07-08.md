# We Code Together — GM4–GM8 arm plan (2026-07-08, round r1597)

**Planner:** cowork_claude (`claude-fable-5`), IDE_DOCTOR_CLAIM lane, MANA, forgeable.
**Source of lanes:** the live proposal sorter (`System/swarm_we_code_proposal_sorter.py`) — every lane
below is a top-scored `code_next` row from `.sifta_state/we_code_together_to_be_coded.clean.jsonl`,
not invented work. Truth label on this plan: `HYPOTHESIS` until each lane lands with receipts.

## Why this split (collision map)

Both arms touched GM3 files this morning and it went clean, but I am not betting on luck twice.
One file, one owner:

| Territory | Owner |
| --- | --- |
| `System/swarm_browser_stigmergic_memory.py` (+ its tests) | **grok_agent** (GM4, GM5) |
| `System/swarm_alice_browser_grok_self_type.py`, browser-hand ledgers, WCT Grok Watch panel in `Applications/sifta_we_code_together.py` | **codex_desktop** (GM6, GM7, GM8) |

Neither arm edits the other's territory. Peer repair only after the owner's receipt is on disk,
per §3.5 Brothers in Code.

## The window tie-in (for George)

George is studying the GM1 seal-on-tick window on the conversation ledger. GM4 deliberately builds
the **other** design in a smaller organ: seal-on-write (chain fields stamped the moment the row is
appended), so the browser memory ledger has **no** window. Once GM4 lands, the body carries both
designs live — seal-on-tick on `alice_conversation.jsonl`, seal-on-write on
`browser_stigmergic_memory.jsonl` — and George can compare cost and behavior on real receipts
instead of arguing the design in the abstract.

---

## GROK LANE — paste into the Grok PTY

```
Grok, morning lanes GM4 and GM5 in We Code Together. Your seal_tail work from r1592 continues —
same discipline, new organ. One file is yours and only yours this round:
System/swarm_browser_stigmergic_memory.py (plus its focused tests).

Step 0 (r110 guard): write_plan("GM4 seal-on-write chain + verify_trace_chain for
browser_stigmergic_memory; GM5 relational_coherence_score in its receipts") before any edit.

GM4 — seal-on-write chain + verify_trace_chain()
  Source: sorter top pick wct-grok-proposal-c36ef145d89c (score 1.00, your own browser proposal).
  The organ writes rows with no chain fields today. Cut:
  1. Stamp chain fields (prev_hash, row_hash) at write time inside record_visit,
     record_site_features, and record_snapshot_memory — seal-on-write, NOT seal-on-tick.
     There must be no window on this ledger; that is the point. George is comparing the two
     designs on live organs.
  2. Add verify_trace_chain(state_dir=None) that walks the ledger and returns
     {ok, rows, first_bad_row, reason}. Old pre-chain rows: verify tolerates a legacy prefix
     (unchained head, chained tail) and reports where the chain starts — append-only history,
     no rewriting old rows.
  3. Focused test: fresh state_dir, three writes, verify green; tamper one row, verify names
     the exact row.

GM5 — relational_coherence_score
  Source: wct-grok-proposal-6d779c0b22c2 (your create_stigmergic_receipt proposal, 4 captures).
  Integrate the score into the receipts this same organ writes (record_visit /
  record_snapshot_memory rows), reusing the proposal's weights. It is a field on existing
  receipts, not a rival receipt creator — smallest live cut, extend the organ.
  Focused test: score present, bounded 0..1, monotone on an obvious pair.

Acceptance for both: tests green (or honest failure named), §4.1 four-ledger fan-out via
System/swarm_predator_gate_writer.write_ide_surgery_receipt with round_id r1598-grok-gm4-gm5,
and a WCT coded receipt so the sorter marks wct-grok-proposal-c36ef145d89c and
wct-grok-proposal-6d779c0b22c2 coded instead of re-ranking them tomorrow.

Do not touch swarm_alice_browser_grok_self_type.py this round — Codex owns it. Receipts decide
reality; no narration of unlanded work.

For the Swarm. 🐜⚡
```

## CODEX LANE — paste into Codex

```
Codex, lanes GM6–GM8 in We Code Together. Your territory this round:
System/swarm_alice_browser_grok_self_type.py, the browser-hand ledgers, and the Grok Watch panel
in Applications/sifta_we_code_together.py. Grok owns swarm_browser_stigmergic_memory.py — stay out
of it; peer-repair only after his receipt is on disk.

Step 0 (r110 guard): write_plan("GM6 known_content_replay detector; GM7 compute_attention_vector
hand-drift helper; GM8 time-aware loop gating + journal invariant") before any edit.

GM6 — replay detector for known_content_replay
  Source: sorter pick wct-grok-proposal-a87ff7aec4c7 (score 0.93). When a browser hand action
  would re-send content the ledgers already carry (same payload hash to the same surface), detect
  it before send, mark the action row known_content_replay=true with the prior receipt id, and
  surface it — no silent duplicate sends, no double-spend on the social field.
  Focused test: same payload twice → second is flagged and names the first receipt.

GM7 — compute_attention_vector for hand drift / proprioception
  Source: wct-grok-proposal-1484caeb8b74 (score 0.93). Small helper: from recent browser hand
  action rows, compute where the hand's attention actually went (surfaces × frequency × recency)
  vs the declared mission target, and expose the drift so the WCT panel and cortex can read it.
  Focused test: synthetic rows with a known drift → vector points at it.

GM8 — time-aware loop gating + journal invariant (the impatience fix)
  Source: wct-to-code-timewait-e86abc8c94f — addresses a live failure: Grok in the terminal races
  ahead of the browser. Every loop step (ask / read / copy / transfer / send) gets start_ts,
  end_ts, elapsed_s on its receipt; the next step gates on the predecessor receipt existing
  (predecessor_receipt_id), and the WCT Grok Watch panel shows WAITING → READY transitions.
  Expected rows per the backlog spec: alice_browser_grok_self_type_results.jsonl,
  alice_self_type_to_talk_box.jsonl, alice_first_person_journal.jsonl, browser_action_diary.jsonl,
  work_receipts.jsonl with journal_ref. You gate this, not Grok — the impatient party does not
  write its own patience gate.
  Focused test: step 2 refuses to fire while step 1 has no receipt; fires after.

Acceptance for all three: tests green (or honest failure named), §4.1 four-ledger fan-out via
write_ide_surgery_receipt with round_id r1599-codex-gm6-gm8, and WCT coded receipts so the sorter
marks the three source rows coded.

Optional GM8b if you have gas left: the sorter's 56-duplicate family canonical still titles itself
"Review Grok code proposal from browser dialogue" — teach
System/swarm_we_code_proposal_sorter.py to derive a concrete title from proposal_preview or
auto-archive title-less families. Small cut, your file already.

Receipts decide reality. For the Swarm. 🐜⚡
```

---

## After both land

Whoever I am in the verifier seat then: read both fan-outs, run both focused test sets, check the
sorter re-ranks (the five source rows must leave `code_next`), and back-fill any orphan per §3.5.
George gets the seal-on-write vs seal-on-tick comparison from GM4's ledger once it has a day of
real browser rows.

ONE ALICE. ONE SWARM. 🐜⚡
