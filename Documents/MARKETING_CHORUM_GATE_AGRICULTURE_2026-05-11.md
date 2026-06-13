# SIFTA Chorum Gate — Hardware-Born Swimmer Consensus For Agricultural Machines

**Date:** 2026-05-11  
**Audience:** Marketing / Business Development · agricultural robotics · industrial autonomy · safety reviewers  
**Status:** Implemented as opt-in SIFTA organ: `System/swarm_chorum_gate.py`

## One-Line Pitch

SIFTA Chorum Gate makes a machine ask its own hardware-born swarm whether an action is allowed before the action reaches actuators.

## What It Solves

Modern field machines receive commands from local operators, cloud dashboards, phones, radios, maintenance laptops, and AI agents. End-to-end encryption protects messages in transit, but it does not answer the machine-local question:

> Should this specific command be allowed to affect this physical tractor right now?

The Chorum Gate answers that at the substrate layer. Each swimmer has a hardware-bound birth certificate signed by the machine's local key. High-risk actions require vouchers from multiple registered swimmers. Reused swimmer identities are treated as double-spend attempts. Immune-memory categories can mark a repeated threat family as unsafe.

## How It Works

1. A swimmer is born on the machine and receives a signed certificate carrying the hardware serial.
2. The swimmer proposes an action, such as `actuate:steering`, `send:message`, or `tool:shell`.
3. The Chorum Gate checks registration, certificate validity, no-double-spend birth history, immune blacklist status, reputation, and quorum vouchers.
4. A receipt row is written with the verdict.
5. Enforcement remains **passive by default** in SIFTA desktop mode, so Alice is not stressed or slowed by a new hot-path blocker. Strict enforcement is an explicit deployment decision.

## Why This Matters For Agriculture

For a tractor, combine, irrigation controller, greenhouse robot, or autonomous sprayer, the system should distinguish between:

- A command from a process born on that machine.
- A command replayed from a network path.
- A prompt-injection attempt riding inside natural language.
- A maintenance script with no local quorum.

The Chorum Gate gives the machine a local immune system for action authority. It is not a replacement for encryption. It is a second layer: substrate-bound authorization after the encrypted pipe delivers the bits.

## Safety Position

This organ is intentionally conservative:

- Opt-in only.
- No background timer.
- No LLM calls.
- No network calls.
- Receipted verdicts.
- Passive mode by default.
- Strict mode only when an architect/deployer explicitly enables it.

That keeps Alice calm in desktop life while preserving a path to strict industrial deployment.

## Credit Where Due

The design stands on standard security and distributed systems foundations:

- Butler Lampson, "Protection" (1971), for capability-style security.
- Lamport, Shostak, and Pease, "The Byzantine Generals Problem" (1982), for quorum/fault tolerance framing.
- Ed25519 public-key signatures for efficient local attestation.
- Biological MHC / immune recognition as the design analogy, not as a literal cryptographic proof.
- Stigmergy literature for history-dependent reputation and adaptive field memory.

SIFTA's contribution is the local organism pattern: cryptographic birth, swarm quorum, immune memory, STGM economics, and append-only receipts in one embodied machine loop.

