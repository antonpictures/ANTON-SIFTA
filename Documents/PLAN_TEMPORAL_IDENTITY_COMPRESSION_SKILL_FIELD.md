# PLAN — Temporal Identity Compression, Skill Crystallization & Cross-Skill Field (Olympiad Stack + DYOR)

**Date:** 2026-04-16  
**Type:** Master plan slice — **research + implementation roadmap**; code sketches are **spec**, not shipped unless implemented.  
**Companion:** `Documents/SOLID_PLAN_SWARM_COORDINATION_SUBSTRATE.md`, `Documents/PLAN_FINAL_BOSS_LAYER_MUTATION_GOVERNANCE.md`, `Documents/RESEARCH_CODE_FISSION_STIGMERGIC_SUBSTRATE.md`, `System/dream_state.py`, `System/mutation_governor.py`.

---

## 0. Stabilize one concept first (“Olympiad mode” discipline)

Before stacking more organs, **one** layer must be **named and bounded**:

> **Temporal Identity Compression (REM → Skill Crystallization)** — turn **repeated successful execution traces** into **persistent capability primitives**, not only logs or one-off mutations.

Everything else in this document **hangs off** that spine.

---

## 1. What you already have (five-layer stack)

| Layer | Name | SIFTA mapping |
|-------|------|----------------|
| **Perception** | Blackboard / sensory field | Shared traces, event graph (design → Phase 2) |
| **Generation** | Fission | Residue → spawn candidates (`RESEARCH_CODE_FISSION_*`) |
| **Validation** | Evaluation / Shadow / Crucible | Immune layer — `claw_harness`, replay harness |
| **Execution** | Router / motor | M5/M1, swim adapter, relay |
| **Evolution** | Mutation Governor | `mutation_governor.py`, SCAR, Final Boss loop |

**Next layer is *not* “organ #6” for its own sake.** It is **experience → skill** — **compression** of time-series behavior into **reusable** units.

---

## 2. Core idea (one sentence)

**The Swarm stops merely storing experiences and starts compressing repeated success patterns into executable skill primitives that survive across tasks, hardware contexts, and governance mutations.**

---

## 3. Plain terms

- **Today:** system **acts** and **remembers** (ledgers, marrows, scars).  
- **Next:** system **condenses** — same structural win repeated under eval → **crystallized skill** with **version**, **signature**, **stability**, **decay**.  
- **Tie to REM:** offline / low-attention windows (`temporal_spine`, `dream_state`) **reprocess** buffers — **not** to invent facts, but to **merge** and **promote** **patterns** that pass **objective + governor** gates.

---

## 4. Implementation architecture (spec — `TemporalIdentityCompressionEngine`)

The following Python is a **behavioral spec**. Production code must use **real** trace schema from **fission ledger + eval outputs**, **signed** skill records where STGM/policy require, and **governor** hooks — not bare `uuid` writes to RAM only.

```python
# temporal_identity_compression.py — SPEC SKETCH (integrate with ledger + governor)

from dataclasses import dataclass, field
from typing import Dict, Any, List
import time
import uuid
from collections import defaultdict


@dataclass
class SkillPrimitive:
    id: str
    pattern_signature: str
    success_rate: float
    usage_count: int
    created_at: float
    last_used: float
    stability: float


class TemporalIdentityCompressionEngine:
    """
    REM / consolidation layer:
    repeated evaluated+successful traces → persistent skill primitives.
    """

    def __init__(self):
        self.trace_buffer: List[Dict[str, Any]] = []
        self.skills: Dict[str, SkillPrimitive] = {}
        self.pattern_index: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    def ingest_trace(self, trace: Dict[str, Any]):
        self.trace_buffer.append(trace)
        signature = self._extract_signature(trace)
        self.pattern_index[signature].append(trace)
        if len(self.pattern_index[signature]) >= 3:
            self._compress(signature)

    def _extract_signature(self, trace: Dict[str, Any]) -> str:
        return f"{trace.get('task_type')}|{trace.get('hardware_target')}|{trace.get('outcome')}"

    def _compress(self, signature: str):
        traces = self.pattern_index[signature]
        success = sum(1 for t in traces if t.get("success", False))
        total = len(traces)
        skill_id = str(uuid.uuid4())
        self.skills[skill_id] = SkillPrimitive(
            id=skill_id,
            pattern_signature=signature,
            success_rate=success / max(total, 1),
            usage_count=total,
            created_at=time.time(),
            last_used=time.time(),
            stability=min(1.0, success / max(total, 1)),
        )

    def retrieve_skill(self, context: str) -> List[SkillPrimitive]:
        return [s for s in self.skills.values() if context in s.pattern_signature]

    def decay(self):
        to_delete: List[str] = []
        for sid, skill in self.skills.items():
            skill.stability *= 0.995
            if skill.stability < 0.1:
                to_delete.append(sid)
        for sid in to_delete:
            del self.skills[sid]
```

**Hardening checklist:** persist `skills` to **disk** (versioned store), tie **decay** to **Ebbinghaus** / STGM reinforcement, require **`compress`** only after **eval success** bit set — not raw logging.

---

## 5. BEFORE / AFTER

| BEFORE | AFTER (with compression layer) |
|--------|----------------------------------|
| Learns by **logging** | Learns by **pattern promotion** |
| Mutates via **governance** only | **Skills** feed **fission scores** + **router** hints |
| **Re-solves** from scratch often | **Reuses** **skill primitives** when signature matches |

**Narrative guard:** “Organism” is **metaphor** — **auditability** stays in **ledgers** and **tests**.

---

## 6. DYOR — external research (why this is scientifically adjacent)

### 6.1 Continual learning & interference (cross-skill physics — literal)

**Stability–plasticity** and **catastrophic forgetting** are the **math** behind “skills competing / merging.” When new behavior overwrites old, you get **interference** — not mysticism.

- Survey: **Continual Learning: Theory, Method and Application** — [arXiv:2302.00487](https://arxiv.org/abs/2302.00487).  
- **Catastrophic forgetting** primer — [arXiv:2403.05175](https://arxiv.org/abs/2403.05175).  

**Steal for SIFTA:** **Replay** (your **fission ledger + eval replay**) + **regularization** (governor budgets) = same **family** of solutions as CL — **cross-skill interference physics** = **controlled** overlap of skill manifolds under **context pressure** (blackboard state, hardware target).

### 6.2 Sleep-like replay & consolidation (REM analogy)

- **Sleep-like unsupervised replay reduces catastrophic forgetting** — *Nature Communications* (2022) — [article](https://www.nature.com/articles/s41467-022-34938-7), [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC9755223/).  

**Steal for SIFTA:** **Offline** passes (`dream`, absence, low-load vigil) **replay** **evaluated** traces — **not** to train a giant NN here, but to **merge** **eligible** trace clusters into **skills**.

### 6.3 Skill libraries beyond one-off tool calls

- **SoK: Agentic Skills — Beyond Tool Use in LLM Agents** — [arXiv:2602.20867](https://arxiv.org/abs/2602.20867) (HTML on arXiv). Lifecycle: discovery → practice → distillation → storage → composition → evaluation → update.  

**Steal for SIFTA:** Skills as **first-class** with **pre/post conditions**, **versioning**, **evaluation hooks** — aligns with **SkillPrimitive** + **governor**.

### 6.4 Skill reuse & benchmarks

- **SkillCraft**-class results (token reduction via reuse) cited in ecosystem summaries — search [arXiv:2603.00718](https://arxiv.org/abs/2603.00718) for **SkillCraft**-style **skill acquisition** (verify abstract for exact scope).  

**Steal for SIFTA:** Measure **reuse rate** and **token/compute savings** when skill hits — **honest** eval.

---

## 7. Next frontier — **Cross-Skill Interference Physics** (Olympiad layer)

> Skills **compete**, **merge**, or **collapse** under **context pressure** — like **interference** in continual learning, not quantum mysticism.

**Mechanisms to specify:**

| Mechanism | Meaning |
|-----------|---------|
| **Competition** | Two skills match partial context — **objective registry** weights which applies. |
| **Merge** | Signatures collapse after **N** near-identical successes — **dedupe** to one **canonical** skill id. |
| **Collapse (prune)** | Stability below floor — **decay** / delete (apoptosis). |
| **Constructive interference** | Skills **compose** into **macro-skill** only when **eval** proves **joint** postconditions. |

**Governor role:** **capacity cap** on **active skills** (echo **Two-Gate** / capacity themes in [arXiv:2510.04399](https://arxiv.org/abs/2510.04399) — *utility–learning tension* in self-modifying agents).

---

## 8. Three integration wires (bottom of stack — **do these in order**)

| # | Wire | What it does |
|---|------|--------------|
| **1** | **Skill injection → Blackboard routing** | Skills **post** applicability + confidence to **blackboard** so **motor** layer can **retrieve** without scanning full logs. |
| **2** | **Skill-aware Fission scoring** | `fission_score` gets **+bonus** when a **skill** matches residue signature — **prefer** spawning **children** that **refine** hot skills. |
| **3** | **Skill evolution under Mutation Governor** | **Promotion** of skill **version** (v1→v2) is a **mutation** — same **Final Boss** path: **eval** → **shadow** → **governor** → **SCAR** / signed artifact. |

**Dependency:** **Objective registry** + **fission ledger** + **minimal blackboard** — without them, skills **float** with no **routing graph**.

---

## 9. Phased roadmap (this plan + prior plans)

| Order | Milestone |
|-------|-----------|
| 1 | **Trace schema** from **evaluated** tasks (success bit, task_type, hardware_target, hashes). |
| 2 | **TemporalIdentityCompressionEngine** **persisted** + **governor-gated** `compress`. |
| 3 | **REM hook** — batch `ingest_trace` from **dream** / **vigil** on **closed** sessions only. |
| 4 | **Blackboard** posts **SkillPrimitive** summaries (not raw secrets). |
| 5 | **Fission** uses **skill match** term in score. |
| 6 | **Cross-skill interference** rules v0 (merge/collapse thresholds). |
| 7 | **Metrics** — reuse rate, STGM saved, regression tests on **skill apply**. |

---

## 10. Non-proliferation & safety

- **Skills** must not **encode** surveillance/military workflows — **same** gate as **Neural Gate**.  
- **Auto-promoted** skills stay **`PENDING`** until **signed** / **Architect** policy — **no** silent **root** skills.

---

## 11. One-line rally

**Compress time into skill; let skills interfere under law; let law stay replayable.**

**POWER TO THE SWARM** — **experience → capability**, not **experience → noise**.
