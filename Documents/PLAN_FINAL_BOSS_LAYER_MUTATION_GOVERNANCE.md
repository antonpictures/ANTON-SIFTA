# PLAN — Final Boss Layer: Closed-Loop Self-Modification with Bounded Identity Drift

**Date:** 2026-04-16  
**Type:** Architecture + research plan — **not** shipped code unless explicitly implemented.  
**Companion:** `Documents/SOLID_PLAN_SWARM_COORDINATION_SUBSTRATE.md` §5.2–5.3, `Documents/RESEARCH_CODE_FISSION_STIGMERGIC_SUBSTRATE.md`, `System/mutation_governor.py`, `System/claw_harness.py`, `Documents/PLAN_CLAW_SWARM_MUTATION_GOVERNOR.md`.

---

## 0. One-sentence answer (frontier)

**Let the Swarm rewrite its own rules only through an evaluation-gated mutation loop that preserves identity under pressure** — i.e. **closed-loop self-modification** where **fission** proposes, **evaluation / shadow** filters, **mutation governor** commits, and **blackboard topology** stays **auditable** and **reversible** within policy.

---

## 1. Biological mapping (three-layer nervous system → SOLID organs)

| Metaphor | Organ (biology) | SIFTA module / artifact | Role |
|----------|-----------------|-------------------------|------|
| **Blackboard 2.0** | **Sensory cortex** (shared perception) | Event graph + residues | One **field** everyone **reads** |
| **Fission ledger + spawn** | **Cell division** (replication under rules) | `RESEARCH_CODE_FISSION_*`, future `blackboard_fission` | **When** a trace becomes a **new** branch/task |
| **Evaluation / Shadow / Crucible** | **Immune system** (self / non-self, toxicity) | Tests, `claw_harness` sandbox, replay harness | **Reject** bad mutations **before** reality |
| **Router / execution** | **Motor cortex** | Swim adapter, relay, node routing M5/M1 | **Where** work runs on **hardware** |
| **Mutation Governor** | **Homeostasis + apoptosis** (bounds) | `mutation_governor.py` + SCAR | **Rate**, **budget**, **gate** |

**What you have today:** strong **creation → filtering → execution** stories **in parts**.  
**Final boss gap:** **Governor output** does not yet **close the loop** into **fission scoring** and **evaluation metrics** as a **single** control law — i.e. **“rules that change rules”** without **identity drift** or **collapse**.

---

## 2. The problem statement

> Right now: *creation → filtering → execution*.  
> Missing: **the Swarm changing its own rules safely** without **hallucinating itself into collapse** (incoherent objectives, lore soup, irreversible kernel drift).

**Formal goal:** **Bounded identity drift** — **policy** and **code** may evolve, but **cryptographic root of trust** (hardware serial, PKI, **Neural Gate** doctrine) and **replay** of decisions remain **intact**.

---

## 3. Final boss layer — control law (conceptual)

**Closed loop:**

```text
Fission event (high score)
    → MutationProposal (governor schema)
        → Shadow / Eval sandbox (immune)
            → Governor allow? (friction, reversibility, attention, climate)
                → SCAR / Kernel.propose (constitutional path)
                    → Commit OR decay
                        → Blackboard posts "mutation_log" + updates fission_score priors
```

**Key:** **Feedback** from **governor** and **eval** **into** **fission scoring** — failed mutations **lower** future spawn appetite for **similar** residues; successes **reinforce** pathways (see **evolving topology** in fission research doc).

---

## 4. DYOR — what external research says (why this is hard)

These papers **do not** prove SIFTA — they **warn** and **tool** the design:

| Topic | Source (public) | Takeaway for SIFTA |
|-------|-----------------|---------------------|
| **Safety verification limits for self-improving systems** | [arXiv:2603.28650](https://arxiv.org/abs/2603.28650) — information-theoretic limits; classifier gates vs overlapping safe/unsafe distributions | **Unbounded** “always approve good” is **not** trivially possible; **verifiers** and **bounded risk** schedules matter. |
| **Utility vs learning in self-modifying agents** | [arXiv:2510.04399](https://arxiv.org/abs/2510.04399) — *Utility-Learning Tension*; **Two-Gate guardrail** (validation margin + **capacity cap**) | **Self-mod** that maximizes short utility can **break** learnability — cap **model/policy capacity** growth **or** pay with **statistical** guarantees. |
| **Open-ended systems need safety** | [arXiv:2502.04512](https://arxiv.org/abs/2502.04512) — safety for **responsible** open-ended systems | **Creativity** without **control** → **misalignment cascades** — align with **governor + eval + decay**. |
| **Tension: control vs creativity (open-ended AI)** | [arXiv:2006.07495](https://arxiv.org/abs/2006.07495) — open questions | Your **entropy budget** + **friction** are **on-theme**. |

**Bottom line from literature:** **Self-modification** is **not** “add `if score > 1.2`.” It needs **capacity bounds**, **verification**, **cooling**, and **replay** — exactly the **Final Boss** stack.

---

## 5. SIFTA-specific invariants (non-negotiable)

1. **No silent kernel rewrite** — mutations touch **repo** only via **SCAR** / **governor** / **signed** ledger rules already in project doctrine.  
2. **Identity frozen at root** — `homeworld_serial`, Ed25519 keys — **not** mutable by fission score.  
3. **Non-proliferation** — `LICENSE` + Neural Gate — **self-mod** must **not** weaken **military/surveillance** blocks.  
4. **Replay** — every **COMMITTED** mutation has a **fission ledger** + **eval artifact** pointer.  
5. **Human gate** on **irreversible** or **high-risk** proposals (`reversibility index` from SOLID §5.2).

---

## 6. Implementation milestones (ordered)

| Phase | Deliverable |
|-------|-------------|
| **A** | **Objective registry** weights → define `expected_gain` / `risk` consistently. |
| **B** | **Fission ledger** append-only + **MutationProposal** schema (subset of below). |
| **C** | **Governor ↔ fission**: `propose_from_fission()` only when **ledger** + **score** + **recurrence** agree. |
| **D** | **Eval sandbox** hook: **no commit** without **eval.evaluate** + **shadow** for code paths. |
| **E** | **Feedback edge**: failed eval → **decrease** spawn prior for **similar** residues (cluster id). |
| **F** | **Topology guard**: “does not destabilize blackboard” = **graph metrics** + **contradiction** checks. |

**Module name (suggested):** `System/mutation_governor_loop.py` or extend **`mutation_governor.py`** — **avoid** duplicate sources of truth.

---

## 7. After the “final boss” — **temporal identity compression** (next horizon)

> **REM → skill crystallization → irreversible skill birth**

Meaning: **offline** consolidation (dream / absence / failure replay) promotes **draft skills** to **crystallized** skills only after **eval + governor + optional Architect seal** — **irreversible** only at a **defined ceremony** (signed mint, versioned `.gene`), not at **every** successful shadow run.

This is **where software starts looking like an organism** — but **only** if **§6** is **honest** first; otherwise it is **narrative**.

---

## 8. Reference pseudocode (spec only — not production)

The following sketch matches the **intent** of a **MutationGovernorLoop**; **thresholds** (`1.2`, `0.8`) are **placeholders** — real values come from **Objective Registry** + **calibration**.

```python
# mutation_governor_loop.py — SPEC SKETCH (see §6 for real integration)

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class MutationProposal:
    id: str
    source: str
    target_module: str
    patch: Dict[str, Any]
    risk: float
    expected_gain: float
    status: str = "PENDING"


class MutationGovernorLoop:
    """Closed loop: fission → proposal → eval → governor → commit → blackboard feedback."""

    def __init__(self, eval_sandbox, fission_engine, blackboard):
        self.eval = eval_sandbox
        self.fission = fission_engine
        self.board = blackboard
        self.proposals: List[MutationProposal] = []

    def propose_from_fission(self, fission_event) -> Optional[MutationProposal]:
        score = fission_event.score()
        if score < 1.2:  # REPLACE with registry-weighted threshold
            return None
        proposal = MutationProposal(
            id=f"mut_{fission_event.id}",
            source=fission_event.task_id,
            target_module="swarm_core",
            patch={"signal": fission_event.payload, "reason": "emergent high-value pattern"},
            risk=fission_event.risk,
            expected_gain=score,
        )
        self.proposals.append(proposal)
        return proposal

    def evaluate_mutation(self, proposal: MutationProposal) -> bool:
        result = self.eval.evaluate(
            task_id=proposal.id,
            payload={"complexity": proposal.risk, "novelty": proposal.expected_gain},
        )
        return result.approved

    def commit(self, proposal: MutationProposal) -> bool:
        if proposal.risk > 0.8:  # REPLACE with reversibility index + gate
            return False
        if not self.evaluate_mutation(proposal):
            return False
        self._apply_patch(proposal)
        proposal.status = "COMMITTED"
        return True

    def _apply_patch(self, proposal: MutationProposal):
        self.board.post(
            topic="mutation_log",
            payload={
                "mutation_id": proposal.id,
                "source": proposal.source,
                "applied_patch": proposal.patch,
            },
            source="mutation_governor",
        )

    def tick(self, fission_events: List[Any]):
        for ev in fission_events:
            proposal = self.propose_from_fission(ev)
            if proposal:
                self.commit(proposal)
```

---

## 9. Non-proliferation

Self-modification **must not** disable **Neural Gate** blocks or **LICENSE** constraints. Any **auto-tuning** of thresholds that **touches** firewall rules requires **Architect** authority or **dual-control**.

---

## 10. Rally line

**Final boss** = **evolution with immune system**, not **evolution with vibes**.

**POWER TO THE SWARM** — **bounded drift**, **replayable law**, **frozen roots**.
