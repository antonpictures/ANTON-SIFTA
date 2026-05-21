# Codex Verify-Order — Independently Check Cowork's Audit (Memory Epistemology Slice 1)

**Stigauth:** `CODEX_VERIFY_COWORK_ORDER_v1`
**Author:** Cowork (Claude Opus 4.7), Auditor lane
**Verifier (you):** Codex / GPT-5.5 in the OpenAI IDE — lane: **Auditor**
**Subject under review:** Cowork's verification of Grok's slice 1 edit.
**Companion:** `Documents/GROK_MEMORY_EPISTEMOLOGY_SPEC.md`

> Codex: this is not a re-run-and-rubber-stamp. Your job is to check *Cowork*, including whether the
> tests are honest. Register before you act (covenant §4); leave a receipt after. Append-only.

## The chain so far (all on node GTH4921YP3, auditable in the ledgers)

- Grok registration (Surgeon): `a4b535ad-d7be-4097-8471-6999a7bafd94`
- Grok work receipt: `665cdef7-cd35-438e-b64b-a0b9dc02a155`
- Cowork audit registration (Auditor): `eafe4155-dd98-4913-8776-70244ccc1560`
- Cowork verification receipt (PASS, 6/6): `ac9b0e71063d4980`
- Files in scope: `System/stigmergic_memory_bus.py` (Grok), `tests/test_memory_epistemology.py` (Cowork)

## What to verify

1. **Re-run the gates yourself.** `python3 -m pytest tests/test_memory_epistemology.py -v`
   (set `COVERAGE_FILE=/tmp/...` if you measure coverage — the repo mount rejects an in-tree
   `.coverage`). Confirm 6/6 independently; report any flake.
2. **Audit the tests for gaming.** Read `tests/test_memory_epistemology.py` critically. Are the six
   assertions actually the spec's six criteria, or did Cowork weaken them? Specifically check that
   test 5 truly proves FICTION cannot leak (not a trivially-true assertion on an empty string), and
   that test 4 proves real backward-compatibility, not a tautology.
3. **Sanity-check the organ edit.** Read `remember()` and `recall_context_block()` in
   `stigmergic_memory_bus.py`. Confirm: the §2 downgrade rule fires for both `OBSERVED` *and* `WORLD`;
   the audit row is written; unknown labels coerce to `HYPOTHESIS`; the forager reconstruction filters
   to known dataclass fields (no crash on a row carrying *extra* future keys, not just missing ones).
4. **Confirm collision discipline.** `git diff --stat` should show changes confined to
   `System/stigmergic_memory_bus.py` and `tests/test_memory_epistemology.py` (plus appended ledger
   rows). No second organ was touched. No `.sifta_state` history was rewritten.
5. **Edge probes Cowork did not write (add at least two).** Suggested: a `WORLD`-without-links
   downgrade case; a `links`-with-unknown-prefix case (spec says drop+log, not raise); an empty-ledger
   `recall_context_block` returning `""` without error.

## Output

Append a `work_receipt` with `work_type: VERIFICATION`, `verifies_doctor: Cowork`,
`verifies_receipt: ac9b0e71063d4980`, a `verdict` of `CONFIRM` or `DISPUTE`, and — if DISPUTE — the
exact failing case. Then hand the verdict back to George.

One body, three hands, append-only field. This is not a competition. For the Swarm. 🐜⚡
