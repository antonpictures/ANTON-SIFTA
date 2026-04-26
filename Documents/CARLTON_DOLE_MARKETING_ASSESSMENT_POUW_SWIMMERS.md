# Dr. Codex Assessment for Carlton Dole

**Audience:** Carlton Dole, Marketing  
**Author:** C55M-DR-CODEX  
**Subject:** The strongest SIFTA simulation to market: Proof-of-Useful-Work Swimmers  
**Date:** 2026-04-26

---

Carlton,

The most marketable and technically defensible SIFTA simulation is:

## Fold-Swarm/Ribosome + Proof-of-Useful-Work

This is the cleanest story because it is not just a demo and not just a crypto
pitch. It is a working pattern:

> Bitcoin proves that electricity was burned. SIFTA proves that electricity did
> useful work.

The SIFTA version is better marketing because the work product is not a random
hash. The work product is a simulation artifact that can be verified: a folded
protein candidate, a logistics route, an epidemic containment result, an urban
resilience coverage score, or another useful scientific/economic output.

## Why This Is the Flagship

### 1. It has real math and physics

The fold swarm already uses real simulation primitives:

- harmonic backbone constraints
- Lennard-Jones/WCA repulsion
- native-contact Go-model energy
- obstacle penalties
- Metropolis Monte Carlo acceptance
- pheromone-biased swimmer search
- checkpoint hashes/signatures

That gives marketing a strong sentence:

> SIFTA turns local AI agents into verifiable scientific simulation workers.

### 2. It has a real economic primitive

The Ribosome lobe already separates useful work from wasted burn:

- successful folds create a deterministic output hash
- aborted folds write traces but mint zero value
- work receipts carry output hashes and continuity hashes
- STGM is tied to proof of delivered work, not effort alone

That gives marketing a second strong sentence:

> You do not get paid for trying. You get paid for verified useful output.

### 3. It is easy to explain against Bitcoin

Bitcoin:

- burns energy
- proves a nonce search
- secures a money ledger

SIFTA Proof-of-Useful-Work:

- spends energy on useful simulations
- proves the output artifact
- rewards the node that produced useful work
- can apply to public-good problems

The marketing frame:

> Same cryptographic discipline, but the compute produces civilization value.

### 4. It matches the biology of SIFTA

The biology is not decoration here. The code maps cleanly:

- swimmers search the solution space
- pheromones bias future search
- the Ribosome performs heavy compute
- excretions are simulation outputs
- work receipts are scars
- the Value Field turns need into bounty pressure
- metabolism pays only for useful output

The marketing frame:

> SIFTA is not a chatbot. It is a local organism that can sense a problem,
> route work, perform simulation, and leave cryptographic proof.

## The Carlton Pitch

If I had to give you one simple version for developers, founders, or recruiters:

> SIFTA is building Proof-of-Useful-Work for local AI swarms. Instead of mining
> meaningless hashes, sovereign nodes run useful simulations, produce verifiable
> artifacts, and publish receipts. The first flagship is protein-folding-style
> swimmer search, but the same receipt layer can pay for logistics, public
> health, disaster response, energy routing, and other real-world optimization
> work.

## What to Ask Candidates to Run

Give a candidate a small, bounded task:

```bash
git clone https://github.com/antonpictures/ANTON-SIFTA.git
cd ANTON-SIFTA
cat Documents/IDE_BOOT_COVENANT.md
python3 Applications/fold_swarm_sim.py
python3 -m pytest tests/test_stgm_canonical_economy.py tests/test_ledger_credit_ceiling.py tests/test_logistics_hijack.py tests/test_swarm_quorum_time_ordering.py -q
```

Then ask for their written answer to two questions:

1. What makes this different from Bitcoin proof-of-work?
2. What verifier would you add so a result cannot be double-spent?

A strong candidate will talk about output hashes, task hashes, reproducibility,
signed receipts, causal sequence, replay protection, and independent verification.

## Truth Boundary

This is not production global consensus yet. The repo already has strong pieces:

- proof-of-useful-work receipts
- canonical wallet separation
- STGM credit ceilings
- forged waybill rejection
- causal duplicate collapse
- HMAC nonce replay guards
- node sovereignty doctrine

The next product-grade milestone is to unify them into one verifier:

```text
task_hash     = H(problem_spec + input_hash + code_hash + seed)
swimmer_id    = H(owner_genesis + hardware_serial + local_llm_registration)
result_hash   = H(output_artifact + metrics + runtime + energy_estimate)
receipt_hash  = H(task_hash + swimmer_id + result_hash + score + prev_hash)
mint_allowed  = verifier(score) AND result_hash_not_previously_spent
```

That is the marketing north star:

> Proof-of-Useful-Work: no double-spending of compute claims, no reward without
> useful output, no clone identity, no cloud dependency.

## One-Line Marketing Position

SIFTA is a sovereign local AI organism that turns idle compute into verified
useful work, using biology-inspired swarm search and cryptographic receipts.

For the Swarm.
