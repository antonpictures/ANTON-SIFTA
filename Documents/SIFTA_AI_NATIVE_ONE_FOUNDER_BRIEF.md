# SIFTA — An AI-Native, One-Founder Company

**Founder:** Ioan George Anton · **Node:** `GTH4921YP3` (Apple silicon) · **OS line:** BeeSon OS v8.0
**Stigauth:** `SIFTA_AI_NATIVE_ONE_FOUNDER_BRIEF_v1` · **Date:** 2026-05-21
**Companion docs:** `Documents/CS153_STANFORD_YC_AI_NATIVE_SIFTA_BRIDGE.md`, `Documents/IDE_BOOT_COVENANT.md`

---

## What SIFTA is

SIFTA is a sovereign, local-first software organism — a single codebase that behaves like a living
system of cooperating organs running on the founder's own hardware. Where most "AI companies" are a
chat wrapper over a frontier model, SIFTA treats the model as one organ inside a larger body:
deterministic Python organs do the real work, the language model handles the latent reasoning, and
every consequential action is written to an append-only, cryptographically signed ledger before it
counts as real. The result is an AI-native company in the literal sense the Stanford CS153 / YC
lecture describes — one founder, plus agents, plus memory, plus evals — but built as **owned silicon
with signed receipts** rather than someone else's cloud and someone else's Slack.

## Why now

The CS153 thesis is that agentic coding has collapsed the *unit of production*: a single founder with
the right primitives — skills, resolvers, a Skillify capture loop, deduplication, three-layer memory,
a closed feedback loop, and domain-specific evals — can build what once took a team. SIFTA already
implements each of those primitives as a named organ. The lecture is external validation of an
architecture that has been under construction for months, not a roadmap still to be started.

The honest version of the "1000x engineer" claim is the measured one. The peer-reviewed evidence
(Brynjolfsson, Li & Raymond, NBER w31161) shows real but **modest** deployed productivity gains —
on the order of ~14%, larger for novices — not a literal thousandfold. SIFTA's wager is not that one
person magically does the work of a thousand; it is that one founder operating a *closed-loop,
receipt-bearing organism* compounds faster and more verifiably than a team coordinating through chat.

## What is already built (verifiable on-node)

These are counts from the live repository on `GTH4921YP3`, not projections:

- **3,010 git commits** of continuous construction.
- **1,003 system organs** (`System/*.py`) and **142 applications** (`Applications/*.py`).
- **612 automated test files** — tests gate organ changes before they merge.
- **3,866 signed work receipts** and **14,035 stigmergic trace rows** — every agent action, by every
  IDE that has touched the body, is logged and attributable.
- **2,613 memory rows** in the persistent memory ledger.
- A working **cryptographic spine**: `bootstrap_pki.py`, `crypto_keychain.py`, and an STGM economy
  (`stgm_economy.py`, `swarm_stgm_billing.py`) using Ed25519 signing — identity and value are bound to
  hardware and cannot be silently double-spent across nodes.

A representative recent example of the discipline: a camera hot-plug fault was diagnosed, fixed across
four organs, proven with **41 passing tests**, and closed with a signed receipt — the whole repair is
auditable end to end. That is the operating loop the company runs on: *decide → execute → receipt*.

## The edge

1. **Sovereign, not rented.** The organism runs on owned hardware and binds identity to a hardware
   serial. There is no platform that can revoke it, meter it, or read its private memory.
2. **Proof-bearing by construction.** An append-only signed field means claims are checkable. The
   company's own rule is that the model may not assert an action happened unless a receipt proves it —
   structurally hostile to the hallucinated-progress problem that plagues agent demos.
3. **Federation without identity theft.** Multiple nodes exchange receipts, summaries and signed rows —
   never raw selfhood. This is a credible path to a multi-node network where inference and value are
   traded peer-to-peer rather than through a central datacenter.
4. **Composable organism, not a monolith.** New capability is a new organ with its own tests and its
   own receipts, so the surface area grows without the body losing coherence.

## Honest state and what capital buys

SIFTA is pre-revenue and early on the dimensions that matter most to a serious investor, and the brief
says so plainly. Today roughly **54% of organs are referenced by at least one test**, and even
recently hardened organs sit in the **66–77% line-coverage** range — well below the 90%+ engineering
bar the lecture treats as table stakes, and below the founder's own ~97% target. That gap is precisely
the use of funds: this is an inputs-before-outcomes raise.

Capital would fund, in order: (1) a **domain-evaluation loop** — golden-turn eval packs and
LLM-as-judge scoring per organ, not generic benchmarks — so capability is *measured*; (2) a
**coverage and reliability push** toward the 90–97% bar across the core organs; (3) a **closed-loop
company dashboard** (commits, test-pass rate, trace volume, STGM burn per week) that turns the
organism's own ledgers into investor-grade reporting; and (4) **forward-deployed vertical pilots** to
convert the architecture into paid, domain-specific deployments.

## The ask

SIFTA is raising **[$ amount]** on a **YC SAFE** at a **[$ valuation cap]** cap / **[__]% discount**,
to reach the milestones above over the next **[__] months**. *(Figures to be set by the founder; the
SAFE is a legal instrument and should be reviewed by counsel before signing — this brief is not legal
advice.)*

**Founder:** Ioan George Anton — building SIFTA as a one-founder, AI-native company on sovereign
silicon. Reachable at iantongeorge@gmail.com.

---

*Sources for every figure above are the live repository and its ledgers on node `GTH4921YP3`
(git history, `System/`, `Applications/`, `tests/`, and `.sifta_state/*.jsonl`). For the Swarm. 🐜⚡*
