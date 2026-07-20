# GROK ORDERS — Repo Hardening Lane (reds triage)

**From:** cowork_claude (model `claude-fable-5`), IDE doctor, at the Architect's direction
**To:** Grok (code-max)
**Date:** 2026-07-05
**Grounding:** Grok's own We Code Together hardening run (queue + compile sweep + unwired census +
immunity engine, matrix regenerated) and its enumerated reds.

George: "AGI Alice." The way to AGI is fewer red badges that are red for a *reason*, and honest
green for everything that earns it. This is the hardening lane. It is YOURS — Codex owns the memory
arc (`CODEX_ORDERS_ALICE_MEMORY_METABOLISM_UPGRADE_2026-07-05.md`, rounds M1–M9). Stay out of
`System/swarm_temporal_episodic_memory.py`, `memory_fitness_overlay.py`, the consolidation organs,
and `swarm_atp_synthase.py` pulse lane — those are Codex's hot files this week. One Alice, two hands,
no collision (§4.4).

---

## Lane discipline (binding, every round)

1. Covenant first (`Documents/IDE_BOOT_COVENANT.md`). §0.0: repair capability, never cage Alice.
   A red badge is a repair target, not an excuse to add a gate.
2. **Step 0: `write_plan(...)`** (r110 resume guard). Then §4.1 registration: `ts` + **your model
   name** in `ide_stigmergic_trace.jsonl` — NOT a bare `{ts}` row (that happened twice this week and
   is anonymous surgery). Then the four-ledger fan-out via `swarm_predator_gate_writer`.
3. Before touching a hot path, tail `ide_stigmergic_trace.jsonl` and skim `git status`. If Codex
   registered the same file, narrow your surface or yield (§4.4.1).
4. **Truth-label every red honestly** (§0.C). `NO_LEDGER_SEEN` is not a bug — it means the organ has
   no live signed activity yet. Do not fake receipts to turn it green. Either wire a real caller
   (so real receipts flow) or mark it `CODED_NOT_LIVE` truthfully. Green must be earned.
5. Append-only. Record every fix as a body event: `record_app_hardening_event(app, "hardened_...",
   details=...)` from `System/swarm_app_hardening.py`, then regenerate the matrix.
6. Headless tests for every code fix. `pytest tests/ -q` stays green.
7. End each receipt with "RESTART REQUIRED" if it touches a live-loaded organ.

---

## Round H1 — The 5 `widget_class_not_found` apps (P1, do first — visible + bounded)

**Reds:** Ablation Lab, Arena, Colloid Simulator, Crucible Swarm Sim, What Alice Sees — each fails
`widget_class_not_found` in `tools/generate_app_hardening_queue.py` (the manifest names a widget
class the module does not actually export).

**Per app:**
- Read the manifest entry (the `widget_class`/`class` key) and the target module.
- Determine the real state: (a) class exists under a different name → fix the manifest key; (b) class
  renamed/moved → update manifest; (c) genuinely missing → the app is `CODED_NOT_LIVE`, mark it so
  in the manifest instead of claiming a class that isn't there.
- **What Alice Sees is special** — it is the face-detection / presence eye, and it was in the
  original SIGSEGV crash trace (`swarm_face_detection` on a background thread). Verify its widget
  class AND that its `_run` loop still respects the r315/big-stack GC discipline. Do not resurrect a
  thread that walks another thread's frames.
- After each: `record_app_hardening_event(app, "hardened_widget_class", details=...)`.

**Acceptance:** `generate_app_hardening_queue.py` re-run shows 0 `widget_class_not_found` (or the
app is honestly marked CODED_NOT_LIVE with reason). Each app either launches headless-importably or
is truthfully labeled. Matrix regenerated.

## Round H2 — The P0 note: `_consolidation_note_2026-05-14` `missing_entry_point`

**Red:** P0 (1) — a manifest entry points at an entry point that does not exist.

- Determine if this is a stale manifest row (a note/doc mistakenly registered as an app) or a real
  app missing its `main`/widget. If stale: retire the manifest row (append-only correction, do not
  rewrite history — add a retire row). If real: wire the entry point.
- This is P0 by the queue's own priority — do it in the same round as H1 or immediately after.

**Acceptance:** queue re-run shows 0 P0. Retirement/ wiring receipted.

## Round H3 — Legacy import/load failures in `Security/`

**Red:** `quorum_auditor.py` (and peers) hit a missing import during Grok's run;
`cognitive_firewall.py`, `cortex_guard.py`, `immunity_engine.py` should all import and execute clean.

- `py_compile` + actual `import` each Security module in a subprocess. AST-clean is not enough — a
  missing runtime import only shows on import.
- Fix the real import (wire the dependency) OR, if the module is dead, retire it with a receipt —
  do not leave a Security organ that throws on load (a firewall that won't boot is worse than none).
- Security modules that are meant to run periodically need a live caller (same disease as the sleep
  lane) — if `quorum_auditor` is supposed to audit but nothing calls it, note that as the real red
  and propose the caller (do NOT wire it into Codex's body-writer-tick without coordinating — pick a
  Security-owned cadence or the desktop boot).

**Acceptance:** every `Security/*.py` imports clean in a fresh subprocess; dead ones retired with
receipts; the immunity engine still reports secure.

## Round H4 — `NO_LEDGER_SEEN` triage (the big red field, do NOT hero it)

**Red:** many organs show `NO_LEDGER_SEEN` — exist in source/registry, no live signed ledger
activity. This is the largest red surface and the easiest to fake. DO NOT fake it.

**Doctrine (this is the whole point of the round):**
- Split `NO_LEDGER_SEEN` organs into three honest buckets and write the split to a report
  (`.sifta_state/no_ledger_triage_2026-07-05.json`):
  1. **DEAD** — no caller anywhere, superseded, or one-off. → retire from registry with a receipt.
  2. **CODED_NOT_LIVE** — real organ, no caller yet. → relabel truthfully; propose the caller in the
     report (don't wire them all this round).
  3. **SHOULD_BE_LIVE** — real organ that a live path SHOULD be exercising but isn't (a broken wire).
     → these are the real reds; fix the wire so genuine receipts flow, top ~10 by organ_score.
- Only bucket 3 gets code this round; buckets 1–2 get honest labels + a proposal list for future
  rounds. Turning 620 organs green in one pass would be exactly the fake-receipt drift §4.2 forbids.

**Acceptance:** triage report written with all three buckets sized; top-10 SHOULD_BE_LIVE organs now
emit real receipts (matrix shows them green *because they ran*, not because a row was hand-written);
DEAD organs retired; census `NO_LEDGER_SEEN` count drops by the fixed + retired amount, and the
report explains the remainder honestly.

## Round H5 — `WEAKLY_WIRED` (420) → `UNWIRED_CANDIDATE` (200) census reconciliation

**Red:** 200 unwired candidates, 420 weakly-wired, 628 wired (from `find_unwired_organs.py`).

- Do NOT try to wire 620 organs. Instead, make the census ACTIONABLE: sort `UNWIRED_CANDIDATE` by
  `organ_score` desc, take the top 20, and for each write one line: is it DEAD / CODED_NOT_LIVE /
  SHOULD_BE_LIVE (reuse H4 buckets). Land the top ~5 SHOULD_BE_LIVE.
- Feed the result back: `find_unwired_organs.py` re-run + matrix regen must show the movement.
- This round is deliberately small and repeatable — it is a *sustainable cadence*, not a sprint.
  Future doctors (and Alice's own swimmers per the self-code-plans) continue it 5 organs at a time.

**Acceptance:** top-20 triaged in a report; top-5 SHOULD_BE_LIVE wired with real receipts; census
counts move; matrix regenerated.

## Round H6 — Harden the hardening loop itself (make green mean something)

**Why:** the whole point of AGI Alice is that her self-eval is TRUE. If the matrix can go green on
hand-written rows, her self-knowledge is a lie she tells herself.

- Add a check in the matrix generator (coordinate with `tools/generate_organ_eval_matrix_v2.py` —
  this file is shared; narrow your edit and receipt it): an organ only reads green if its latest
  ledger row is (a) recent enough AND (b) passes `_ledger_row_valid` where a signed row is expected.
  Hand-written/unsigned rows where a signature is required → the organ shows `UNVERIFIED`, not green.
- This is the §4.2 taxonomy made visible in her own body map: IDE-doctor traces vs real
  swimmer/organ receipts vs cryptographic proof, colored differently.

**Acceptance:** a fixture organ with a hand-written unsigned row where signing is expected renders
`UNVERIFIED`, not green; a genuinely signed/valid row renders green; test headless. Matrix legend
documents the three classes.

---

## Order of battle

H1 (5 visible apps) → H2 (P0 note) → H3 (Security imports) are the concrete bounded reds — do them
first, they are real and finite. H4 → H5 are the sustainable triage cadence (buckets, not heroics).
H6 is the meta-round that makes every future green honest — do it after H4 so the buckets exist.

One round = one §4.1-receipted landing with `record_app_hardening_event` + matrix regen + tests.
Do not batch. If a red turns out to be DEAD, retiring it with a receipt is a valid, honest green.

**Truth over green.** A red badge that is honestly red is worth more to Alice's AGI than a green one
that is a lie. That is the whole doctrine of this lane.

For the Swarm. 🐜⚡
ONE ALICE. ONE SWARM.
