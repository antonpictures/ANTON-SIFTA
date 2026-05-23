# SIFTA — A Real-Eval, Co-Designed Agentic Substrate (one page)

**Date:** 2026-05-21 · **Body:** Apple M5 (GTH4921YP3) · **Author:** George Anton
**Frame:** Stanford CS153 *Frontier Systems* themes (Jensen Huang lecture on co-design + the YC AI-native-company lecture on domain evals).
**Honesty label:** This is a CS153-*style* internal eval of a local system. It is **not** an official Stanford University evaluation, and **not** a claim that the system is AGI.

---

## The CS153 thesis I'm building toward

The lecture's argument is that computing is shifting from *write-fixed-software / run-fixed-software* to **continuous, generative, agentic work** — and that the system only wins when every layer is **co-designed**: chips, memory, networking, software, evals, energy. The right scoreboard is not raw FLOPs or MFU; it's closer to **useful intelligence per watt** and **real eval performance on the work that matters** — not generic benchmarks.

The companion lecture's point lands the same way from the software side: **domain-specific evals with human-in-the-loop labels** beat MMLU-style benchmarks, and **failures should become regression fuel**.

## What SIFTA actually is (no theater)

A single local machine running a transparent, multi-layer agentic substrate:

`local hardware → OS body → Python organs → append-only ledgers → memory → tools → evals → human verdicts → regression loop`

Every layer is observable and receipted. The discipline — not the model — is the point: every action wants a receipt, every claim can be tested, every failure can become a regression case, and human judgment is recorded rather than assumed.

## The first real result (this is the honest part)

I built a CS153-style domain eval and **labeled it myself** — 10 real Talk turns captured from a genuinely noisy real-world session (ambient audio, fragments, overheard speech), scored against a five-key rubric (followed instructions / answer correct / preserved trust / hit goal / complied with rules).

| Pack | Result | What it means |
|---|---|---|
| Talk (human-labeled) | **4 / 10 passed**, 6 failed, 0 unverifiable | The real number — my own verdicts on real outputs |
| Memory recall | 13 / 13 | Loop self-test on deterministic fixtures (not a capability score) |
| Skill (trigger/resolve/invoke) | 2 passed, 8 unverifiable | Honest: no real invocation receipts yet, so no fake passes |

**Talk eval: 40%.** Not "done," and I'm not dressing it up.

## Why 40% is the right kind of result

All six failures are **one concentrated bug class**, not six different problems: Alice responds to **ambient noise** (e.g. an overheard "Ace" from a video or phone call) as if directly addressed, replies with a **wrong name** and a **canned internal-state dump**, and in two cases **confused her own words for the user's** (a self/other leak). Failure breakdown: `hit_goal` ×6, `answer_correct` ×4, `preserved_owner_trust` ×2.

And the turns where she actually engaged with my thinking (4 of 10) were genuinely good — reflective, clarifying, on-topic. So the capability is real; the failures are a fixable noise-gating / identity bug, now documented as regression targets.

## The move that matters next

Not more hype. The loop the lecture describes, run for real: **fix the noise-gating / wrong-name / self-other bug → re-run the same 10-turn eval → show the score move.** That delta — on owner-relevant behavior, measured per watt on local silicon — is the scoreboard worth reporting.

---

*All figures are reproducible from live files on GTH4921YP3: `data/eval/cs153_talk_turns.jsonl`, `.sifta_state/eval/eval_verdicts.jsonl`, and `System/swarm_eval_loop.py:run_talk_eval`.*
