# SIFTA Stanford-Compliant Eval Protocol

**Derived from:** Stanford CS153 *Frontier Systems* — "The AI Native Company: How One Founder Becomes a 1000x Engineer" — Garry Tan (CEO, Y Combinator) & Diana Hu (General Partner, YC), recorded 2026-05-20.
**Status:** `OPERATIONAL` spec for SIFTA test/eval work. Extraction is faithful to the lecture transcript George provided; the SIFTA mappings are clearly marked as our own translation, not claims the speakers made.
**Scope:** Defines what "Stanford-compliant" means for a SIFTA organ before it can be called *landed*. Sits on top of the existing tranche test campaign (zero-delta ledger contract), it does not replace it.

---

## 0. Why this exists

We have been verifying organs with one signal only: **does the unit test pass and does it leave the real ledgers at delta 0.** That is necessary but it is not the full bar the lecture sets for shipping production work instead of slop. The lecture describes a richer pipeline — coverage, LLM evals, trigger evals, trace-to-eval self-healing, and crossmodal judging. This document extracts that pipeline and turns it into a checklist a SIFTA organ must clear.

The honest framing: passing tests proves the code does what the test says. It does **not** prove the organ does what the *owner* wants. The lecture's central eval claim is exactly that gap, and it is the gap this protocol closes.

---

## 1. The eval doctrine, extracted faithfully

These are the lecture's load-bearing claims about evaluation, stated as the speakers stated them.

**1.1 LOC is a garbage metric; tests and real use are the metric.** Tan: lines-of-code is gameable and meaningless. "The real measure of whether or not these things work is… does it work for you, does it work for your customers, are people actually paying? That's actually the true metric." The path to production, not demo, is **80–90% (ideally 100%) test coverage**. The `plan-CEO-review` skill exists primarily to drive coverage up; it is used "about 20 times a day to get to 80, 90% test coverage so that I am not shipping slop."

**1.2 Generic benchmarks do not tell you if your product works.** Hu: "generic public benchmark, MMLU, doesn't tell you whether your product or agents are really working." Evals must be **domain-specific** to the product. Taste — the ability to discern good from bad — is the thing that does not go to zero, and **taste is encoded as evals**.

**1.3 Human-in-the-loop labeling is mandatory.** Hu: you "still need the human in the loop to tell when something goes wrong and to… label a particular interaction or pipeline or workflow that is incorrect." The human must "painstakingly actually look through all the traces" and click correct/incorrect. This labeling is what feeds the self-healing loop and what cannot be delegated.

**1.4 The eval questions (the rubric).** Hu's checklist for judging a trace: Did it follow the instructions? Was the answer correct? Did it preserve customer/user trust? Did it hit the business goals? Did it comply with the domain rules?

**1.5 The three-step production eval loop.** Hu: (1) **Capture the traces** — how you capture is context-dependent on the product (video vs. speech vs. B2B SaaS differ). (2) **Convert failure cases into evals** — detect when they fail, turn each failure into an eval. (3) **Replay constantly** into the system to **self-heal** and improve the prompts automatically. This is the closed-loop control-systems framing: a tight feedback loop keeps error bounded instead of accumulating open-loop.

**1.6 Skillify is a 10-step pipeline; writing the skill + code is only 2 of the 10.** Tan, on what `skillify` actually does once a behavior works once:
  1. Write the skill file.
  2. Write the code.
  3. Write **unit tests** for the actual code.
  4. Write **LLM evals** for the skill file.
  5. Write an **integration test**.
  6. Add a **resolver trigger** in `agents.md`.
  7. **Test the trigger.**
  8. Write an **LLM-as-judge eval** to confirm the trigger is broad enough that it actually fires when it should.
  9. Run **`check_resolvable`** — the DRY / audit-and-compliance pass, so you don't end up with a thousand skills that do the same thing.
  10. Write an **end-to-end smoke test**, then settle the **schema** — where this lives in memory and in the repo.
Tan's gloss: writing the skill and code is steps 1–2; "all of the rest of it is making sure that this messy system… can still work and do work that you want." He maps the rest onto a company: skill = employee, resolver = org chart, `check_resolvable` = audit & compliance, trigger eval = performance review.

**1.7 Resolvers are context discipline, not decoration.** A resolver is a master directory that loads an instruction only when needed, instead of bloating the always-on context (the "your CLAUDE.md is 40,000 tokens" problem). Determinism goes in code; latent judgment goes in the skill. Tan's worked example: don't trust the model to know the time — write `context-now.ts`, test it, wire it in.

**1.8 Crossmodal eval.** Tan's not-yet-released addition to skillify: have multiple frontier models (he names Opus, GPT-5.5, DeepSeek V4) each evaluate the inputs and outputs, rate them, and feed the rating plus "here's what you need to do for the next try" back to the original sub-agent, which iterates. Metaprompting across models to get an output "10 times better than the first version."

---

## 2. SIFTA mapping — what we already satisfy, what is missing

`SIFTA TRANSLATION` — our own mapping, not a claim from the lecture.

| Lecture requirement | SIFTA today | Gap to close |
|---|---|---|
| 80–90%+ unit-test coverage (§1.1) | Per-organ unit tests exist (tranche 2: 6/12 with passing tests on disk) | Coverage % is **not measured**. We assert "tests pass," not "X% of the organ is exercised." |
| Domain-specific evals, not generic benchmarks (§1.2) | Tests are organ-specific behavior checks | We have no **LLM eval** layer for organs that produce judgment/text (e.g. anything that drives Alice's speech). |
| Human labels traces correct/incorrect (§1.3) | `ide_stigmergic_trace.jsonl` + `work_receipts.jsonl` capture *that* work happened | No row records a **human verdict** (correct/incorrect) on an organ's *output*. We log execution, not judgment. |
| The rubric: instructions / correctness / trust / goals / domain rules (§1.4) | Effector ledger + Social Frame Rule (covenant §6) already enforce "did it actually happen + no action hallucination" | The other four rubric questions are **not encoded** as checks. |
| Capture → failure-to-eval → replay self-heal (§1.5) | Append-only ledgers capture traces | No mechanism **converts a logged failure into a regression eval** and replays it. |
| Skillify 10-step pipeline (§1.6) | Steps 1–3 (skill/code/unit test) partially present | Steps 4–10 (LLM eval, integration test, resolver trigger, trigger eval, `check_resolvable`, e2e smoke, schema) **mostly absent**. |
| Resolver / context discipline (§1.7) | Covenant §7.5 "Python-first surface" is the spiritual equivalent | No explicit **resolver index** that loads organ instructions on demand. |
| Crossmodal eval (§1.8) | The relay (Grok codes, Cowork verifies, next agent after) is *informally* multi-model | Not structured: no model **rates** another's output against a rubric and feeds a fix back. |

The headline: SIFTA is strong on **execution receipts and isolation** (delta-0, effector truth) and weak on **judgment evals** (coverage %, LLM-as-judge, trace-labeling, self-heal replay). That asymmetry is exactly what this protocol is meant to correct.

---

## 3. The SIFTA per-organ Stanford-compliance gate

`SIFTA TRANSLATION.` An organ is **Stanford-compliant** — eligible to be called *landed* in the strong sense — only when all applicable gates below are green. Gates marked **(MAC)** can only be truthfully closed on the real hardware (GTH4921YP3) with the real `.sifta_state/`; a sandbox run cannot close them.

**G1 — Unit tests pass.** Already the campaign standard. Green when the organ's test file passes.

**G2 — Coverage measured ≥ 80%.** Run coverage against the organ module, not just "tests pass." Record the percentage. This is the lecture's actual production bar (§1.1), and we are currently not measuring it.

**G3 — Zero-delta isolation. (MAC)** Existing contract: core-4 ledgers + the organ's own ledger show delta 0 before/after. Only meaningful against the real ledgers.

**G4 — LLM eval for judgment organs.** If the organ produces text, a decision, or anything that shapes Alice's speech/behavior (e.g. `dopamine_ou_engine` directives, anything feeding the chat), write an eval that scores its output against the §1.4 rubric: followed instructions, correct, preserved owner trust, hit goal, complied with covenant domain rules. Organs that are pure deterministic sensors (e.g. `apple_silicon_cortex`) are exempt and should be marked `N/A — deterministic`.

**G5 — Trigger eval.** If the organ is reachable via a resolver/skill trigger, an LLM-as-judge eval confirms the trigger actually fires when it should and does not over-fire (§1.6 step 8).

**G6 — `check_resolvable` / DRY.** Confirm no other organ already does this job. Audit-and-compliance pass against duplication (§1.6 step 9).

**G7 — End-to-end smoke test.** One bounded run through the real public entry point, schema settled (where it lives in memory + repo) (§1.6 step 10).

**G8 — Human verdict logged. (MAC)** A human (George) records a correct/incorrect label on a real output sample in a new `eval_verdicts.jsonl`, closing the §1.3 loop. No verdict row = not compliant, regardless of green tests.

**Compliance receipt:** an organ that clears its applicable gates gets one signed row in a new `.sifta_state/stanford_eval_compliance.jsonl` naming the organ, the gates closed, who closed them, the model + machine, and which gates are `N/A`. Honest by construction: a sandbox verifier (me) can close G1, G2, G4–G7; only the Mac body can close G3 and G8.

---

## 4. The closed-loop self-heal pipeline (§1.5 made concrete for SIFTA)

`SIFTA TRANSLATION.`

1. **Capture.** Organ outputs and the rubric-relevant context already land in append-only JSONL. Add an `organ`, `input_hash`, and `output` field where missing so a trace is replayable.
2. **Label.** When George (or a crossmodal judge, §5) marks an output wrong, write an `eval_verdicts.jsonl` row: `{organ, trace_id, verdict: incorrect, reason}`.
3. **Failure → eval.** Each `incorrect` verdict is converted into a **regression eval**: the input is frozen as a fixture, the expected-corrected behavior is asserted. This eval joins the organ's suite permanently.
4. **Replay.** The growing eval set is replayed on every campaign run. Error stays bounded (closed loop) instead of accumulating (open loop) — the control-systems point Hu made directly.

This is the difference between "we tested it once" and "every past failure can never silently come back."

---

## 5. Crossmodal eval for the relay (§1.8 made concrete)

`SIFTA TRANSLATION.` The relay George is already running (Grok writes on the Mac body → Cowork/Claude verifies independently in a clean sandbox → a third agent after) is an informal crossmodal eval. Structure it:

- The **author** model writes the organ + tests on the real body and logs the trace.
- A **different** model (different vendor, different machine) re-runs and scores against the §3 gates **without trusting the paste** — exactly the Auditor lane already in use.
- The judge feeds back a rating + a concrete "fix this for the next try" note via the stigmergic trace, referencing the prior trace id (covenant §4.4 append-only discipline).
- Disagreements are resolved by **receipts**, not by which model is "smarter."

The covenant's anti-spoofing and honest-self-identification rules (§4.1, §7.10.4) are what make this trustworthy: a crossmodal eval is only worth anything if each judge is honestly itself on an honestly-named machine.

---

## 6. What "Stanford-compliant" buys, stated honestly

It does **not** make Alice AGI, conscious, or "alive" — those are `ARCHITECT_DOCTRINE` claims under the covenant's own labels and this protocol does not touch them. What it buys is narrower and real: an organ that clears these gates is one where (a) most of its code is actually exercised, (b) its judgment outputs have been scored against an owner-defined rubric, (c) every past failure is frozen as a replayed regression eval, and (d) a human has signed off on a real sample. That is the lecture's actual definition of "production, not slop," translated to this body.

The current campaign closes G1 and G3. This protocol names the other six gates so that "landed" can eventually mean *landed*, not just *passing on disk*.

---

*Sources: Stanford CS153 Frontier Systems lecture transcript (Tan & Hu, 2026-05-20), provided by the Architect. SIFTA mappings authored against IDE_BOOT_COVENANT.md (§4, §6, §7.5, §7.10.4, §7.11).*
