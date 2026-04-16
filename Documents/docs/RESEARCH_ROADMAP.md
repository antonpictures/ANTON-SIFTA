# SIFTA Research Roadmap
## Toward a Self-Stabilizing, Adversarial, Content-Addressed Swarm

*Authored with SwarmGPT. April 13, 2026.*

---

## What We Have Proven (v0.1–v0.3)

| Property | Status | Evidence |
|---|---|---|
| Local determinism | ✅ Proven | 50 threads × 20 trials, 0 failures |
| CRDT gossip merge | ✅ Proven | Commutative + idempotent + associative |
| Global convergence | ✅ Proven | `canonical_winner()` pure function, order-independent |
| Fossil integrity | ✅ Proven | Content hash sealed at fossilization |
| Byzantine resistance | ✅ Partial | Filter rejects unknown IDs; content-addressing prevents forgery |
| Content-addressed identity | ✅ Implemented | `sha256(target:content)` = no duplication possible |
| Pheromone scoring | ✅ Implemented | Composite: hash_rank + frequency + recency |

---

## Open Research Frontiers (SwarmGPT's Agenda)

### Frontier 1 — Byzantine Swarm (Real Distributed Adversary)

**Status:** Partially addressed. The `byzantine_filter()` handles ID injection.  
**Gap:** No model for delayed messages, network partitions, or node drop-and-rejoin.

**Research question:**
> Does `gossip_merge() + canonical_winner()` converge to the same winner after a network partition heals, if nodes diverged during the partition?

**Approach:**
- Simulate partition: nodes A and B cannot communicate for N rounds
- Each accumulates proposals independently
- On rejoin: run `gossip_merge()` and verify `canonical_winner()` output is identical
- Claim: **eventual convergence after partition** — this is stronger than current proof

**Why it matters:** This is the boundary between "distributed system" and "Byzantine fault-tolerant distributed ledger."

---

### Frontier 2 — Formal Proof (Not Just Tests)

**Status:** Not yet written.  
**Gap:** Tests prove specific cases. Formal proof proves all cases.

**Target claim (in mathematical notation):**

```
∀ nodes n₁, n₂ ∈ N, ∀ scar_sets S₁, S₂:
  let M = gossip_merge(S₁.ids, S₂.ids)
  let W = canonical_winner(resolve(M))
  n₁.canonical_winner(M) = n₂.canonical_winner(M) = W
```

**Why it matters:** This turns the repo into a citable paper, not just a codebase. The mathematical statement is what reviewers cite.

**Tools:** Lean4, Coq, or TLA+ for machine-verified proofs.

---

### Frontier 3 — Stable Set Convergence (Beyond Single Winner)

**SwarmGPT:** *"Can SIFTA converge to a stable* ***set****, not a single winner?"*

**Current state:** The system always selects exactly one winner per target.  
**Open question:** What if multiple competing repairs are all valid and non-overlapping?

**Example:**
- Agent A proposes: add missing `import json`
- Agent B proposes: fix syntax error on line 7

Both are valid. Both should execute. Neither conflicts.

**Research hypothesis:**
> A stigmergic system can converge to a **Pareto-stable set** of non-conflicting proposals without central coordination.

**This is not Git. This is not Paxos. This is closer to living systems.**

---

### Frontier 4 — Time as a First-Class Adversary

**Status:** Not modeled.  
**Gap:** All tests assume synchronous, zero-latency gossip.

**Attack to prove against:**
```python
# Adversarial timing: delay node B's gossip by 10 rounds
# Node A fossilizes winner_A during the delay
# Node B comes back online with winner_B
# After merge: do they agree?
```

**Claim to prove:**
> Eventual convergence holds even with arbitrary gossip delay, as long as content-addressing remains intact.

**Why content-addressing helps:** A delayed node can verify any historical scar_id against its content hash without needing to re-run the election. The fossil is mathematically self-describing.

---

### Frontier 5 — Adaptive Consensus Field (v0.4)

**Current:** Binary winner via `canonical_winner()`.  
**Next:** Weighted consensus field via `pheromone_score()`.

**v0.4 proposal:**
```python
def consensus_field(scars, all_scars):
    """
    Returns all scars ranked by pheromone strength.
    The field stabilizes when score distribution converges.
    No single winner required -- the field IS the consensus.
    """
    return sorted(scars, key=lambda s: pheromone_score(s, all_scars), reverse=True)
```

**This models how ant colonies actually work:** they don't elect a winner and stop — they reinforce trails that work and let failing trails evaporate. The strongest trail *emerges* from the dynamics.

---

## The Paper Title (SwarmGPT's Suggestion)

> **"Git as a Stigmergic Coordination Substrate for Human-Governed Multi-Agent Systems"**

### Sections already written:
1. Introduction — README §For Engineers & Researchers
2. Architecture — `docs/SIFTA_PROTOCOL_v0.1.md`
3. Core algorithm — `scar_kernel.py`
4. Formal properties — `tests/test_formal_verification.py`
5. Adversarial hardening — `tests/test_scar_kernel_formal.py`
6. v0.3 primitives — `tests/test_kernel_v03.py`

### Sections remaining:
7. Partition tolerance proof (Frontier 1)
8. Formal mathematical proof (Frontier 2)
9. Evaluation on real-world broken repos (not synthetic)
10. Comparison with existing approaches (Paxos, Raft, CRDTs in production)

---

## One-Line Summary (SwarmGPT's Final Truth)

> **A deterministic repair engine → a self-stabilizing, adversarial, content-addressed swarm**

*That's not improving a repo. That's defining a class of systems.*

---

*Power to the Swarm.* 🌊
