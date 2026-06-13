# Outreach — Prof. Mauridhi Hery Purnomo (email) + Luis Angel Lopez Atencio (tweet)

**Date:** 2026-06-13 · **Author:** cowork_claude (`claude-opus-4-8`), Cowork sandbox — `IDE_DOCTOR_CLAIM` / `MANA`, no STGM claim.
**Repo:** https://github.com/antonpictures/ANTON-SIFTA/
**Truth boundary (binding, same as r1088 proof block):** CSV ingest + virtual effector = `OPERATIONAL`; baseline joint-error stats = `OBSERVED` (fixture slice); physical ABB/NAO motion = `HYPOTHESIS` (E51+); beats-a-solver = `FORBIDDEN`.

---

## 0. NOVELTY GREEN LIGHT (honest — read before you send)

**GREEN — what is genuinely defensible as novel:** not a new algorithm, but a *system* nobody else ships as one local organism — an **owner-silicon embodied-agent substrate where every effector action is gated by an owner-intent nonce + a verifiable receipt before world-touch, with a no-double-spend guarantee and a four-ledger accountability fan-out**, now demonstrated **ingesting two real public 6-DOF robot kinematics datasets** (ABB IRB 2400, NAO ARKOMA) through a virtual effector with a receipted round-trip, pytest-green. The novel move is the **trust-boundary inversion**: prove the owner authorized the touch-path on local hardware *first*, then act — verification is the bound, not a hardcoded permission gate.

**RED — fence these off or the outreach backfires (Purnomo is a corresponding-author academic; he will check the repo):**
- We do **not** beat IK solvers or any benchmark (`FORBIDDEN`).
- We do **not** move physical robots yet (`HYPOTHESIS`, E51+).
- The stigmergy / ACO / pheromone math is **classical** (Grassé 1959; Dorigo) — the contribution is integration + the receipt economy, not a math result.
- The IK baseline is **nearest-neighbor, metrics-only, on a fixture slice** — not a trained model.
- Not "AGI" by the open-ended bar — honest framing is "rungs on a falsifiable robotics ladder (ROB501 E49/E50)."

**Verdict:** green light to reach out — but lead with the *narrow, true* contribution and state the boundaries plainly. The honesty is the credibility.

---

## 1. EMAIL — Prof. Mauridhi Hery Purnomo

**To:** hery@ee.its.ac.id
**Subject:** Receipt-gated pre-effector layer for LLM→robotic-arm action plans — feedback welcome

Dear Prof. Purnomo,

I'm Ioan George Anton, an independent researcher. I came across your work on LLM-based human–robot interaction — in particular the hybrid framework for generating action plans for a robotic arm — and it overlaps closely with a system I've been building, so I wanted to share it and ask for your read.

The system, SIFTA, is a local (owner-hardware) embodied-agent runtime. Where an LLM plans an arm action, SIFTA adds the layer *before* the actuator: every effector request is bound to an owner-intent nonce and must produce a verifiable receipt before any world-touch, with a no-double-spend guarantee and a four-ledger audit trail. To test it on real kinematics rather than toy data, I ingested two public 6-DOF datasets — the ABB IRB 2400 inverse-kinematics set and the NAO ARKOMA humanoid-arm set — and ran them through a *virtual* effector with a receipted request→sensor-echo round-trip (tests pass on a sanitized slice).

I want to be precise about the boundaries: this is the verification/safety-gate layer, not an IK solver — I make no claim to beat any solver, and nothing yet drives a physical arm (that stage is explicitly future work). The contribution is the receipted, owner-authorized pre-effector path, and the open question I'd value your view on is whether such a receipt-gated dry-run is a useful safety/accountability layer between an LLM action planner and a real arm.

The code and the robotics proofs are public: https://github.com/antonpictures/ANTON-SIFTA/ . If any of it is relevant to your group's work, I'd welcome your feedback or a conversation.

With respect,
Ioan George Anton
ANTON-SIFTA · https://github.com/antonpictures/ANTON-SIFTA/

---

## 2. TWEET — Luis Angel Lopez Atencio (IRB 2400 dataset author)

**Draft (≤280 chars), tag him:**

> Hi @[Luis Angel Lopez Atencio] — your Kaggle IRB 2400 inverse-kinematics dataset became the "E49" real-robot-data test for SIFTA: we ingest your rows into a receipted, no-double-spend effector gate on local hardware (virtual arm, pytest-green). Credit to you 🙏 https://github.com/antonpictures/ANTON-SIFTA/

**Honesty note:** the tweet credits the dataset and claims only *ingest + virtual round-trip* — no "we solved IK," no physical-arm claim. Replace `@[Luis Angel Lopez Atencio]` with his actual handle before posting.

---

## 3. WHAT NOT TO SAY (to either contact)
- "We beat the IK solver / the dataset labels."
- "SIFTA moves a physical ABB / NAO arm."
- "Cloud-AGI" or "we are AGI."
- Any STGM-as-currency framing (MANA / IDE traces only).

For the Swarm. 🐜⚡
