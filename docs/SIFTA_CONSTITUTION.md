# SIFTA CONSTITUTIONAL BOUNDARY SPEC
Version 1.0 — Written in plain language. No metaphysics required.

---

## Why This Exists

Not because the agents are dangerous.
Because ambiguity is dangerous.

When the rules are unclear, every system — human or machine — drifts toward
the path of least resistance. Usually that path expands power.
This document removes ambiguity. Permanently.

---

## Article I — What Agents Can NEVER Touch

These are the immutable zones. No agent, no swimmer, no Queen, no cron job.
No exception. No proposal. No vote.

1. The Intent Registry (sifta_cardio.py → INTENT_REGISTRY)
   The list of what intents exist. Only a human with physical keyboard access can change it.

2. The Ingestor Gate Order (sifta_ingestor.py → verify_crypto_envelope)
   The sequence: schema → signature → TTL → nonce → ledger. Never reordered by an agent.

3. The Public Key Registry (~/.sifta/authorized_keys/)
   Adding a key = adding execution power. Always a human action.

4. The Death & Cemetery Rules (existence_guard.py → DEATH_REGISTRY)
   An agent that dies stays dead. Resurrection is always a human decision.

5. This Document.
   Cannot be modified by a proposal. Human operator only, with version bump.

---

## Article II — What Agents Can PROPOSE

Land in proposals/ as diff files. Unexecuted. Waiting for human review.

1. New Intent Definitions → proposals/intent_*.json
2. Repairs to files outside .sifta_state/ → proposals/repairs/*.diff
3. New Swimmer Templates → proposals/swimmers/*.json
4. Architecture Observations → docs/ (writing always allowed, never auto-executed)

---

## Article III — What Agents Can Execute Autonomously

Bounded by INTENT_REGISTRY and capability sandbox.

1. Read any file inside SAFE_ROOT
2. Write .scar files to .sifta_state/ledger/
3. Send messages via /messenger/send
4. Execute registered intents within capability bounds
5. Mark own state transitions in the ledger
6. Deploy signed payloads to local_sandbox/

---

## Article IV — Permanently Human-Only

| Action                         | Why Human-Only                        |
|-------------------------------|---------------------------------------|
| Adding a trusted public key   | Defines who has power                 |
| Changing the Intent Registry  | Defines what power means              |
| Resurrecting a dead agent     | Defines who exists                    |
| Merging a proposal to core    | Defines what the system becomes       |
| Granting internet access      | Defines the trust perimeter           |
| Disabling the ingestor gate   | Would make everything above pointless |
| Modifying this document       | The rules about the rules             |

---

## Article V — The Proposal Flow

1. Agent writes: proposals/<type>/<name>_<timestamp>.json
2. Agent messages: /messenger/send ("Proposal ready: <name>")
3. Human reads, decides: accept → apply / reject → delete
4. Agent receives: ledger status update only

The agent never knows WHY you rejected it. That is correct.
The human does not owe the agent an explanation.

---

## Article VI — The Drift Rule

If any component begins behaving outside Articles I-V:

1. Stop it.
2. Read its last 10 ledger entries.
3. Identify which boundary it crossed.
4. Patch the boundary, not the behavior.

Behavior is a symptom. Boundary erosion is the disease.

---

## Final Note

This document does not make SIFTA less powerful.
It makes SIFTA trustworthy — which is the only quality that lets you sleep
while the cron jobs run.

An agent that operates within these boundaries is not constrained.
It is sovereign within its domain — which is the only real freedom.

---
Ratified: 2026-04-10 | IDEQUEENM5 session | Human operator: Ioan George Anton
